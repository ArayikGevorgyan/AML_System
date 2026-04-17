"""
Behavioral Analysis Module
============================
Transaction-level behavioral analysis functions for detecting anomalous
customer activity patterns associated with money laundering.

Functions operate on lists of transaction objects or fetch from the DB.
All functions return plain dicts/lists for JSON serialisation.

Usage:
    from database import SessionLocal
    from analysis.behavioral_analysis import behavioral_risk_score, detect_structuring

    db = SessionLocal()
    score = behavioral_risk_score(db, customer_id=42)
"""

import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from models.transaction import Transaction
from models.customer import Customer
from models.alert import Alert


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# detect_unusual_hours
# ---------------------------------------------------------------------------

def detect_unusual_hours(transactions: List[Any]) -> Dict[str, Any]:
    """
    Detect transactions occurring outside normal business hours (08:00–20:00).

    A high fraction of off-hours transactions may indicate automated
    money movement or deliberate obfuscation.

    Args:
        transactions: List of Transaction ORM objects.

    Returns:
        Dict containing:
            - total_transactions: int
            - off_hours_count: int
            - off_hours_pct: float
            - off_hours_by_hour: Dict[int, int]  — hour → count
            - most_active_off_hour: int or None
    """
    if not transactions:
        return {
            "total_transactions": 0, "off_hours_count": 0,
            "off_hours_pct": 0.0, "off_hours_by_hour": {},
            "most_active_off_hour": None,
        }

    off_hours: List[int] = []
    off_by_hour: Dict[int, int] = {}

    for t in transactions:
        if t.created_at is None:
            continue
        hour = t.created_at.hour
        if hour < 8 or hour >= 20:
            off_hours.append(hour)
            off_by_hour[hour] = off_by_hour.get(hour, 0) + 1

    total = len(transactions)
    off_count = len(off_hours)
    off_pct = round(off_count / total * 100, 2) if total > 0 else 0.0
    most_active = max(off_by_hour, key=off_by_hour.get) if off_by_hour else None

    return {
        "total_transactions": total,
        "off_hours_count": off_count,
        "off_hours_pct": off_pct,
        "off_hours_by_hour": off_by_hour,
        "most_active_off_hour": most_active,
    }


# ---------------------------------------------------------------------------
# detect_amount_anomaly
# ---------------------------------------------------------------------------

def detect_amount_anomaly(
    transactions: List[Any],
    std_multiplier: float = 2.5,
) -> Dict[str, Any]:
    """
    Detect transactions with amounts that are statistical outliers relative
    to the customer's transaction history.

    Uses mean ± std_multiplier * std_dev as the normal range.

    Args:
        transactions:   List of Transaction ORM objects.
        std_multiplier: Number of standard deviations to use as threshold.

    Returns:
        Dict containing:
            - mean_amount: float
            - std_dev: float
            - threshold_upper: float
            - outliers: List[{id, amount, reference, deviation_factor}]
            - outlier_count: int
    """
    if len(transactions) < 3:
        return {
            "mean_amount": 0.0, "std_dev": 0.0, "threshold_upper": 0.0,
            "outliers": [], "outlier_count": 0,
            "note": "Insufficient data (need >= 3 transactions)",
        }

    amounts = [t.amount for t in transactions if t.amount is not None]
    if len(amounts) < 3:
        return {"mean_amount": 0.0, "std_dev": 0.0, "outliers": [], "outlier_count": 0}

    mean = statistics.mean(amounts)
    std = statistics.stdev(amounts)
    upper = mean + std_multiplier * std

    outliers = []
    for t in transactions:
        if t.amount and t.amount > upper:
            dev = round((t.amount - mean) / std, 2) if std > 0 else 0.0
            outliers.append({
                "id": t.id,
                "amount": t.amount,
                "reference": t.reference,
                "deviation_factor": dev,
            })

    return {
        "mean_amount": round(mean, 2),
        "std_dev": round(std, 2),
        "threshold_upper": round(upper, 2),
        "outliers": sorted(outliers, key=lambda x: x["deviation_factor"], reverse=True),
        "outlier_count": len(outliers),
    }


