"""
Compliance Report Generator CLI
==================================
Generates a plain-text or CSV compliance summary report for a given
date range. Useful for monthly compliance reviews, board reports, and
regulatory submissions.

Report includes:
  - Transaction volume and flagged transaction summary
  - Alert statistics by severity and status
  - Top 10 highest-risk customers
  - Sanctions screening summary
  - Open SAR cases

Usage:
    python scripts/generate_report.py                          # last 30 days
    python scripts/generate_report.py --days 90               # last 90 days
    python scripts/generate_report.py --from 2024-01-01 --to 2024-01-31
    python scripts/generate_report.py --format csv --output report.csv
    python scripts/generate_report.py --format text            # default
"""

import argparse
import csv
import sys
import os
from datetime import datetime, timedelta, timezone
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.transaction import Transaction
from models.alert import Alert
from models.customer import Customer
from models.case import Case
from sqlalchemy import func


def fetch_report_data(db, date_from: datetime, date_to: datetime) -> dict:
    """Fetch all stats needed for the report."""

    # Transaction stats
    total_txns = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at.between(date_from, date_to)
    ).scalar() or 0

    flagged_txns = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at.between(date_from, date_to),
        Transaction.flagged == True,
    ).scalar() or 0

    total_volume = db.query(func.sum(Transaction.amount)).filter(
        Transaction.created_at.between(date_from, date_to)
    ).scalar() or 0.0

    flagged_volume = db.query(func.sum(Transaction.amount)).filter(
        Transaction.created_at.between(date_from, date_to),
        Transaction.flagged == True,
    ).scalar() or 0.0

    # Alert stats
    alerts_by_severity = {}
    for sev in ("low", "medium", "high", "critical"):
        alerts_by_severity[sev] = db.query(func.count(Alert.id)).filter(
            Alert.created_at.between(date_from, date_to),
            Alert.severity == sev,
        ).scalar() or 0

    alerts_by_status = {}
    for status in ("open", "closed", "false_positive", "escalated"):
        alerts_by_status[status] = db.query(func.count(Alert.id)).filter(
            Alert.created_at.between(date_from, date_to),
            Alert.status == status,
        ).scalar() or 0

    # Top 10 risky customers
    top_customers = db.query(Customer).filter(
        Customer.risk_level.in_(["high", "critical"])
    ).order_by(Customer.risk_level.desc()).limit(10).all()

    # Customer risk breakdown
    risk_breakdown = {}
    for level in ("low", "medium", "high", "critical"):
        risk_breakdown[level] = db.query(func.count(Customer.id)).filter(
            Customer.risk_level == level
        ).scalar() or 0

    # PEP and sanctions
    pep_count = db.query(func.count(Customer.id)).filter(Customer.pep_status == True).scalar() or 0
    sanctioned_count = db.query(func.count(Customer.id)).filter(Customer.sanctions_flag == True).scalar() or 0

    # Open cases
    try:
        open_cases = db.query(func.count(Case.id)).filter(
            Case.status.in_(["open", "escalated"])
        ).scalar() or 0
    except Exception:
        open_cases = 0

    return {
        "period": {
            "from": date_from.strftime("%Y-%m-%d"),
            "to": date_to.strftime("%Y-%m-%d"),
        },
        "transactions": {
            "total": total_txns,
            "flagged": flagged_txns,
            "flag_rate": round(flagged_txns / total_txns * 100, 2) if total_txns else 0,
            "total_volume": round(total_volume, 2),
            "flagged_volume": round(flagged_volume, 2),
        },
        "alerts": {
            "by_severity": alerts_by_severity,
            "by_status": alerts_by_status,
            "total": sum(alerts_by_severity.values()),
        },
        "customers": {
            "risk_breakdown": risk_breakdown,
            "pep_count": pep_count,
            "sanctioned_count": sanctioned_count,
            "top_high_risk": [
                {
                    "name": c.full_name,
                    "number": c.customer_number,
                    "risk_level": c.risk_level,
                    "pep": c.pep_status,
                    "country": c.country or "—",
                }
                for c in top_customers
            ],
        },
        "cases": {
            "open": open_cases,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def format_text_report(data: dict) -> str:
    out = StringIO()
    w = out.write

    w("=" * 65 + "\n")
    w("         AML COMPLIANCE SUMMARY REPORT\n")
    w(f"         Period: {data['period']['from']} to {data['period']['to']}\n")
    w(f"         Generated: {data['generated_at'][:19]} UTC\n")
    w("=" * 65 + "\n\n")

    # Transactions
    t = data["transactions"]
    w("TRANSACTION ACTIVITY\n")
    w("─" * 40 + "\n")
    w(f"  Total transactions:    {t['total']:>10,}\n")
    w(f"  Flagged transactions:  {t['flagged']:>10,}  ({t['flag_rate']}%)\n")
    w(f"  Total volume:          ${t['total_volume']:>14,.2f}\n")
    w(f"  Flagged volume:        ${t['flagged_volume']:>14,.2f}\n\n")

    # Alerts
    a = data["alerts"]
    w("ALERT STATISTICS\n")
    w("─" * 40 + "\n")
    w(f"  Total alerts:          {a['total']:>10,}\n")
    w("  By severity:\n")
    for sev, cnt in a["by_severity"].items():
        w(f"    {sev.capitalize():<12}          {cnt:>6,}\n")
    w("  By status:\n")
    for status, cnt in a["by_status"].items():
        w(f"    {status.capitalize():<12}          {cnt:>6,}\n")
    w("\n")

    # Customers
    c = data["customers"]
    w("CUSTOMER RISK PROFILE\n")
    w("─" * 40 + "\n")
    for level, cnt in c["risk_breakdown"].items():
        w(f"  {level.capitalize():<12}              {cnt:>6,}\n")
    w(f"  PEP customers:         {c['pep_count']:>10,}\n")
    w(f"  Sanctioned customers:  {c['sanctioned_count']:>10,}\n\n")

    # Top high-risk
    if c["top_high_risk"]:
        w("TOP HIGH-RISK CUSTOMERS\n")
        w("─" * 40 + "\n")
        for cust in c["top_high_risk"]:
            pep_tag = " [PEP]" if cust["pep"] else ""
            w(f"  {cust['number']:<15} {cust['name']:<25} {cust['risk_level'].upper()}{pep_tag}\n")
        w("\n")

    # Cases
    w("INVESTIGATION CASES\n")
    w("─" * 40 + "\n")
    w(f"  Open / Escalated:      {data['cases']['open']:>10,}\n\n")

    w("=" * 65 + "\n")
    w("  END OF REPORT\n")
    w("=" * 65 + "\n")

    return out.getvalue()


def format_csv_report(data: dict) -> str:
    out = StringIO()
    writer = csv.writer(out)

    writer.writerow(["AML Compliance Report"])
    writer.writerow(["Period", f"{data['period']['from']} to {data['period']['to']}"])
    writer.writerow(["Generated", data["generated_at"][:19]])
    writer.writerow([])

    writer.writerow(["TRANSACTIONS"])
    writer.writerow(["Metric", "Value"])
    t = data["transactions"]
    writer.writerow(["Total Transactions", t["total"]])
    writer.writerow(["Flagged Transactions", t["flagged"]])
    writer.writerow(["Flag Rate (%)", t["flag_rate"]])
    writer.writerow(["Total Volume (USD)", t["total_volume"]])
    writer.writerow(["Flagged Volume (USD)", t["flagged_volume"]])
    writer.writerow([])

    writer.writerow(["ALERTS BY SEVERITY"])
    for sev, cnt in data["alerts"]["by_severity"].items():
        writer.writerow([sev.capitalize(), cnt])
    writer.writerow([])

    writer.writerow(["CUSTOMER RISK BREAKDOWN"])
    for level, cnt in data["customers"]["risk_breakdown"].items():
        writer.writerow([level.capitalize(), cnt])
    writer.writerow(["PEP Customers", data["customers"]["pep_count"]])
    writer.writerow(["Sanctioned Customers", data["customers"]["sanctioned_count"]])
    writer.writerow([])

    writer.writerow(["TOP HIGH-RISK CUSTOMERS"])
    writer.writerow(["Customer Number", "Name", "Risk Level", "PEP", "Country"])
    for cust in data["customers"]["top_high_risk"]:
        writer.writerow([cust["number"], cust["name"], cust["risk_level"], cust["pep"], cust["country"]])

    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Generate AML compliance report")
    parser.add_argument("--days",   type=int, default=30, help="Report period in days (default: 30)")
    parser.add_argument("--from",   dest="date_from", help="Start date YYYY-MM-DD")
    parser.add_argument("--to",     dest="date_to",   help="End date YYYY-MM-DD")
    parser.add_argument("--format", choices=["text", "csv"], default="text", help="Output format")
    parser.add_argument("--output", help="Write to file instead of stdout")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.date_from and args.date_to:
        date_from = datetime.strptime(args.date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        date_to   = datetime.strptime(args.date_to,   "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        date_to   = now
        date_from = now - timedelta(days=args.days)

    db = SessionLocal()
    try:
        data = fetch_report_data(db, date_from, date_to)
    finally:
        db.close()

    if args.format == "csv":
        output = format_csv_report(data)
    else:
        output = format_text_report(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
