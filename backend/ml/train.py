"""
ML Model Training Script
==========================
Trains the CustomerRiskModel on historical data from the database.
Run this periodically (e.g. monthly) to keep the model up to date
as new SAR cases and transaction patterns accumulate.

What it does:
  1. Fetches all customers from the database
  2. For each customer, extracts their last 180 days of transactions + alerts
  3. Labels each customer: 1 = generated a SAR case, 0 = did not
  4. Trains the GradientBoosting model
  5. Saves the trained model to disk (models/customer_risk_model.pkl)
  6. Prints a classification report and feature importances

Usage:
    python ml/train.py
    python ml/train.py --min-samples 50   # require at least 50 SAR positives
    python ml/train.py --output models/my_model.pkl

Requirements:
    pip install scikit-learn numpy
"""

import argparse
import os
import sys
import logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_training_data(db):
    """
    Build training dataset from the database.

    A customer is labelled as positive (1) if they have at least one
    'escalated' or closed investigation case — indicating a SAR was filed
    or the case was serious enough to escalate.
    """
    from models.customer import Customer
    from models.transaction import Transaction
    from models.alert import Alert
    from models.case import Case
    from ml.risk_model import _extract_customer_features

    logger.info("Loading customers...")
    customers = db.query(Customer).all()
    logger.info(f"Found {len(customers)} customers")

    # Build SAR label: customer_id → 1 if had a serious case
    try:
        sar_cases = db.query(Case).filter(
            Case.status.in_(["escalated", "closed"])
        ).all()
        sar_customer_ids = set()
        for case in sar_cases:
            if hasattr(case, 'customer_id') and case.customer_id:
                sar_customer_ids.add(case.customer_id)
        logger.info(f"Found {len(sar_customer_ids)} customers with SAR/escalated cases")
    except Exception as e:
        logger.warning(f"Could not load cases: {e}. Using sanctions_flag as proxy.")
        sar_customer_ids = {c.id for c in customers if c.sanctions_flag or c.risk_level == "critical"}

    training_data = []
    labels = []
    skipped = 0

    for customer in customers:
        # Load transactions
        txns = db.query(Transaction).filter(
            Transaction.from_customer_id == customer.id
        ).order_by(Transaction.created_at.desc()).limit(500).all()

        # Load alerts
        alerts = db.query(Alert).filter(
            Alert.customer_id == customer.id
        ).order_by(Alert.created_at.desc()).limit(200).all()

        features = _extract_customer_features(customer, txns, alerts)
        if features is None:
            skipped += 1
            continue

        label = 1 if customer.id in sar_customer_ids else 0
        training_data.append(features)
        labels.append(label)

    logger.info(
        f"Training data built: {len(training_data)} samples "
        f"({sum(labels)} positive / {len(labels) - sum(labels)} negative), "
        f"{skipped} skipped"
    )
    return training_data, labels


def evaluate_model(model, X_test, y_test):
    """Print classification metrics."""
    try:
        from sklearn.metrics import classification_report, roc_auc_score
        import numpy as np

        predictions = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]

        print("\n" + "=" * 50)
        print("MODEL EVALUATION")
        print("=" * 50)
        print(classification_report(y_test, predictions, target_names=["Clean", "SAR"]))
        try:
            auc = roc_auc_score(y_test, proba)
            print(f"ROC-AUC Score: {auc:.4f}")
        except Exception:
            pass
        print("=" * 50)
    except Exception as e:
        logger.warning(f"Evaluation failed: {e}")


def train_and_save(output_path: str, min_positive_samples: int = 10):
    """Full training pipeline."""
    try:
        import pickle
        from sklearn.model_selection import train_test_split
        import numpy as np
    except ImportError:
        logger.error("Required packages missing. Run: pip install scikit-learn numpy")
        sys.exit(1)

    from database import SessionLocal
    from ml.risk_model import CustomerRiskModel, FEATURE_NAMES

    db = SessionLocal()
    try:
        training_data, labels = load_training_data(db)
    finally:
        db.close()

    if len(training_data) < 20:
        logger.error(f"Insufficient training data ({len(training_data)} samples). Need at least 20.")
        sys.exit(1)

    positive_count = sum(labels)
    if positive_count < min_positive_samples:
        logger.warning(
            f"Only {positive_count} positive samples (SAR cases). "
            f"Model may have poor recall. Consider lowering --min-samples or adding more data."
        )

    X = np.array([[d.get(f, 0.0) for f in FEATURE_NAMES] for d in training_data])
    y = np.array(labels)

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if positive_count >= 2 else None
    )

    logger.info(f"Training on {len(X_train)} samples, evaluating on {len(X_test)}")

    # Train
    model = CustomerRiskModel()
    success = model.train(training_data[:len(X_train)], labels[:len(X_train)])
    if not success:
        logger.error("Training failed")
        sys.exit(1)

    # Evaluate (using sklearn pipeline directly)
    evaluate_model(model.model, X_test, y_test)

    # Feature importances
    print("\nFEATURE IMPORTANCES:")
    sorted_features = sorted(model.feature_importances.items(), key=lambda x: x[1], reverse=True)
    for name, imp in sorted_features:
        bar = "█" * int(imp * 50)
        print(f"  {name:<30} {imp:.4f}  {bar}")

    # Save model
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(model, f)

    logger.info(f"Model saved to: {output_path}")
    print(f"\n✓ Model saved to: {output_path}")
    print(f"  Training samples: {len(training_data)}")
    print(f"  Positive (SAR):   {positive_count}")
    print(f"  Negative (clean): {len(labels) - positive_count}")


def main():
    parser = argparse.ArgumentParser(description="Train AML customer risk ML model")
    parser.add_argument("--output", default="backend/ml/models/customer_risk_model.pkl",
                        help="Output path for trained model")
    parser.add_argument("--min-samples", type=int, default=10,
                        help="Minimum positive (SAR) samples required")
    args = parser.parse_args()
    train_and_save(output_path=args.output, min_positive_samples=args.min_samples)


if __name__ == "__main__":
    main()
