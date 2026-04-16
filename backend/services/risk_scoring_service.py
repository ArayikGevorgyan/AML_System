"""
Customer Risk Scoring Service
==============================
Calculates a composite risk score (0-100) for each customer based on:
  - Base risk level from profile (PEP, sanctions flag, nationality)
  - Transaction behaviour (volume, frequency, flagged ratio)
  - Alert history (count, severity weights)
  - Country risk (FATF/OFAC high-risk jurisdictions)

Score bands:
  0-24   → LOW
  25-49  → MEDIUM
  50-74  → HIGH
  75-100 → CRITICAL
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.customer import Customer
from models.transaction import Transaction
from models.alert import Alert
from config import settings


# Severity weights for alert scoring
SEVERITY_WEIGHTS = {
    "low": 2,
    "medium": 5,
    "high": 10,
    "critical": 20,
}

# Country risk tiers
HIGH_RISK_COUNTRIES   = set(settings.HIGH_RISK_COUNTRIES)
MEDIUM_RISK_COUNTRIES = {"RU", "BY", "CN", "NG", "PK", "AF", "MM", "LA", "KH", "ZW"}


def _base_profile_score(customer: Customer) -> float:
    """Score from static customer profile attributes."""
    score = 0.0

    # Risk level set by analyst
    risk_map = {"low": 0, "medium": 15, "high": 30, "critical": 50}
    score += risk_map.get(customer.risk_level, 0)

    # PEP status adds significant risk
    if customer.pep_status:
        score += 20

    # Sanctions flag — maximum contribution
    if customer.sanctions_flag:
        score += 30

    # Country risk
    country = (customer.nationality or customer.country or "").upper()
    if country in HIGH_RISK_COUNTRIES:
        score += 20
    elif country in MEDIUM_RISK_COUNTRIES:
        score += 10

    return min(score, 60)  # cap profile contribution


def _transaction_behaviour_score(customer_id: int, db: Session) -> float:
    """Score from transaction patterns in the last 90 days."""
    since = datetime.now(timezone.utc) - timedelta(days=90)

    txns = db.query(Transaction).filter(
        Transaction.from_customer_id == customer_id,
        Transaction.created_at >= since,
    ).all()

    if not txns:
        return 0.0

    total      = len(txns)
    flagged    = sum(1 for t in txns if t.flagged)
    total_amt  = sum(t.amount for t in txns)
    score      = 0.0

    # Flagged transaction ratio
    flagged_ratio = flagged / total
    score += flagged_ratio * 25

    # High volume in 90 days
    if total_amt > 500_000:
        score += 15
    elif total_amt > 100_000:
        score += 8
    elif total_amt > 50_000:
        score += 4

    # High frequency
    if total > 50:
        score += 10
    elif total > 20:
        score += 5

    return min(score, 30)


def _alert_history_score(customer_id: int, db: Session) -> float:
    """Score from alert history in the last 180 days."""
    since = datetime.now(timezone.utc) - timedelta(days=180)

    alerts = db.query(Alert).filter(
        Alert.customer_id == customer_id,
        Alert.created_at >= since,
        Alert.status != "false_positive",
    ).all()

    if not alerts:
        return 0.0

    weighted = sum(SEVERITY_WEIGHTS.get(a.severity, 0) for a in alerts)
    # Normalize: 50+ weighted points = max contribution of 25
    score = min((weighted / 50) * 25, 25)

    # Bonus if any critical alert exists
    if any(a.severity == "critical" for a in alerts):
        score = min(score + 10, 25)

    return score


def compute_customer_risk_score(customer: Customer, db: Session) -> dict:
    """
    Compute full risk score for a customer.
    Returns dict with score, band, and breakdown.
    """
    profile_score  = _base_profile_score(customer)
    txn_score      = _transaction_behaviour_score(customer.id, db)
    alert_score    = _alert_history_score(customer.id, db)

    total = min(round(profile_score + txn_score + alert_score, 1), 100)

    if total >= 75:
        band = "critical"
    elif total >= 50:
        band = "high"
    elif total >= 25:
        band = "medium"
    else:
        band = "low"

    return {
        "customer_id":     customer.id,
        "customer_number": customer.customer_number,
        "full_name":       customer.full_name,
        "risk_score":      total,
        "risk_band":       band,
        "breakdown": {
            "profile_score":     round(profile_score, 1),
            "transaction_score": round(txn_score, 1),
            "alert_score":       round(alert_score, 1),
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_all_customer_scores(db: Session) -> list:
    """Compute risk scores for all active customers."""
    customers = db.query(Customer).all()
    results = []
    for c in customers:
        try:
            results.append(compute_customer_risk_score(c, db))
        except Exception:
            pass
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results
