"""
Tests for Alert Service
========================
Tests alert creation, listing, updating, and stats.

Run with:
    pytest backend/tests/test_alert_service.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone
from fastapi import HTTPException

from services.alert_service import AlertService, _generate_alert_number
from services.rules_engine import RuleMatch


@pytest.fixture
def service():
    return AlertService()


def make_rule_match(**kwargs):
    return RuleMatch(
        rule_id=kwargs.get("rule_id", 1),
        rule_name=kwargs.get("rule_name", "Large Transaction"),
        category=kwargs.get("category", "large_transaction"),
        severity=kwargs.get("severity", "high"),
        reason=kwargs.get("reason", "Amount exceeds threshold"),
        risk_score=kwargs.get("risk_score", 75.0),
        details=kwargs.get("details", {"amount": 15000}),
    )


def make_transaction(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.from_customer_id = kwargs.get("from_customer_id", 1)
    t.flagged = False
    t.risk_score = 0.0
    return t


def make_alert(**kwargs):
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.alert_number = kwargs.get("alert_number", "ALT-20240101-00001")
    a.severity = kwargs.get("severity", "high")
    a.status = kwargs.get("status", "open")
    a.assigned_to = kwargs.get("assigned_to", None)
    a.closed_at = None
    return a


# ── Alert Number Generator ─────────────────────────────────────────────────

class TestGenerateAlertNumber:
    def test_format(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_alert_number(db)
        assert number.startswith("ALT-")
        assert len(number.split("-")) == 3

    def test_sequential_numbers(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 99
        number = _generate_alert_number(db)
        assert number.endswith("00100")

    def test_zero_based_count(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_alert_number(db)
        assert number.endswith("00001")


# ── Create Alerts From Matches ─────────────────────────────────────────────

class TestCreateAlertsFromMatches:
    def test_creates_one_alert_per_match(self, service):
        matches = [make_rule_match(severity="high"), make_rule_match(severity="critical")]
        txn = make_transaction()
        db = MagicMock()
        db.query.return_value.count.return_value = 0

        with patch("services.alert_service.audit_service"):
            result = service.create_alerts_from_matches(matches, txn, db)

        assert db.add.call_count == 2
        assert db.flush.call_count == 2

    def test_flags_transaction_on_match(self, service):
        matches = [make_rule_match()]
        txn = make_transaction()
        db = MagicMock()
        db.query.return_value.count.return_value = 0

        service.create_alerts_from_matches(matches, txn, db)
        assert txn.flagged is True

    def test_sets_max_risk_score_on_transaction(self, service):
        matches = [
            make_rule_match(risk_score=60.0),
            make_rule_match(risk_score=90.0),
            make_rule_match(risk_score=75.0),
        ]
        txn = make_transaction()
        db = MagicMock()
        db.query.return_value.count.return_value = 0

        service.create_alerts_from_matches(matches, txn, db)
        assert txn.risk_score == 90.0

    def test_empty_matches_returns_empty_list(self, service):
        txn = make_transaction()
        db = MagicMock()
        result = service.create_alerts_from_matches([], txn, db)
        assert result == []
        assert txn.flagged is False

    def test_details_stored_as_json(self, service):
        matches = [make_rule_match(details={"amount": 15000, "threshold": 10000})]
        txn = make_transaction()
        db = MagicMock()
        db.query.return_value.count.return_value = 0

        service.create_alerts_from_matches(matches, txn, db)

        # Check the Alert object was created with JSON-encoded details
        added_alert = db.add.call_args_list[0][0][0]
        details = json.loads(added_alert.details)
        assert details["amount"] == 15000


# ── Get Alert ──────────────────────────────────────────────────────────────

class TestGetAlert:
    def test_returns_alert_when_found(self, service):
        alert = make_alert()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = alert
        result = service.get_alert(1, db)
        assert result == alert

    def test_raises_404_when_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_alert(999, db)
        assert exc.value.status_code == 404


# ── List Alerts ────────────────────────────────────────────────────────────

class TestListAlerts:
    def _make_db(self, items, total):
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.count.return_value = total
        query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = items
        return db

    def test_returns_paginated_results(self, service):
        alerts = [make_alert(id=i) for i in range(5)]
        db = self._make_db(alerts, 50)
        result = service.list_alerts(db, page=1, page_size=5)
        assert result["total"] == 50
        assert result["page"] == 1
        assert result["page_size"] == 5

    def test_no_filters_returns_all(self, service):
        db = self._make_db([], 0)
        result = service.list_alerts(db)
        assert "total" in result
        assert "items" in result


# ── Update Alert ───────────────────────────────────────────────────────────

class TestUpdateAlert:
    def test_updates_status(self, service):
        alert = make_alert(status="open")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = alert
        user = MagicMock()

        with patch("services.alert_service.audit_service"):
            result = service.update_alert(1, {"status": "closed"}, db, user)

        assert alert.status == "closed"

    def test_sets_closed_at_when_closing(self, service):
        alert = make_alert(status="open")
        alert.closed_at = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = alert
        user = MagicMock()

        with patch("services.alert_service.audit_service"):
            service.update_alert(1, {"status": "closed"}, db, user)

        assert alert.closed_at is not None

    def test_sets_closed_at_on_false_positive(self, service):
        alert = make_alert(status="open")
        alert.closed_at = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = alert
        user = MagicMock()

        with patch("services.alert_service.audit_service"):
            service.update_alert(1, {"status": "false_positive"}, db, user)

        assert alert.closed_at is not None

    def test_raises_404_on_missing_alert(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()

        with pytest.raises(HTTPException) as exc:
            service.update_alert(999, {"status": "closed"}, db, user)
        assert exc.value.status_code == 404


# ── Alert Stats ────────────────────────────────────────────────────────────

class TestGetAlertsStats:
    def test_returns_all_severities(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = 5
        stats = service.get_alerts_stats(db)
        assert "low" in stats
        assert "medium" in stats
        assert "high" in stats
        assert "critical" in stats

    def test_zero_counts_returned_when_no_alerts(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = None
        stats = service.get_alerts_stats(db)
        for sev in ("low", "medium", "high", "critical"):
            assert stats[sev] == 0
