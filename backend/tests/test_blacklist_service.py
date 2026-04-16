"""
Tests for Blacklist Service
==============================
Tests adding, moving, removing, and screening entries on the blacklist.

Run with:
    pytest backend/tests/test_blacklist_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta, timezone

from services.blacklist_service import (
    add_entry,
    move_entry,
    remove_entry,
    get_all_entries,
    is_blacklisted,
    get_list_status,
    screen_transaction,
    get_blacklist_stats,
    VALID_TYPES,
    VALID_LIST_TYPES,
)


def make_entry(**kwargs):
    e = MagicMock()
    e.id         = kwargs.get("id", 1)
    e.entry_type = kwargs.get("entry_type", "ip")
    e.value      = kwargs.get("value", "192.168.1.1")
    e.reason     = kwargs.get("reason", "Fraud detected")
    e.severity   = kwargs.get("severity", "high")
    e.list_type  = kwargs.get("list_type", "black")
    e.is_active  = kwargs.get("is_active", True)
    e.expires_at = kwargs.get("expires_at", None)
    e.review_note = kwargs.get("review_note", None)
    return e


# ── Add Entry ──────────────────────────────────────────────────────────────

class TestAddEntry:
    def _make_db(self, existing=None):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = existing
        return db

    def test_adds_new_entry_successfully(self):
        db = self._make_db(existing=None)
        entry = add_entry(db, "ip", "1.2.3.4", "Fraud IP", list_type="black")
        db.add.assert_called()
        db.commit.assert_called()

    def test_raises_on_duplicate_active_entry(self):
        existing = make_entry()
        db = self._make_db(existing=existing)
        with pytest.raises(ValueError, match="already exists"):
            add_entry(db, "ip", "1.2.3.4", "Fraud", list_type="black")

    def test_raises_on_invalid_entry_type(self):
        db = self._make_db()
        with pytest.raises(ValueError, match="Invalid entry_type"):
            add_entry(db, "invalid_type", "value", "reason")

    def test_raises_on_invalid_list_type(self):
        db = self._make_db(existing=None)
        with pytest.raises(ValueError, match="Invalid list_type"):
            add_entry(db, "ip", "1.2.3.4", "reason", list_type="invalid")

    def test_value_stored_lowercase(self):
        db = self._make_db(existing=None)
        add_entry(db, "ip", "1.2.3.4", "Fraud")
        added = db.add.call_args_list[0][0][0]
        assert added.value == "1.2.3.4"

    def test_creates_movement_log(self):
        db = self._make_db(existing=None)
        add_entry(db, "country", "IR", "Sanctioned country")
        # Should add both the entry and a movement log
        assert db.add.call_count == 2

    @pytest.mark.parametrize("entry_type", list(VALID_TYPES))
    def test_all_valid_entry_types_accepted(self, entry_type):
        db = self._make_db(existing=None)
        add_entry(db, entry_type, "test_value", "test reason")
        db.add.assert_called()

    @pytest.mark.parametrize("list_type", list(VALID_LIST_TYPES))
    def test_all_valid_list_types_accepted(self, list_type):
        db = self._make_db(existing=None)
        add_entry(db, "ip", "1.2.3.4", "reason", list_type=list_type)
        db.add.assert_called()


# ── Move Entry ─────────────────────────────────────────────────────────────

class TestMoveEntry:
    def _make_db(self, entry=None):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry
        return db

    def test_moves_entry_to_new_list(self):
        entry = make_entry(list_type="black")
        db = self._make_db(entry)
        user = MagicMock()
        user.id = 1
        user.full_name = "Admin User"

        result = move_entry(db, 1, "white", "Customer cleared", moved_by_user=user)
        assert entry.list_type == "white"

    def test_raises_on_invalid_to_list(self):
        entry = make_entry()
        db = self._make_db(entry)
        with pytest.raises(ValueError, match="Invalid list_type"):
            move_entry(db, 1, "invalid", "reason")

    def test_raises_when_entry_not_found(self):
        db = self._make_db(entry=None)
        with pytest.raises(ValueError, match="not found"):
            move_entry(db, 999, "white", "reason")

    def test_creates_movement_log(self):
        entry = make_entry(list_type="yellow")
        db = self._make_db(entry)
        user = MagicMock()
        user.id = 1
        user.full_name = "Analyst"

        move_entry(db, 1, "black", "Escalated", moved_by_user=user)
        db.add.assert_called_once()  # movement log


# ── Remove Entry ───────────────────────────────────────────────────────────

class TestRemoveEntry:
    def test_deactivates_entry(self):
        entry = make_entry(is_active=True)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        result = remove_entry(db, 1)
        assert result is True
        assert entry.is_active is False
        db.commit.assert_called_once()

    def test_returns_false_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = remove_entry(db, 999)
        assert result is False


# ── Is Blacklisted ─────────────────────────────────────────────────────────

class TestIsBlacklisted:
    def test_returns_entry_when_active(self):
        entry = make_entry(is_active=True, expires_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = entry

        result = is_blacklisted(db, "ip", "1.2.3.4")
        assert result == entry

    def test_returns_none_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None
        result = is_blacklisted(db, "ip", "1.2.3.4")
        assert result is None

    def test_deactivates_and_returns_none_when_expired(self):
        expired = make_entry(
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = expired

        result = is_blacklisted(db, "ip", "1.2.3.4")
        assert result is None
        assert expired.is_active is False


# ── Screen Transaction ─────────────────────────────────────────────────────

class TestScreenTransaction:
    def test_flags_high_risk_originating_country(self):
        entry = make_entry(entry_type="country", value="ir")
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = entry

        txn = MagicMock()
        txn.originating_country = "IR"
        txn.destination_country = "US"

        hits = screen_transaction(db, txn)
        assert len(hits) >= 1

    def test_clean_transaction_no_hits(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None

        txn = MagicMock()
        txn.originating_country = "US"
        txn.destination_country = "DE"

        hits = screen_transaction(db, txn)
        assert hits == []


# ── Blacklist Stats ────────────────────────────────────────────────────────

class TestGetBlacklistStats:
    def test_returns_required_keys(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 5
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 2

        stats = get_blacklist_stats(db)
        assert "total_active" in stats
        assert "by_type" in stats
        assert "by_list" in stats

    def test_by_type_contains_all_types(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0

        stats = get_blacklist_stats(db)
        for t in VALID_TYPES:
            assert t in stats["by_type"]

    def test_by_list_contains_all_list_types(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0

        stats = get_blacklist_stats(db)
        for lt in VALID_LIST_TYPES:
            assert lt in stats["by_list"]
