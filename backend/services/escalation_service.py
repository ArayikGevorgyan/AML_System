"""
Alert Escalation Engine
========================
Automatically escalates alerts based on configurable rules:

Rule 1 — Time-based escalation:
    Alerts that remain OPEN for more than OPEN_HOURS_THRESHOLD hours
    are escalated to severity=CRITICAL and status=escalated.

Rule 2 — Repeat offender escalation:
    If the same customer triggers REPEAT_ALERT_THRESHOLD or more
    alerts within REPEAT_WINDOW_DAYS days, all their open alerts
    are escalated.

Rule 3 — Severity upgrade:
    HIGH severity alerts open longer than HIGH_UPGRADE_HOURS are
    promoted to CRITICAL.

Run via: python scripts/run_escalation.py
Or called from a cron job / background task.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.alert import Alert
from models.customer import Customer
from database import SessionLocal


# ── Thresholds ──────────────────────────────────────────────────────────────
OPEN_HOURS_THRESHOLD   = 48    # escalate open alerts after 48 hours
HIGH_UPGRADE_HOURS     = 24    # upgrade HIGH → CRITICAL after 24 hours
REPEAT_ALERT_THRESHOLD = 3     # number of alerts to trigger repeat-offender rule
REPEAT_WINDOW_DAYS     = 7     # look-back window for repeat offender check


def _now() -> datetime:
    return datetime.now(timezone.utc)


def escalate_stale_open_alerts(db: Session) -> list:
    """
    Rule 1: Escalate alerts that have been OPEN for too long.
    Returns list of escalated alert IDs.
    """
    cutoff = _now() - timedelta(hours=OPEN_HOURS_THRESHOLD)
    stale_alerts = db.query(Alert).filter(
        Alert.status == "open",
        Alert.created_at <= cutoff,
        Alert.severity != "critical",
    ).all()

    escalated_ids = []
    for alert in stale_alerts:
        alert.status   = "escalated"
        alert.severity = "critical"
        escalated_ids.append(alert.id)

    if escalated_ids:
        db.commit()

    return escalated_ids


def escalate_high_severity_alerts(db: Session) -> list:
    """
    Rule 3: Upgrade HIGH alerts that are still open after HIGH_UPGRADE_HOURS.
    Returns list of upgraded alert IDs.
    """
    cutoff = _now() - timedelta(hours=HIGH_UPGRADE_HOURS)
    high_alerts = db.query(Alert).filter(
        Alert.status.in_(["open", "under_review"]),
        Alert.severity == "high",
        Alert.created_at <= cutoff,
    ).all()

    upgraded_ids = []
    for alert in high_alerts:
        alert.severity = "critical"
        upgraded_ids.append(alert.id)

    if upgraded_ids:
        db.commit()

    return upgraded_ids


def escalate_repeat_offenders(db: Session) -> list:
    """
    Rule 2: Escalate all open alerts for customers who triggered
    REPEAT_ALERT_THRESHOLD+ alerts within REPEAT_WINDOW_DAYS days.
    Returns list of escalated alert IDs.
    """
    since = _now() - timedelta(days=REPEAT_WINDOW_DAYS)

    # Find customers with too many recent alerts
    repeat_customers = (
        db.query(Alert.customer_id, func.count(Alert.id).label("cnt"))
        .filter(
            Alert.created_at >= since,
            Alert.status != "false_positive",
        )
        .group_by(Alert.customer_id)
        .having(func.count(Alert.id) >= REPEAT_ALERT_THRESHOLD)
        .all()
    )

    repeat_customer_ids = [r.customer_id for r in repeat_customers]
    if not repeat_customer_ids:
        return []

    open_alerts = db.query(Alert).filter(
        Alert.customer_id.in_(repeat_customer_ids),
        Alert.status == "open",
    ).all()

    escalated_ids = []
    for alert in open_alerts:
        alert.status = "escalated"
        escalated_ids.append(alert.id)

    if escalated_ids:
        db.commit()

    return escalated_ids


def run_all_escalation_rules(db: Session) -> dict:
    """
    Run all escalation rules and return a summary report.
    """
    stale    = escalate_stale_open_alerts(db)
    upgraded = escalate_high_severity_alerts(db)
    repeat   = escalate_repeat_offenders(db)

    summary = {
        "run_at":                    _now().isoformat(),
        "stale_alerts_escalated":    len(stale),
        "high_alerts_upgraded":      len(upgraded),
        "repeat_offender_escalated": len(repeat),
        "total_actions":             len(stale) + len(upgraded) + len(repeat),
        "escalated_alert_ids":       stale + upgraded + repeat,
    }
    return summary


def get_escalation_candidates(db: Session) -> dict:
    """
    Preview which alerts would be escalated without actually escalating.
    Useful for the API endpoint to show pending escalations.
    """
    now = _now()
    stale_cutoff   = now - timedelta(hours=OPEN_HOURS_THRESHOLD)
    upgrade_cutoff = now - timedelta(hours=HIGH_UPGRADE_HOURS)
    since          = now - timedelta(days=REPEAT_WINDOW_DAYS)

    stale_count = db.query(Alert).filter(
        Alert.status == "open",
        Alert.created_at <= stale_cutoff,
        Alert.severity != "critical",
    ).count()

    upgrade_count = db.query(Alert).filter(
        Alert.status.in_(["open", "under_review"]),
        Alert.severity == "high",
        Alert.created_at <= upgrade_cutoff,
    ).count()

    repeat_customers = (
        db.query(Alert.customer_id, func.count(Alert.id).label("cnt"))
        .filter(Alert.created_at >= since, Alert.status != "false_positive")
        .group_by(Alert.customer_id)
        .having(func.count(Alert.id) >= REPEAT_ALERT_THRESHOLD)
        .count()
    )

    return {
        "stale_open_alerts":       stale_count,
        "high_severity_upgrades":  upgrade_count,
        "repeat_offender_customers": repeat_customers,
        "thresholds": {
            "open_hours":           OPEN_HOURS_THRESHOLD,
            "high_upgrade_hours":   HIGH_UPGRADE_HOURS,
            "repeat_alert_count":   REPEAT_ALERT_THRESHOLD,
            "repeat_window_days":   REPEAT_WINDOW_DAYS,
        },
    }
