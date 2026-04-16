"""
ML-Based Customer Risk Model
==============================
A gradient boosting model (XGBoost / scikit-learn GradientBoostingClassifier)
that predicts whether a customer will generate a SAR (Suspicious Activity Report)
within the next 90 days.

This complements the rule-based risk scoring by learning non-linear patterns
from historical data — e.g. the combination of medium transaction volume +
frequent international transfers + recent PEP change is predictive of SARs
even if each factor alone doesn't trigger a rule.

How it works:
  1. Feature engineering: extract ~15 features per customer from their
     transaction history, alert history, and profile attributes
  2. Training: fit a GradientBoostingClassifier on labelled historical data
     (customers who generated SARs = positive class)
  3. Prediction: output probability (0–1) of SAR in next 90 days
  4. Explainability: return top contributing features for each prediction

Requirements:
    pip install scikit-learn numpy

Usage:
    from ml.risk_model import CustomerRiskModel
    model = CustomerRiskModel()
    model.train(customers, transactions, alerts, sar_labels)
    prediction = model.predict(customer, transactions, alerts)
"""

import math
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# High-risk country codes (ISO-2) used as features
HIGH_RISK_COUNTRIES = {
    "IR", "KP", "SY", "CU", "RU", "BY", "MM", "YE",
    "LY", "SO", "SD", "ZW", "CD", "CF", "ML", "IQ",
}


def _extract_customer_features(
    customer,
    transactions: list,
    alerts: list,
    lookback_days: int = 180,
) -> Optional[Dict[str, float]]:
    """
    Extract ~15 numerical features from a customer's profile and history.

    Returns a feature dict, or None if extraction fails.
    """
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=lookback_days)

        # Filter transactions to lookback window
        recent_txns = []
        for t in transactions:
            created = t.created_at
            if created is None:
                continue
            if hasattr(created, 'tzinfo') and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                recent_txns.append(t)

        # Filter alerts to lookback window
        recent_alerts = []
        for a in alerts:
            created = a.created_at
            if created is None:
                continue
            if hasattr(created, 'tzinfo') and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                recent_alerts.append(a)

        # Transaction features
        txn_count = len(recent_txns)
        total_amount = sum(float(t.amount or 0) for t in recent_txns)
        flagged_count = sum(1 for t in recent_txns if getattr(t, 'flagged', False))
        intl_count = sum(1 for t in recent_txns if getattr(t, 'is_international', False))
        avg_amount = total_amount / txn_count if txn_count > 0 else 0.0

        # Velocity: transactions per week
        weeks = max(lookback_days / 7, 1)
        txn_velocity = txn_count / weeks

        # Flag ratio
        flag_ratio = flagged_count / txn_count if txn_count > 0 else 0.0

        # International ratio
        intl_ratio = intl_count / txn_count if txn_count > 0 else 0.0

        # Alert features
        alert_count = len(recent_alerts)
        critical_alerts = sum(1 for a in recent_alerts if getattr(a, 'severity', '') == 'critical')
        high_alerts = sum(1 for a in recent_alerts if getattr(a, 'severity', '') == 'high')
        alert_severity_score = critical_alerts * 4 + high_alerts * 2 + alert_count

        # Profile features
        risk_level = getattr(customer, 'risk_level', 'low') or 'low'
        risk_map = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        risk_code = float(risk_map.get(risk_level, 0))

        is_pep = 1.0 if getattr(customer, 'pep_status', False) else 0.0
        is_sanctioned = 1.0 if getattr(customer, 'sanctions_flag', False) else 0.0

        country = (getattr(customer, 'country', '') or '').upper()
        nationality = (getattr(customer, 'nationality', '') or '').upper()
        is_high_risk_country = 1.0 if (country in HIGH_RISK_COUNTRIES or nationality in HIGH_RISK_COUNTRIES) else 0.0

        # Account age in days
        created_at = getattr(customer, 'created_at', None)
        if created_at:
            if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            account_age_days = (now - created_at).days
        else:
            account_age_days = 365

        return {
            "txn_count":              float(txn_count),
            "log_total_amount":       math.log1p(total_amount),
            "log_avg_amount":         math.log1p(avg_amount),
            "txn_velocity_per_week":  round(txn_velocity, 3),
            "flag_ratio":             round(flag_ratio, 3),
            "intl_ratio":             round(intl_ratio, 3),
            "alert_count":            float(alert_count),
            "critical_alerts":        float(critical_alerts),
            "alert_severity_score":   float(alert_severity_score),
            "risk_level_code":        risk_code,
            "is_pep":                 is_pep,
            "is_sanctioned":          is_sanctioned,
            "is_high_risk_country":   is_high_risk_country,
            "account_age_days":       float(min(account_age_days, 3650)),
        }
    except Exception as e:
        logger.warning(f"Feature extraction failed for customer: {e}")
        return None


