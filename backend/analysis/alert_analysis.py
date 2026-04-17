"""
Alert Analysis Module
======================
Provides statistical and trend analysis functions over the alerts table.
Used by compliance officers and analysts to understand alert patterns,
rule performance, and operational efficiency.

All functions accept a SQLAlchemy Session as first argument and return
plain dicts/lists suitable for JSON serialisation.

Usage:
    from database import SessionLocal
    from analysis.alert_analysis import alert_velocity, top_alerted_customers

    db = SessionLocal()
    print(alert_velocity(db, days=30))
    print(top_alerted_customers(db, limit=10))
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.alert import Alert
from models.customer import Customer
from models.rule import Rule


def _now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def _since(days: int) -> datetime:
    """Return UTC datetime N days ago."""
    return _now() - timedelta(days=days)


# ---------------------------------------------------------------------------
# alert_velocity
# ---------------------------------------------------------------------------

def alert_velocity(db: Session, days: int = 30) -> Dict[str, Any]:
    """
    Compute alert creation velocity over the specified number of days.

    Breaks down total alert count by day and computes daily averages,
    peak day, and percentage change vs the preceding equal window.

    Args:
        db:   SQLAlchemy session.
        days: Number of days to look back (default 30).

    Returns:
        Dict containing:
            - period_days: int
            - total_alerts: int
            - avg_per_day: float
            - peak_day: str (YYYY-MM-DD) or None
            - peak_count: int
            - daily_counts: List[Dict]  [{date, count}]
            - pct_change_vs_prior: float   (e.g. +12.5 means 12.5% more)
    """
    cutoff = _since(days)
    prior_cutoff = _since(days * 2)

    alerts = (
        db.query(Alert)
        .filter(Alert.created_at >= cutoff)
        .all()
    )

    prior_count = (
        db.query(Alert)
        .filter(Alert.created_at >= prior_cutoff, Alert.created_at < cutoff)
        .count()
    )

    daily: Dict[str, int] = {}
    for alert in alerts:
        day = alert.created_at.strftime("%Y-%m-%d") if alert.created_at else "unknown"
        daily[day] = daily.get(day, 0) + 1

    total = len(alerts)
    avg_per_day = round(total / days, 2) if days > 0 else 0.0
    peak_day = max(daily, key=daily.get) if daily else None
    peak_count = daily[peak_day] if peak_day else 0

    if prior_count > 0:
        pct_change = round((total - prior_count) / prior_count * 100, 2)
    elif total > 0:
        pct_change = 100.0
    else:
        pct_change = 0.0

    daily_list = [
        {"date": d, "count": c}
        for d, c in sorted(daily.items())
    ]

    return {
        "period_days": days,
        "total_alerts": total,
        "avg_per_day": avg_per_day,
        "peak_day": peak_day,
        "peak_count": peak_count,
        "daily_counts": daily_list,
        "pct_change_vs_prior": pct_change,
    }


# ---------------------------------------------------------------------------
# alert_by_rule
# ---------------------------------------------------------------------------

def alert_by_rule(db: Session) -> List[Dict[str, Any]]:
    """
    Return alert counts grouped by rule, with severity breakdown.

    Useful for understanding which rules are firing most frequently
    and what severity they produce.

    Args:
        db: SQLAlchemy session.

    Returns:
        List of dicts, each representing one rule:
            [{rule_id, rule_name, category, total, open, closed,
              critical, high, medium, low}]
        Sorted by total descending.
    """
    rules = db.query(Rule).all()
    result = []

    for rule in rules:
        alerts = db.query(Alert).filter(Alert.rule_id == rule.id).all()
        total = len(alerts)
        open_count = sum(1 for a in alerts if a.status == "open")
        closed_count = sum(1 for a in alerts if a.status == "closed")
        critical = sum(1 for a in alerts if a.severity == "critical")
        high = sum(1 for a in alerts if a.severity == "high")
        medium = sum(1 for a in alerts if a.severity == "medium")
        low = sum(1 for a in alerts if a.severity == "low")

        result.append({
            "rule_id": rule.id,
            "rule_name": rule.name,
            "category": rule.category,
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        })

    return sorted(result, key=lambda x: x["total"], reverse=True)


# ---------------------------------------------------------------------------
# alert_escalation_rate
# ---------------------------------------------------------------------------

def alert_escalation_rate(db: Session) -> Dict[str, Any]:
    """
    Compute the escalation rate: what fraction of open alerts were escalated.

    An alert is considered "escalated" if its status is 'escalated'.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_open_or_escalated: int
            - escalated_count: int
            - escalation_rate_pct: float
    """
    total = db.query(Alert).filter(
        Alert.status.in_(["open", "escalated", "under_review"])
    ).count()

    escalated = db.query(Alert).filter(Alert.status == "escalated").count()

    rate = round(escalated / total * 100, 2) if total > 0 else 0.0

    return {
        "total_open_or_escalated": total,
        "escalated_count": escalated,
        "escalation_rate_pct": rate,
    }


# ---------------------------------------------------------------------------
# false_positive_rate
# ---------------------------------------------------------------------------

def false_positive_rate(db: Session) -> Dict[str, Any]:
    """
    Compute the false positive rate: fraction of resolved alerts that were
    marked as false_positive.

    A high false positive rate indicates over-sensitive rules that need tuning.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - total_closed: int
            - false_positive_count: int
            - false_positive_rate_pct: float
            - confirmed_positive_count: int
    """
    closed = db.query(Alert).filter(
        Alert.status.in_(["closed", "false_positive"])
    ).count()

    false_pos = db.query(Alert).filter(Alert.status == "false_positive").count()
    confirmed = closed - false_pos

    rate = round(false_pos / closed * 100, 2) if closed > 0 else 0.0

    return {
        "total_closed": closed,
        "false_positive_count": false_pos,
        "false_positive_rate_pct": rate,
        "confirmed_positive_count": confirmed,
    }


# ---------------------------------------------------------------------------
# mean_time_to_resolve
# ---------------------------------------------------------------------------

def mean_time_to_resolve(db: Session) -> Dict[str, Any]:
    """
    Compute mean, median, min, and max time to resolve (close) an alert,
    in hours.

    Only considers alerts that have both created_at and closed_at populated.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - sample_size: int
            - mean_hours: float
            - median_hours: float
            - min_hours: float
            - max_hours: float
    """
    resolved = db.query(Alert).filter(
        Alert.closed_at.isnot(None),
        Alert.created_at.isnot(None),
    ).all()

    if not resolved:
        return {
            "sample_size": 0,
            "mean_hours": 0.0,
            "median_hours": 0.0,
            "min_hours": 0.0,
            "max_hours": 0.0,
        }

    durations = []
    for alert in resolved:
        try:
            diff = alert.closed_at - alert.created_at
            hours = diff.total_seconds() / 3600
            durations.append(hours)
        except Exception:
            continue

    if not durations:
        return {"sample_size": 0, "mean_hours": 0.0, "median_hours": 0.0,
                "min_hours": 0.0, "max_hours": 0.0}

    durations.sort()
    n = len(durations)
    mean_h = round(sum(durations) / n, 2)
    if n % 2 == 0:
        median_h = round((durations[n // 2 - 1] + durations[n // 2]) / 2, 2)
    else:
        median_h = round(durations[n // 2], 2)

    return {
        "sample_size": n,
        "mean_hours": mean_h,
        "median_hours": median_h,
        "min_hours": round(min(durations), 2),
        "max_hours": round(max(durations), 2),
    }


# ---------------------------------------------------------------------------
# alert_severity_trend
# ---------------------------------------------------------------------------

def alert_severity_trend(db: Session, days: int = 30) -> List[Dict[str, Any]]:
    """
    Return daily breakdown of alert creation by severity over the past N days.

    Useful for identifying whether the mix of alert severities is shifting
    (e.g., more criticals being generated recently).

    Args:
        db:   SQLAlchemy session.
        days: Lookback window in days.

    Returns:
        List of daily dicts:
            [{date, critical, high, medium, low, total}]
        Sorted by date ascending.
    """
    cutoff = _since(days)
    alerts = (
        db.query(Alert)
        .filter(Alert.created_at >= cutoff)
        .all()
    )

    daily: Dict[str, Dict[str, int]] = {}
    for alert in alerts:
        day = alert.created_at.strftime("%Y-%m-%d") if alert.created_at else "unknown"
        if day not in daily:
            daily[day] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
        sev = alert.severity or "low"
        daily[day][sev] = daily[day].get(sev, 0) + 1
        daily[day]["total"] += 1

    return [
        {"date": d, **v}
        for d, v in sorted(daily.items())
    ]


# ---------------------------------------------------------------------------
# top_alerted_customers
# ---------------------------------------------------------------------------

def top_alerted_customers(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return the top N customers by total alert count.

    Args:
        db:    SQLAlchemy session.
        limit: Maximum number of customers to return.

    Returns:
        List of dicts:
            [{customer_id, customer_name, risk_level, pep_status,
              total_alerts, open_alerts, critical_alerts}]
        Sorted by total_alerts descending.
    """
    # Count alerts per customer
    customer_alert_counts: Dict[int, int] = {}
    alerts = db.query(Alert).all()

    for alert in alerts:
        cid = alert.customer_id
        customer_alert_counts[cid] = customer_alert_counts.get(cid, 0) + 1

    # Sort by count descending, take top N
    top_ids = sorted(customer_alert_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    result = []
    for cid, total in top_ids:
        customer = db.query(Customer).filter(Customer.id == cid).first()
        if not customer:
            continue

        cust_alerts = [a for a in alerts if a.customer_id == cid]
        open_count = sum(1 for a in cust_alerts if a.status == "open")
        critical_count = sum(1 for a in cust_alerts if a.severity == "critical")

        result.append({
            "customer_id": cid,
            "customer_name": customer.full_name,
            "risk_level": customer.risk_level,
            "pep_status": customer.pep_status,
            "total_alerts": total,
            "open_alerts": open_count,
            "critical_alerts": critical_count,
        })

    return result


# ---------------------------------------------------------------------------
# alert_resolution_breakdown
# ---------------------------------------------------------------------------

def alert_resolution_breakdown(db: Session) -> Dict[str, Any]:
    """
    Return breakdown of alert final statuses and overall resolution statistics.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict containing:
            - status_counts: Dict[str, int]  — counts per status
            - status_pct: Dict[str, float]   — percentage per status
            - total: int
            - resolved_pct: float            — closed + false_positive combined
    """
    alerts = db.query(Alert).all()
    total = len(alerts)

    status_counts: Dict[str, int] = {}
    for alert in alerts:
        s = alert.status or "unknown"
        status_counts[s] = status_counts.get(s, 0) + 1

    status_pct: Dict[str, float] = {}
    for s, cnt in status_counts.items():
        status_pct[s] = round(cnt / total * 100, 2) if total > 0 else 0.0

    resolved = status_counts.get("closed", 0) + status_counts.get("false_positive", 0)
    resolved_pct = round(resolved / total * 100, 2) if total > 0 else 0.0

    return {
        "status_counts": status_counts,
        "status_pct": status_pct,
        "total": total,
        "resolved_pct": resolved_pct,
    }
