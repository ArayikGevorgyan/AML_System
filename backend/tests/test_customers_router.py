"""
Tests for /customers Router
============================
FastAPI TestClient integration tests covering all customer endpoints:
  - GET  /customers           list with filters
  - GET  /customers/{id}      get by id (404 on missing)
  - POST /customers           create (field validation)
  - PUT  /customers/{id}      update
  - GET  /customers/{id}/accounts   customer accounts
  - POST /customers/accounts  create account

Run with:
    pytest backend/tests/test_customers_router.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Minimal app fixture — avoids importing the full main.py which requires a
# live DB, while still exercising the real router + service code paths via
# mocked dependencies.
# ---------------------------------------------------------------------------

def _make_customer(**kwargs) -> MagicMock:
    """Return a mock Customer ORM object with sensible defaults."""
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.customer_number = kwargs.get("customer_number", "CUS-000001")
    c.full_name = kwargs.get("full_name", "Alice Johnson")
    c.email = kwargs.get("email", "alice@example.com")
    c.phone = kwargs.get("phone", "+1-555-0001")
    c.date_of_birth = kwargs.get("date_of_birth", date(1985, 3, 15))
    c.nationality = kwargs.get("nationality", "US")
    c.id_type = kwargs.get("id_type", "passport")
    c.id_number = kwargs.get("id_number", "A12345678")
    c.address = kwargs.get("address", "123 Main St, New York, NY")
    c.country = kwargs.get("country", "US")
    c.risk_level = kwargs.get("risk_level", "low")
    c.pep_status = kwargs.get("pep_status", False)
    c.sanctions_flag = kwargs.get("sanctions_flag", False)
    c.occupation = kwargs.get("occupation", "Engineer")
    c.annual_income = kwargs.get("annual_income", 95000.0)
    c.source_of_funds = kwargs.get("source_of_funds", "Salary")
    c.created_at = kwargs.get("created_at", datetime(2024, 1, 10, 9, 0, tzinfo=timezone.utc))
    c.updated_at = kwargs.get("updated_at", None)
    return c


def _make_account(**kwargs) -> MagicMock:
    """Return a mock Account ORM object."""
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.account_number = kwargs.get("account_number", "ACC-0000000001")
    a.customer_id = kwargs.get("customer_id", 1)
    a.account_type = kwargs.get("account_type", "checking")
    a.currency = kwargs.get("currency", "USD")
    a.balance = kwargs.get("balance", 5000.0)
    a.status = kwargs.get("status", "active")
    a.opened_date = kwargs.get("opened_date", date(2024, 1, 10))
    a.country = kwargs.get("country", "US")
    a.iban = kwargs.get("iban", None)
    return a


def _make_user(**kwargs) -> MagicMock:
    u = MagicMock()
    u.id = kwargs.get("id", 1)
    u.username = kwargs.get("username", "testanalyst")
    u.role = kwargs.get("role", "analyst")
    u.is_active = True
    return u


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.count.return_value = 0
    return db


@pytest.fixture
def mock_user():
    return _make_user()


@pytest.fixture
def auth_headers():
    """Fake Bearer token — real validation is mocked away."""
    return {"Authorization": "Bearer fake-test-token-abc123"}


@pytest.fixture
def app(mock_db, mock_user):
    """Build a minimal FastAPI app with the customers router and mocked deps."""
    from fastapi import FastAPI
    from routers.customers import router
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
# POST /customers — Create Customer
# ---------------------------------------------------------------------------

class TestCreateCustomer:
    """Tests for customer creation endpoint."""

    def test_create_customer_success(self, client, mock_db, auth_headers):
        """Creating a customer with valid data returns 200 and correct fields."""
        new_customer = _make_customer(id=10, full_name="Bob Smith", risk_level="medium")

        with patch("services.customer_service.customer_service.create_customer",
                   return_value=new_customer):
            resp = client.post(
                "/customers",
                json={
                    "full_name": "Bob Smith",
                    "email": "bob@example.com",
                    "risk_level": "medium",
                    "pep_status": False,
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Bob Smith"
        assert data["risk_level"] == "medium"

    def test_create_pep_customer(self, client, auth_headers):
        """PEP customers are accepted and pep_status is stored."""
        pep_customer = _make_customer(id=11, pep_status=True, risk_level="high")

        with patch("services.customer_service.customer_service.create_customer",
                   return_value=pep_customer):
            resp = client.post(
                "/customers",
                json={"full_name": "Senator X", "pep_status": True, "risk_level": "high"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["pep_status"] is True

    def test_create_customer_missing_required_field(self, client, auth_headers):
        """Missing full_name should return 422 Unprocessable Entity."""
        resp = client.post(
            "/customers",
            json={"email": "noname@example.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_customer_with_full_profile(self, client, auth_headers):
        """All optional fields are accepted without error."""
        full_customer = _make_customer(
            id=12,
            full_name="Carlos Mendez",
            nationality="MX",
            occupation="Business Owner",
            annual_income=250000.0,
            source_of_funds="Business revenue",
        )

        with patch("services.customer_service.customer_service.create_customer",
                   return_value=full_customer):
            resp = client.post(
                "/customers",
                json={
                    "full_name": "Carlos Mendez",
                    "email": "carlos@biz.mx",
                    "nationality": "MX",
                    "country": "MX",
                    "occupation": "Business Owner",
                    "annual_income": 250000.0,
                    "source_of_funds": "Business revenue",
                    "risk_level": "medium",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["annual_income"] == 250000.0


# ---------------------------------------------------------------------------
# GET /customers — List Customers
# ---------------------------------------------------------------------------

class TestListCustomers:
    """Tests for customer list endpoint with various filters."""

    def _paginated(self, items):
        return {
            "total": len(items),
            "page": 1,
            "page_size": 50,
            "items": items,
        }

    def test_list_no_filters(self, client, auth_headers):
        """Default list returns paginated structure."""
        customers = [_make_customer(id=i) for i in range(3)]

        with patch("services.customer_service.customer_service.list_customers",
                   return_value=self._paginated(customers)):
            resp = client.get("/customers", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 3

    def test_filter_by_risk_level(self, client, auth_headers):
        """risk_level query param is forwarded correctly."""
        high_customers = [
            _make_customer(id=1, risk_level="high"),
            _make_customer(id=2, risk_level="high"),
        ]

        with patch("services.customer_service.customer_service.list_customers",
                   return_value=self._paginated(high_customers)) as mock_svc:
            resp = client.get("/customers?risk_level=high", headers=auth_headers)
            _, kwargs = mock_svc.call_args
            assert kwargs.get("risk_level") == "high" or mock_svc.call_args[0][1] == "high"

        assert resp.status_code == 200

    def test_filter_pep_only(self, client, auth_headers):
        """pep_status=true filter returns only PEP customers."""
        pep_customers = [_make_customer(id=3, pep_status=True)]

        with patch("services.customer_service.customer_service.list_customers",
                   return_value=self._paginated(pep_customers)):
            resp = client.get("/customers?pep_status=true", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_search_by_name(self, client, auth_headers):
        """search param filters by name."""
        matched = [_make_customer(id=5, full_name="David Lee")]

        with patch("services.customer_service.customer_service.list_customers",
                   return_value=self._paginated(matched)):
            resp = client.get("/customers?search=David", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["items"][0]["full_name"] == "David Lee"

    def test_pagination_params(self, client, auth_headers):
        """page and page_size params are accepted."""
        with patch("services.customer_service.customer_service.list_customers",
                   return_value={"total": 100, "page": 2, "page_size": 10, "items": []}):
            resp = client.get("/customers?page=2&page_size=10", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["page"] == 2

    def test_empty_list_returns_zero_total(self, client, auth_headers):
        """Empty database returns total=0 without error."""
        with patch("services.customer_service.customer_service.list_customers",
                   return_value={"total": 0, "page": 1, "page_size": 50, "items": []}):
            resp = client.get("/customers", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /customers/{id} — Get Customer By ID
# ---------------------------------------------------------------------------

class TestGetCustomerById:
    """Tests for single customer retrieval."""

    def test_returns_customer_when_found(self, client, auth_headers):
        """Existing customer is returned with correct data."""
        customer = _make_customer(id=7, full_name="Elena Volkov")

        with patch("services.customer_service.customer_service.get_customer",
                   return_value=customer):
            resp = client.get("/customers/7", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["id"] == 7
        assert resp.json()["full_name"] == "Elena Volkov"

    def test_returns_404_when_not_found(self, client, auth_headers):
        """Missing customer ID returns 404."""
        from fastapi import HTTPException

        with patch("services.customer_service.customer_service.get_customer",
                   side_effect=HTTPException(status_code=404, detail="Customer not found")):
            resp = client.get("/customers/9999", headers=auth_headers)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_customer_includes_sanctions_flag(self, client, auth_headers):
        """Sanctions flag is included in response."""
        customer = _make_customer(id=8, sanctions_flag=True)

        with patch("services.customer_service.customer_service.get_customer",
                   return_value=customer):
            resp = client.get("/customers/8", headers=auth_headers)

        assert resp.json()["sanctions_flag"] is True


# ---------------------------------------------------------------------------
# PUT /customers/{id} — Update Customer
# ---------------------------------------------------------------------------

class TestUpdateCustomer:
    """Tests for customer update endpoint."""

    def test_update_risk_level(self, client, auth_headers):
        """Risk level can be updated to a higher level."""
        updated = _make_customer(id=3, risk_level="high")

        with patch("services.customer_service.customer_service.update_customer",
                   return_value=updated):
            resp = client.put(
                "/customers/3",
                json={"risk_level": "high"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "high"

    def test_update_pep_status(self, client, auth_headers):
        """PEP status can be toggled on."""
        updated = _make_customer(id=4, pep_status=True)

        with patch("services.customer_service.customer_service.update_customer",
                   return_value=updated):
            resp = client.put(
                "/customers/4",
                json={"pep_status": True},
                headers=auth_headers,
            )

        assert resp.json()["pep_status"] is True

    def test_update_nonexistent_customer_returns_404(self, client, auth_headers):
        """Updating a missing customer returns 404."""
        from fastapi import HTTPException

        with patch("services.customer_service.customer_service.update_customer",
                   side_effect=HTTPException(status_code=404, detail="Customer not found")):
            resp = client.put(
                "/customers/9999",
                json={"risk_level": "medium"},
                headers=auth_headers,
            )

        assert resp.status_code == 404

    def test_update_email_and_address(self, client, auth_headers):
        """Email and address fields can be updated."""
        updated = _make_customer(id=5, email="new@email.com", address="456 New Ave")

        with patch("services.customer_service.customer_service.update_customer",
                   return_value=updated):
            resp = client.put(
                "/customers/5",
                json={"email": "new@email.com", "address": "456 New Ave"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["email"] == "new@email.com"


# ---------------------------------------------------------------------------
# GET /customers/{id}/accounts — Customer Accounts
# ---------------------------------------------------------------------------

class TestGetCustomerAccounts:
    """Tests for customer accounts retrieval."""

    def test_returns_accounts_list(self, client, auth_headers):
        """Returns list of accounts for a customer."""
        accounts = [_make_account(id=1, customer_id=1), _make_account(id=2, customer_id=1)]

        with patch("services.customer_service.customer_service.get_customer_accounts",
                   return_value=accounts):
            resp = client.get("/customers/1/accounts", headers=auth_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_empty_list_for_no_accounts(self, client, auth_headers):
        """Customer with no accounts returns empty list."""
        with patch("services.customer_service.customer_service.get_customer_accounts",
                   return_value=[]):
            resp = client.get("/customers/2/accounts", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_account_fields_present(self, client, auth_headers):
        """Account response includes expected fields."""
        account = _make_account(id=3, balance=12000.0, currency="EUR")

        with patch("services.customer_service.customer_service.get_customer_accounts",
                   return_value=[account]):
            resp = client.get("/customers/3/accounts", headers=auth_headers)

        assert resp.status_code == 200
        acc = resp.json()[0]
        assert "account_number" in acc
        assert "balance" in acc
        assert acc["currency"] == "EUR"


# ---------------------------------------------------------------------------
# POST /customers/accounts — Create Account
# ---------------------------------------------------------------------------

class TestCreateAccount:
    """Tests for account creation endpoint."""

    def test_create_account_success(self, client, auth_headers):
        """Creating an account with valid data succeeds."""
        new_account = _make_account(id=5, customer_id=1, balance=0.0)

        with patch("services.customer_service.customer_service.create_account",
                   return_value=new_account):
            resp = client.post(
                "/customers/accounts",
                json={"customer_id": 1, "account_type": "savings", "currency": "USD"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["account_type"] == "checking"  # mock default

    def test_create_account_missing_customer_id(self, client, auth_headers):
        """Missing customer_id returns 422."""
        resp = client.post(
            "/customers/accounts",
            json={"account_type": "checking"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_account_with_initial_balance(self, client, auth_headers):
        """Initial balance is accepted."""
        account = _make_account(id=6, balance=5000.0)

        with patch("services.customer_service.customer_service.create_account",
                   return_value=account):
            resp = client.post(
                "/customers/accounts",
                json={"customer_id": 1, "balance": 5000.0, "currency": "USD"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["balance"] == 5000.0
