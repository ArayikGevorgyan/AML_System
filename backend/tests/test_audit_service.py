"""
Tests for Audit Service
=========================
Verifies that AuditService.log() creates AuditLog entries with the correct
field values, and that get_logs() returns entries ordered by created_at desc
with proper pagination support.

The database session is fully mocked — no live DB required.

Run with:
    pytest backend/tests/test_audit_service.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, call
from datetime import datetime, timezone, timedelta

from services.audit_service import AuditService


@pytest.fixture
def service():
    return AuditService()


def make_user(**kwargs) -> MagicMock:
    user = MagicMock()
    user.id       = kwargs.get("id", 1)
    user.username = kwargs.get("username", "analyst")
    return user


def make_log_entry(**kwargs) -> MagicMock:
    entry = MagicMock()
    entry.id          = kwargs.get("id", 1)
    entry.action      = kwargs.get("action", "CREATE_ALERT")
    entry.user_id     = kwargs.get("user_id", 1)
    entry.username    = kwargs.get("username", "analyst")
    entry.description = kwargs.get("description", "Test entry")
    entry.entity_type = kwargs.get("entity_type", "alert")
    entry.entity_id   = kwargs.get("entity_id", 42)
    entry.created_at  = kwargs.get("created_at", datetime.now(timezone.utc))
    return entry


# ── log() — Entry Creation ─────────────────────────────────────────────────

class TestLog:
    def test_adds_entry_to_db(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        user = make_user()
        service.log(db, action="CREATE_CUSTOMER", user=user, description="Created new customer")

        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_created_entry_has_correct_action(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="UPDATE_ALERT", user=make_user())

        added = db.add.call_args[0][0]
        assert added.action == "UPDATE_ALERT"

    def test_created_entry_has_correct_user_id(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        user = make_user(id=7)
        service.log(db, action="CLOSE_CASE", user=user)

        added = db.add.call_args[0][0]
        assert added.user_id == 7

    def test_created_entry_has_correct_username(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        user = make_user(username="compliance_officer")
        service.log(db, action="CLOSE_CASE", user=user)

        added = db.add.call_args[0][0]
        assert added.username == "compliance_officer"

    def test_created_entry_has_description(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="DELETE_RULE", user=make_user(), description="Rule obsolete")

        added = db.add.call_args[0][0]
        assert added.description == "Rule obsolete"

    def test_created_entry_has_entity_type_and_id(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="VIEW_CUSTOMER", user=make_user(),
                    entity_type="customer", entity_id=99)

        added = db.add.call_args[0][0]
        assert added.entity_type == "customer"
        assert added.entity_id   == 99

    def test_new_value_serialized_as_json(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="UPDATE_ALERT", user=make_user(),
                    new_value={"status": "closed", "reason": "resolved"})

        added = db.add.call_args[0][0]
        parsed = json.loads(added.new_value)
        assert parsed["status"] == "closed"

    def test_old_value_serialized_as_json(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="UPDATE_ALERT", user=make_user(),
                    old_value={"status": "open"})

        added = db.add.call_args[0][0]
        parsed = json.loads(added.old_value)
        assert parsed["status"] == "open"

    def test_no_user_sets_username_to_system(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="SCHEDULED_SCAN", user=None)

        added = db.add.call_args[0][0]
        assert added.user_id  is None
        assert added.username == "system"

    def test_no_old_or_new_value_leaves_none(self, service):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        service.log(db, action="LOGIN", user=make_user())

        added = db.add.call_args[0][0]
        assert added.old_value is None
        assert added.new_value is None

    def test_returns_audit_log_entry(self, service):
        db = MagicMock()
        expected = make_log_entry()
        db.refresh.side_effect = lambda obj: None

        # Simulate refresh populating the object (the real service returns the
        # same object it added after calling db.refresh)
        result = service.log(db, action="CREATE_ALERT", user=make_user())

        # The return value is the AuditLog instance that was db.add()'d
        assert result is db.add.call_args[0][0]


# ── get_logs() — Querying & Ordering ──────────────────────────────────────

class TestGetLogs:
    def _make_db_with_entries(self, entries, total=None):
        """Build a mock DB whose query chain returns given entries."""
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.count.return_value  = total if total is not None else len(entries)
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = entries
        return db

    def test_returns_dict_with_items_and_total(self, service):
        entries = [make_log_entry(id=i) for i in range(3)]
        db = self._make_db_with_entries(entries, total=3)

        result = service.get_logs(db)
        assert "items" in result
        assert "total" in result

    def test_total_reflects_db_count(self, service):
        db = self._make_db_with_entries([], total=42)
        result = service.get_logs(db)
        assert result["total"] == 42

    def test_items_list_length_matches_returned_entries(self, service):
        entries = [make_log_entry(id=i) for i in range(5)]
        db = self._make_db_with_entries(entries, total=5)
        result = service.get_logs(db)
        assert len(result["items"]) == 5

    def test_order_by_created_at_desc_called(self, service):
        db = self._make_db_with_entries([])
        service.get_logs(db)
        # Ensure order_by was invoked on the query chain
        db.query.return_value.order_by.assert_called_once()

    def test_action_filter_applied(self, service):
        db = self._make_db_with_entries([])
        service.get_logs(db, action="CREATE_ALERT")
        # filter() must have been called at least once
        db.query.return_value.filter.assert_called()

    def test_user_id_filter_applied(self, service):
        db = self._make_db_with_entries([])
        service.get_logs(db, user_id=3)
        db.query.return_value.filter.assert_called()

    def test_entity_type_filter_applied(self, service):
        db = self._make_db_with_entries([])
        service.get_logs(db, entity_type="transaction")
        db.query.return_value.filter.assert_called()

    def test_pagination_page_and_page_size(self, service):
        db = self._make_db_with_entries([])
        result = service.get_logs(db, page=2, page_size=10)
        # offset(10) should have been called for page 2
        db.query.return_value.order_by.return_value.offset.assert_called_with(10)
        db.query.return_value.order_by.return_value \
            .offset.return_value.limit.assert_called_with(10)

    def test_empty_db_returns_zero_total(self, service):
        db = self._make_db_with_entries([], total=0)
        result = service.get_logs(db)
        assert result["total"] == 0
        assert result["items"] == []
