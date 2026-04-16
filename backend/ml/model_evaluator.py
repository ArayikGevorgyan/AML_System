"""
ML Model Evaluator
===================
Evaluates trained ML models with standard classification metrics.
Produces detailed performance reports including precision, recall,
F1-score, ROC-AUC, confusion matrix, and threshold analysis.

Used after training to assess model quality before deploying to production.
Also supports A/B comparison between two model versions.

Usage:
    from ml.model_evaluator import ModelEvaluator
    evaluator = ModelEvaluator()

    # Evaluate a trained sklearn model
    report = evaluator.evaluate(model, X_test, y_test)
    evaluator.print_report(report)

    # Compare two models
    comparison = evaluator.compare(model_v1, model_v2, X_test, y_test)
"""

import math
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    Comprehensive evaluation suite for binary classification models.
    Designed for AML risk models where class imbalance is common
    (few SARs vs many clean customers).
    """

    DEFAULT_THRESHOLD = 0.5

    # ── Core Evaluation ────────────────────────────────────────────────

    def evaluate(
        self,
        model,
        X_test,
        y_test,
        threshold: float = DEFAULT_THRESHOLD,
        model_name: str = "Model",
    ) -> Dict[str, Any]:
        """
        Full evaluation of a trained sklearn-compatible model.

        Args:
            model:      Trained sklearn model with predict_proba()
            X_test:     Test feature matrix (numpy array)
            y_test:     True labels (numpy array of 0/1)
            threshold:  Decision threshold (default 0.5)
            model_name: Name for the report

        Returns:
            Dict with all evaluation metrics
        """
        try:
            import numpy as np
            from sklearn.metrics import (
                classification_report,
                confusion_matrix,
                roc_auc_score,
                average_precision_score,
                precision_recall_curve,
                roc_curve,
            )
        except ImportError:
            raise ImportError("scikit-learn required: pip install scikit-learn numpy")

        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred  = (y_proba >= threshold).astype(int)

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

        # Core metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        accuracy    = (tp + tn) / len(y_test) if len(y_test) > 0 else 0.0

        # AUC metrics
        try:
            roc_auc = roc_auc_score(y_test, y_proba)
        except Exception:
            roc_auc = 0.0

        try:
            avg_precision = average_precision_score(y_test, y_proba)
        except Exception:
            avg_precision = 0.0

        # Class distribution
        positive_rate = float(np.mean(y_test))
        predicted_positive_rate = float(np.mean(y_pred))

        # False positive cost analysis
        # In AML: false negatives (missing SAR) are much costlier than false positives
        false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        return {
            "model_name":            model_name,
            "threshold":             threshold,
            "n_samples":             len(y_test),
            "n_positive":            int(np.sum(y_test)),
            "n_negative":            int(len(y_test) - np.sum(y_test)),
            "positive_rate":         round(positive_rate, 4),
            "confusion_matrix": {
                "true_negative":     int(tn),
                "false_positive":    int(fp),
                "false_negative":    int(fn),
                "true_positive":     int(tp),
            },
            "metrics": {
                "accuracy":          round(accuracy, 4),
                "precision":         round(precision, 4),
                "recall":            round(recall, 4),
                "f1_score":          round(f1, 4),
                "specificity":       round(specificity, 4),
                "roc_auc":           round(roc_auc, 4),
                "avg_precision":     round(avg_precision, 4),
                "false_negative_rate": round(false_negative_rate, 4),
                "false_positive_rate": round(false_positive_rate, 4),
            },
            "aml_assessment": self._aml_assessment(recall, precision, roc_auc),
        }

    def _aml_assessment(
        self, recall: float, precision: float, roc_auc: float
    ) -> Dict[str, Any]:
        """
        AML-specific model quality assessment.
        In AML, recall (catching all SARs) is more important than precision.
        A recall < 0.70 means 30%+ of money laundering goes undetected.
        """
        issues = []
        warnings = []

        if recall < 0.70:
            issues.append(f"LOW RECALL ({recall:.1%}): over 30% of SARs will be missed")
        elif recall < 0.80:
            warnings.append(f"Recall {recall:.1%} is below recommended 80% for AML")

        if precision < 0.30:
            warnings.append(f"LOW PRECISION ({precision:.1%}): analysts will face high false-positive workload")

        if roc_auc < 0.70:
            issues.append(f"ROC-AUC {roc_auc:.3f} is poor — model barely better than random")
        elif roc_auc < 0.80:
            warnings.append(f"ROC-AUC {roc_auc:.3f} is acceptable but room for improvement")

        if roc_auc >= 0.85 and recall >= 0.80:
            grade = "GOOD — suitable for production"
        elif roc_auc >= 0.75 and recall >= 0.70:
            grade = "ACCEPTABLE — monitor closely in production"
        else:
            grade = "POOR — do not deploy, retrain with more data"

        return {
            "grade":    grade,
            "issues":   issues,
            "warnings": warnings,
        }

    # ── Threshold Analysis ─────────────────────────────────────────────

    def threshold_analysis(
        self, model, X_test, y_test, thresholds: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate model performance at multiple decision thresholds.
        Helps choose the optimal threshold for the AML use case.
        Lower threshold = higher recall (fewer missed SARs) but more false positives.
        """
        try:
            import numpy as np
        except ImportError:
            raise ImportError("numpy required")

        if thresholds is None:
            thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        y_proba = model.predict_proba(X_test)[:, 1]
        results = []

        for t in thresholds:
            y_pred = (y_proba >= t).astype(int)
            tp = int(np.sum((y_pred == 1) & (y_test == 1)))
            fp = int(np.sum((y_pred == 1) & (y_test == 0)))
            fn = int(np.sum((y_pred == 0) & (y_test == 1)))
            tn = int(np.sum((y_pred == 0) & (y_test == 0)))

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1        = (2 * precision * recall / (precision + recall)
                         if (precision + recall) > 0 else 0.0)

            results.append({
                "threshold":      t,
                "precision":      round(precision, 4),
                "recall":         round(recall, 4),
                "f1":             round(f1, 4),
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "flagged_pct":    round(float(np.mean(y_pred)) * 100, 1),
            })

        return results

    # ── Cross-Validation ───────────────────────────────────────────────

    def cross_validate(
        self,
        model_class,
        model_params: Dict,
        X,
        y,
        n_splits: int = 5,
    ) -> Dict[str, Any]:
        """
        K-fold cross-validation to get stable performance estimates.
        More reliable than a single train/test split, especially for
        small imbalanced datasets typical in AML.
        """
        try:
            from sklearn.model_selection import StratifiedKFold, cross_validate as sk_cv
            from sklearn.metrics import make_scorer, recall_score, precision_score, roc_auc_score
            import numpy as np
        except ImportError:
            raise ImportError("scikit-learn required")

        model = model_class(**model_params)
        skf   = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        scoring = {
            "roc_auc":   "roc_auc",
            "recall":    make_scorer(recall_score, zero_division=0),
            "precision": make_scorer(precision_score, zero_division=0),
            "f1":        "f1",
        }

        cv_results = sk_cv(model, X, y, cv=skf, scoring=scoring, return_train_score=False)

        summary = {}
        for metric in ("roc_auc", "recall", "precision", "f1"):
            scores = cv_results[f"test_{metric}"]
            summary[metric] = {
                "mean":  round(float(np.mean(scores)), 4),
                "std":   round(float(np.std(scores)), 4),
                "min":   round(float(np.min(scores)), 4),
                "max":   round(float(np.max(scores)), 4),
                "scores": [round(float(s), 4) for s in scores],
            }

        return {
            "n_splits":       n_splits,
            "n_samples":      len(y),
            "positive_rate":  round(float(np.mean(y)), 4),
            "metrics":        summary,
        }

    # ── Model Comparison ───────────────────────────────────────────────

    def compare(
        self,
        model_a,
        model_b,
        X_test,
        y_test,
        name_a: str = "Model A",
        name_b: str = "Model B",
    ) -> Dict[str, Any]:
        """
        Side-by-side comparison of two models on the same test set.
        Useful for deciding whether to deploy a new model version.
        """
        report_a = self.evaluate(model_a, X_test, y_test, model_name=name_a)
        report_b = self.evaluate(model_b, X_test, y_test, model_name=name_b)

        metrics = ("accuracy", "precision", "recall", "f1_score", "roc_auc")
        comparison = {}

        for metric in metrics:
            val_a = report_a["metrics"][metric]
            val_b = report_b["metrics"][metric]
            delta = round(val_b - val_a, 4)
            comparison[metric] = {
                name_a: val_a,
                name_b: val_b,
                "delta": delta,
                "winner": name_b if delta > 0 else name_a if delta < 0 else "tie",
            }

        # Overall winner by recall (most important for AML)
        recall_a = report_a["metrics"]["recall"]
        recall_b = report_b["metrics"]["recall"]
        recommended = name_b if recall_b > recall_a else name_a

        return {
            "comparison":   comparison,
            "recommended":  recommended,
            "reason":       f"{recommended} has higher recall ({max(recall_a, recall_b):.1%}), "
                            f"which minimises missed SARs",
            "report_a":     report_a,
            "report_b":     report_b,
        }

    # ── Reporting ──────────────────────────────────────────────────────

    def print_report(self, report: Dict[str, Any]) -> None:
        """Print a formatted evaluation report to stdout."""
        name    = report.get("model_name", "Model")
        metrics = report.get("metrics", {})
        cm      = report.get("confusion_matrix", {})
        assess  = report.get("aml_assessment", {})

        print(f"\n{'=' * 55}")
        print(f"  MODEL EVALUATION: {name}")
        print(f"  Samples: {report.get('n_samples', 0)} "
              f"({report.get('n_positive', 0)} positive / {report.get('n_negative', 0)} negative)")
        print(f"{'=' * 55}")
        print(f"  Accuracy:    {metrics.get('accuracy', 0):.1%}")
        print(f"  Precision:   {metrics.get('precision', 0):.1%}")
        print(f"  Recall:      {metrics.get('recall', 0):.1%}  ← most important for AML")
        print(f"  F1 Score:    {metrics.get('f1_score', 0):.1%}")
        print(f"  ROC-AUC:     {metrics.get('roc_auc', 0):.4f}")
        print(f"  Avg Precision: {metrics.get('avg_precision', 0):.4f}")
        print(f"\n  Confusion Matrix:")
        print(f"    True Positive:  {cm.get('true_positive', 0):>6}")
        print(f"    False Positive: {cm.get('false_positive', 0):>6}")
        print(f"    True Negative:  {cm.get('true_negative', 0):>6}")
        print(f"    False Negative: {cm.get('false_negative', 0):>6}")
        print(f"\n  AML Assessment: {assess.get('grade', 'N/A')}")
        for issue in assess.get("issues", []):
            print(f"    ✗ {issue}")
        for warning in assess.get("warnings", []):
            print(f"    ⚠ {warning}")
        print(f"{'=' * 55}\n")


# Module-level singleton
model_evaluator = ModelEvaluator()
