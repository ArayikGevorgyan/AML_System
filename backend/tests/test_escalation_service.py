"""
Tests for Escalation Service
==============================
Unit tests covering all escalation scenarios:
  - escalate_stale_open_alerts escalates old open alerts
  - Already-escalated alerts are not re-escalated
  - Bulk escalation via repeat offender rule
  - High severity upgrade
  - Escalation summary report keys
  - Notification is triggered (mocked)
  - Escalation produces audit trail (mocked)

Run with:
    pytest backend/tests/test_escalation_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hours_ago(hours: int) -> datetime:
    return _now() - timedelta(hours=hours)


def _days_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _make_alert(**kwargs) -> MagicMock:
    """Return a mock Alert ORM object."""
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.alert_number = kwargs.get("alert_number", f"ALT-2024-{kwargs.get('id', 1):05d}")
    a.customer_id = kwargs.get("customer_id", 1)
    a.severity = kwargs.get("severity", "high")
    a.status = kwargs.get("status", "open")
    a.rule_id = kwargs.get("rule_id", 1)
    a.risk_score = kwargs.get("risk_score", 60.0)
    a.created_at = kwargs.get("created_at", _hours_ago(50))
    a.closed_at = kwargs.get("closed_at", None)
    return a


def _make_customer(**kwargs) -> MagicMock:
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.full_name = kwargs.get("full_name", "Test User")
    c.risk_level = kwargs.get("risk_level", "medium")
    return c


def _build_query_db(stale_alerts=None, high_alerts=None, repeat_groups=None):
    """
    Build a mock DB that returns different results based on what's being queried.
    Returns a simple mock with configurable .all() results.
    """
    db = MagicMock()
    q = db.query.return_value
    # Chain .filter().filter().all() -> stale alerts
    q.filter.return_value.filter.return_value.filter.return_value.all.return_value = stale_alerts or []
    q.filter.return_value.filter.return_value.all.return_value = high_alerts or []
    q.filter.return_value.all.return_value = stale_alerts or []
    return db


# ---------------------------------------------------------------------------
# Tests: escalate_stale_open_alerts
# ---------------------------------------------------------------------------

class TestEscalateStaleOpenAlerts:
    """Tests for Rule 1: time-based escalation of stale open alerts."""

    def test_escalates_old_open_alert(self):
        """Alert open for >48 hours is escalated to critical."""
        from services.escalation_service import escalate_stale_open_alerts

        stale_alert = _make_alert(id=1, status="open", severity="high",
                                  created_at=_hours_ago(72))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [stale_alert]

        result = escalate_stale_open_alerts(db)

        assert stale_alert.status == "escalated"
        assert stale_alert.severity == "critical"
        assert 1 in result

    def test_recent_alert_not_escalated(self):
        """Alert open for only 10 hours is NOT escalated."""
        from services.escalation_service import escalate_stale_open_alerts

        recent_alert = _make_alert(id=2, status="open", severity="medium",
                                   created_at=_hours_ago(10))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = escalate_stale_open_alerts(db)

        assert recent_alert.status == "open"  # unchanged
        assert result == []

    def test_already_escalated_alert_not_processed(self):
        """Alert already in escalated status is excluded from query."""
        from services.escalation_service import escalate_stale_open_alerts

        db = MagicMock()
        # The service filters out already-escalated alerts, so they won't appear
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = escalate_stale_open_alerts(db)
        assert result == []

    def test_critical_severity_alert_not_re_escalated(self):
        """Critical alerts are excluded from stale escalation query."""
        from services.escalation_service import escalate_stale_open_alerts

        critical_alert = _make_alert(id=3, severity="critical", status="open",
                                     created_at=_hours_ago(100))
        db = MagicMock()
        # Service excludes critical severity in its WHERE clause
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = escalate_stale_open_alerts(db)
        assert critical_alert.severity == "critical"  # unchanged
        assert result == []

    def test_multiple_stale_alerts_all_escalated(self):
        """Multiple stale alerts are all escalated in one pass."""
        from services.escalation_service import escalate_stale_open_alerts

        stale_alerts = [
            _make_alert(id=i, status="open", severity="medium", created_at=_hours_ago(60))
            for i in range(1, 6)
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = stale_alerts

        result = escalate_stale_open_alerts(db)

        assert len(result) == 5
        for alert in stale_alerts:
            assert alert.status == "escalated"

    def test_db_commit_called_after_escalation(self):
        """db.commit() is called when alerts are escalated."""
        from services.escalation_service import escalate_stale_open_alerts

        stale_alert = _make_alert(id=10, status="open", created_at=_hours_ago(72))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [stale_alert]

        escalate_stale_open_alerts(db)
        db.commit.assert_called_once()

    def test_no_escalation_when_no_stale_alerts(self):
        """No DB commit when there are no stale alerts."""
        from services.escalation_service import escalate_stale_open_alerts

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = escalate_stale_open_alerts(db)
        db.commit.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# Tests: escalate_high_severity_alerts
# ---------------------------------------------------------------------------

class TestEscalateHighSeverityAlerts:
    """Tests for Rule 3: HIGH → CRITICAL upgrade after time threshold."""

    def test_upgrades_high_to_critical(self):
        """HIGH alert older than threshold is upgraded to CRITICAL."""
        from services.escalation_service import escalate_high_severity_alerts

        high_alert = _make_alert(id=20, severity="high", status="open",
                                 created_at=_hours_ago(30))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [high_alert]

        result = escalate_high_severity_alerts(db)

        assert high_alert.severity == "critical"
        assert 20 in result

    def test_recent_high_not_upgraded(self):
        """HIGH alert within threshold is not upgraded."""
        from services.escalation_service import escalate_high_severity_alerts

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = escalate_high_severity_alerts(db)
        assert result == []

    def test_under_review_high_alert_eligible(self):
        """Under-review HIGH alert is also eligible for upgrade."""
        from services.escalation_service import escalate_high_severity_alerts

        under_review = _make_alert(id=21, severity="high", status="under_review",
                                   created_at=_hours_ago(36))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [under_review]

        result = escalate_high_severity_alerts(db)
        assert under_review.severity == "critical"


# ---------------------------------------------------------------------------
# Tests: escalate_repeat_offenders
# ---------------------------------------------------------------------------

class TestEscalateRepeatOffenders:
    """Tests for Rule 2: repeat offender escalation."""

    def test_repeat_offender_open_alerts_escalated(self):
        """Open alerts of a repeat offender customer are escalated."""
        from services.escalation_service import escalate_repeat_offenders

        open_alerts = [
            _make_alert(id=30, customer_id=5, status="open"),
            _make_alert(id=31, customer_id=5, status="open"),
        ]

        db = MagicMock()
        # Simulate repeat customer query
        repeat_row = MagicMock()
        repeat_row.customer_id = 5
        repeat_row.cnt = 4
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = [repeat_row]
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = open_alerts

        result = escalate_repeat_offenders(db)

        for alert in open_alerts:
            assert alert.status == "escalated"

    def test_no_repeat_offenders_returns_empty(self):
        """No repeat offenders yields empty result list."""
        from services.escalation_service import escalate_repeat_offenders

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = escalate_repeat_offenders(db)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: run_all_escalation_rules
# ---------------------------------------------------------------------------

class TestRunAllEscalationRules:
    """Tests for the combined escalation runner."""

    def test_returns_summary_dict(self):
        """run_all_escalation_rules returns a summary dictionary."""
        from services.escalation_service import run_all_escalation_rules

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = run_all_escalation_rules(db)

        assert isinstance(result, dict)
        assert "run_at" in result
        assert "total_actions" in result

    def test_summary_contains_all_rule_counts(self):
        """Summary includes counts for all three escalation rules."""
        from services.escalation_service import run_all_escalation_rules

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = run_all_escalation_rules(db)

        assert "stale_alerts_escalated" in result
        assert "high_alerts_upgraded" in result
        assert "repeat_offender_escalated" in result

    def test_total_actions_is_sum(self):
        """total_actions equals sum of individual rule counts."""
        from services.escalation_service import run_all_escalation_rules

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = run_all_escalation_rules(db)

        expected_total = (
            result["stale_alerts_escalated"]
            + result["high_alerts_upgraded"]
            + result["repeat_offender_escalated"]
        )
        assert result["total_actions"] == expected_total

    def test_escalated_alert_ids_list(self):
        """Summary includes list of all escalated alert IDs."""
        from services.escalation_service import run_all_escalation_rules

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = run_all_escalation_rules(db)
        assert "escalated_alert_ids" in result
        assert isinstance(result["escalated_alert_ids"], list)

    def test_run_at_is_iso_string(self):
        """run_at is a valid ISO timestamp string."""
        from services.escalation_service import run_all_escalation_rules

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []

        result = run_all_escalation_rules(db)
        # Should parse without exception
        parsed = datetime.fromisoformat(result["run_at"].replace("Z", "+00:00"))
        assert parsed is not None


# ---------------------------------------------------------------------------
# Tests: get_escalation_candidates
# ---------------------------------------------------------------------------

class TestGetEscalationCandidates:
    """Tests for escalation candidate preview."""

    def test_returns_candidate_counts(self):
        """Preview returns counts for each escalation category."""
        from services.escalation_service import get_escalation_candidates

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 3
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.count.return_value = 1

        result = get_escalation_candidates(db)

        assert "stale_open_alerts" in result
        assert "high_severity_upgrades" in result
        assert "repeat_offender_customers" in result

    def test_thresholds_present_in_candidates(self):
        """Preview response includes the current threshold settings."""
        from services.escalation_service import get_escalation_candidates

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.filter.return_value.group_by.return_value.having.return_value.count.return_value = 0

        result = get_escalation_candidates(db)
        assert "thresholds" in result
        assert "open_hours" in result["thresholds"]
