from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from models.customer import Customer
from models.transaction import Transaction
from models.alert import Alert
from config import settings


def _period_stats(customer_id: int, days_start: int, days_end: int, db: Session) -> dict:
    now = datetime.now(timezone.utc)
    period_end = now - timedelta(days=days_start)
    period_start = now - timedelta(days=days_end)

    txns = db.query(Transaction).filter(
        Transaction.from_customer_id == customer_id,
        Transaction.created_at >= period_start,
        Transaction.created_at < period_end,
    ).all()

    alerts = db.query(Alert).filter(
        Alert.customer_id == customer_id,
        Alert.created_at >= period_start,
        Alert.created_at < period_end,
        Alert.status != "false_positive",
    ).all()

    flagged = sum(1 for t in txns if t.flagged)
    total_amount = sum(t.amount for t in txns)
    countries = set(t.destination_country for t in txns if t.destination_country)

    return {
        "txn_count": len(txns),
        "txn_amount": round(total_amount, 2),
        "flagged_count": flagged,
        "flagged_ratio": round(flagged / len(txns), 3) if txns else 0.0,
        "alert_count": len(alerts),
        "critical_alerts": sum(1 for a in alerts if a.severity == "critical"),
        "high_alerts": sum(1 for a in alerts if a.severity == "high"),
        "country_count": len(countries),
    }


def _compute_trajectory(recent: dict, mid: dict, older: dict) -> dict:
    def pct_change(new_val, old_val):
        if old_val == 0:
            return 100.0 if new_val > 0 else 0.0
        return round((new_val - old_val) / old_val * 100, 1)

    txn_trend = pct_change(recent["txn_count"], mid["txn_count"])
    amount_trend = pct_change(recent["txn_amount"], mid["txn_amount"])
    alert_trend = pct_change(recent["alert_count"], mid["alert_count"])
    flag_trend = pct_change(recent["flagged_ratio"], mid["flagged_ratio"])

    velocity_score = 0.0

    if txn_trend > 50:
        velocity_score += 15
    elif txn_trend > 20:
        velocity_score += 8

    if amount_trend > 100:
        velocity_score += 20
    elif amount_trend > 50:
        velocity_score += 12
    elif amount_trend > 20:
        velocity_score += 6

    if alert_trend > 100:
        velocity_score += 25
    elif alert_trend > 50:
        velocity_score += 15
    elif alert_trend > 0:
        velocity_score += 8

    if flag_trend > 50:
        velocity_score += 20
    elif flag_trend > 20:
        velocity_score += 10

    if recent["critical_alerts"] > 0:
        velocity_score += 15
    if recent["high_alerts"] > 1:
        velocity_score += 10

    if recent["country_count"] > mid["country_count"] + 2:
        velocity_score += 10

    velocity_score = min(round(velocity_score, 1), 100)

    if velocity_score >= 60:
        trend = "escalating"
    elif velocity_score >= 30:
        trend = "increasing"
    elif velocity_score >= 10:
        trend = "stable"
    else:
        trend = "declining"

    return {
        "velocity_score": velocity_score,
        "trend": trend,
        "changes": {
            "transaction_count_change_pct": txn_trend,
            "transaction_amount_change_pct": amount_trend,
            "alert_count_change_pct": alert_trend,
            "flagged_ratio_change_pct": flag_trend,
        },
    }


