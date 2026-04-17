"""
Customer Risk Analysis Module
===============================
Statistical analysis functions focused on customer risk profiles.
Used by compliance teams to understand portfolio-level risk exposure,
identify high-risk segments, and track risk evolution over time.

All functions accept a SQLAlchemy Session and return JSON-serialisable dicts.

Usage:
    from database import SessionLocal
    from analysis.customer_risk_analysis import risk_distribution, top_risky_customers

    db = SessionLocal()
    print(risk_distribution(db))
    print(top_risky_customers(db, limit=5))
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from models.customer import Customer
from models.alert import Alert
from models.transaction import Transaction


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# risk_distribution
# ---------------------------------------------------------------------------

def risk_distribution(db: Session) -> Dict[str, Any]:
    """
    Compute the distribution of customers across risk levels.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_customers: int
            - by_risk_level: Dict[str, int]      counts per level
            - by_risk_level_pct: Dict[str, float] percentage per level
            - high_or_critical: int               combined high+critical count
            - high_or_critical_pct: float
    """
    customers = db.query(Customer).all()
    total = len(customers)

    counts: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for c in customers:
        level = c.risk_level or "low"
        counts[level] = counts.get(level, 0) + 1

    pct: Dict[str, float] = {
        level: round(cnt / total * 100, 2) if total > 0 else 0.0
        for level, cnt in counts.items()
    }

    high_or_critical = counts.get("high", 0) + counts.get("critical", 0)
    hoc_pct = round(high_or_critical / total * 100, 2) if total > 0 else 0.0

    return {
        "total_customers": total,
        "by_risk_level": counts,
        "by_risk_level_pct": pct,
        "high_or_critical": high_or_critical,
        "high_or_critical_pct": hoc_pct,
    }


# ---------------------------------------------------------------------------
# pep_statistics
# ---------------------------------------------------------------------------

def pep_statistics(db: Session) -> Dict[str, Any]:
    """
    Return statistics about Politically Exposed Persons (PEPs) in the system.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_pep: int
            - pep_pct_of_portfolio: float
            - pep_high_risk: int           PEPs with high or critical risk level
            - pep_with_alerts: int         PEPs that have at least one open alert
            - pep_sanctioned: int          PEPs with sanctions_flag=True
            - pep_by_nationality: Dict[str, int]
    """
    total_customers = db.query(Customer).count()
    pep_customers = db.query(Customer).filter(Customer.pep_status == True).all()
    total_pep = len(pep_customers)

    pep_pct = round(total_pep / total_customers * 100, 2) if total_customers > 0 else 0.0
    pep_high_risk = sum(1 for c in pep_customers if c.risk_level in ("high", "critical"))
    pep_sanctioned = sum(1 for c in pep_customers if c.sanctions_flag)

    # PEPs with at least one open alert
    pep_ids = {c.id for c in pep_customers}
    pep_with_alerts = 0
    if pep_ids:
        alerted_pep_ids = set(
            row.customer_id
            for row in db.query(Alert).filter(
                Alert.customer_id.in_(list(pep_ids)),
                Alert.status == "open",
            ).all()
        )
        pep_with_alerts = len(alerted_pep_ids)

    # Nationality breakdown
    by_nationality: Dict[str, int] = {}
    for c in pep_customers:
        nat = c.nationality or "Unknown"
        by_nationality[nat] = by_nationality.get(nat, 0) + 1

    return {
        "total_pep": total_pep,
        "pep_pct_of_portfolio": pep_pct,
        "pep_high_risk": pep_high_risk,
        "pep_with_alerts": pep_with_alerts,
        "pep_sanctioned": pep_sanctioned,
        "pep_by_nationality": dict(
            sorted(by_nationality.items(), key=lambda x: x[1], reverse=True)
        ),
    }


# ---------------------------------------------------------------------------
# top_risky_customers
# ---------------------------------------------------------------------------

def top_risky_customers(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the top N riskiest customers based on a composite risk score.

    Risk composite = base score (critical=100, high=75, medium=40, low=10) +
                     PEP bonus (+15) + sanctions bonus (+20) +
                     open alerts count × 5.

    Args:
        db:    SQLAlchemy session.
        limit: Maximum number of customers to return.

    Returns:
        List of dicts with customer info and composite risk score.
        Sorted by composite_score descending.
    """
    base_scores = {"low": 10, "medium": 40, "high": 75, "critical": 100}

    customers = db.query(Customer).all()
    if not customers:
        return []

    customer_ids = [c.id for c in customers]

    # Preload open alert counts per customer
    alerts = db.query(Alert).filter(
        Alert.customer_id.in_(customer_ids),
        Alert.status.in_(["open", "escalated"]),
    ).all()

    alert_counts: Dict[int, int] = {}
    for alert in alerts:
        alert_counts[alert.customer_id] = alert_counts.get(alert.customer_id, 0) + 1

    scored = []
    for c in customers:
        base = base_scores.get(c.risk_level, 10)
        pep_bonus = 15 if c.pep_status else 0
        sanc_bonus = 20 if c.sanctions_flag else 0
        alert_bonus = min(alert_counts.get(c.id, 0) * 5, 30)
        composite = min(base + pep_bonus + sanc_bonus + alert_bonus, 150)

        scored.append({
            "customer_id": c.id,
            "customer_number": c.customer_number,
            "full_name": c.full_name,
            "risk_level": c.risk_level,
            "pep_status": c.pep_status,
            "sanctions_flag": c.sanctions_flag,
            "open_alerts": alert_counts.get(c.id, 0),
            "composite_score": composite,
            "nationality": c.nationality,
        })

    return sorted(scored, key=lambda x: x["composite_score"], reverse=True)[:limit]