class CustomerRiskModel:
    """
    Gradient Boosting model that predicts SAR probability for a customer.

    Higher predicted probability = higher likelihood of generating a SAR
    in the next 90 days.
    """

    FEATURE_NAMES = [
        "txn_count", "log_total_amount", "log_avg_amount",
        "txn_velocity_per_week", "flag_ratio", "intl_ratio",
        "alert_count", "critical_alerts", "alert_severity_score",
        "risk_level_code", "is_pep", "is_sanctioned",
        "is_high_risk_country", "account_age_days",
    ]

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.training_samples = 0
        self.feature_importances: Dict[str, float] = {}

    def train(
        self,
        training_data: List[Dict[str, Any]],
        labels: List[int],
    ) -> bool:
        """
        Train the risk model.

        Args:
            training_data: List of feature dicts from _extract_customer_features()
            labels: List of 0/1 labels (1 = customer generated a SAR)

        Returns:
            True if training succeeded
        """
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import Pipeline
            import numpy as np
        except ImportError:
            logger.error("scikit-learn not installed. Run: pip install scikit-learn numpy")
            return False

        if len(training_data) < 20:
            logger.warning(f"Insufficient training data: {len(training_data)} samples (need at least 20)")
            return False

        X = np.array([
            [d.get(f, 0.0) for f in self.FEATURE_NAMES]
            for d in training_data
        ])
        y = np.array(labels)

        self.model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                min_samples_split=5,
                random_state=42,
            )),
        ])
        self.model.fit(X, y)
        self.is_trained = True
        self.training_samples = len(training_data)

        # Extract feature importances
        clf = self.model.named_steps["clf"]
        importances = clf.feature_importances_
        self.feature_importances = {
            name: round(float(imp), 4)
            for name, imp in zip(self.FEATURE_NAMES, importances)
        }

        logger.info(
            f"Risk model trained on {self.training_samples} samples. "
            f"Top feature: {max(self.feature_importances, key=self.feature_importances.get)}"
        )
        return True

    def predict(
        self,
        customer,
        transactions: list,
        alerts: list,
    ) -> Dict[str, Any]:
        """
        Predict SAR probability for a customer.

        Returns:
            dict with:
              - sar_probability (0.0–1.0)
              - risk_band ("low" | "medium" | "high" | "critical")
              - top_factors: list of (feature_name, importance) tuples
              - features: raw feature values used for the prediction
        """
        if not self.is_trained or self.model is None:
            return {
                "sar_probability": 0.0,
                "risk_band": "unknown",
                "top_factors": [],
                "features": {},
                "error": "Model not trained",
            }

        try:
            import numpy as np
        except ImportError:
            return {"error": "numpy not installed"}

        features = _extract_customer_features(customer, transactions, alerts)
        if features is None:
            return {"error": "Feature extraction failed"}

        X = np.array([[features.get(f, 0.0) for f in self.FEATURE_NAMES]])
        proba = self.model.predict_proba(X)[0]

        # proba[1] = probability of SAR (positive class)
        sar_prob = float(proba[1]) if len(proba) > 1 else 0.0

        if sar_prob >= 0.75:
            risk_band = "critical"
        elif sar_prob >= 0.50:
            risk_band = "high"
        elif sar_prob >= 0.25:
            risk_band = "medium"
        else:
            risk_band = "low"

        # Top contributing features
        top_factors = sorted(
            self.feature_importances.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "sar_probability":   round(sar_prob, 4),
            "sar_probability_pct": round(sar_prob * 100, 1),
            "risk_band":         risk_band,
            "top_factors":       top_factors,
            "features":          {k: round(v, 3) for k, v in features.items()},
        }

    def predict_batch(
        self,
        customers_data: List[Tuple],
    ) -> List[Dict[str, Any]]:
        """
        Predict SAR probability for multiple customers at once.

        Args:
            customers_data: List of (customer, transactions, alerts) tuples

        Returns:
            List of prediction dicts sorted by sar_probability descending
        """
        results = []
        for customer, transactions, alerts in customers_data:
            pred = self.predict(customer, transactions, alerts)
            pred["customer_id"] = getattr(customer, "id", None)
            pred["customer_name"] = getattr(customer, "full_name", "")
            results.append(pred)

        results.sort(key=lambda x: x.get("sar_probability", 0), reverse=True)
        return results

    def explain(self, customer, transactions: list, alerts: list) -> str:
        """
        Generate a human-readable explanation of the risk prediction.

        Returns a plain-English string suitable for analyst review.
        """
        prediction = self.predict(customer, transactions, alerts)
        if "error" in prediction:
            return f"Unable to explain: {prediction['error']}"

        prob = prediction["sar_probability_pct"]
        band = prediction["risk_band"].upper()
        name = getattr(customer, "full_name", "Customer")

        lines = [
            f"Risk Assessment for {name}",
            f"SAR Probability: {prob}% [{band}]",
            "",
            "Key risk drivers:",
        ]

        features = prediction.get("features", {})
        top_factors = prediction.get("top_factors", [])

        factor_descriptions = {
            "flag_ratio":             f"  • {round(features.get('flag_ratio', 0) * 100)}% of transactions are flagged",
            "alert_severity_score":   f"  • Alert severity score: {features.get('alert_severity_score', 0):.0f}",
            "critical_alerts":        f"  • {features.get('critical_alerts', 0):.0f} critical alert(s)",
            "is_pep":                 f"  • Customer is a Politically Exposed Person (PEP)",
            "is_sanctioned":          f"  • Customer has a sanctions flag",
            "is_high_risk_country":   f"  • Customer is from a high-risk jurisdiction",
            "intl_ratio":             f"  • {round(features.get('intl_ratio', 0) * 100)}% international transactions",
            "log_total_amount":       f"  • High transaction volume (log-scaled: {features.get('log_total_amount', 0):.1f})",
            "txn_velocity_per_week":  f"  • {features.get('txn_velocity_per_week', 0):.1f} transactions per week",
            "risk_level_code":        f"  • Profile risk level: {['low','medium','high','critical'][int(features.get('risk_level_code', 0))]}",
        }

        for factor_name, _ in top_factors:
            if factor_name in factor_descriptions and features.get(factor_name, 0) > 0:
                lines.append(factor_descriptions[factor_name])

        return "\n".join(lines)


# Module-level singleton
customer_risk_model = CustomerRiskModel()
