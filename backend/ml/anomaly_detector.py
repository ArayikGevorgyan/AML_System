"""
Transaction Anomaly Detector
==============================
Detects statistically anomalous transactions using an Isolation Forest model.
Unlike rule-based detection (which catches known patterns), this model catches
unknown/novel anomalies — transactions that are statistically unusual for that
customer even if no specific rule is triggered.

How it works:
  1. Extracts numerical features from each transaction (amount, hour, day, etc.)
  2. Trains an Isolation Forest on a customer's historical transactions
  3. Scores new transactions — high anomaly score = unusual behaviour
  4. Returns a normalized anomaly score (0–100) where 100 = most anomalous

Why Isolation Forest?
  - Works well on small datasets (doesn't need millions of records)
  - Unsupervised — no labelled fraud data needed
  - Fast at inference time
  - Interpretable: feature importance can be extracted

Requirements:
    pip install scikit-learn numpy

Usage:
    from ml.anomaly_detector import AnomalyDetector
    detector = AnomalyDetector()
    detector.train(historical_transactions)
    score = detector.score(new_transaction)
"""

import math
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def _extract_features(transaction) -> Optional[List[float]]:
    """
    Extract numerical features from a Transaction object.

    Features:
      0: log(amount + 1)                — log-scaled to reduce skew
      1: hour of day (0–23)             — time-of-day pattern
      2: day of week (0=Mon, 6=Sun)     — weekday vs weekend
      3: is_international (0 or 1)      — cross-border flag
      4: is_round_amount (0 or 1)       — behavioural signal
      5: transaction_type_code          — numeric encoding
      6: channel_code                   — numeric encoding
    """
    try:
        amount = float(transaction.amount) if transaction.amount else 0.0

        created_at = transaction.created_at
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        hour    = created_at.hour
        weekday = created_at.weekday()

        is_international = 1.0 if getattr(transaction, 'is_international', False) else 0.0

        # Round amount detection — ends in 000 or 500
        is_round = 1.0 if (amount > 0 and amount % 500 == 0 and amount == int(amount)) else 0.0

        # Transaction type encoding
        type_map = {
            "transfer": 1, "deposit": 2, "withdrawal": 3,
            "wire": 4, "payment": 5, "cash": 6,
        }
        txn_type = getattr(transaction, 'transaction_type', '') or ''
        type_code = float(type_map.get(txn_type.lower(), 0))

        # Channel encoding
        channel_map = {"online": 1, "branch": 2, "atm": 3, "mobile": 4}
        channel = getattr(transaction, 'channel', '') or ''
        channel_code = float(channel_map.get(channel.lower(), 0))

        return [
            math.log1p(amount),
            float(hour),
            float(weekday),
            is_international,
            is_round,
            type_code,
            channel_code,
        ]
    except Exception as e:
        logger.warning(f"Feature extraction failed: {e}")
        return None


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector for transaction data.

    Train once on a customer's historical transactions, then score
    new transactions in real-time.
    """

    MIN_TRAINING_SAMPLES = 10   # Need at least this many transactions to train
    CONTAMINATION = 0.05        # Expect ~5% of transactions to be anomalous

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.training_size = 0
        self.feature_names = [
            "log_amount", "hour_of_day", "day_of_week",
            "is_international", "is_round_amount",
            "transaction_type", "channel",
        ]

    def train(self, transactions: list) -> bool:
        """
        Train the anomaly detector on historical transactions.

        Args:
            transactions: List of Transaction ORM objects

        Returns:
            True if training succeeded, False if insufficient data
        """
        try:
            from sklearn.ensemble import IsolationForest
            import numpy as np
        except ImportError:
            logger.error("scikit-learn not installed. Run: pip install scikit-learn numpy")
            return False

        features = []
        for txn in transactions:
            f = _extract_features(txn)
            if f is not None:
                features.append(f)

        if len(features) < self.MIN_TRAINING_SAMPLES:
            logger.warning(
                f"Insufficient training data: {len(features)} samples "
                f"(minimum {self.MIN_TRAINING_SAMPLES})"
            )
            return False

        X = np.array(features)
        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.CONTAMINATION,
            max_samples=min(256, len(features)),
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X)
        self.is_trained = True
        self.training_size = len(features)
        logger.info(f"Anomaly detector trained on {self.training_size} transactions")
        return True

    def score(self, transaction) -> Dict[str, Any]:
        """
        Score a single transaction for anomaly.

        Returns:
            dict with keys:
              - anomaly_score (0–100, higher = more anomalous)
              - is_anomaly (bool, True if score > threshold)
              - confidence ("low" | "medium" | "high")
              - reason (human-readable explanation)
        """
        if not self.is_trained or self.model is None:
            return {
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "confidence": "low",
                "reason": "Model not trained — insufficient historical data",
            }

        try:
            import numpy as np
        except ImportError:
            return {"anomaly_score": 0.0, "is_anomaly": False,
                    "confidence": "low", "reason": "numpy not available"}

        features = _extract_features(transaction)
        if features is None:
            return {"anomaly_score": 0.0, "is_anomaly": False,
                    "confidence": "low", "reason": "Feature extraction failed"}

        X = np.array([features])

        # decision_function returns negative scores for anomalies
        # (more negative = more anomalous)
        raw_score = self.model.decision_function(X)[0]
        prediction = self.model.predict(X)[0]  # -1 = anomaly, 1 = normal

        # Normalize to 0–100 (invert so higher = more anomalous)
        # Typical range is [-0.5, 0.5]; clip and rescale
        normalized = max(0.0, min(100.0, (-raw_score + 0.3) * 100))

        is_anomaly = prediction == -1

        # Confidence based on training size
        if self.training_size >= 100:
            confidence = "high"
        elif self.training_size >= 30:
            confidence = "medium"
        else:
            confidence = "low"

        # Build human-readable reason
        amount = float(transaction.amount or 0)
        reasons = []
        if features[0] > 9.0:  # log(8000+)
            reasons.append(f"unusually large amount (${amount:,.2f})")
        if features[3] == 1.0:
            reasons.append("international transfer")
        if features[4] == 1.0:
            reasons.append("round-number amount")
        hour = int(features[1])
        if hour < 6 or hour > 22:
            reasons.append(f"unusual time ({hour:02d}:00)")

        reason = (
            f"Anomalous transaction detected: {', '.join(reasons)}"
            if reasons
            else "Statistical outlier based on customer behaviour history"
        )

        return {
            "anomaly_score": round(normalized, 2),
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "reason": reason if is_anomaly else "Transaction within normal behaviour range",
        }

    def score_batch(self, transactions: list) -> List[Dict[str, Any]]:
        """Score multiple transactions at once."""
        return [self.score(txn) for txn in transactions]


class CustomerAnomalyDetectorRegistry:
    """
    Manages one AnomalyDetector per customer.
    Trains lazily on first use and caches the model in memory.
    In production, models would be serialized to disk/Redis.
    """

    def __init__(self):
        self._detectors: Dict[int, AnomalyDetector] = {}

    def get_or_train(self, customer_id: int, historical_transactions: list) -> AnomalyDetector:
        """Return trained detector for customer, training if not yet done."""
        if customer_id not in self._detectors:
            detector = AnomalyDetector()
            detector.train(historical_transactions)
            self._detectors[customer_id] = detector
        return self._detectors[customer_id]

    def retrain(self, customer_id: int, historical_transactions: list) -> AnomalyDetector:
        """Force retrain — call after significant new transaction history."""
        detector = AnomalyDetector()
        detector.train(historical_transactions)
        self._detectors[customer_id] = detector
        return detector

    def score_transaction(
        self,
        customer_id: int,
        transaction,
        historical_transactions: list,
    ) -> Dict[str, Any]:
        """
        Convenience method: get/train detector and score a transaction.

        Args:
            customer_id: Customer ID
            transaction: New transaction to score
            historical_transactions: Past transactions for training

        Returns:
            Anomaly score dict
        """
        detector = self.get_or_train(customer_id, historical_transactions)
        return detector.score(transaction)


# Module-level singleton registry
anomaly_registry = CustomerAnomalyDetectorRegistry()
