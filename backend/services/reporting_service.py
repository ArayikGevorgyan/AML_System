"""
Reporting & Export Service
===========================
Generates compliance reports for the AML system:

- Monthly Transaction Summary
- Alert Statistics Report
- SAR (Suspicious Activity Report) Summary
- Customer Risk Distribution Report
- Rule Performance Report
- Full Compliance Export (all reports combined)
"""

from datetime import datetime, timedelta, timezone, date
from calendar import monthrange
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from models.transaction import Transaction
from models.alert import Alert
from models.case import Case
from models.customer import Customer
from models.rule import Rule


def _now() -> datetime:
    return datetime.now(timezone.utc)


def monthly_transaction_summary(db: Session, year: int, month: int) -> dict:
    """
    Generate a transaction summary for a given month.
    Includes total count, total volume, flagged count, by-type breakdown,
    by-currency breakdown, and daily trend.
    """
    # Month boundaries
    _, last_day = monthrange(year, month)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end   = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    txns = db.query(Transaction).filter(
        Transaction.created_at >= start,
        Transaction.created_at <= end,
    ).all()

    total_count   = len(txns)
    total_volume  = round(sum(t.amount for t in txns), 2)
    flagged_count = sum(1 for t in txns if t.flagged)
    avg_amount    = round(total_volume / total_count, 2) if total_count else 0
    intl_count    = sum(1 for t in txns if t.is_international)

    # By type
    by_type: dict = {}
    for t in txns:
        by_type[t.transaction_type] = by_type.get(t.transaction_type, 0) + 1

    # By currency
    by_currency: dict = {}
    for t in txns:
        by_currency[t.currency] = by_currency.get(t.currency, 0) + round(t.amount, 2)

    # Daily trend
    daily: dict = {}
    for t in txns:
        day = t.created_at.strftime("%Y-%m-%d") if t.created_at else "unknown"
        if day not in daily:
            daily[day] = {"count": 0, "volume": 0.0, "flagged": 0}
        daily[day]["count"]  += 1
        daily[day]["volume"] += t.amount
        if t.flagged:
            daily[day]["flagged"] += 1

    daily_trend = [
        {"date": d, **v} for d, v in sorted(daily.items())
    ]

    return {
        "report_type":    "monthly_transaction_summary",
        "period":         f"{year}-{month:02d}",
        "generated_at":   _now().isoformat(),
        "summary": {
            "total_transactions":  total_count,
            "total_volume_usd":    total_volume,
            "flagged_transactions": flagged_count,
            "flagged_ratio":       round(flagged_count / total_count, 4) if total_count else 0,
            "average_amount":      avg_amount,
            "international_count": intl_count,
        },
        "by_type":     by_type,
        "by_currency": by_currency,
        "daily_trend": daily_trend,
    }


def alert_statistics_report(db: Session, days: int = 30) -> dict:
    """
    Alert statistics for the last N days.
    Includes counts by severity, status, top rules, and resolution times.
    """
    since = _now() - timedelta(days=days)
    alerts = db.query(Alert).filter(Alert.created_at >= since).all()

    total = len(alerts)

    by_severity: dict = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    by_status:   dict = {}
    for a in alerts:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        by_status[a.status]     = by_status.get(a.status, 0) + 1

    # Resolution time for closed alerts
    closed = [a for a in alerts if a.status == "closed" and a.closed_at and a.created_at]
    avg_resolution_hours = 0.0
    if closed:
        total_hours = sum(
            (a.closed_at - a.created_at).total_seconds() / 3600
            for a in closed
        )
        avg_resolution_hours = round(total_hours / len(closed), 1)

    # Top rules by alert count
    rule_counts: dict = {}
    for a in alerts:
        if a.rule_id:
            rule_counts[a.rule_id] = rule_counts.get(a.rule_id, 0) + 1

    top_rules = []
    for rule_id, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()
        top_rules.append({
            "rule_id":   rule_id,
            "rule_name": rule.name if rule else "Unknown",
            "count":     count,
        })

    return {
        "report_type":  "alert_statistics",
        "period_days":  days,
        "generated_at": _now().isoformat(),
        "summary": {
            "total_alerts":          total,
            "open_alerts":           by_status.get("open", 0),
            "escalated_alerts":      by_status.get("escalated", 0),
            "false_positive_rate":   round(by_status.get("false_positive", 0) / total, 4) if total else 0,
            "avg_resolution_hours":  avg_resolution_hours,
        },
        "by_severity": by_severity,
        "by_status":   by_status,
        "top_rules":   top_rules,
    }


