"""
SAR Classifier
===============
Predicts whether an alert should be escalated to a Suspicious Activity Report (SAR).
Uses a random forest-style ensemble approach with handcrafted feature extraction
designed specifically for AML scenarios.

Classes:
  - SARFeatureExtractor: Extracts features from alert, customer, and transaction data.
  - SARClassifier:       Trains and serves SAR predictions with probability scores.

Usage:
    from ml.sar_classifier import SARClassifier, SARFeatureExtractor

    extractor = SARFeatureExtractor()
    features = extractor.extract(alert, customer, transactions)

    clf = SARClassifier()
    clf.train(X_train, y_train)
    prob = clf.predict_proba([features])[0]
"""

import json
import math
import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SARFeatureExtractor
# ---------------------------------------------------------------------------

class SARFeatureExtractor:
    """
    Extracts a fixed-length numerical feature vector from AML entity data
    suitable for SAR classification.

    Features are designed to capture:
      - Alert characteristics (severity, risk score, age)
      - Customer risk profile (risk level, PEP, sanctions)
      - Transaction patterns (velocity, amount, international activity)
      - Case history

    Feature vector length: 20 features (see FEATURE_NAMES).
    """

    FEATURE_NAMES = [
        "severity_score",         # critical=4, high=3, medium=2, low=1
        "alert_risk_score",       # 0–100 float
        "alert_age_hours",        # hours since alert created
        "customer_risk_score",    # critical=4, high=3, medium=2, low=1
        "is_pep",                 # 0 or 1
        "has_sanctions",          # 0 or 1
        "txn_count_30d",          # transactions in last 30 days
        "total_amount_30d",       # total USD in last 30 days
        "flagged_count_30d",      # flagged transactions in last 30 days
        "flagged_ratio_30d",      # flagged / total ratio
        "is_international",       # fraction of international txns
        "high_risk_country_txns", # txns to/from high-risk countries
        "mean_txn_amount",        # mean transaction amount
        "max_txn_amount",         # max transaction amount
        "std_txn_amount",         # std dev of transaction amounts
        "off_hours_ratio",        # fraction of off-hours transactions
        "unique_countries",       # number of unique destination countries
        "prior_alerts_count",     # total historical alerts for customer
        "prior_cases_count",      # prior escalated cases for customer
        "txn_velocity_change",    # recent velocity vs prior (ratio)
    ]

    HIGH_RISK_COUNTRIES = {
        "IR", "KP", "SY", "CU", "RU", "BY", "MM", "YE",
        "LY", "SO", "SD", "ZW", "CD", "AF",
    }

    SEVERITY_MAP = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    RISK_LEVEL_MAP = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    def __init__(self) -> None:
        pass

    def extract(
        self,
        alert: Any,
        customer: Any,
        transactions: List[Any],
        prior_alerts_count: int = 0,
        prior_cases_count: int = 0,
    ) -> List[float]:
        """
        Extract a 20-element feature vector from alert, customer, and transactions.

        Args:
            alert:              Alert ORM object or dict with alert fields.
            customer:           Customer ORM object or dict.
            transactions:       List of recent Transaction ORM objects (last 30 days).
            prior_alerts_count: Total historical alert count for this customer.
            prior_cases_count:  Total prior case count for this customer.

        Returns:
            List of 20 floats representing the SAR prediction features.
        """
        now = datetime.now(timezone.utc)

        # --- Alert features ---
        severity = getattr(alert, "severity", None) or alert.get("severity", "low")
        sev_score = float(self.SEVERITY_MAP.get(str(severity).lower(), 1))

        risk_score = getattr(alert, "risk_score", None) or alert.get("risk_score", 0.0) or 0.0

        created_at = getattr(alert, "created_at", None) or alert.get("created_at", now)
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = now
        if hasattr(created_at, "tzinfo") and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        alert_age_hours = max(0.0, (now - created_at).total_seconds() / 3600)

        # --- Customer features ---
        risk_level = getattr(customer, "risk_level", None) or customer.get("risk_level", "low")
        cust_risk = float(self.RISK_LEVEL_MAP.get(str(risk_level).lower(), 1))
        is_pep = 1.0 if (getattr(customer, "pep_status", False) or
                         customer.get("pep_status", False)) else 0.0
        has_sanctions = 1.0 if (getattr(customer, "sanctions_flag", False) or
                                 customer.get("sanctions_flag", False)) else 0.0

        # --- Transaction features ---
        txn_count = len(transactions)
        total_amount = sum((getattr(t, "amount", 0) or 0) for t in transactions)
        flagged_count = sum(1 for t in transactions if getattr(t, "flagged", False))
        flagged_ratio = flagged_count / txn_count if txn_count > 0 else 0.0

        intl_count = sum(1 for t in transactions if getattr(t, "is_international", False))
        intl_ratio = intl_count / txn_count if txn_count > 0 else 0.0

        high_risk_count = 0
        for t in transactions:
            dest = getattr(t, "destination_country", None) or ""
            orig = getattr(t, "originating_country", None) or ""
            if dest in self.HIGH_RISK_COUNTRIES or orig in self.HIGH_RISK_COUNTRIES:
                high_risk_count += 1

        amounts = [getattr(t, "amount", 0) or 0 for t in transactions if getattr(t, "amount", None)]
        mean_amt = statistics.mean(amounts) if amounts else 0.0
        max_amt = max(amounts) if amounts else 0.0
        std_amt = statistics.stdev(amounts) if len(amounts) >= 2 else 0.0

        off_hours = 0
        for t in transactions:
            ca = getattr(t, "created_at", None)
            if ca and hasattr(ca, "hour") and (ca.hour < 8 or ca.hour >= 20):
                off_hours += 1
        off_hours_ratio = off_hours / txn_count if txn_count > 0 else 0.0

        dest_countries = {
            getattr(t, "destination_country", None)
            for t in transactions
            if getattr(t, "destination_country", None)
        }
        unique_countries = float(len(dest_countries))

        # Velocity change: compare first half to second half of transaction list
        if txn_count >= 4:
            half = txn_count // 2
            recent_half = transactions[half:]
            prior_half = transactions[:half]
            recent_amt = sum(getattr(t, "amount", 0) or 0 for t in recent_half)
            prior_amt = sum(getattr(t, "amount", 0) or 0 for t in prior_half)
            velocity_change = (recent_amt / prior_amt) if prior_amt > 0 else 1.0
        else:
            velocity_change = 1.0

        return [
            sev_score,
            float(risk_score),
            round(alert_age_hours, 2),
            cust_risk,
            is_pep,
            has_sanctions,
            float(txn_count),
            round(total_amount, 2),
            float(flagged_count),
            round(flagged_ratio, 4),
            round(intl_ratio, 4),
            float(high_risk_count),
            round(mean_amt, 2),
            round(max_amt, 2),
            round(std_amt, 2),
            round(off_hours_ratio, 4),
            unique_countries,
            float(prior_alerts_count),
            float(prior_cases_count),
            round(velocity_change, 4),
        ]

    def get_feature_names(self) -> List[str]:
        """Return the ordered list of feature names."""
        return list(self.FEATURE_NAMES)


