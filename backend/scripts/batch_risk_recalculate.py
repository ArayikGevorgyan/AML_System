"""
Batch Risk Score Recalculation CLI
=====================================
Iterates over all customers (or a specific one) and recalculates
their risk score using the risk scoring service. Logs changed scores
and optionally commits changes.

Arguments:
  --dry-run         Preview changes without writing to DB
  --min-change      Only commit if score changed by at least this amount
  --customer-id     Recalculate only this specific customer ID
  --verbose         Print every customer, not just changed ones

Usage:
    python scripts/batch_risk_recalculate.py
    python scripts/batch_risk_recalculate.py --dry-run
    python scripts/batch_risk_recalculate.py --min-change 0.1
    python scripts/batch_risk_recalculate.py --customer-id 42

Exit code 0 on success, 1 on error.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.customer import Customer


# ---------------------------------------------------------------------------
# Risk score computation
# ---------------------------------------------------------------------------

RISK_SCORE_MAP = {"low": 0.10, "medium": 0.40, "high": 0.70, "critical": 0.90}
RISK_LEVEL_THRESHOLDS = [
    (0.75, "critical"),
    (0.55, "high"),
    (0.30, "medium"),
    (0.00, "low"),
]


def compute_risk_score(customer, db) -> float:
    """
    Compute a risk score (0.0–1.0) for a customer from available signals.

    Signal contributions:
      - Current risk level base score  (0.10 – 0.90)
      - PEP bonus                      (+0.10)
      - Sanctions flag                 (+0.20)
      - Recent alert count             (+0.05 per alert, max +0.20)
      - High-risk nationality          (+0.05)

    Args:
        customer: Customer ORM object.
        db:       SQLAlchemy session.

    Returns:
        Risk score float in [0.0, 1.0].
    """
    from models.alert import Alert

    base = RISK_SCORE_MAP.get(customer.risk_level or "low", 0.10)
    bonus = 0.0

    if customer.pep_status:
        bonus += 0.10

    if customer.sanctions_flag:
        bonus += 0.20

    # Recent alert count (last 30 days signal)
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        alert_count = db.query(Alert).filter(
            Alert.customer_id == customer.id,
            Alert.created_at >= cutoff,
            Alert.status != "false_positive",
        ).count()
        bonus += min(alert_count * 0.05, 0.20)
    except Exception:
        pass

    # High-risk nationalities
    HIGH_RISK_NATS = {"IR", "KP", "SY", "AF", "MM", "YE", "SO"}
    if customer.nationality and customer.nationality.upper() in HIGH_RISK_NATS:
        bonus += 0.05

    return min(round(base + bonus, 3), 1.0)


def score_to_risk_level(score: float) -> str:
    """Map a float score to a risk level string."""
    for threshold, level in RISK_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "low"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch recalculate customer risk scores.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without committing to the database",
    )
    parser.add_argument(
        "--min-change",
        type=float,
        default=0.0,
        dest="min_change",
        help="Minimum score change required to commit (default: any change)",
    )
    parser.add_argument(
        "--customer-id",
        type=int,
        default=None,
        dest="customer_id",
        help="Process only this specific customer ID",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print status for every customer, not just changed ones",
    )
    return parser


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

def print_progress(current: int, total: int, changed: int, dry_run: bool) -> None:
    """Print a progress indicator with stats."""
    pct = int(current / total * 100)
    bar_len = 35
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    mode = "[DRY RUN] " if dry_run else ""
    print(
        f"\r  {mode}[{bar}] {pct}%  processed={current}/{total}  changed={changed}",
        end="",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_customer(customer, db, min_change: float, dry_run: bool) -> dict:
    """
    Compute new risk score and optionally update the customer record.

    Returns:
        Dict with keys: customer_id, old_score, new_score, old_level,
        new_level, changed, committed.
    """
    old_level = customer.risk_level or "low"
    old_score = RISK_SCORE_MAP.get(old_level, 0.10)
    new_score = compute_risk_score(customer, db)
    new_level = score_to_risk_level(new_score)

    delta = abs(new_score - old_score)
    changed = delta >= 0.001 or new_level != old_level
    committed = False

    if changed and delta >= min_change and not dry_run:
        customer.risk_level = new_level
        committed = True

    return {
        "customer_id": customer.id,
        "customer_number": customer.customer_number,
        "full_name": customer.full_name,
        "old_score": old_score,
        "new_score": new_score,
        "old_level": old_level,
        "new_level": new_level,
        "delta": round(delta, 3),
        "changed": changed,
        "committed": committed,
    }


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  Batch Risk Score Recalculation")
    if args.dry_run:
        print(f"  Mode: DRY RUN (no changes will be committed)")
    else:
        print(f"  Mode: LIVE")
    if args.customer_id:
        print(f"  Target: Customer ID {args.customer_id}")
    else:
        print(f"  Target: All customers")
    if args.min_change > 0:
        print(f"  Min change threshold: {args.min_change:.3f}")
    print(f"{'='*55}\n")

    db = SessionLocal()

    try:
        # Fetch target customers
        if args.customer_id:
            customers = db.query(Customer).filter(Customer.id == args.customer_id).all()
            if not customers:
                print(f"[ERROR] Customer ID {args.customer_id} not found.")
                return 1
        else:
            customers = db.query(Customer).order_by(Customer.id).all()

        total = len(customers)
        print(f"[batch_risk] Processing {total} customer(s) ...")

        changed_list = []
        skipped = 0
        committed_count = 0

        for i, customer in enumerate(customers):
            result = process_customer(customer, db, args.min_change, args.dry_run)

            if result["changed"]:
                changed_list.append(result)
                if result["committed"]:
                    committed_count += 1
            else:
                skipped += 1

            if args.verbose:
                print(
                    f"  [{result['customer_number']}] "
                    f"{result['old_level']} ({result['old_score']:.2f}) → "
                    f"{result['new_level']} ({result['new_score']:.2f})"
                    + (" [CHANGED]" if result["changed"] else "")
                )
            elif total >= 20 and (i + 1) % max(1, total // 20) == 0:
                print_progress(i + 1, total, len(changed_list), args.dry_run)

        if not args.dry_run and committed_count > 0:
            db.commit()
            print(f"\n[batch_risk] Committed {committed_count} changes to database.")

        # Print changed records
        print(f"\n\n{'='*60}")
        print(f"  Recalculation Complete")
        print(f"{'='*60}")
        print(f"  Customers processed:  {total}")
        print(f"  Scores changed:       {len(changed_list)}")
        print(f"  Committed to DB:      {committed_count if not args.dry_run else 'N/A (dry run)'}")
        print(f"  Unchanged / skipped:  {skipped}")

        if changed_list:
            print(f"\n  Changed customers:")
            print(f"  {'ID':<8} {'Number':<15} {'Name':<25} {'Old':<10} {'New':<10} {'Delta'}")
            print(f"  {'-'*8} {'-'*15} {'-'*25} {'-'*10} {'-'*10} {'-'*6}")
            for r in changed_list[:50]:  # cap output at 50
                print(
                    f"  {r['customer_id']:<8} {r['customer_number']:<15} "
                    f"{r['full_name'][:24]:<25} "
                    f"{r['old_level']:<10} {r['new_level']:<10} "
                    f"{r['delta']:+.3f}"
                )
            if len(changed_list) > 50:
                print(f"  ... and {len(changed_list) - 50} more")

        print(f"{'='*60}\n")
        return 0

    except Exception as exc:
        print(f"\n[batch_risk] ERROR: {exc}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