# ---------------------------------------------------------------------------
# nationality_risk_breakdown
# ---------------------------------------------------------------------------

def nationality_risk_breakdown(db: Session) -> List[Dict[str, Any]]:
    """
    Return risk profile breakdown grouped by customer nationality.

    Args:
        db: SQLAlchemy session.

    Returns:
        List of dicts per nationality:
            [{nationality, total, high_risk_count, pep_count, sanctioned_count,
              high_risk_pct}]
        Sorted by high_risk_count descending.
    """
    customers = db.query(Customer).all()
    groups: Dict[str, Dict[str, Any]] = {}

    for c in customers:
        nat = c.nationality or "Unknown"
        if nat not in groups:
            groups[nat] = {
                "nationality": nat,
                "total": 0,
                "high_risk_count": 0,
                "pep_count": 0,
                "sanctioned_count": 0,
            }
        groups[nat]["total"] += 1
        if c.risk_level in ("high", "critical"):
            groups[nat]["high_risk_count"] += 1
        if c.pep_status:
            groups[nat]["pep_count"] += 1
        if c.sanctions_flag:
            groups[nat]["sanctioned_count"] += 1

    result = []
    for nat, data in groups.items():
        total = data["total"]
        data["high_risk_pct"] = round(data["high_risk_count"] / total * 100, 2) if total > 0 else 0.0
        result.append(data)

    return sorted(result, key=lambda x: x["high_risk_count"], reverse=True)


# ---------------------------------------------------------------------------
# customer_alert_correlation
# ---------------------------------------------------------------------------

def customer_alert_correlation(db: Session) -> Dict[str, Any]:
    """
    Compute correlation between customer risk levels and alert counts.

    Returns average alert counts per risk level and the fraction of each
    risk level that has ever triggered an alert.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict keyed by risk_level:
            {low: {avg_alerts, pct_with_alerts, total_customers}, ...}
    """
    customers = db.query(Customer).all()
    all_alerts = db.query(Alert).all()

    alerts_by_customer: Dict[int, int] = {}
    for a in all_alerts:
        alerts_by_customer[a.customer_id] = alerts_by_customer.get(a.customer_id, 0) + 1

    by_level: Dict[str, Dict] = {
        "low": {"total_customers": 0, "total_alerts": 0, "with_alerts": 0},
        "medium": {"total_customers": 0, "total_alerts": 0, "with_alerts": 0},
        "high": {"total_customers": 0, "total_alerts": 0, "with_alerts": 0},
        "critical": {"total_customers": 0, "total_alerts": 0, "with_alerts": 0},
    }

    for c in customers:
        level = c.risk_level or "low"
        if level not in by_level:
            by_level[level] = {"total_customers": 0, "total_alerts": 0, "with_alerts": 0}
        cnt = alerts_by_customer.get(c.id, 0)
        by_level[level]["total_customers"] += 1
        by_level[level]["total_alerts"] += cnt
        if cnt > 0:
            by_level[level]["with_alerts"] += 1

    result = {}
    for level, data in by_level.items():
        total = data["total_customers"]
        total_alerts = data["total_alerts"]
        with_alerts = data["with_alerts"]
        result[level] = {
            "total_customers": total,
            "avg_alerts": round(total_alerts / total, 2) if total > 0 else 0.0,
            "pct_with_alerts": round(with_alerts / total * 100, 2) if total > 0 else 0.0,
        }

    return result