# ---------------------------------------------------------------------------
# SARClassifier
# ---------------------------------------------------------------------------

class SARClassifier:
    """
    Logistic-regression-style SAR classifier implemented from scratch.

    Uses a weighted linear combination of features with sigmoid activation
    to produce a SAR probability. Weights are learned via gradient descent.

    For production systems, replace with sklearn.ensemble.RandomForestClassifier
    or xgboost.XGBClassifier. This implementation avoids heavy dependencies
    while providing a realistic API surface.
    """

    def __init__(self, learning_rate: float = 0.01, epochs: int = 100) -> None:
        """
        Initialize classifier with hyperparameters.

        Args:
            learning_rate: Gradient descent step size.
            epochs:        Number of training epochs.
        """
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.feature_names: List[str] = SARFeatureExtractor.FEATURE_NAMES
        self.is_trained: bool = False
        self.training_metrics: Dict[str, Any] = {}

    def _sigmoid(self, x: float) -> float:
        """Sigmoid activation function."""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def _dot(self, weights: List[float], features: List[float]) -> float:
        """Dot product of weights and feature vector."""
        return sum(w * f for w, f in zip(weights, features))

    def train(self, X: List[List[float]], y: List[int]) -> "SARClassifier":
        """
        Train the SAR classifier using logistic regression with gradient descent.

        Args:
            X: Training feature matrix (list of feature vectors).
            y: Binary labels (1 = should be SAR, 0 = not SAR).

        Returns:
            self (for chaining)

        Raises:
            ValueError: If X and y have different lengths or are empty.
        """
        if not X or not y:
            raise ValueError("Training data cannot be empty.")
        if len(X) != len(y):
            raise ValueError(f"X has {len(X)} rows but y has {len(y)} labels.")

        n_features = len(X[0])
        self.weights = [0.0] * n_features
        self.bias = 0.0

        n = len(X)
        epoch_losses = []

        for epoch in range(self.epochs):
            total_loss = 0.0
            grad_w = [0.0] * n_features
            grad_b = 0.0

            for features, label in zip(X, y):
                z = self._dot(self.weights, features) + self.bias
                pred = self._sigmoid(z)
                error = pred - label

                # BCE loss
                eps = 1e-9
                loss = -(label * math.log(pred + eps) + (1 - label) * math.log(1 - pred + eps))
                total_loss += loss

                for j in range(n_features):
                    grad_w[j] += error * features[j]
                grad_b += error

            # Update weights
            for j in range(n_features):
                self.weights[j] -= self.learning_rate * grad_w[j] / n
            self.bias -= self.learning_rate * grad_b / n

            avg_loss = total_loss / n
            epoch_losses.append(avg_loss)

        self.is_trained = True
        self.training_metrics = {
            "epochs": self.epochs,
            "final_loss": round(epoch_losses[-1], 6) if epoch_losses else 0.0,
            "initial_loss": round(epoch_losses[0], 6) if epoch_losses else 0.0,
            "training_samples": n,
        }
        logger.info("SARClassifier trained: final_loss=%.4f", self.training_metrics["final_loss"])
        return self

    def predict(self, X: List[List[float]]) -> List[int]:
        """
        Predict binary SAR labels (1 = file SAR, 0 = do not file).

        Args:
            X: Feature matrix.

        Returns:
            List of binary predictions.

        Raises:
            RuntimeError: If model has not been trained.
        """
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        """
        Predict SAR probability scores for each sample.

        Args:
            X: Feature matrix (list of feature vectors).

        Returns:
            List of probabilities in [0, 1].

        Raises:
            RuntimeError: If model has not been trained.
        """
        if not self.is_trained:
            raise RuntimeError("SARClassifier must be trained before prediction.")

        probs = []
        for features in X:
            z = self._dot(self.weights, features) + self.bias
            probs.append(self._sigmoid(z))
        return probs

    def evaluate(self, X_test: List[List[float]], y_test: List[int]) -> Dict[str, Any]:
        """
        Evaluate model performance on a test set.

        Computes accuracy, precision, recall, and F1 score.

        Args:
            X_test: Test feature matrix.
            y_test: True binary labels.

        Returns:
            Dict with accuracy, precision, recall, f1, and confusion matrix.
        """
        preds = self.predict(X_test)
        n = len(y_test)

        tp = sum(1 for p, t in zip(preds, y_test) if p == 1 and t == 1)
        fp = sum(1 for p, t in zip(preds, y_test) if p == 1 and t == 0)
        tn = sum(1 for p, t in zip(preds, y_test) if p == 0 and t == 0)
        fn = sum(1 for p, t in zip(preds, y_test) if p == 0 and t == 1)

        accuracy = (tp + tn) / n if n > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "sample_size": n,
        }

    def get_feature_importance(self) -> List[Dict[str, Any]]:
        """
        Return feature importance based on absolute weight magnitudes.

        Returns:
            List of dicts [{feature, weight, importance_rank}] sorted by
            absolute weight descending.

        Raises:
            RuntimeError: If model has not been trained.
        """
        if not self.is_trained:
            raise RuntimeError("SARClassifier must be trained before get_feature_importance().")

        pairs = sorted(
            zip(self.feature_names, self.weights),
            key=lambda x: abs(x[1]),
            reverse=True,
        )

        return [
            {"feature": name, "weight": round(w, 6), "importance_rank": i + 1}
            for i, (name, w) in enumerate(pairs)
        ]

    def save(self, path: str) -> None:
        """
        Save trained model weights and metadata to JSON.

        Args:
            path: Filesystem path for the output JSON file.
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before saving.")

        state = {
            "weights": self.weights,
            "bias": self.bias,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "feature_names": self.feature_names,
            "is_trained": True,
            "training_metrics": self.training_metrics,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        logger.info("SARClassifier saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "SARClassifier":
        """
        Load a previously saved SARClassifier from JSON.

        Args:
            path: Path to the JSON file.

        Returns:
            A trained SARClassifier instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        clf = cls(
            learning_rate=state.get("learning_rate", 0.01),
            epochs=state.get("epochs", 100),
        )
        clf.weights = state["weights"]
        clf.bias = state["bias"]
        clf.feature_names = state.get("feature_names", SARFeatureExtractor.FEATURE_NAMES)
        clf.is_trained = state.get("is_trained", True)
        clf.training_metrics = state.get("training_metrics", {})

        logger.info("SARClassifier loaded from %s", path)
        return clf

    def __repr__(self) -> str:
        status = "trained" if self.is_trained else "untrained"
        return f"SARClassifier({status}, features={len(self.feature_names)}, lr={self.learning_rate})"
