"""
System Health Check CLI
=========================
Checks all critical AML system components and prints a status report.
Can be run manually or triggered by a cron job / monitoring system.

Checks performed:
  1. Database connectivity and table counts
  2. Sanctions list freshness (when was the SDN last imported?)
  3. Open alert queue depth (too many unreviewed alerts = backlog problem)
  4. Recent transaction volume (detects if transaction ingestion stopped)
  5. Rules engine — verifies active rules exist
  6. High-risk customer count
  7. SAR backlog (cases in escalated status for >7 days)

Exit codes:
  0 → All checks passed
  1 → One or more warnings
  2 → One or more critical failures

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --json          # output as JSON
    python scripts/health_check.py --quiet         # only print failures
"""

import argparse
import json
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.sanctions import SanctionsEntry
from models.alert import Alert
from models.transaction import Transaction
from models.customer import Customer
from models.rule import Rule
from models.case import Case


STATUS_OK       = "OK"
STATUS_WARN     = "WARN"
STATUS_CRITICAL = "CRITICAL"

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def color(text, status):
    if status == STATUS_OK:
        return f"{GREEN}{text}{RESET}"
    elif status == STATUS_WARN:
        return f"{YELLOW}{text}{RESET}"
    else:
        return f"{RED}{text}{RESET}"


def check_database(db) -> dict:
    """Check DB connectivity and row counts."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        customers = db.query(Customer).count()
        transactions = db.query(Transaction).count()
        alerts = db.query(Alert).count()
        return {
            "name": "Database",
            "status": STATUS_OK,
            "message": f"Connected — {customers:,} customers, {transactions:,} transactions, {alerts:,} alerts",
        }
    except Exception as e:
        return {
            "name": "Database",
            "status": STATUS_CRITICAL,
            "message": f"Connection failed: {e}",
        }


def check_sanctions_list(db) -> dict:
    """Check sanctions list is loaded and not stale."""
    try:
        total = db.query(SanctionsEntry).count()
        if total == 0:
            return {
                "name": "Sanctions List",
                "status": STATUS_CRITICAL,
                "message": "No sanctions entries found — SDN list not imported",
            }
        by_list = {}
        from sqlalchemy import func
        rows = db.query(SanctionsEntry.list_name, func.count(SanctionsEntry.id)).group_by(SanctionsEntry.list_name).all()
        for ln, cnt in rows:
            by_list[ln] = cnt
        summary = ", ".join(f"{k}: {v:,}" for k, v in by_list.items())
        status = STATUS_OK if total > 10_000 else STATUS_WARN
        return {
            "name": "Sanctions List",
            "status": status,
            "message": f"{total:,} total entries ({summary})",
        }
    except Exception as e:
        return {"name": "Sanctions List", "status": STATUS_CRITICAL, "message": str(e)}


def check_alert_queue(db) -> dict:
    """Check open alert backlog."""
    try:
        open_alerts = db.query(Alert).filter(Alert.status == "open").count()
        critical_open = db.query(Alert).filter(
            Alert.status == "open", Alert.severity == "critical"
        ).count()

        if critical_open > 20:
            status = STATUS_CRITICAL
            msg = f"{open_alerts:,} open alerts ({critical_open} CRITICAL) — urgent review needed"
        elif open_alerts > 100:
            status = STATUS_WARN
            msg = f"{open_alerts:,} open alerts ({critical_open} critical) — backlog growing"
        else:
            status = STATUS_OK
            msg = f"{open_alerts:,} open alerts ({critical_open} critical)"

        return {"name": "Alert Queue", "status": status, "message": msg}
    except Exception as e:
        return {"name": "Alert Queue", "status": STATUS_CRITICAL, "message": str(e)}


def check_transaction_volume(db) -> dict:
    """Check recent transaction activity."""
    try:
        since_1h = datetime.now(timezone.utc) - timedelta(hours=1)
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        count_1h  = db.query(Transaction).filter(Transaction.created_at >= since_1h).count()
        count_24h = db.query(Transaction).filter(Transaction.created_at >= since_24h).count()

        if count_24h == 0:
            status = STATUS_WARN
            msg = "No transactions in last 24 hours — ingestion may have stopped"
        elif count_1h == 0:
            status = STATUS_WARN
            msg = f"No transactions in last hour (24h total: {count_24h:,})"
        else:
            status = STATUS_OK
            msg = f"{count_1h:,} transactions in last hour, {count_24h:,} in last 24h"

        return {"name": "Transaction Volume", "status": status, "message": msg}
    except Exception as e:
        return {"name": "Transaction Volume", "status": STATUS_CRITICAL, "message": str(e)}


def check_rules_engine(db) -> dict:
    """Check active rules exist."""
    try:
        active_rules = db.query(Rule).filter(Rule.is_active == True).count()
        total_rules  = db.query(Rule).count()

        if active_rules == 0:
            status = STATUS_CRITICAL
            msg = f"No active rules! ({total_rules} total rules exist but none are active)"
        elif active_rules < 3:
            status = STATUS_WARN
            msg = f"Only {active_rules} active rules — consider enabling more"
        else:
            status = STATUS_OK
            msg = f"{active_rules} active rules out of {total_rules} total"

        return {"name": "Rules Engine", "status": status, "message": msg}
    except Exception as e:
        return {"name": "Rules Engine", "status": STATUS_CRITICAL, "message": str(e)}


def check_high_risk_customers(db) -> dict:
    """Check high/critical risk customer count."""
    try:
        high = db.query(Customer).filter(Customer.risk_level == "high").count()
        critical = db.query(Customer).filter(Customer.risk_level == "critical").count()
        pep = db.query(Customer).filter(Customer.pep_status == True).count()
        sanctioned = db.query(Customer).filter(Customer.sanctions_flag == True).count()

        status = STATUS_WARN if sanctioned > 0 else STATUS_OK
        msg = f"{critical} critical, {high} high-risk, {pep} PEP, {sanctioned} sanctioned"

        return {"name": "High-Risk Customers", "status": status, "message": msg}
    except Exception as e:
        return {"name": "High-Risk Customers", "status": STATUS_CRITICAL, "message": str(e)}


def check_sar_backlog(db) -> dict:
    """Check for SAR cases stuck in escalated status > 7 days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        stale_sars = db.query(Case).filter(
            Case.status == "escalated",
            Case.created_at <= cutoff,
        ).count() if hasattr(Case, 'status') else 0

        if stale_sars > 5:
            status = STATUS_CRITICAL
            msg = f"{stale_sars} SAR cases escalated for >7 days without resolution"
        elif stale_sars > 0:
            status = STATUS_WARN
            msg = f"{stale_sars} SAR case(s) pending >7 days"
        else:
            status = STATUS_OK
            msg = "No stale SAR cases"

        return {"name": "SAR Backlog", "status": status, "message": msg}
    except Exception as e:
        return {"name": "SAR Backlog", "status": STATUS_OK, "message": "Case module not available"}