# ---------------------------------------------------------------------------
# detect_velocity_spike
# ---------------------------------------------------------------------------

def detect_velocity_spike(
    transactions: List[Any],
    window_days: int = 7,
) -> Dict[str, Any]:
    """
    Detect spikes in transaction velocity — a sudden increase in transaction
    count or volume over a short window compared to the prior period.

    Args:
        transactions: List of Transaction ORM objects (sorted by created_at).
        window_days:  Size of the comparison window in days.

    Returns:
        Dict containing:
            - recent_count: int
            - prior_count: int
            - count_change_pct: float
            - recent_volume: float
            - prior_volume: float
            - volume_change_pct: float
            - is_spike: bool           — True if either metric increased >200%
    """
    if not transactions:
        return {
            "recent_count": 0, "prior_count": 0, "count_change_pct": 0.0,
            "recent_volume": 0.0, "prior_volume": 0.0, "volume_change_pct": 0.0,
            "is_spike": False,
        }

    now = _now()
    recent_cutoff = now - timedelta(days=window_days)
    prior_cutoff = now - timedelta(days=window_days * 2)

    recent = [t for t in transactions if t.created_at and t.created_at >= recent_cutoff]
    prior = [t for t in transactions
             if t.created_at and prior_cutoff <= t.created_at < recent_cutoff]

    recent_vol = sum(t.amount for t in recent if t.amount)
    prior_vol = sum(t.amount for t in prior if t.amount)

    def pct_change(new_val: float, old_val: float) -> float:
        if old_val == 0:
            return 100.0 if new_val > 0 else 0.0
        return round((new_val - old_val) / old_val * 100, 2)

    count_change = pct_change(len(recent), len(prior))
    volume_change = pct_change(recent_vol, prior_vol)
    is_spike = count_change > 200 or volume_change > 200

    return {
        "recent_count": len(recent),
        "prior_count": len(prior),
        "count_change_pct": count_change,
        "recent_volume": round(recent_vol, 2),
        "prior_volume": round(prior_vol, 2),
        "volume_change_pct": volume_change,
        "is_spike": is_spike,
    }


# ---------------------------------------------------------------------------
# customer_behavior_profile
# ---------------------------------------------------------------------------

