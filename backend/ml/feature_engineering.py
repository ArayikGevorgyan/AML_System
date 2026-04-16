"""
Feature Engineering Pipeline
================================
Centralised feature extraction and transformation for all ML models
in the AML system. Separating feature engineering from model code
means features can be reused across different models and tested
independently.

Features are organised into groups:
  - Transaction features  (from raw transaction records)
  - Customer profile features (from KYC/onboarding data)
  - Behavioural features  (derived from transaction history patterns)
  - Network features      (relationships between accounts)
  - Temporal features     (time-based patterns)

Usage:
    from analysis.feature_engineering import FeatureEngineer
    engineer = FeatureEngineer()
    features = engineer.build_customer_features(customer, transactions, alerts)
"""

import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple


# ── Constants ──────────────────────────────────────────────────────────────

HIGH_RISK_COUNTRIES = {
    "IR", "KP", "SY", "CU", "RU", "BY", "MM", "YE",
    "LY", "SO", "SD", "ZW", "CD", "CF", "ML", "IQ", "AF",
}

MEDIUM_RISK_COUNTRIES = {
    "NG", "PK", "UA", "VE", "LB", "TN", "KZ", "UZ", "TM",
}

TRANSACTION_TYPE_RISK = {
    "cash":       5,
    "wire":       4,
    "transfer":   3,
    "withdrawal": 3,
    "payment":    2,
    "deposit":    1,
}

CHANNEL_RISK = {
    "atm":    4,
    "branch": 3,
    "online": 2,
    "mobile": 1,
}


# ── Individual Feature Extractors ──────────────────────────────────────────

def extract_amount_features(transactions: list) -> Dict[str, float]:
    """
    Statistical features derived from transaction amounts.
    Captures distribution shape, outliers, and structuring signals.
    """
    if not transactions:
        return {
            "amount_mean":    0.0,
            "amount_std":     0.0,
            "amount_max":     0.0,
            "amount_min":     0.0,
            "amount_median":  0.0,
            "amount_skew":    0.0,
            "large_txn_count": 0.0,
            "structuring_count": 0.0,
            "round_amount_count": 0.0,
        }

    amounts = [float(t.amount or 0) for t in transactions]
    n = len(amounts)

    mean   = statistics.mean(amounts)
    std    = statistics.stdev(amounts) if n > 1 else 0.0
    median = statistics.median(amounts)
    max_a  = max(amounts)
    min_a  = min(amounts)

    # Pearson skewness (normalised)
    skew = (3 * (mean - median) / std) if std > 0 else 0.0

    # Structuring: amounts in 80-99.9% of $10k threshold
    structuring = sum(1 for a in amounts if 8_000 <= a < 10_000)

    # Round amounts (multiples of 1000)
    round_count = sum(1 for a in amounts if a >= 1000 and a % 1000 == 0 and a == int(a))

    # Large transactions (>$10k)
    large = sum(1 for a in amounts if a >= 10_000)

    return {
        "amount_mean":       round(mean, 2),
        "amount_std":        round(std, 2),
        "amount_max":        round(max_a, 2),
        "amount_min":        round(min_a, 2),
        "amount_median":     round(median, 2),
        "amount_skew":       round(skew, 4),
        "large_txn_count":   float(large),
        "structuring_count": float(structuring),
        "round_amount_count": float(round_count),
    }


def extract_velocity_features(
    transactions: list,
    windows: Optional[List[int]] = None,
) -> Dict[str, float]:
    """
    Transaction velocity at multiple time windows (1h, 24h, 7d, 30d).
    High velocity relative to normal = suspicious.
    """
    if windows is None:
        windows = [1, 24, 168, 720]  # hours

    now = datetime.now(timezone.utc)
    result = {}

    for hours in windows:
        cutoff = now - timedelta(hours=hours)
        window_txns = []
        for t in transactions:
            created = t.created_at
            if created is None:
                continue
            if hasattr(created, 'tzinfo') and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                window_txns.append(t)

        label = f"{hours}h" if hours < 168 else f"{hours // 24}d"
        result[f"txn_count_{label}"]   = float(len(window_txns))
        result[f"txn_volume_{label}"]  = round(sum(float(t.amount or 0) for t in window_txns), 2)

    return result


