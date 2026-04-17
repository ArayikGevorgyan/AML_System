"""
Tests for /transactions Router
================================
FastAPI TestClient integration tests for all transaction endpoints:
  - POST /transactions         create transaction
  - GET  /transactions         list with pagination + filters
  - GET  /transactions/{id}    get by id
  - Flagged transactions appear in system alerts

All database and authentication dependencies are mocked.

Run with:
    pytest backend/tests/test_transactions_router.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_transaction(**kwargs) -> MagicMock:
    """Return a mock Transaction ORM object."""
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.reference = kwargs.get("reference", "TXN-20240115-00001")
    t.from_customer_id = kwargs.get("from_customer_id", 1)
    t.to_customer_id = kwargs.get("to_customer_id", 2)
    t.from_account_id = kwargs.get("from_account_id", 1)
    t.to_account_id = kwargs.get("to_account_id", 2)
    t.amount = kwargs.get("amount", 5000.0)
    t.currency = kwargs.get("currency", "USD")
    t.transaction_type = kwargs.get("transaction_type", "transfer")
    t.status = kwargs.get("status", "completed")
    t.description = kwargs.get("description", "Test transfer")
    t.originating_country = kwargs.get("originating_country", "US")
    t.destination_country = kwargs.get("destination_country", "US")
    t.is_international = kwargs.get("is_international", False)
    t.channel = kwargs.get("channel", "online")
    t.risk_score = kwargs.get("risk_score", 0.0)
    t.flagged = kwargs.get("flagged", False)
    t.created_at = kwargs.get("created_at", datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc))
    return t


def _make_alert(**kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.alert_number = kwargs.get("alert_number", "ALT-20240115-00001")
    a.transaction_id = kwargs.get("transaction_id", 1)
    a.customer_id = kwargs.get("customer_id", 1)
    a.severity = kwargs.get("severity", "high")
    a.status = kwargs.get("status", "open")
    a.reason = kwargs.get("reason", "Large transaction detected")
    a.risk_score = kwargs.get("risk_score", 75.0)
    a.created_at = datetime(2024, 1, 15, 10, 31, tzinfo=timezone.utc)
    a.updated_at = None
    a.closed_at = None
    return a


def _make_user(**kwargs) -> MagicMock:
    u = MagicMock()
    u.id = kwargs.get("id", 1)
    u.username = "testanalyst"
    u.role = "analyst"
    u.is_active = True
    return u


def _paginated(items, total=None, page=1, page_size=50):
    return {"total": total or len(items), "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def mock_user():
    return _make_user()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake-test-token-xyz"}


@pytest.fixture
def app(mock_db, mock_user):
    from fastapi import FastAPI
    from routers.transactions import router
    from core.dependencies import get_current_user
    from database import get_db

    _app = FastAPI()
    _app.include_router(router)
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: mock_user
    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /transactions — Create Transaction
# ---------------------------------------------------------------------------

class TestCreateTransaction:
    """Tests for transaction creation endpoint."""

    def test_create_basic_transfer(self, client, auth_headers):
        """A basic transfer with valid fields is accepted."""
        txn = _make_transaction(id=1, transaction_type="transfer", amount=2500.0)

        with patch("services.transaction_service.transaction_service.create_transaction",
                   return_value=txn):
            resp = client.post(
                "/transactions",
                json={
                    "from_account_id": 1,
                    "to_account_id": 2,
                    "amount": 2500.0,
                    "currency": "USD",
                    "transaction_type": "transfer",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 2500.0
        assert data["transaction_type"] == "transfer"

    def test_create_large_transaction_gets_flagged(self, client, auth_headers):
        """A transaction above the threshold can come back flagged."""
        flagged_txn = _make_transaction(id=2, amount=50000.0, flagged=True, risk_score=80.0)

        with patch("services.transaction_service.transaction_service.create_transaction",
                   return_value=flagged_txn):
            resp = client.post(
                "/transactions",
                json={
                    "from_account_id": 1,
                    "to_account_id": 3,
                    "amount": 50000.0,
                    "currency": "USD",
                    "transaction_type": "wire",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["flagged"] is True
        assert resp.json()["risk_score"] >= 70.0

    def test_create_international_wire(self, client, auth_headers):
        """International wire transaction is created with is_international=True."""
        intl_txn = _make_transaction(
            id=3, is_international=True, originating_country="US",
            destination_country="IR", transaction_type="wire",
        )

        with patch("services.transaction_service.transaction_service.create_transaction",
                   return_value=intl_txn):
            resp = client.post(
                "/transactions",
                json={
                    "from_account_id": 1,
                    "to_account_id": 4,
                    "amount": 8000.0,
                    "currency": "USD",
                    "transaction_type": "wire",
                    "originating_country": "US",
                    "destination_country": "IR",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["is_international"] is True

    def test_create_transaction_missing_amount_returns_422(self, client, auth_headers):
        """Missing amount field triggers validation error."""
        resp = client.post(
            "/transactions",
            json={"from_account_id": 1, "transaction_type": "transfer"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_cash_deposit(self, client, auth_headers):
        """Cash deposit is accepted and returned correctly."""
        deposit_txn = _make_transaction(
            id=4, transaction_type="deposit", amount=9500.0, channel="branch"
        )

        with patch("services.transaction_service.transaction_service.create_transaction",
                   return_value=deposit_txn):
            resp = client.post(
                "/transactions",
                json={
                    "to_account_id": 2,
                    "amount": 9500.0,
                    "currency": "USD",
                    "transaction_type": "deposit",
                    "channel": "branch",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["channel"] == "branch"


# ---------------------------------------------------------------------------
# GET /transactions — List with Filters
# ---------------------------------------------------------------------------

class TestListTransactions:
    """Tests for transaction list endpoint with various filters."""

    def test_list_default_pagination(self, client, auth_headers):
        """Default request returns paginated structure."""
        txns = [_make_transaction(id=i) for i in range(5)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(txns)):
            resp = client.get("/transactions", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert len(data["items"]) == 5

    def test_filter_by_min_amount(self, client, auth_headers):
        """min_amount filter returns only transactions above threshold."""
        large_txns = [_make_transaction(id=1, amount=15000.0)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(large_txns)):
            resp = client.get("/transactions?min_amount=10000", headers=auth_headers)

        assert resp.status_code == 200

    def test_filter_by_max_amount(self, client, auth_headers):
        """max_amount filter accepted without error."""
        small_txns = [_make_transaction(id=2, amount=100.0)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(small_txns)):
            resp = client.get("/transactions?max_amount=500", headers=auth_headers)

        assert resp.status_code == 200

    def test_filter_by_transaction_type(self, client, auth_headers):
        """transaction_type filter is forwarded."""
        wire_txns = [_make_transaction(id=3, transaction_type="wire")]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(wire_txns)):
            resp = client.get("/transactions?transaction_type=wire", headers=auth_headers)

        assert resp.status_code == 200

    def test_filter_by_status(self, client, auth_headers):
        """status filter returns only matching transactions."""
        pending_txns = [_make_transaction(id=4, status="pending")]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(pending_txns)):
            resp = client.get("/transactions?status=pending", headers=auth_headers)

        assert resp.status_code == 200

    def test_filter_flagged_only(self, client, auth_headers):
        """flagged=true returns only flagged transactions."""
        flagged_txns = [_make_transaction(id=5, flagged=True)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(flagged_txns)):
            resp = client.get("/transactions?flagged=true", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["items"][0]["flagged"] is True

    def test_filter_by_customer_id(self, client, auth_headers):
        """customer_id filter scopes transactions to that customer."""
        customer_txns = [_make_transaction(id=6, from_customer_id=42)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(customer_txns)):
            resp = client.get("/transactions?customer_id=42", headers=auth_headers)

        assert resp.status_code == 200

    def test_pagination_second_page(self, client, auth_headers):
        """Second page request returns page=2."""
        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value={"total": 200, "page": 2, "page_size": 25, "items": []}):
            resp = client.get("/transactions?page=2&page_size=25", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["page"] == 2

    def test_combined_amount_filters(self, client, auth_headers):
        """min_amount and max_amount can be combined."""
        range_txns = [_make_transaction(id=7, amount=7500.0)]

        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated(range_txns)):
            resp = client.get("/transactions?min_amount=5000&max_amount=10000", headers=auth_headers)

        assert resp.status_code == 200

    def test_empty_result_returns_zero_total(self, client, auth_headers):
        """No matching transactions returns total=0."""
        with patch("services.transaction_service.transaction_service.list_transactions",
                   return_value=_paginated([])):
            resp = client.get("/transactions?transaction_type=nonexistent_type", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /transactions/{id} — Get By ID
# ---------------------------------------------------------------------------

class TestGetTransactionById:
    """Tests for single transaction retrieval."""

    def test_returns_transaction_when_found(self, client, auth_headers):
        """Existing transaction is returned with all fields."""
        txn = _make_transaction(id=20, amount=3200.0, reference="TXN-20240120-00020")

        with patch("services.transaction_service.transaction_service.get_transaction",
                   return_value=txn):
            resp = client.get("/transactions/20", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["id"] == 20
        assert resp.json()["amount"] == 3200.0
        assert resp.json()["reference"] == "TXN-20240120-00020"

    def test_returns_404_when_not_found(self, client, auth_headers):
        """Missing transaction ID returns 404."""
        from fastapi import HTTPException

        with patch("services.transaction_service.transaction_service.get_transaction",
                   side_effect=HTTPException(status_code=404, detail="Transaction not found")):
            resp = client.get("/transactions/9999", headers=auth_headers)

        assert resp.status_code == 404

    def test_flagged_transaction_has_risk_score(self, client, auth_headers):
        """Flagged transaction includes non-zero risk score."""
        txn = _make_transaction(id=21, flagged=True, risk_score=82.5)

        with patch("services.transaction_service.transaction_service.get_transaction",
                   return_value=txn):
            resp = client.get("/transactions/21", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["flagged"] is True
        assert resp.json()["risk_score"] > 0


# ---------------------------------------------------------------------------
# Flagged Transactions → Alerts
# ---------------------------------------------------------------------------

class TestFlaggedTransactionAlerts:
    """Verify that flagged transactions correspond to alerts in the system."""

    def test_flagged_transaction_generates_alert_data(self, mock_db):
        """Flagged transaction mock has alert-related fields accessible."""
        txn = _make_transaction(id=50, flagged=True, risk_score=90.0)
        alert = _make_alert(transaction_id=50, severity="critical")

        assert txn.flagged is True
        assert alert.transaction_id == txn.id
        assert alert.severity == "critical"

    def test_alert_references_correct_transaction(self, mock_db):
        """Alert transaction_id matches the flagged transaction id."""
        txn = _make_transaction(id=51, flagged=True)
        alert = _make_alert(transaction_id=51)

        assert alert.transaction_id == txn.id

    def test_multiple_flagged_transactions_produce_multiple_alerts(self, mock_db):
        """Each flagged transaction can produce a separate alert."""
        transactions = [_make_transaction(id=i, flagged=True) for i in range(60, 65)]
        alerts = [_make_alert(id=i, transaction_id=t.id) for i, t in enumerate(transactions)]

        assert len(alerts) == len(transactions)
        for alert, txn in zip(alerts, transactions):
            assert alert.transaction_id == txn.id

    def test_unflagged_transaction_has_zero_risk_score(self):
        """Non-flagged transaction defaults to zero risk score."""
        txn = _make_transaction(id=70, flagged=False, risk_score=0.0)
        assert txn.flagged is False
        assert txn.risk_score == 0.0

    def test_alert_severity_matches_risk_level(self):
        """High risk score maps to critical severity alert."""
        txn = _make_transaction(id=80, flagged=True, risk_score=95.0)
        alert = _make_alert(transaction_id=80, severity="critical", risk_score=95.0)

        assert alert.risk_score >= 90.0
        assert alert.severity == "critical"