def sar_summary_report(db: Session, year: int) -> dict:
    """
    Suspicious Activity Report summary for a given year.
    Lists all SAR-filed cases with key details.
    """
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end   = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    sar_cases = db.query(Case).filter(
        Case.sar_filed == True,
        Case.created_at >= start,
        Case.created_at <= end,
    ).all()

    cases_data = []
    for c in sar_cases:
        customer = db.query(Customer).filter(Customer.id == c.customer_id).first() if c.customer_id else None
        cases_data.append({
            "case_number":    c.case_number,
            "sar_reference":  c.sar_reference,
            "customer":       customer.full_name if customer else "Unknown",
            "customer_number": customer.customer_number if customer else None,
            "status":         c.status,
            "priority":       c.priority,
            "filed_at":       c.updated_at.isoformat() if c.updated_at else None,
        })

    return {
        "report_type":  "sar_summary",
        "year":         year,
        "generated_at": _now().isoformat(),
        "total_sars_filed": len(sar_cases),
        "cases": cases_data,
    }


def customer_risk_distribution_report(db: Session) -> dict:
    """
    Distribution of customers across risk levels.
    Includes PEP counts, sanctions flags, and high-risk country breakdown.
    """
    customers = db.query(Customer).all()
    total     = len(customers)

    by_risk: dict = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    pep_count      = 0
    sanctions_count = 0
    by_country: dict = {}

    for c in customers:
        by_risk[c.risk_level] = by_risk.get(c.risk_level, 0) + 1
        if c.pep_status:
            pep_count += 1
        if c.sanctions_flag:
            sanctions_count += 1
        country = c.nationality or c.country or "Unknown"
        by_country[country] = by_country.get(country, 0) + 1

    top_countries = sorted(by_country.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "report_type":   "customer_risk_distribution",
        "generated_at":  _now().isoformat(),
        "total_customers": total,
        "by_risk_level": by_risk,
        "pep_customers": pep_count,
        "sanctioned_customers": sanctions_count,
        "high_risk_ratio": round((by_risk.get("high", 0) + by_risk.get("critical", 0)) / total, 4) if total else 0,
        "top_nationalities": [{"country": c, "count": n} for c, n in top_countries],
    }


def rule_performance_report(db: Session, days: int = 30) -> dict:
    """
    Performance metrics for each AML rule:
    - Total alerts fired
    - False positive rate
    - Average risk score of triggered transactions
    """
    since = _now() - timedelta(days=days)
    rules = db.query(Rule).all()

    rule_stats = []
    for rule in rules:
        alerts = db.query(Alert).filter(
            Alert.rule_id == rule.id,
            Alert.created_at >= since,
        ).all()

        total          = len(alerts)
        false_pos      = sum(1 for a in alerts if a.status == "false_positive")
        avg_risk_score = round(sum(a.risk_score for a in alerts) / total, 1) if total else 0

        rule_stats.append({
            "rule_id":          rule.id,
            "rule_name":        rule.name,
            "category":         rule.category,
            "is_active":        rule.is_active,
            "alerts_fired":     total,
            "false_positives":  false_pos,
            "false_pos_rate":   round(false_pos / total, 4) if total else 0,
            "avg_risk_score":   avg_risk_score,
        })

    rule_stats.sort(key=lambda x: x["alerts_fired"], reverse=True)

    return {
        "report_type":  "rule_performance",
        "period_days":  days,
        "generated_at": _now().isoformat(),
        "rules":        rule_stats,
    }


def full_compliance_export(db: Session) -> dict:
    """
    Full compliance export — all reports combined into one response.
    Used for periodic regulatory reporting.
    """
    now   = _now()
    year  = now.year
    month = now.month

    return {
        "export_type":  "full_compliance_export",
        "generated_at": now.isoformat(),
        "system":       "AML Transaction Monitoring System",
        "reports": {
            "transaction_summary":      monthly_transaction_summary(db, year, month),
            "alert_statistics":         alert_statistics_report(db, days=30),
            "sar_summary":              sar_summary_report(db, year),
            "customer_risk_distribution": customer_risk_distribution_report(db),
            "rule_performance":         rule_performance_report(db, days=30),
        },
    }
