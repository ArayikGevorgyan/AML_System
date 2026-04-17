"""
Compliance Metrics Module
===========================
Provides KPI and compliance metrics for AML regulatory reporting.
Functions cover SAR filing rates, case resolution times, rule effectiveness,
alert-to-case conversion, and overall compliance scoring.

All functions accept a SQLAlchemy Session and return JSON-serialisable dicts.

Usage:
    from database import SessionLocal
    from analysis.compliance_metrics import aml_kpi_summary

    db = SessionLocal()
    summary = aml_kpi_summary(db)
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.alert import Alert
from models.case import Case
from models.customer import Customer
from models.rule import Rule
from models.transaction import Transaction


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _since(days: int) -> datetime:
    return _now() - timedelta(days=days)


# ---------------------------------------------------------------------------
# sar_filing_rate
# ---------------------------------------------------------------------------

def sar_filing_rate(db: Session, days: int = 90) -> Dict[str, Any]:
    """
    Compute the SAR filing rate: what fraction of closed cases resulted
    in a SAR being filed.

    Args:
        db:   SQLAlchemy session.
        days: Lookback window.

    Returns:
        Dict containing:
            - period_days: int
            - total_closed_cases: int
            - sar_filed_count: int
            - sar_filing_rate_pct: float
            - by_month: Dict[str, int]  — SARs filed per month
    """
    cutoff = _since(days)
    closed_cases = db.query(Case).filter(
        Case.status.in_(["closed", "filed_sar"]),
        Case.created_at >= cutoff,
    ).all()

    total_closed = len(closed_cases)
    sar_count = sum(1 for c in closed_cases if c.sar_filed)
    rate = round(sar_count / total_closed * 100, 2) if total_closed > 0 else 0.0

    by_month: Dict[str, int] = {}
    for case in closed_cases:
        if case.sar_filed and case.created_at:
            month_key = case.created_at.strftime("%Y-%m")
            by_month[month_key] = by_month.get(month_key, 0) + 1

    return {
        "period_days": days,
        "total_closed_cases": total_closed,
        "sar_filed_count": sar_count,
        "sar_filing_rate_pct": rate,
        "by_month": dict(sorted(by_month.items())),
    }


# ---------------------------------------------------------------------------
# case_resolution_time_stats
# ---------------------------------------------------------------------------

def case_resolution_time_stats(db: Session) -> Dict[str, Any]:
    """
    Compute case resolution time statistics (in hours and days).

    Only cases with both created_at and closed_at are included.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - sample_size: int
            - mean_hours: float
            - median_hours: float
            - min_hours: float
            - max_hours: float
            - mean_days: float
            - within_sla_24h: int    — cases resolved within 24 hours
            - within_sla_72h: int    — cases resolved within 72 hours
            - sla_24h_pct: float
            - sla_72h_pct: float
    """
    resolved = db.query(Case).filter(
        Case.closed_at.isnot(None),
        Case.created_at.isnot(None),
    ).all()

    if not resolved:
        return {
            "sample_size": 0, "mean_hours": 0.0, "median_hours": 0.0,
            "min_hours": 0.0, "max_hours": 0.0, "mean_days": 0.0,
            "within_sla_24h": 0, "within_sla_72h": 0,
            "sla_24h_pct": 0.0, "sla_72h_pct": 0.0,
        }

    hours_list = []
    for case in resolved:
        try:
            diff = case.closed_at - case.created_at
            hours = diff.total_seconds() / 3600
            hours_list.append(hours)
        except Exception:
            continue

    if not hours_list:
        return {"sample_size": 0}

    hours_list.sort()
    n = len(hours_list)
    mean_h = round(sum(hours_list) / n, 2)
    if n % 2 == 0:
        median_h = round((hours_list[n // 2 - 1] + hours_list[n // 2]) / 2, 2)
    else:
        median_h = round(hours_list[n // 2], 2)

    within_24 = sum(1 for h in hours_list if h <= 24)
    within_72 = sum(1 for h in hours_list if h <= 72)

    return {
        "sample_size": n,
        "mean_hours": mean_h,
        "median_hours": median_h,
        "min_hours": round(min(hours_list), 2),
        "max_hours": round(max(hours_list), 2),
        "mean_days": round(mean_h / 24, 2),
        "within_sla_24h": within_24,
        "within_sla_72h": within_72,
        "sla_24h_pct": round(within_24 / n * 100, 2),
        "sla_72h_pct": round(within_72 / n * 100, 2),
    }


# ---------------------------------------------------------------------------
# rule_effectiveness
# ---------------------------------------------------------------------------

def rule_effectiveness(db: Session) -> List[Dict[str, Any]]:
    """
    Evaluate how effective each AML rule is by comparing true positives
    (alerts that became cases or were confirmed) vs false positives.

    Args:
        db: SQLAlchemy session.

    Returns:
        List of dicts per rule:
            [{rule_id, rule_name, total_alerts, false_positives,
              confirmed, effectiveness_pct, avg_risk_score}]
        Sorted by effectiveness_pct descending.
    """
    rules = db.query(Rule).all()
    result = []

    for rule in rules:
        alerts = db.query(Alert).filter(Alert.rule_id == rule.id).all()
        total = len(alerts)
        if total == 0:
            continue

        false_pos = sum(1 for a in alerts if a.status == "false_positive")
        confirmed = total - false_pos
        effectiveness = round(confirmed / total * 100, 2) if total > 0 else 0.0

        risk_scores = [a.risk_score for a in alerts if a.risk_score is not None]
        avg_score = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0

        result.append({
            "rule_id": rule.id,
            "rule_name": rule.name,
            "category": getattr(rule, "category", "unknown"),
            "is_active": getattr(rule, "is_active", True),
            "total_alerts": total,
            "false_positives": false_pos,
            "confirmed": confirmed,
            "effectiveness_pct": effectiveness,
            "avg_risk_score": avg_score,
        })

    return sorted(result, key=lambda x: x["effectiveness_pct"], reverse=True)


# ---------------------------------------------------------------------------
# alert_to_case_conversion
# ---------------------------------------------------------------------------

def alert_to_case_conversion(db: Session, days: int = 90) -> Dict[str, Any]:
    """
    Compute the rate at which alerts are escalated to full investigations (cases).

    Args:
        db:   SQLAlchemy session.
        days: Lookback window.

    Returns:
        Dict containing:
            - total_alerts: int
            - alerts_with_cases: int
            - conversion_rate_pct: float
            - by_severity: Dict[str, {alerts, with_cases, rate_pct}]
    """
    cutoff = _since(days)
    alerts = db.query(Alert).filter(Alert.created_at >= cutoff).all()
    total = len(alerts)

    # Find alert IDs that have associated cases
    alert_ids_with_cases = set(
        c.alert_id
        for c in db.query(Case).filter(Case.alert_id.isnot(None)).all()
    )

    alerts_with_cases = sum(1 for a in alerts if a.id in alert_ids_with_cases)
    overall_rate = round(alerts_with_cases / total * 100, 2) if total > 0 else 0.0

    # By severity
    by_severity: Dict[str, Dict] = {}
    for sev in ("low", "medium", "high", "critical"):
        sev_alerts = [a for a in alerts if a.severity == sev]
        sev_total = len(sev_alerts)
        sev_with_cases = sum(1 for a in sev_alerts if a.id in alert_ids_with_cases)
        rate = round(sev_with_cases / sev_total * 100, 2) if sev_total > 0 else 0.0
        by_severity[sev] = {
            "alerts": sev_total,
            "with_cases": sev_with_cases,
            "rate_pct": rate,
        }

    return {
        "period_days": days,
        "total_alerts": total,
        "alerts_with_cases": alerts_with_cases,
        "conversion_rate_pct": overall_rate,
        "by_severity": by_severity,
    }


# ---------------------------------------------------------------------------
# compliance_score
# ---------------------------------------------------------------------------

def compliance_score(db: Session) -> Dict[str, Any]:
    """
    Compute an overall compliance health score (0–100) based on multiple KPIs.

    Scoring components:
      - SAR filing rate      (15% weight)
      - Case SLA compliance  (20% weight)
      - False positive rate  (inverse, 20% weight)
      - Alert resolution %   (20% weight)
      - KYC coverage         (25% weight)

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - overall_score: float (0–100)
            - grade: str (A/B/C/D/F)
            - components: Dict[str, {score, weight, weighted_score}]
    """
    # --- SAR filing rate component ---
    sar_data = sar_filing_rate(db, days=90)
    sar_rate = min(sar_data["sar_filing_rate_pct"], 100.0)
    sar_score = min(sar_rate * 1.5, 100.0)  # expect ~20-30% filing rate as good

    # --- SLA compliance component ---
    resolution = case_resolution_time_stats(db)
    sla_score = resolution.get("sla_72h_pct", 0.0)

    # --- False positive component (lower is better, inverted) ---
    total_closed = db.query(Alert).filter(
        Alert.status.in_(["closed", "false_positive"])
    ).count()
    false_pos = db.query(Alert).filter(Alert.status == "false_positive").count()
    fp_rate = (false_pos / total_closed * 100) if total_closed > 0 else 0.0
    fp_score = max(100.0 - fp_rate, 0.0)

    # --- Alert resolution component ---
    total_alerts = db.query(Alert).count()
    resolved_alerts = db.query(Alert).filter(
        Alert.status.in_(["closed", "false_positive"])
    ).count()
    alert_resolution_pct = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0.0

    # --- KYC coverage component ---
    total_customers = db.query(Customer).count()
    kyc_complete = db.query(Customer).filter(
        Customer.id_type.isnot(None),
        Customer.id_number.isnot(None),
        Customer.date_of_birth.isnot(None),
    ).count()
    kyc_pct = (kyc_complete / total_customers * 100) if total_customers > 0 else 0.0

    components = {
        "sar_filing": {"score": round(sar_score, 2), "weight": 0.15,
                       "weighted_score": round(sar_score * 0.15, 2)},
        "case_sla": {"score": round(sla_score, 2), "weight": 0.20,
                     "weighted_score": round(sla_score * 0.20, 2)},
        "false_positive": {"score": round(fp_score, 2), "weight": 0.20,
                           "weighted_score": round(fp_score * 0.20, 2)},
        "alert_resolution": {"score": round(alert_resolution_pct, 2), "weight": 0.20,
                             "weighted_score": round(alert_resolution_pct * 0.20, 2)},
        "kyc_coverage": {"score": round(kyc_pct, 2), "weight": 0.25,
                         "weighted_score": round(kyc_pct * 0.25, 2)},
    }

    overall = sum(c["weighted_score"] for c in components.values())
    overall = round(min(overall, 100.0), 2)

    if overall >= 90:
        grade = "A"
    elif overall >= 80:
        grade = "B"
    elif overall >= 70:
        grade = "C"
    elif overall >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "overall_score": overall,
        "grade": grade,
        "components": components,
        "computed_at": _now().isoformat(),
    }


# ---------------------------------------------------------------------------
# regulatory_breach_count
# ---------------------------------------------------------------------------

def regulatory_breach_count(db: Session, days: int = 30) -> Dict[str, Any]:
    """
    Count potential regulatory breaches in the past N days.

    Breaches are defined as:
      - Critical alerts open for more than 5 days
      - Cases with no activity for more than 7 days
      - Customers with sanctions flag and no review (open alerts)

    Args:
        db:   SQLAlchemy session.
        days: Window for recent breach detection.

    Returns:
        Dict containing:
            - total_breaches: int
            - stale_critical_alerts: int
            - stale_open_cases: int
            - unreviewed_sanctioned_customers: int
    """
    cutoff = _since(days)

    stale_critical = db.query(Alert).filter(
        Alert.severity == "critical",
        Alert.status == "open",
        Alert.created_at <= _now() - timedelta(days=5),
    ).count()

    stale_cases = db.query(Case).filter(
        Case.status.in_(["open", "investigating"]),
        Case.updated_at <= _now() - timedelta(days=7),
    ).count()

    sanc_customers = db.query(Customer).filter(Customer.sanctions_flag == True).all()
    sanc_ids = [c.id for c in sanc_customers]
    unreviewed_sanc = 0
    if sanc_ids:
        unreviewed_sanc = db.query(Alert).filter(
            Alert.customer_id.in_(sanc_ids),
            Alert.status == "open",
        ).count()

    total = stale_critical + stale_cases + unreviewed_sanc

    return {
        "period_days": days,
        "total_breaches": total,
        "stale_critical_alerts": stale_critical,
        "stale_open_cases": stale_cases,
        "unreviewed_sanctioned_customers": len(sanc_customers),
        "sanctioned_customers_with_open_alerts": unreviewed_sanc,
    }


# ---------------------------------------------------------------------------
# kyc_coverage_rate
# ---------------------------------------------------------------------------

def kyc_coverage_rate(db: Session) -> Dict[str, Any]:
    """
    Compute KYC (Know Your Customer) data completeness across the customer base.

    Checks for presence of: id_type, id_number, date_of_birth, nationality,
    address, email.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_customers: int
            - fully_complete: int
            - fully_complete_pct: float
            - field_coverage: Dict[str, {count, pct}]
    """
    customers = db.query(Customer).all()
    total = len(customers)

    if total == 0:
        return {"total_customers": 0, "fully_complete": 0, "fully_complete_pct": 0.0,
                "field_coverage": {}}

    fields = ["id_type", "id_number", "date_of_birth", "nationality", "address", "email"]
    field_counts: Dict[str, int] = {f: 0 for f in fields}
    fully_complete = 0

    for c in customers:
        all_filled = True
        for field in fields:
            val = getattr(c, field, None)
            if val is not None and str(val).strip():
                field_counts[field] += 1
            else:
                all_filled = False
        if all_filled:
            fully_complete += 1

    field_coverage = {
        field: {
            "count": cnt,
            "pct": round(cnt / total * 100, 2),
        }
        for field, cnt in field_counts.items()
    }

    return {
        "total_customers": total,
        "fully_complete": fully_complete,
        "fully_complete_pct": round(fully_complete / total * 100, 2),
        "field_coverage": field_coverage,
    }


# ---------------------------------------------------------------------------
# aml_kpi_summary
# ---------------------------------------------------------------------------

def aml_kpi_summary(db: Session) -> Dict[str, Any]:
    """
    Aggregate all AML KPI metrics into a single summary dict.

    This is the primary function for dashboard and executive reporting.
    Calls all individual metric functions and assembles them.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing all metric groups plus a generated_at timestamp.
    """
    return {
        "generated_at": _now().isoformat(),
        "sar_filing": sar_filing_rate(db, days=90),
        "case_resolution_time": case_resolution_time_stats(db),
        "rule_effectiveness": rule_effectiveness(db),
        "alert_to_case_conversion": alert_to_case_conversion(db, days=90),
        "compliance_score": compliance_score(db),
        "regulatory_breaches": regulatory_breach_count(db, days=30),
        "kyc_coverage": kyc_coverage_rate(db),
    }