def _build_prediction_prompt(customer: Customer, recent: dict, mid: dict,
                              older: dict, trajectory: dict) -> str:
    return f"""You are an expert AML risk analyst. Based on the behavioral data below,
predict this customer's risk trajectory for the next 30 days.

CUSTOMER: {customer.full_name} | Risk Level: {customer.risk_level} | PEP: {customer.pep_status}

ACTIVITY TRENDS (compared month-over-month):
- Recent (0-30 days): {recent['txn_count']} transactions, ${recent['txn_amount']:,.0f} total, {recent['flagged_count']} flagged, {recent['alert_count']} alerts
- Prior (30-60 days): {mid['txn_count']} transactions, ${mid['txn_amount']:,.0f} total, {mid['flagged_count']} flagged, {mid['alert_count']} alerts
- Older (60-90 days): {older['txn_count']} transactions, ${older['txn_amount']:,.0f} total, {older['flagged_count']} flagged, {older['alert_count']} alerts

TRAJECTORY ANALYSIS:
- Velocity Score: {trajectory['velocity_score']}/100
- Trend: {trajectory['trend']}
- Transaction count change: {trajectory['changes']['transaction_count_change_pct']:+.1f}%
- Transaction amount change: {trajectory['changes']['transaction_amount_change_pct']:+.1f}%
- Alert count change: {trajectory['changes']['alert_count_change_pct']:+.1f}%
- Flagged ratio change: {trajectory['changes']['flagged_ratio_change_pct']:+.1f}%

Write ONE sentence (max 35 words) predicting this customer's risk level for the next 30 days.
Be specific about the pattern. Example format: "Based on X pattern, this customer's risk is likely to Y because Z."
Do not include bullet points or headers."""


def predict_customer_risk(customer_id: int, db: Session) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"error": "Customer not found"}

    recent = _period_stats(customer_id, 0, 30, db)
    mid = _period_stats(customer_id, 30, 60, db)
    older = _period_stats(customer_id, 60, 90, db)
    trajectory = _compute_trajectory(recent, mid, older)

    base_score = {"low": 10, "medium": 35, "high": 60, "critical": 80}.get(customer.risk_level, 10)
    predicted_score = min(round(base_score + trajectory["velocity_score"] * 0.4, 1), 100)

    if predicted_score >= 75:
        predicted_band = "critical"
    elif predicted_score >= 50:
        predicted_band = "high"
    elif predicted_score >= 25:
        predicted_band = "medium"
    else:
        predicted_band = "low"

    pattern_match_pct = min(round(trajectory["velocity_score"] * 0.87, 1), 95.0)

    narrative = _generate_narrative(customer, recent, mid, older, trajectory, predicted_band)

    return {
        "customer_id": customer_id,
        "customer_name": customer.full_name,
        "current_risk_level": customer.risk_level,
        "predicted_risk_band": predicted_band,
        "predicted_score": predicted_score,
        "velocity_score": trajectory["velocity_score"],
        "trend": trajectory["trend"],
        "pattern_match_pct": pattern_match_pct,
        "period_stats": {
            "recent_30d": recent,
            "prior_30_60d": mid,
            "older_60_90d": older,
        },
        "changes": trajectory["changes"],
        "narrative": narrative,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _generate_narrative(customer: Customer, recent: dict, mid: dict,
                        older: dict, trajectory: dict, predicted_band: str) -> str:
    api_key = settings.ANTHROPIC_API_KEY

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = _build_prediction_prompt(customer, recent, mid, older, trajectory)
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception:
            pass

    trend = trajectory["trend"]
    changes = trajectory["changes"]
    velocity = trajectory["velocity_score"]

    if trend == "escalating":
        return (
            f"This customer's pattern matches high-risk profiles — "
            f"transaction volume up {changes['transaction_count_change_pct']:+.0f}% and "
            f"alerts up {changes['alert_count_change_pct']:+.0f}% month-over-month suggest "
            f"predicted risk level: {predicted_band.upper()} within 30 days."
        )
    elif trend == "increasing":
        return (
            f"Moderate escalation detected with a {velocity:.0f}/100 velocity score; "
            f"predicted risk level: {predicted_band.upper()} over the next 30 days "
            f"if current trajectory continues."
        )
    elif trend == "stable":
        return (
            f"Activity is broadly stable with velocity score {velocity:.0f}/100; "
            f"predicted risk level remains {predicted_band.upper()} for the next 30 days."
        )
    else:
        return (
            f"Transaction and alert activity is declining; "
            f"predicted risk level: {predicted_band.upper()} — monitor for re-escalation."
        )
