"""
Export Customers CLI
======================
Exports customer records from the AML system to CSV or JSON.

Filters:
  --risk-level     Filter by risk level (low/medium/high/critical)
  --pep-only       Export only Politically Exposed Persons
  --sanctioned-only Export only customers with active sanctions flags
  --format         Output format: csv (default) or json
  --output         Output file path (default: customers_export.csv)

Usage:
    python scripts/export_customers.py --output customers.csv
    python scripts/export_customers.py --risk-level high --format json
    python scripts/export_customers.py --pep-only --output pep_customers.csv
    python scripts/export_customers.py --sanctioned-only --format json

Exit code 0 on success, 1 on error.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.customer import Customer


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export AML system customers to CSV or JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output", "-o",
        default="customers_export.csv",
        help="Output file path (default: customers_export.csv)",
    )
    parser.add_argument(
        "--risk-level",
        choices=["low", "medium", "high", "critical"],
        default=None,
        help="Filter by risk level",
    )
    parser.add_argument(
        "--pep-only",
        action="store_true",
        default=False,
        help="Export only Politically Exposed Persons",
    )
    parser.add_argument(
        "--sanctioned-only",
        action="store_true",
        default=False,
        help="Export only customers with sanctions flags",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        dest="fmt",
        help="Output format: csv or json (default: csv)",
    )
    return parser


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

EXPORT_FIELDS = [
    "id",
    "customer_number",
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "nationality",
    "id_type",
    "id_number",
    "address",
    "country",
    "risk_level",
    "pep_status",
    "sanctions_flag",
    "occupation",
    "annual_income",
    "source_of_funds",
    "created_at",
    "updated_at",
]


def customer_to_dict(customer: Customer) -> dict:
    """Convert a Customer ORM object to an export-friendly dict."""
    return {
        "id": customer.id,
        "customer_number": customer.customer_number,
        "full_name": customer.full_name,
        "email": customer.email or "",
        "phone": customer.phone or "",
        "date_of_birth": str(customer.date_of_birth) if customer.date_of_birth else "",
        "nationality": customer.nationality or "",
        "id_type": customer.id_type or "",
        "id_number": customer.id_number or "",
        "address": customer.address or "",
        "country": customer.country or "",
        "risk_level": customer.risk_level,
        "pep_status": "yes" if customer.pep_status else "no",
        "sanctions_flag": "yes" if customer.sanctions_flag else "no",
        "occupation": customer.occupation or "",
        "annual_income": customer.annual_income or "",
        "source_of_funds": customer.source_of_funds or "",
        "created_at": customer.created_at.isoformat() if customer.created_at else "",
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else "",
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def fetch_customers(db, risk_level=None, pep_only=False, sanctioned_only=False):
    """
    Fetch customers from the database with optional filters.

    Args:
        db:              SQLAlchemy session.
        risk_level:      Optional risk level filter string.
        pep_only:        If True, return only PEP customers.
        sanctioned_only: If True, return only customers with sanctions flag.

    Returns:
        List of Customer ORM objects.
    """
    query = db.query(Customer)

    if risk_level:
        query = query.filter(Customer.risk_level == risk_level)

    if pep_only:
        query = query.filter(Customer.pep_status == True)

    if sanctioned_only:
        query = query.filter(Customer.sanctions_flag == True)

    return query.order_by(Customer.id).all()


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

def export_csv(customers, output_path: str) -> None:
    """Write customer records to a CSV file."""
    rows = [customer_to_dict(c) for c in customers]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export_json(customers, output_path: str) -> None:
    """Write customer records to a JSON file."""
    rows = [customer_to_dict(c) for c in customers]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(rows),
                "customers": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

def print_summary(customers, args, output_path: str) -> None:
    """Print an export summary to stdout."""
    filters = []
    if args.risk_level:
        filters.append(f"risk_level={args.risk_level}")
    if args.pep_only:
        filters.append("pep_only=True")
    if args.sanctioned_only:
        filters.append("sanctioned_only=True")

    filter_str = ", ".join(filters) if filters else "none"

    risk_counts = {}
    for c in customers:
        risk_counts[c.risk_level] = risk_counts.get(c.risk_level, 0) + 1
    pep_count = sum(1 for c in customers if c.pep_status)
    sanc_count = sum(1 for c in customers if c.sanctions_flag)

    print(f"\n{'='*50}")
    print(f"  Customer Export Summary")
    print(f"{'='*50}")
    print(f"  Filters applied:  {filter_str}")
    print(f"  Total records:    {len(customers)}")
    print(f"  Risk breakdown:   {risk_counts}")
    print(f"  PEP customers:    {pep_count}")
    print(f"  Sanctioned:       {sanc_count}")
    print(f"  Format:           {args.fmt.upper()}")
    print(f"  Output file:      {output_path}")
    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args()

    print(f"[export_customers] Connecting to database ...")
    db = SessionLocal()

    try:
        print(f"[export_customers] Fetching customers ...")
        customers = fetch_customers(
            db,
            risk_level=args.risk_level,
            pep_only=args.pep_only,
            sanctioned_only=args.sanctioned_only,
        )

        if not customers:
            print("[export_customers] No customers matched the specified filters.")
            return 0

        print(f"[export_customers] Found {len(customers)} customers. Exporting ...")

        output_path = args.output
        if args.fmt == "json" and not output_path.endswith(".json"):
            output_path = output_path.rsplit(".", 1)[0] + ".json"

        if args.fmt == "csv":
            export_csv(customers, output_path)
        else:
            export_json(customers, output_path)

        print_summary(customers, args, output_path)
        print(f"[export_customers] Export complete: {output_path}")
        return 0

    except Exception as exc:
        print(f"[export_customers] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