def extract_temporal_features(transactions: list) -> Dict[str, float]:
    """
    Time-of-day and day-of-week patterns.
    Off-hours activity (night, weekends) correlates with automated fraud.
    """
    if not transactions:
        return {
            "night_txn_ratio":    0.0,
            "weekend_txn_ratio":  0.0,
            "avg_hour_of_day":    12.0,
            "business_hours_ratio": 0.0,
        }

    hours   = []
    weekday = []

    for t in transactions:
        created = t.created_at
        if created is None:
            continue
        if hasattr(created, 'tzinfo') and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        hours.append(created.hour)
        weekday.append(created.weekday())

    n = len(hours)
    if n == 0:
        return {"night_txn_ratio": 0.0, "weekend_txn_ratio": 0.0,
                "avg_hour_of_day": 12.0, "business_hours_ratio": 0.0}

    night_count    = sum(1 for h in hours if h < 6 or h >= 22)
    weekend_count  = sum(1 for d in weekday if d >= 5)
    business_count = sum(1 for h in hours if 9 <= h <= 17)

    return {
        "night_txn_ratio":     round(night_count / n, 3),
        "weekend_txn_ratio":   round(weekend_count / n, 3),
        "avg_hour_of_day":     round(statistics.mean(hours), 2),
        "business_hours_ratio": round(business_count / n, 3),
    }


def extract_geographic_features(transactions: list) -> Dict[str, float]:
    """
    Geographic diversity and risk features from transaction countries.
    Many unique countries or high-risk country involvement raises risk.
    """
    if not transactions:
        return {
            "unique_originating_countries": 0.0,
            "unique_destination_countries": 0.0,
            "high_risk_country_txns":       0.0,
            "international_ratio":          0.0,
        }

    orig_countries = set()
    dest_countries = set()
    intl_count     = 0
    high_risk_count = 0

    for t in transactions:
        orig = (getattr(t, 'originating_country', None) or '').upper()
        dest = (getattr(t, 'destination_country', None) or '').upper()
        is_intl = getattr(t, 'is_international', False)

        if orig:
            orig_countries.add(orig)
        if dest:
            dest_countries.add(dest)
        if is_intl:
            intl_count += 1
        if orig in HIGH_RISK_COUNTRIES or dest in HIGH_RISK_COUNTRIES:
            high_risk_count += 1

    n = len(transactions)
    return {
        "unique_originating_countries": float(len(orig_countries)),
        "unique_destination_countries": float(len(dest_countries)),
        "high_risk_country_txns":       float(high_risk_count),
        "high_risk_country_ratio":      round(high_risk_count / n, 3),
        "international_ratio":          round(intl_count / n, 3),
    }


def extract_alert_features(alerts: list) -> Dict[str, float]:
    """
    Features derived from the customer's alert history.
    Alert count, recency, and severity distribution.
    """
    if not alerts:
        return {
            "alert_count_total":    0.0,
            "alert_count_90d":      0.0,
            "critical_alert_count": 0.0,
            "high_alert_count":     0.0,
            "open_alert_count":     0.0,
            "alert_severity_score": 0.0,
            "days_since_last_alert": 999.0,
        }

    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)

    severity_weights = {"low": 1, "medium": 3, "high": 7, "critical": 15}

    recent_alerts = []
    for a in alerts:
        created = a.created_at
        if created and hasattr(created, 'tzinfo') and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created and created >= cutoff:
            recent_alerts.append(a)

    critical = sum(1 for a in alerts if getattr(a, 'severity', '') == 'critical')
    high     = sum(1 for a in alerts if getattr(a, 'severity', '') == 'high')
    open_a   = sum(1 for a in alerts if getattr(a, 'status', '') == 'open')
    severity_score = sum(severity_weights.get(getattr(a, 'severity', ''), 0) for a in alerts)

    # Days since most recent alert
    alert_dates = []
    for a in alerts:
        created = getattr(a, 'created_at', None)
        if created:
            if hasattr(created, 'tzinfo') and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            alert_dates.append(created)

    days_since = (now - max(alert_dates)).days if alert_dates else 999

    return {
        "alert_count_total":    float(len(alerts)),
        "alert_count_90d":      float(len(recent_alerts)),
        "critical_alert_count": float(critical),
        "high_alert_count":     float(high),
        "open_alert_count":     float(open_a),
        "alert_severity_score": float(severity_score),
        "days_since_last_alert": float(min(days_since, 999)),
    }


