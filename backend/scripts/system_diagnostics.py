"""
System Diagnostics CLI
========================
Checks all critical AML system components and prints a colored status report.
Covers: DB connection, table counts, sanctions data, rules loaded,
recent alerts, backend health, dependency versions.

Usage:
    python scripts/system_diagnostics.py
    python scripts/system_diagnostics.py --json      # JSON output
    python scripts/system_diagnostics.py --no-color  # plain text

Exit codes:
  0 → All checks passed
  1 → One or more warnings
  2 → One or more critical failures
"""

import argparse
import json
import os
import sys
import importlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
CYAN = "\033[96m"


def _c(text: str, color: str, use_color: bool) -> str:
    return f"{color}{text}{RESET}" if use_color else text


def check_mark(use_color: bool) -> str:
    return _c("✓", GREEN, use_color)


def warn_mark(use_color: bool) -> str:
    return _c("⚠", YELLOW, use_color)


def fail_mark(use_color: bool) -> str:
    return _c("✗", RED, use_color)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_db_connection(use_color: bool) -> dict:
    """Check database connectivity and return table record counts."""
    try:
        from database import SessionLocal
        db = SessionLocal()

        from models.customer import Customer
        from models.transaction import Transaction
        from models.alert import Alert
        from models.case import Case
        from models.rule import Rule

        counts = {
            "customers": db.query(Customer).count(),
            "transactions": db.query(Transaction).count(),
            "alerts": db.query(Alert).count(),
            "cases": db.query(Case).count(),
            "rules": db.query(Rule).count(),
        }
        db.close()

        return {
            "name": "Database Connection",
            "status": "ok",
            "mark": check_mark(use_color),
            "detail": f"Connected. Records: {counts}",
            "data": counts,
        }
    except Exception as e:
        return {
            "name": "Database Connection",
            "status": "critical",
            "mark": fail_mark(use_color),
            "detail": f"FAILED: {e}",
        }


def check_sanctions_data(use_color: bool) -> dict:
    """Verify sanctions data is loaded."""
    try:
        from database import SessionLocal
        from models.sanctions import SanctionsEntry

        db = SessionLocal()
        count = db.query(SanctionsEntry).count()
        db.close()

        if count == 0:
            return {
                "name": "Sanctions Data",
                "status": "warning",
                "mark": warn_mark(use_color),
                "detail": "No sanctions entries found. Run import_sanctions.py.",
                "count": 0,
            }

        return {
            "name": "Sanctions Data",
            "status": "ok",
            "mark": check_mark(use_color),
            "detail": f"{count:,} sanctions entries loaded",
            "count": count,
        }
    except Exception as e:
        return {
            "name": "Sanctions Data",
            "status": "warning",
            "mark": warn_mark(use_color),
            "detail": f"Could not check: {e}",
        }


def check_rules_loaded(use_color: bool) -> dict:
    """Verify AML rules are loaded and active."""
    try:
        from database import SessionLocal
        from models.rule import Rule

        db = SessionLocal()
        total = db.query(Rule).count()
        active = db.query(Rule).filter(Rule.is_active == True).count()
        db.close()

        if total == 0:
            return {
                "name": "AML Rules",
                "status": "critical",
                "mark": fail_mark(use_color),
                "detail": "No rules found. Run seed_data.py.",
                "total": 0,
                "active": 0,
            }

        if active == 0:
            return {
                "name": "AML Rules",
                "status": "warning",
                "mark": warn_mark(use_color),
                "detail": f"{total} rules exist but NONE are active.",
                "total": total,
                "active": active,
            }

        return {
            "name": "AML Rules",
            "status": "ok",
            "mark": check_mark(use_color),
            "detail": f"{active} active rules (out of {total} total)",
            "total": total,
            "active": active,
        }
    except Exception as e:
        return {
            "name": "AML Rules",
            "status": "critical",
            "mark": fail_mark(use_color),
            "detail": f"Error: {e}",
        }


def check_recent_alerts(use_color: bool) -> dict:
    """Check recent alert activity in the last 24 hours."""
    try:
        from database import SessionLocal
        from models.alert import Alert

        db = SessionLocal()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = db.query(Alert).filter(Alert.created_at >= cutoff).count()
        open_alerts = db.query(Alert).filter(Alert.status == "open").count()
        critical_open = db.query(Alert).filter(
            Alert.status == "open", Alert.severity == "critical"
        ).count()
        db.close()

        status = "ok"
        detail = f"{recent} alerts in last 24h | {open_alerts} open | {critical_open} critical open"

        if critical_open > 10:
            status = "warning"

        return {
            "name": "Recent Alerts (24h)",
            "status": status,
            "mark": check_mark(use_color) if status == "ok" else warn_mark(use_color),
            "detail": detail,
            "recent_24h": recent,
            "open": open_alerts,
            "critical_open": critical_open,
        }
    except Exception as e:
        return {
            "name": "Recent Alerts (24h)",
            "status": "warning",
            "mark": warn_mark(use_color),
            "detail": f"Could not check: {e}",
        }