# ---------------------------------------------------------------------------
# risk_score_histogram
# ---------------------------------------------------------------------------

def risk_score_histogram(db: Session, bins: int = 10) -> List[Dict[str, Any]]:
    """
    Generate a histogram of customer transaction risk scores.

    Uses transaction risk_score values associated with each customer.

    Args:
        db:   SQLAlchemy session.
        bins: Number of histogram bins (default 10).

    Returns:
        List of bin dicts: [{bin_start, bin_end, label, count}]
    """
    txns = db.query(Transaction).filter(Transaction.risk_score > 0).all()
    scores = [t.risk_score for t in txns if t.risk_score is not None]

    if not scores:
        return []

    min_s = 0.0
    max_s = 100.0
    step = (max_s - min_s) / bins

    histogram = []
    for i in range(bins):
        bin_start = round(min_s + i * step, 1)
        bin_end = round(min_s + (i + 1) * step, 1)
        count = sum(1 for s in scores if bin_start <= s < bin_end)
        histogram.append({
            "bin_start": bin_start,
            "bin_end": bin_end,
            "label": f"{bin_start:.0f}-{bin_end:.0f}",
            "count": count,
        })

    return histogram


# ---------------------------------------------------------------------------
# sanctioned_customer_stats
# ---------------------------------------------------------------------------

def sanctioned_customer_stats(db: Session) -> Dict[str, Any]:
    """
    Return statistics for customers with active sanctions flags.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_sanctioned: int
            - pct_of_portfolio: float
            - by_risk_level: Dict[str, int]
            - by_nationality: Dict[str, int]
            - with_open_alerts: int
    """
    total = db.query(Customer).count()
    sanctioned = db.query(Customer).filter(Customer.sanctions_flag == True).all()
    sanc_count = len(sanctioned)

    pct = round(sanc_count / total * 100, 2) if total > 0 else 0.0

    by_risk: Dict[str, int] = {}
    by_nat: Dict[str, int] = {}
    for c in sanctioned:
        rl = c.risk_level or "low"
        by_risk[rl] = by_risk.get(rl, 0) + 1
        nat = c.nationality or "Unknown"
        by_nat[nat] = by_nat.get(nat, 0) + 1

    sanc_ids = [c.id for c in sanctioned]
    with_open_alerts = 0
    if sanc_ids:
        open_alert_ids = set(
            a.customer_id
            for a in db.query(Alert).filter(
                Alert.customer_id.in_(sanc_ids),
                Alert.status == "open",
            ).all()
        )
        with_open_alerts = len(open_alert_ids)

    return {
        "total_sanctioned": sanc_count,
        "pct_of_portfolio": pct,
        "by_risk_level": by_risk,
        "by_nationality": dict(sorted(by_nat.items(), key=lambda x: x[1], reverse=True)),
        "with_open_alerts": with_open_alerts,
    }


# ---------------------------------------------------------------------------
# risk_trend_over_time
# ---------------------------------------------------------------------------

def risk_trend_over_time(db: Session, days: int = 90) -> List[Dict[str, Any]]:
    """
    Track how the portfolio risk mix has changed over the past N days by looking
    at customer updated_at timestamps and their current risk levels.

    Note: Since the system stores current risk level (not historical),
    this uses transaction creation dates to approximate the risk exposure
    over time by weighting risk scores per day.

    Args:
        db:   SQLAlchemy session.
        days: Lookback period in days.

    Returns:
        List of weekly buckets:
            [{week_start, high_risk_txn_count, total_txn_count, high_risk_pct}]
    """
    cutoff = _now() - timedelta(days=days)
    txns = db.query(Transaction).filter(Transaction.created_at >= cutoff).all()

    # Group by week
    weekly: Dict[str, Dict[str, int]] = {}
    for t in txns:
        if not t.created_at:
            continue
        # Round down to start of week (Monday)
        dt = t.created_at
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        if week_key not in weekly:
            weekly[week_key] = {"total": 0, "high_risk": 0}
        weekly[week_key]["total"] += 1
        if t.risk_score and t.risk_score >= 60:
            weekly[week_key]["high_risk"] += 1

    result = []
    for week, data in sorted(weekly.items()):
        total = data["total"]
        high = data["high_risk"]
        result.append({
            "week_start": week,
            "high_risk_txn_count": high,
            "total_txn_count": total,
            "high_risk_pct": round(high / total * 100, 2) if total > 0 else 0.0,
        })

    return result