def extract_profile_features(customer) -> Dict[str, float]:
    """
    Numerical encoding of customer profile attributes.
    Converts categorical KYC fields into model-ready features.
    """
    risk_map = {"low": 0.0, "medium": 1.0, "high": 2.0, "critical": 3.0}
    risk_level = getattr(customer, 'risk_level', 'low') or 'low'

    country    = (getattr(customer, 'country', '') or '').upper()
    nationality = (getattr(customer, 'nationality', '') or '').upper()

    country_risk = (
        2.0 if (country in HIGH_RISK_COUNTRIES or nationality in HIGH_RISK_COUNTRIES)
        else 1.0 if (country in MEDIUM_RISK_COUNTRIES or nationality in MEDIUM_RISK_COUNTRIES)
        else 0.0
    )

    created_at = getattr(customer, 'created_at', None)
    now = datetime.now(timezone.utc)
    if created_at:
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        account_age_days = (now - created_at).days
    else:
        account_age_days = 365

    annual_income = float(getattr(customer, 'annual_income', 0) or 0)

    return {
        "risk_level_code":      risk_map.get(risk_level, 0.0),
        "is_pep":               1.0 if getattr(customer, 'pep_status', False) else 0.0,
        "is_sanctioned":        1.0 if getattr(customer, 'sanctions_flag', False) else 0.0,
        "country_risk_code":    country_risk,
        "account_age_days":     float(min(account_age_days, 3650)),
        "log_annual_income":    math.log1p(annual_income),
        "has_id_document":      1.0 if getattr(customer, 'id_number', None) else 0.0,
    }


# ── Full Feature Engineer ──────────────────────────────────────────────────

class FeatureEngineer:
    """
    Combines all feature extractors into a unified pipeline.
    Produces a flat feature dict ready for ML model input.
    """

    def build_customer_features(
        self,
        customer,
        transactions: list,
        alerts: list,
    ) -> Dict[str, float]:
        """
        Build the complete feature set for a customer.

        Args:
            customer:     Customer ORM object
            transactions: List of Transaction ORM objects
            alerts:       List of Alert ORM objects

        Returns:
            Flat dict of feature_name → float value
        """
        features = {}
        features.update(extract_profile_features(customer))
        features.update(extract_amount_features(transactions))
        features.update(extract_velocity_features(transactions))
        features.update(extract_temporal_features(transactions))
        features.update(extract_geographic_features(transactions))
        features.update(extract_alert_features(alerts))
        return features

    def get_feature_names(self) -> List[str]:
        """Return ordered list of all feature names."""
        dummy_customer = type('C', (), {
            'risk_level': 'low', 'pep_status': False, 'sanctions_flag': False,
            'country': 'US', 'nationality': 'US', 'created_at': datetime.now(timezone.utc),
            'annual_income': 0, 'id_number': None,
        })()
        features = self.build_customer_features(dummy_customer, [], [])
        return list(features.keys())

    def build_feature_matrix(
        self,
        customers_data: List[Tuple],
    ) -> Tuple[List[Dict], List[str]]:
        """
        Build feature matrix for a list of customers.

        Args:
            customers_data: List of (customer, transactions, alerts) tuples

        Returns:
            (feature_dicts, feature_names)
        """
        feature_names = None
        feature_dicts = []

        for customer, transactions, alerts in customers_data:
            features = self.build_customer_features(customer, transactions, alerts)
            if feature_names is None:
                feature_names = list(features.keys())
            feature_dicts.append(features)

        return feature_dicts, feature_names or []

    def to_numpy_array(self, feature_dicts: List[Dict], feature_names: List[str]):
        """Convert list of feature dicts to numpy array for sklearn."""
        try:
            import numpy as np
            return np.array([
                [d.get(name, 0.0) for name in feature_names]
                for d in feature_dicts
            ])
        except ImportError:
            raise ImportError("numpy required: pip install numpy")


# Module-level singleton
feature_engineer = FeatureEngineer()
