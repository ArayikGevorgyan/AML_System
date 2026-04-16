from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from models.case import Case, CaseNote
from models.alert import Alert
from models.customer import Customer
from models.transaction import Transaction
from config import settings


def _collect_case_context(case: Case, db: Session) -> dict:
    context = {
        "case_number": case.case_number,
        "title": case.title,
        "description": case.description or "",
        "status": case.status,
        "priority": case.priority,
        "sar_filed": case.sar_filed,
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "customer": None,
        "transactions": [],
        "alerts": [],
        "notes": [],
    }

    alert = None
    if case.alert_id:
        alert = db.query(Alert).filter(Alert.id == case.alert_id).first()

    customer = None
    if alert and alert.customer_id:
        customer = db.query(Customer).filter(Customer.id == alert.customer_id).first()

    if customer:
        context["customer"] = {
            "name": customer.full_name,
            "customer_number": customer.customer_number,
            "nationality": customer.nationality or "Unknown",
            "risk_level": customer.risk_level,
            "pep_status": customer.pep_status,
            "sanctions_flag": customer.sanctions_flag,
            "occupation": customer.occupation or "Unknown",
            "annual_income": customer.annual_income or 0,
        }

        since = datetime.now(timezone.utc) - timedelta(days=90)
        txns = db.query(Transaction).filter(
            Transaction.from_customer_id == customer.id,
            Transaction.created_at >= since,
        ).order_by(Transaction.created_at.desc()).limit(20).all()

        for t in txns:
            context["transactions"].append({
                "amount": round(t.amount, 2),
                "currency": t.currency,
                "type": t.transaction_type,
                "flagged": t.flagged,
                "risk_score": t.risk_score,
                "country": t.destination_country or t.originating_country or "Unknown",
                "date": t.created_at.strftime("%Y-%m-%d") if t.created_at else "",
            })

        since180 = datetime.now(timezone.utc) - timedelta(days=180)
        alerts = db.query(Alert).filter(
            Alert.customer_id == customer.id,
            Alert.created_at >= since180,
        ).order_by(Alert.created_at.desc()).limit(10).all()

        for a in alerts:
            context["alerts"].append({
                "severity": a.severity,
                "reason": a.reason,
                "status": a.status,
                "date": a.created_at.strftime("%Y-%m-%d") if a.created_at else "",
            })

    notes = db.query(CaseNote).filter(
        CaseNote.case_id == case.id
    ).order_by(CaseNote.created_at.asc()).all()

    for n in notes:
        if n.note_type == "comment":
            context["notes"].append(n.note)

    return context


def _build_prompt(ctx: dict) -> str:
    customer = ctx["customer"]
    txns = ctx["transactions"]
    alerts = ctx["alerts"]

    flagged_count = sum(1 for t in txns if t.get("flagged"))
    total_amount = sum(t["amount"] for t in txns)
    countries = list(set(t["country"] for t in txns if t["country"] not in ("Unknown", None)))

    prompt = f"""You are an AML (Anti-Money Laundering) compliance analyst assistant.
Generate a concise, professional plain-English case summary for an investigator.
Use clear, factual language. Do not use bullet points — write in 2-3 short paragraphs.

CASE INFORMATION:
- Case Number: {ctx['case_number']}
- Title: {ctx['title']}
- Status: {ctx['status']}
- Priority: {ctx['priority']}
- SAR Filed: {ctx['sar_filed']}
- Description: {ctx['description']}
"""

    if customer:
        prompt += f"""
CUSTOMER PROFILE:
- Name: {customer['name']} ({customer['customer_number']})
- Nationality: {customer['nationality']}
- Risk Level: {customer['risk_level']}
- PEP Status: {customer['pep_status']}
- Sanctions Flag: {customer['sanctions_flag']}
- Occupation: {customer['occupation']}
- Annual Income: ${customer['annual_income']:,.0f}
"""

    if txns:
        prompt += f"""
TRANSACTION ACTIVITY (last 90 days):
- Total transactions: {len(txns)}
- Total amount: ${total_amount:,.2f}
- Flagged transactions: {flagged_count} of {len(txns)}
- Countries involved: {', '.join(countries) if countries else 'Domestic only'}
- Transaction types: {', '.join(set(t['type'] for t in txns))}
"""

    if alerts:
        severity_counts = {}
        for a in alerts:
            severity_counts[a['severity']] = severity_counts.get(a['severity'], 0) + 1
        alert_summary = ', '.join(f"{v} {k}" for k, v in severity_counts.items())
        alert_reasons = list(set(a['reason'] for a in alerts if a.get('reason')))[:4]
        prompt += f"""
ALERT HISTORY (last 180 days):
- Total alerts: {len(alerts)} ({alert_summary})
- Alert reasons: {', '.join(alert_reasons)}
"""

    if ctx["notes"]:
        prompt += f"""
ANALYST NOTES:
{chr(10).join(f'- {n}' for n in ctx['notes'][:5])}
"""

    prompt += """
Write a 2-3 paragraph case summary that:
1. Identifies the customer and the core concern
2. Describes the suspicious activity patterns observed
3. States the current investigation status and any key findings

Be direct and factual. Do not include headers or bullet points in your response."""

    return prompt


def generate_case_summary(case_id: int, db: Session) -> dict:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return {"error": "Case not found"}

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return _fallback_summary(case, db)

    try:
        import anthropic
        ctx = _collect_case_context(case, db)
        prompt = _build_prompt(ctx)

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        summary_text = response.content[0].text.strip()

        return {
            "case_number": case.case_number,
            "summary": summary_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": "claude-opus-4-6",
            "source": "ai",
        }

    except Exception:
        return _fallback_summary(case, db)


def _fallback_summary(case: Case, db: Session) -> dict:
    ctx = _collect_case_context(case, db)
    customer = ctx["customer"]
    txns = ctx["transactions"]
    alerts = ctx["alerts"]

    parts = []
    if customer:
        risk_note = f"risk level: {customer['risk_level']}"
        if customer["pep_status"]:
            risk_note += ", PEP"
        if customer["sanctions_flag"]:
            risk_note += ", SANCTIONS FLAG"
        parts.append(
            f"Case {case.case_number} involves customer {customer['name']} "
            f"({customer['customer_number']}, {risk_note})."
        )
    else:
        parts.append(f"Case {case.case_number}: {case.title}.")

    if txns:
        flagged = sum(1 for t in txns if t.get("flagged"))
        total = sum(t["amount"] for t in txns)
        countries = list(set(t["country"] for t in txns if t["country"] not in ("Unknown", None)))
        parts.append(
            f"In the last 90 days, {len(txns)} transactions totaling "
            f"${total:,.0f} were recorded, with {flagged} flagged as suspicious"
            + (f" across {len(countries)} countries ({', '.join(countries[:3])})." if countries else ".")
        )

    if alerts:
        critical = sum(1 for a in alerts if a["severity"] == "critical")
        high = sum(1 for a in alerts if a["severity"] == "high")
        parts.append(
            f"Alert history shows {len(alerts)} alerts in 180 days"
            + (f", including {critical} critical and {high} high severity." if critical or high else ".")
        )

    parts.append(f"Current status: {case.status.replace('_', ' ')} | Priority: {case.priority}.")

    return {
        "case_number": case.case_number,
        "summary": " ".join(parts),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "rule-based",
        "source": "fallback",
    }
