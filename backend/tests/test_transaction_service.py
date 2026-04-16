"""
Tests for Transaction Service
================================
Tests transaction creation, listing, filtering, and rules engine integration.

Run with:
    pytest backend/tests/test_transaction_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, call
from fastapi import HTTPException

from services.transaction_service import TransactionService, _generate_reference


@pytest.fixture
def service():
    return TransactionService()


def make_create_data(**kwargs):
    data = MagicMock()
    data.from_account_id  = kwargs.get("from_account_id", None)
    data.to_account_id    = kwargs.get("to_account_id", None)
    data.from_customer_id = kwargs.get("from_customer_id", 1)
    data.to_customer_id   = kwargs.get("to_customer_id", 2)
    data.amount           = kwargs.get("amount", 500.0)
    data.currency         = kwargs.get("currency", "USD")
    data.transaction_type = kwargs.get("transaction_type", "transfer")
    data.description      = kwargs.get("description", None)
    data.originating_country = kwargs.get("originating_country", "US")
    data.destination_country = kwargs.get("destination_country", "US")
    data.channel          = kwargs.get("channel", "online")
    return data


def make_transaction(**kwargs):
    t = MagicMock()
    t.id        = kwargs.get("id", 1)
    t.reference = kwargs.get("reference", "TXN-20240101-000001")
    t.amount    = kwargs.get("amount", 500.0)
    t.flagged   = False
    t.from_customer_id = kwargs.get("from_customer_id", 1)
    t.to_customer_id   = kwargs.get("to_customer_id", 2)
    t.originating_country = kwargs.get("originating_country", "US")
    t.destination_country = kwargs.get("destination_country", "US")
    return t


# ── Reference Generator ────────────────────────────────────────────────────

class TestGenerateReference:
    def test_format(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        ref = _generate_reference(db)
        assert ref.startswith("TXN-")
        parts = ref.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD

    def test_sequential(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 5
        ref = _generate_reference(db)
        assert ref.endswith("000006")

    def test_zero_based(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        ref = _generate_reference(db)
        assert ref.endswith("000001")


# ── Create Transaction ─────────────────────────────────────────────────────

class TestCreateTransaction:
    def _make_db(self, txn):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = None
        db.refresh.side_effect = lambda obj: None
        return db

    def test_creates_transaction_successfully(self, service):
        data = make_create_data()
        db = self._make_db(None)
        user = MagicMock()

        with patch("services.transaction_service.rules_engine") as mock_engine, \
             patch("services.transaction_service.alert_service"), \
             patch("services.transaction_service.audit_service"):
            mock_engine.evaluate.return_value = []
            result = service.create_transaction(data, db, user)

        db.add.assert_called_once()
        db.commit.assert_called()

    def test_international_flag_set_for_different_countries(self, service):
        data = make_create_data(originating_country="US", destination_country="IR")
        db = self._make_db(None)
        user = MagicMock()

        with patch("services.transaction_service.rules_engine") as mock_engine, \
             patch("services.transaction_service.alert_service"), \
             patch("services.transaction_service.audit_service"):
            mock_engine.evaluate.return_value = []
            service.create_transaction(data, db, user)

        added_txn = db.add.call_args[0][0]
        assert added_txn.is_international is True

    def test_not_international_for_same_country(self, service):
        data = make_create_data(originating_country="US", destination_country="US")
        db = self._make_db(None)
        user = MagicMock()

        with patch("services.transaction_service.rules_engine") as mock_engine, \
             patch("services.transaction_service.alert_service"), \
             patch("services.transaction_service.audit_service"):
            mock_engine.evaluate.return_value = []
            service.create_transaction(data, db, user)

        added_txn = db.add.call_args[0][0]
        assert added_txn.is_international is False

    def test_rules_engine_called_after_creation(self, service):
        data = make_create_data()
        db = self._make_db(None)
        user = MagicMock()

        with patch("services.transaction_service.rules_engine") as mock_engine, \
             patch("services.transaction_service.alert_service"), \
             patch("services.transaction_service.audit_service"):
            mock_engine.evaluate.return_value = []
            service.create_transaction(data, db, user)

        mock_engine.evaluate.assert_called_once()

    def test_alerts_created_when_rules_match(self, service):
        data = make_create_data()
        db = self._make_db(None)
        user = MagicMock()

        rule_match = MagicMock()
        with patch("services.transaction_service.rules_engine") as mock_engine, \
             patch("services.transaction_service.alert_service") as mock_alert, \
             patch("services.transaction_service.audit_service"):
            mock_engine.evaluate.return_value = [rule_match]
            service.create_transaction(data, db, user)

        mock_alert.create_alerts_from_matches.assert_called_once()

    def test_invalid_account_raises_404(self, service):
        data = make_create_data(from_account_id=999)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = MagicMock()

        with pytest.raises(HTTPException) as exc:
            service.create_transaction(data, db, user)
        assert exc.value.status_code == 404


# ── Get Transaction ────────────────────────────────────────────────────────

class TestGetTransaction:
    def test_returns_transaction_when_found(self, service):
        txn = make_transaction()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = txn
        result = service.get_transaction(1, db)
        assert result == txn

    def test_raises_404_when_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_transaction(999, db)
        assert exc.value.status_code == 404


# ── List Transactions ──────────────────────────────────────────────────────

class TestListTransactions:
    def _make_db(self, items, total):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.count.return_value = total
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = items
        return db

    def test_returns_paginated_result(self, service):
        txns = [make_transaction(id=i) for i in range(3)]
        db = self._make_db(txns, 100)
        filters = MagicMock()
        filters.customer_id = None
        filters.transaction_type = None
        filters.status = None
        filters.flagged = None
        filters.min_amount = None
        filters.max_amount = None
        filters.date_from = None
        filters.date_to = None
        filters.originating_country = None
        filters.page = 1
        filters.page_size = 3

        result = service.list_transactions(filters, db)
        assert result["total"] == 100
        assert result["page"] == 1

    def test_filters_by_customer_id(self, service):
        db = self._make_db([], 0)
        filters = MagicMock()
        filters.customer_id = 42
        filters.transaction_type = None
        filters.status = None
        filters.flagged = None
        filters.min_amount = None
        filters.max_amount = None
        filters.date_from = None
        filters.date_to = None
        filters.originating_country = None
        filters.page = 1
        filters.page_size = 50

        result = service.list_transactions(filters, db)
        assert "total" in result

    def test_filters_by_flagged(self, service):
        db = self._make_db([], 0)
        filters = MagicMock()
        filters.customer_id = None
        filters.transaction_type = None
        filters.status = None
        filters.flagged = True
        filters.min_amount = None
        filters.max_amount = None
        filters.date_from = None
        filters.date_to = None
        filters.originating_country = None
        filters.page = 1
        filters.page_size = 50

        result = service.list_transactions(filters, db)
        assert "total" in result

    def test_amount_range_filter(self, service):
        db = self._make_db([], 0)
        filters = MagicMock()
        filters.customer_id = None
        filters.transaction_type = None
        filters.status = None
        filters.flagged = None
        filters.min_amount = 1000.0
        filters.max_amount = 50000.0
        filters.date_from = None
        filters.date_to = None
        filters.originating_country = None
        filters.page = 1
        filters.page_size = 50

        result = service.list_transactions(filters, db)
        assert "total" in result
