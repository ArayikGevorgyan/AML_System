"""
Cleanup Old Data CLI
======================
Removes stale data from the AML system database:
  - Audit logs older than N days
  - Closed cases older than N days
  - Resolved/closed alerts older than N days
  - Expired user sessions

By default, runs in dry-run mode — use --execute to actually delete.

Arguments:
  --days      Retention period in days (default: 90)
  --dry-run   Show what would be deleted without deleting (default)
  --execute   Actually perform deletions (requires confirmation or --yes)
  --yes       Skip confirmation prompt (for automated pipelines)

Usage:
    python scripts/cleanup_old_data.py --days 90
    python scripts/cleanup_old_data.py --days 30 --execute
    python scripts/cleanup_old_data.py --days 60 --execute --yes

Exit code 0 on success, 1 on error or cancellation.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean up old data from the AML system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Retention period in days (data older than this will be removed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Show what would be deleted (default: True unless --execute is set)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually perform deletions (requires confirmation)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Skip confirmation prompt",
    )
    return parser


# ---------------------------------------------------------------------------
# Count helpers
# ---------------------------------------------------------------------------

def count_old_audit_logs(db, cutoff: datetime) -> int:
    """Count audit log entries older than cutoff."""
    try:
        from models.audit_log import AuditLog
        return db.query(AuditLog).filter(AuditLog.created_at < cutoff).count()
    except Exception:
        return 0


def count_old_closed_cases(db, cutoff: datetime) -> int:
    """Count closed cases older than cutoff."""
    try:
        from models.case import Case
        return db.query(Case).filter(
            Case.status == "closed",
            Case.closed_at < cutoff,
        ).count()
    except Exception:
        return 0


def count_old_resolved_alerts(db, cutoff: datetime) -> int:
    """Count resolved/closed alerts older than cutoff."""
    try:
        from models.alert import Alert
        return db.query(Alert).filter(
            Alert.status.in_(["closed", "false_positive"]),
            Alert.closed_at < cutoff,
        ).count()
    except Exception:
        return 0


def count_expired_sessions(db, cutoff: datetime) -> int:
    """Count user sessions that have expired."""
    try:
        from models.session import UserSession
        return db.query(UserSession).filter(UserSession.expires_at < cutoff).count()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Delete helpers
# ---------------------------------------------------------------------------

def delete_old_audit_logs(db, cutoff: datetime) -> int:
    """Delete audit log entries older than cutoff. Returns deleted count."""
    try:
        from models.audit_log import AuditLog
        rows = db.query(AuditLog).filter(AuditLog.created_at < cutoff).all()
        count = len(rows)
        for row in rows:
            db.delete(row)
        return count
    except Exception as e:
        print(f"  [WARN] Could not delete audit logs: {e}")
        return 0


def delete_old_closed_cases(db, cutoff: datetime) -> int:
    """Delete closed cases older than cutoff. Returns deleted count."""
    try:
        from models.case import Case, CaseNote
        cases = db.query(Case).filter(
            Case.status == "closed",
            Case.closed_at < cutoff,
        ).all()
        count = len(cases)
        for case in cases:
            db.query(CaseNote).filter(CaseNote.case_id == case.id).delete()
            db.delete(case)
        return count
    except Exception as e:
        print(f"  [WARN] Could not delete old cases: {e}")
        return 0


def delete_old_resolved_alerts(db, cutoff: datetime) -> int:
    """Delete resolved alerts older than cutoff. Returns deleted count."""
    try:
        from models.alert import Alert
        alerts = db.query(Alert).filter(
            Alert.status.in_(["closed", "false_positive"]),
            Alert.closed_at < cutoff,
        ).all()
        count = len(alerts)
        for alert in alerts:
            db.delete(alert)
        return count
    except Exception as e:
        print(f"  [WARN] Could not delete old alerts: {e}")
        return 0


def delete_expired_sessions(db, cutoff: datetime) -> int:
    """Delete expired user sessions. Returns deleted count."""
    try:
        from models.session import UserSession
        sessions = db.query(UserSession).filter(UserSession.expires_at < cutoff).all()
        count = len(sessions)
        for s in sessions:
            db.delete(s)
        return count
    except Exception as e:
        print(f"  [WARN] Could not delete expired sessions: {e}")
        return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve mode
    is_dry_run = not args.execute or args.dry_run

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    print(f"\n{'='*55}")
    print(f"  AML System Data Cleanup")
    print(f"{'='*55}")
    print(f"  Retention period:  {args.days} days")
    print(f"  Cutoff date:       {cutoff.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode:              {'DRY RUN (preview only)' if is_dry_run else 'EXECUTE (will delete)'}")
    print(f"{'='*55}\n")

    db = SessionLocal()

    try:
        print("  Counting records to be affected ...\n")

        audit_count = count_old_audit_logs(db, cutoff)
        cases_count = count_old_closed_cases(db, cutoff)
        alerts_count = count_old_resolved_alerts(db, cutoff)
        sessions_count = count_expired_sessions(db, cutoff)

        total = audit_count + cases_count + alerts_count + sessions_count

        print(f"  {'Category':<35} {'Records':>10}")
        print(f"  {'-'*35} {'-'*10}")
        print(f"  {'Audit logs (older than cutoff)':<35} {audit_count:>10,}")
        print(f"  {'Closed cases (older than cutoff)':<35} {cases_count:>10,}")
        print(f"  {'Resolved alerts (older than cutoff)':<35} {alerts_count:>10,}")
        print(f"  {'Expired user sessions':<35} {sessions_count:>10,}")
        print(f"  {'-'*35} {'-'*10}")
        print(f"  {'TOTAL TO DELETE':<35} {total:>10,}")
        print()

        if total == 0:
            print("  No records to clean up. Database is already tidy.")
            return 0

        if is_dry_run:
            print("  [DRY RUN] No changes made. Use --execute to perform deletions.")
            return 0

        # Confirmation prompt
        if not args.yes:
            print(f"  WARNING: This will permanently delete {total:,} records.")
            print(f"  This action cannot be undone.\n")
            confirm = input("  Type 'yes' to confirm deletion: ").strip().lower()
            if confirm != "yes":
                print("\n  Deletion cancelled.")
                return 1

        print("\n  Deleting records ...")

        deleted_audit = delete_old_audit_logs(db, cutoff)
        print(f"  ✓ Deleted {deleted_audit:,} audit log entries")

        deleted_cases = delete_old_closed_cases(db, cutoff)
        print(f"  ✓ Deleted {deleted_cases:,} closed cases (+ their notes)")

        deleted_alerts = delete_old_resolved_alerts(db, cutoff)
        print(f"  ✓ Deleted {deleted_alerts:,} resolved alerts")

        deleted_sessions = delete_expired_sessions(db, cutoff)
        print(f"  ✓ Deleted {deleted_sessions:,} expired sessions")

        db.commit()

        total_deleted = deleted_audit + deleted_cases + deleted_alerts + deleted_sessions
        print(f"\n  Cleanup complete. Total records removed: {total_deleted:,}")
        print(f"  Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return 0

    except Exception as exc:
        print(f"\n  [ERROR] {exc}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
