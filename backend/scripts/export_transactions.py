"""
Export Transactions CLI
========================
Exports transaction records from the AML system to CSV or JSON.

Filters:
  --days          Export transactions from last N days
  --min-amount    Minimum amount filter
  --flagged-only  Export only flagged (suspicious) transactions
  --format        Output format: csv (default) or json
  --output        Output file path

Usage:
    python scripts/export_transactions.py --output transactions.csv
    python scripts/export_transactions.py --days 30 --flagged-only --format json
    python scripts/export_transactions.py --min-amount 10000 --output large.csv

Exit code 0 on success, 1 on error.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.transaction import Transaction
from models.customer import Customer
from models.account import Account


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export AML transaction records to CSV or JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output", "-o",
        default="transactions_export.csv",
        help="Output file path",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Export transactions from last N days",
    )
    parser.add_argument(
        "--min-amount",
        type=float,
        default=None,
        dest="min_amount",
        help="Minimum transaction amount filter",
    )
    parser.add_argument(
        "--flagged-only",
        action="store_true",
        default=False,
        dest="flagged_only",
        help="Export only flagged transactions",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        dest="fmt",
    )
    return parser


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

EXPORT_FIELDS = [
    "id",
    "reference",
    "from_customer_id",
    "from_customer_name",
    "from_account_id",
    "to_customer_id",
    "to_customer_name",
    "to_account_id",
    "amount",
    "currency",
    "transaction_type",
    "status",
    "description",
    "originating_country",
    "destination_country",
    "is_international",
    "channel",
    "risk_score",
    "flagged",
    "created_at",
]


def txn_to_dict(
    txn: Transaction,
    from_name: str,
    to_name: str,
) -> dict:
    """Convert a Transaction ORM object to an export-friendly dict."""
    return {
        "id": txn.id,
        "reference": txn.reference,
        "from_customer_id": txn.from_customer_id or "",
        "from_customer_name": from_name,
        "from_account_id": txn.from_account_id or "",
        "to_customer_id": txn.to_customer_id or "",
        "to_customer_name": to_name,
        "to_account_id": txn.to_account_id or "",
        "amount": txn.amount,
        "currency": txn.currency,
        "transaction_type": txn.transaction_type,
        "status": txn.status,
        "description": txn.description or "",
        "originating_country": txn.originating_country or "",
        "destination_country": txn.destination_country or "",
        "is_international": "yes" if txn.is_international else "no",
        "channel": txn.channel or "",
        "risk_score": txn.risk_score or 0.0,
        "flagged": "yes" if txn.flagged else "no",
        "created_at": txn.created_at.isoformat() if txn.created_at else "",
    }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def fetch_transactions(db, days=None, min_amount=None, flagged_only=False):
    """
    Fetch transactions from the database with optional filters.

    Args:
        db:           SQLAlchemy session.
        days:         If set, only return transactions from last N days.
        min_amount:   Minimum amount threshold.
        flagged_only: If True, only return flagged transactions.

    Returns:
        List of Transaction ORM objects.
    """
    query = db.query(Transaction)

    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(Transaction.created_at >= cutoff)

    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)

    if flagged_only:
        query = query.filter(Transaction.flagged == True)

    return query.order_by(Transaction.created_at.desc()).all()


def build_customer_map(db, transactions):
    """
    Build a customer_id → customer name lookup dict.

    Args:
        db:           SQLAlchemy session.
        transactions: List of Transaction objects.

    Returns:
        Dict mapping customer_id → full_name.
    """
    ids = set()
    for t in transactions:
        if t.from_customer_id:
            ids.add(t.from_customer_id)
        if t.to_customer_id:
            ids.add(t.to_customer_id)

    if not ids:
        return {}

    customers = db.query(Customer).filter(Customer.id.in_(list(ids))).all()
    return {c.id: c.full_name for c in customers}


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

def export_csv(rows: list, output_path: str) -> None:
    """Write transaction rows to CSV."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export_json(rows: list, output_path: str) -> None:
    """Write transaction rows to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(rows),
                "transactions": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_progress(current: int, total: int) -> None:
    """Print a manual progress bar to stdout."""
    pct = int(current / total * 100)
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = "=" * filled + "-" * (bar_len - filled)
    print(f"\r  [{bar}] {pct}%  ({current}/{total})", end="", flush=True)


def print_summary(rows: list, args, output_path: str) -> None:
    """Print export summary."""
    total_amount = sum(float(r.get("amount", 0)) for r in rows)
    flagged = sum(1 for r in rows if r.get("flagged") == "yes")
    intl = sum(1 for r in rows if r.get("is_international") == "yes")

    type_counts = {}
    for r in rows:
        tt = r.get("transaction_type", "unknown")
        type_counts[tt] = type_counts.get(tt, 0) + 1

    print(f"\n\n{'='*55}")
    print(f"  Transaction Export Summary")
    print(f"{'='*55}")
    print(f"  Total records:       {len(rows)}")
    print(f"  Total volume:        ${total_amount:,.2f}")
    print(f"  Flagged:             {flagged}")
    print(f"  International:       {intl}")
    print(f"  By type:             {type_counts}")
    if args.days:
        print(f"  Days filter:         last {args.days} days")
    if args.min_amount:
        print(f"  Min amount filter:   ${args.min_amount:,.2f}")
    if args.flagged_only:
        print(f"  Flagged only:        True")
    print(f"  Format:              {args.fmt.upper()}")
    print(f"  Output file:         {output_path}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    print("[export_transactions] Connecting to database ...")
    db = SessionLocal()

    try:
        print("[export_transactions] Fetching transactions ...")
        transactions = fetch_transactions(
            db,
            days=args.days,
            min_amount=args.min_amount,
            flagged_only=args.flagged_only,
        )

        if not transactions:
            print("[export_transactions] No transactions matched the specified filters.")
            return 0

        print(f"[export_transactions] Building customer lookup for {len(transactions)} records ...")
        customer_map = build_customer_map(db, transactions)

        rows = []
        print("[export_transactions] Processing records ...")
        for i, txn in enumerate(transactions):
            from_name = customer_map.get(txn.from_customer_id, "") if txn.from_customer_id else ""
            to_name = customer_map.get(txn.to_customer_id, "") if txn.to_customer_id else ""
            rows.append(txn_to_dict(txn, from_name, to_name))

            if len(transactions) >= 100 and (i + 1) % 50 == 0:
                print_progress(i + 1, len(transactions))

        if len(transactions) >= 100:
            print_progress(len(transactions), len(transactions))

        output_path = args.output
        if args.fmt == "json" and not output_path.endswith(".json"):
            output_path = output_path.rsplit(".", 1)[0] + ".json"

        if args.fmt == "csv":
            export_csv(rows, output_path)
        else:
            export_json(rows, output_path)

        print_summary(rows, args, output_path)
        print(f"[export_transactions] Export complete: {output_path}")
        return 0

    except Exception as exc:
        print(f"\n[export_transactions] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