def check_backend_health(use_color: bool) -> dict:
    """Check if the FastAPI backend is responding."""
    try:
        import urllib.request
        import urllib.error

        url = "http://localhost:8000/health"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return {
                "name": "Backend Health Endpoint",
                "status": "ok",
                "mark": check_mark(use_color),
                "detail": f"HTTP 200 — {url}",
            }

    except Exception as e:
        return {
            "name": "Backend Health Endpoint",
            "status": "warning",
            "mark": warn_mark(use_color),
            "detail": f"Not reachable (is the server running?): {type(e).__name__}",
        }


def check_dependency_versions(use_color: bool) -> dict:
    """Check installed package versions and warn about known issues."""
    warnings = []

    checks = [
        ("fastapi", "0.100.0"),
        ("sqlalchemy", "2.0.0"),
        ("pydantic", "2.0.0"),
    ]

    for pkg, min_version in checks:
        try:
            mod = importlib.import_module(pkg.replace("-", "_"))
            ver = getattr(mod, "__version__", "unknown")
        except ImportError:
            warnings.append(f"{pkg} not installed")

    # Check bcrypt version (4.x has known compatibility issues with passlib)
    try:
        import bcrypt
        ver = getattr(bcrypt, "__version__", "unknown")
        major = int(ver.split(".")[0]) if ver != "unknown" else 0
        if major >= 4:
            warnings.append(f"bcrypt {ver}: may cause passlib deprecation warnings (non-critical)")
    except ImportError:
        warnings.append("bcrypt not installed")

    if warnings:
        return {
            "name": "Dependency Versions",
            "status": "warning",
            "mark": warn_mark(use_color),
            "detail": "; ".join(warnings),
            "warnings": warnings,
        }

    return {
        "name": "Dependency Versions",
        "status": "ok",
        "mark": check_mark(use_color),
        "detail": "All checked dependencies present",
    }


def check_high_risk_customers(use_color: bool) -> dict:
    """Check count of high/critical risk customers needing review."""
    try:
        from database import SessionLocal
        from models.customer import Customer

        db = SessionLocal()
        high = db.query(Customer).filter(Customer.risk_level == "high").count()
        critical = db.query(Customer).filter(Customer.risk_level == "critical").count()
        pep = db.query(Customer).filter(Customer.pep_status == True).count()
        sanctioned = db.query(Customer).filter(Customer.sanctions_flag == True).count()
        db.close()

        status = "ok"
        if critical > 0:
            status = "warning"

        return {
            "name": "High-Risk Customers",
            "status": status,
            "mark": check_mark(use_color) if status == "ok" else warn_mark(use_color),
            "detail": f"High={high}, Critical={critical}, PEP={pep}, Sanctioned={sanctioned}",
            "high": high,
            "critical": critical,
            "pep": pep,
            "sanctioned": sanctioned,
        }
    except Exception as e:
        return {
            "name": "High-Risk Customers",
            "status": "warning",
            "mark": warn_mark(use_color),
            "detail": f"Could not check: {e}",
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AML System Diagnostics")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Output results as JSON")
    parser.add_argument("--no-color", action="store_true", default=False,
                        dest="no_color", help="Disable colored output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    use_color = not args.no_color and sys.stdout.isatty() or not args.no_color

    print(f"\n{_c(BOLD + 'AML System Diagnostics', BOLD, use_color)}")
    print(f"Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    checks = [
        check_db_connection,
        check_sanctions_data,
        check_rules_loaded,
        check_recent_alerts,
        check_backend_health,
        check_dependency_versions,
        check_high_risk_customers,
    ]

    results = []
    for check_fn in checks:
        result = check_fn(use_color)
        results.append(result)

    if args.json:
        # Strip ANSI codes for JSON output
        clean_results = []
        for r in results:
            clean = dict(r)
            clean.pop("mark", None)
            clean_results.append(clean)
        print(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                          "checks": clean_results}, indent=2))
        exit_code = 2 if any(r["status"] == "critical" for r in results) else (
            1 if any(r["status"] == "warning" for r in results) else 0
        )
        return exit_code

    # Print formatted report
    col_w = 35
    print(f"  {'Check':<{col_w}}  {'Status'}")
    print(f"  {'-'*col_w}  {'-'*50}")

    critical_count = 0
    warning_count = 0

    for result in results:
        mark = result.get("mark", "?")
        name = result.get("name", "Unknown")
        detail = result.get("detail", "")
        status = result.get("status", "unknown")

        if status == "critical":
            critical_count += 1
        elif status == "warning":
            warning_count += 1

        status_label = _c(status.upper(), RED if status == "critical" else
                          (YELLOW if status == "warning" else GREEN), use_color)

        print(f"  {mark} {name:<{col_w-2}}  {status_label}")
        if detail:
            print(f"    {_c(detail, CYAN, use_color)}")

    print(f"\n  {'='*60}")

    if critical_count > 0:
        print(f"  {_c(f'RESULT: {critical_count} CRITICAL issue(s) found. Immediate action required.', RED, use_color)}")
        exit_code = 2
    elif warning_count > 0:
        print(f"  {_c(f'RESULT: {warning_count} warning(s). Review recommended.', YELLOW, use_color)}")
        exit_code = 1
    else:
        print(f"  {_c('RESULT: All checks passed. System is healthy.', GREEN, use_color)}")
        exit_code = 0

    print(f"  {'='*60}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