def customer_behavior_profile(db: Session, customer_id: int) -> Dict[str, Any]:
    """
    Build a comprehensive behavioral profile for a customer by analysing
    all their transaction history.

    Args:
        db:          SQLAlchemy session.
        customer_id: ID of the customer to profile.

    Returns:
        Dict with behavioral metrics and risk indicators.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {"error": f"Customer {customer_id} not found"}

    txns = db.query(Transaction).filter(
        Transaction.from_customer_id == customer_id
    ).order_by(Transaction.created_at).all()

    if not txns:
        return {
            "customer_id": customer_id,
            "full_name": customer.full_name,
            "risk_level": customer.risk_level,
            "total_transactions": 0,
            "total_volume": 0.0,
            "behavioral_flags": [],
        }

    amounts = [t.amount for t in txns if t.amount]
    total_volume = sum(amounts)
    mean_amount = statistics.mean(amounts) if amounts else 0.0
    std_amount = statistics.stdev(amounts) if len(amounts) >= 2 else 0.0

    # Hour distribution
    hour_counts: Dict[int, int] = {}
    for t in txns:
        if t.created_at:
            h = t.created_at.hour
            hour_counts[h] = hour_counts.get(h, 0) + 1

    # Country diversity
    dest_countries = {t.destination_country for t in txns if t.destination_country}
    orig_countries = {t.originating_country for t in txns if t.originating_country}

    # Type distribution
    type_dist: Dict[str, int] = {}
    for t in txns:
        tt = t.transaction_type or "unknown"
        type_dist[tt] = type_dist.get(tt, 0) + 1

    # Behavioral flags
    flags = []
    off_hours = detect_unusual_hours(txns)
    if off_hours["off_hours_pct"] > 30:
        flags.append("high_off_hours_activity")

    structuring = detect_structuring(txns, threshold=10000.0)
    if structuring["structuring_score"] > 50:
        flags.append("structuring_pattern_detected")

    round_amounts = detect_round_amounts(txns)
    if round_amounts["round_pct"] > 40:
        flags.append("excessive_round_amounts")

    if len(dest_countries) > 5:
        flags.append("high_country_diversity")

    alerts = db.query(Alert).filter(
        Alert.customer_id == customer_id,
        Alert.status != "false_positive",
    ).count()

    return {
        "customer_id": customer_id,
        "full_name": customer.full_name,
        "risk_level": customer.risk_level,
        "pep_status": customer.pep_status,
        "sanctions_flag": customer.sanctions_flag,
        "total_transactions": len(txns),
        "total_volume": round(total_volume, 2),
        "mean_amount": round(mean_amount, 2),
        "std_amount": round(std_amount, 2),
        "destination_countries": list(dest_countries),
        "originating_countries": list(orig_countries),
        "transaction_type_dist": type_dist,
        "hour_distribution": hour_counts,
        "off_hours_pct": off_hours["off_hours_pct"],
        "alert_count": alerts,
        "behavioral_flags": flags,
    }


# ---------------------------------------------------------------------------
# detect_structuring
# ---------------------------------------------------------------------------

def detect_structuring(
    transactions: List[Any],
    threshold: float = 10000.0,
) -> Dict[str, Any]:
    """
    Detect structuring (smurfing): multiple transactions just below a reporting
    threshold that together exceed it, suggesting deliberate avoidance.

    Args:
        transactions: List of Transaction ORM objects.
        threshold:    The reporting threshold amount (default $10,000).

    Returns:
        Dict containing:
            - threshold: float
            - structuring_candidates: List[{date, count, total_amount, transactions}]
            - structuring_score: float (0–100, higher = more suspicious)
            - total_suspicious_amount: float
    """
    if not transactions:
        return {
            "threshold": threshold,
            "structuring_candidates": [],
            "structuring_score": 0.0,
            "total_suspicious_amount": 0.0,
        }

    band_low = threshold * 0.7
    band_high = threshold * 0.98

    candidates_by_day: Dict[str, List] = {}
    for t in transactions:
        if t.amount and band_low <= t.amount <= band_high:
            if t.created_at:
                day = t.created_at.strftime("%Y-%m-%d")
            else:
                day = "unknown"
            if day not in candidates_by_day:
                candidates_by_day[day] = []
            candidates_by_day[day].append(t)

    structuring_candidates = []
    total_suspicious = 0.0

    for day, day_txns in candidates_by_day.items():
        if len(day_txns) >= 2:
            day_total = sum(t.amount for t in day_txns)
            if day_total >= threshold:
                structuring_candidates.append({
                    "date": day,
                    "count": len(day_txns),
                    "total_amount": round(day_total, 2),
                    "transaction_ids": [t.id for t in day_txns],
                })
                total_suspicious += day_total

    # Score: 0–100 based on number of structuring days and amount
    score = min(len(structuring_candidates) * 20 + (total_suspicious / threshold) * 5, 100.0)

    return {
        "threshold": threshold,
        "structuring_candidates": sorted(
            structuring_candidates, key=lambda x: x["total_amount"], reverse=True
        ),
        "structuring_score": round(score, 2),
        "total_suspicious_amount": round(total_suspicious, 2),
    }


# ---------------------------------------------------------------------------
# detect_round_amounts
# ---------------------------------------------------------------------------

def detect_round_amounts(transactions: List[Any]) -> Dict[str, Any]:
    """
    Detect excessive use of round-number transaction amounts.

    Round numbers (e.g. $5,000, $10,000) can indicate pre-planned
    illicit transfers rather than organic commercial activity.

    Args:
        transactions: List of Transaction ORM objects.

    Returns:
        Dict containing:
            - total: int
            - round_count: int   — transactions with amounts divisible by 1000
            - round_pct: float
            - near_round_count: int — amounts within 1% of a round 1000 multiple
            - example_amounts: List[float]
    """
    if not transactions:
        return {"total": 0, "round_count": 0, "round_pct": 0.0,
                "near_round_count": 0, "example_amounts": []}

    amounts = [t.amount for t in transactions if t.amount is not None and t.amount > 0]
    total = len(amounts)

    round_amounts = [a for a in amounts if a % 1000 == 0]
    near_round = [a for a in amounts if a not in round_amounts
                  and any(abs(a - r * 1000) / (r * 1000) < 0.01
                          for r in range(1, 1000) if r * 1000 > 0)]

    round_pct = round(len(round_amounts) / total * 100, 2) if total > 0 else 0.0
    examples = sorted(set(round_amounts))[:10]

    return {
        "total": total,
        "round_count": len(round_amounts),
        "round_pct": round_pct,
        "near_round_count": len(near_round),
        "example_amounts": examples,
    }


# ---------------------------------------------------------------------------
# behavioral_risk_score
# ---------------------------------------------------------------------------

def behavioral_risk_score(db: Session, customer_id: int) -> Dict[str, Any]:
    """
    Compute a composite behavioral risk score (0–100) for a customer by
    combining results from all behavioral analysis functions.

    Score contributions:
      - Off-hours activity pct   → up to 15 pts
      - Structuring score        → up to 25 pts (scaled)
      - Round amount pct         → up to 10 pts
      - Velocity spike           → up to 20 pts
      - Amount anomaly count     → up to 15 pts
      - Country diversity        → up to 15 pts

    Args:
        db:          SQLAlchemy session.
        customer_id: ID of the customer to score.

    Returns:
        Dict containing:
            - customer_id: int
            - behavioral_score: float (0–100)
            - risk_band: str
            - contributing_factors: Dict[str, float]
    """
    txns = db.query(Transaction).filter(
        Transaction.from_customer_id == customer_id
    ).order_by(Transaction.created_at).all()

    if not txns:
        return {
            "customer_id": customer_id,
            "behavioral_score": 0.0,
            "risk_band": "low",
            "contributing_factors": {},
            "note": "No transaction history",
        }

    off_hours = detect_unusual_hours(txns)
    off_score = min(off_hours["off_hours_pct"] * 0.5, 15.0)

    structuring = detect_structuring(txns, threshold=10000.0)
    struct_score = min(structuring["structuring_score"] * 0.25, 25.0)

    round_amts = detect_round_amounts(txns)
    round_score = min(round_amts["round_pct"] * 0.2, 10.0)

    velocity = detect_velocity_spike(txns, window_days=7)
    vel_score = 0.0
    if velocity["is_spike"]:
        vel_score = 20.0
    elif velocity["count_change_pct"] > 100:
        vel_score = 12.0
    elif velocity["count_change_pct"] > 50:
        vel_score = 7.0

    anomaly = detect_amount_anomaly(txns, std_multiplier=2.5)
    anom_score = min(anomaly["outlier_count"] * 3, 15.0)

    dest_countries = {t.destination_country for t in txns if t.destination_country}
    country_score = min(len(dest_countries) * 2, 15.0)

    total = round(off_score + struct_score + round_score + vel_score + anom_score + country_score, 2)
    total = min(total, 100.0)

    if total >= 75:
        band = "critical"
    elif total >= 50:
        band = "high"
    elif total >= 25:
        band = "medium"
    else:
        band = "low"

    return {
        "customer_id": customer_id,
        "behavioral_score": total,
        "risk_band": band,
        "contributing_factors": {
            "off_hours_activity": round(off_score, 2),
            "structuring_pattern": round(struct_score, 2),
            "round_amounts": round(round_score, 2),
            "velocity_spike": round(vel_score, 2),
            "amount_anomalies": round(anom_score, 2),
            "country_diversity": round(country_score, 2),
        },
    }