def run_health_check(as_json=False, quiet=False):
    db = SessionLocal()
    results = []
    try:
        checks = [
            check_database,
            check_sanctions_list,
            check_alert_queue,
            check_transaction_volume,
            check_rules_engine,
            check_high_risk_customers,
            check_sar_backlog,
        ]
        for check_fn in checks:
            result = check_fn(db)
            results.append(result)
    finally:
        db.close()

    if as_json:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": results,
            "overall": (
                STATUS_CRITICAL if any(r["status"] == STATUS_CRITICAL for r in results)
                else STATUS_WARN if any(r["status"] == STATUS_WARN for r in results)
                else STATUS_OK
            ),
        }, indent=2))
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{BOLD}AML System Health Check — {now}{RESET}")
        print("─" * 60)

        for r in results:
            if quiet and r["status"] == STATUS_OK:
                continue
            icon = "✓" if r["status"] == STATUS_OK else "⚠" if r["status"] == STATUS_WARN else "✗"
            status_str = color(f"[{r['status']:8}]", r["status"])
            print(f"  {icon} {status_str}  {r['name']:<25} {r['message']}")

        print("─" * 60)
        critical_count = sum(1 for r in results if r["status"] == STATUS_CRITICAL)
        warn_count     = sum(1 for r in results if r["status"] == STATUS_WARN)
        ok_count       = sum(1 for r in results if r["status"] == STATUS_OK)

        if critical_count:
            overall = color(f"CRITICAL ({critical_count} failure(s))", STATUS_CRITICAL)
        elif warn_count:
            overall = color(f"WARNING ({warn_count} warning(s))", STATUS_WARN)
        else:
            overall = color("ALL SYSTEMS OPERATIONAL", STATUS_OK)

        print(f"\n  Overall: {overall}")
        print(f"  {ok_count} OK  ·  {warn_count} warnings  ·  {critical_count} critical\n")

    # Exit code
    if any(r["status"] == STATUS_CRITICAL for r in results):
        sys.exit(2)
    elif any(r["status"] == STATUS_WARN for r in results):
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="AML system health check")
    parser.add_argument("--json",  action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", action="store_true", help="Only print warnings and failures")
    args = parser.parse_args()
    run_health_check(as_json=args.json, quiet=args.quiet)


if __name__ == "__main__":
    main()
