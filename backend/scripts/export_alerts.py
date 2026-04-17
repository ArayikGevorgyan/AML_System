"""
Export Alerts CLI
==================
Exports alert records from the AML system to CSV or JSON.

Filters:
  --status     Filter by status (open/closed/false_positive/escalated)
  --severity   Filter by severity (low/medium/high/critical)
  --days       Export alerts from the last N days (default: all)
  --format     Output format: csv (default) or json
  --output     Output file path (default: alerts_export.csv)

Usage:
    python scripts/export_alerts.py --output alerts.csv
    python scripts/export_alerts.py --status open --severity critical --format json
    python scripts/export_alerts.py --days 30 --output recent_alerts.csv

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
from models.alert import Alert
from models.customer import Customer
from models.rule import Rule


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export AML alerts to CSV or JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output", "-o",
        default="alerts_export.csv",
        help="Output file path",
    )
    parser.add_argument(
        "--status",
        choices=["open", "closed", "false_positive", "escalated", "under_review"],
        default=None,
        help="Filter by alert status",
    )
    parser.add_argument(
        "--severity",
        choices=["low", "medium", "high", "critical"],
        default=None,
        help="Filter by alert severity",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Export alerts from last N days (default: all time)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        dest="fmt",
        help="Output format: csv or json",
    )
    return parser


# ---------------------------------------------------------------------------
# Export fields
# ---------------------------------------------------------------------------

EXPORT_FIELDS = [
    "id",
    "alert_number",
    "customer_id",
    "customer_name",
    "customer_risk_level",
    "transaction_id",
    "rule_id",
    "rule_name",
    "severity",
    "status",
    "reason",
    "risk_score",
    "assigned_to",
    "created_at",
    "updated_at",
    "closed_at",
]


def alert_to_dict(
    alert: Alert,
    customer_name: str,
    customer_risk_level: str,
    rule_name: str,
) -> dict:
    """Convert an Alert ORM object to an export dict with enriched fields."""
    return {
        "id": alert.id,
        "alert_number": alert.alert_number,
        "customer_id": alert.customer_id,
        "customer_name": customer_name,
        "customer_risk_level": customer_risk_level,
        "transaction_id": alert.transaction_id or "",
        "rule_id": alert.rule_id or "",
        "rule_name": rule_name,
        "severity": alert.severity,
        "status": alert.status,
        "reason": alert.reason,
        "risk_score": alert.risk_score or 0.0,
        "assigned_to": alert.assigned_to or "",
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else "",
        "closed_at": alert.closed_at.isoformat() if alert.closed_at else "",
    }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def fetch_alerts(db, status=None, severity=None, days=None):
    """
    Fetch alerts with optional filters.

    Args:
        db:       SQLAlchemy session.
        status:   Optional status filter.
        severity: Optional severity filter.
        days:     If set, only return alerts created in the last N days.

    Returns:
        List of Alert ORM objects.
    """
    query = db.query(Alert)

    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(Alert.created_at >= cutoff)

    return query.order_by(Alert.created_at.desc()).all()


def build_lookup_maps(db, alerts):
    """
    Build customer and rule lookup maps for enriching alert records.

    Args:
        db:     SQLAlchemy session.
        alerts: List of Alert objects.

    Returns:
        Tuple (customer_map, rule_map) where each is a dict of id → object.
    """
    customer_ids = list({a.customer_id for a in alerts if a.customer_id})
    rule_ids = list({a.rule_id for a in alerts if a.rule_id})

    customers = {}
    if customer_ids:
        for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all():
            customers[c.id] = c

    rules = {}
    if rule_ids:
        for r in db.query(Rule).filter(Rule.id.in_(rule_ids)).all():
            rules[r.id] = r

    return customers, rules


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

def export_csv(rows: list, output_path: str) -> None:
    """Write alert rows to CSV."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export_json(rows: list, output_path: str) -> None:
    """Write alert rows to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(rows),
                "alerts": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(rows: list, args, output_path: str) -> None:
    """Print export summary to stdout."""
    severity_counts = {}
    status_counts = {}
    for row in rows:
        sev = row.get("severity", "unknown")
        sta = row.get("status", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        status_counts[sta] = status_counts.get(sta, 0) + 1

    print(f"\n{'='*55}")
    print(f"  Alert Export Summary")
    print(f"{'='*55}")
    print(f"  Total records:     {len(rows)}")
    if args.status:
        print(f"  Status filter:     {args.status}")
    if args.severity:
        print(f"  Severity filter:   {args.severity}")
    if args.days:
        print(f"  Days filter:       last {args.days} days")
    print(f"  By severity:       {severity_counts}")
    print(f"  By status:         {status_counts}")
    print(f"  Format:            {args.fmt.upper()}")
    print(f"  Output file:       {output_path}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args()

    print("[export_alerts] Connecting to database ...")
    db = SessionLocal()

    try:
        print("[export_alerts] Fetching alerts ...")
        alerts = fetch_alerts(db, status=args.status, severity=args.severity, days=args.days)

        if not alerts:
            print("[export_alerts] No alerts matched the specified filters.")
            return 0

        print(f"[export_alerts] Enriching {len(alerts)} alerts with customer/rule data ...")
        customers, rules = build_lookup_maps(db, alerts)

        rows = []
        for i, alert in enumerate(alerts):
            customer = customers.get(alert.customer_id)
            rule = rules.get(alert.rule_id) if alert.rule_id else None
            rows.append(alert_to_dict(
                alert=alert,
                customer_name=customer.full_name if customer else f"Customer {alert.customer_id}",
                customer_risk_level=customer.risk_level if customer else "unknown",
                rule_name=rule.name if rule else "N/A",
            ))

            if (i + 1) % 100 == 0:
                pct = int((i + 1) / len(alerts) * 100)
                print(f"  Progress: {pct}% ({i+1}/{len(alerts)})")

        output_path = args.output
        if args.fmt == "json" and not output_path.endswith(".json"):
            output_path = output_path.rsplit(".", 1)[0] + ".json"

        if args.fmt == "csv":
            export_csv(rows, output_path)
        else:
            export_json(rows, output_path)

        print_summary(rows, args, output_path)
        print(f"[export_alerts] Export complete: {output_path}")
        return 0

    except Exception as exc:
        print(f"[export_alerts] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
