"""
Tests for Customer Service
============================
Unit tests for CustomerService:
  - create_customer
  - get_customer (404 on missing)
  - update_customer (field updates, risk level changes)
  - list_customers (filters: risk_level, pep_status, search)
  - Customer with sanctions hit is flagged
  - get_customer_accounts
  - create_account

Run with:
    pytest backend/tests/test_customer_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, date, timezone
from fastapi import HTTPException

from services.customer_service import CustomerService, _generate_customer_number


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_customer(**kwargs) -> MagicMock:
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
    c.address = kwargs.get("address", "123 Main St")
    c.country = kwargs.get("country", "US")
    c.risk_level = kwargs.get("risk_level", "low")
    c.pep_status = kwargs.get("pep_status", False)
    c.sanctions_flag = kwargs.get("sanctions_flag", False)
    c.occupation = kwargs.get("occupation", "Engineer")
    c.annual_income = kwargs.get("annual_income", 85000.0)
    c.source_of_funds = kwargs.get("source_of_funds", "Salary")
    c.created_at = kwargs.get("created_at", datetime(2024, 1, 1, tzinfo=timezone.utc))
    c.updated_at = kwargs.get("updated_at", None)
    return c


def _make_account(**kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.account_number = kwargs.get("account_number", "ACC-0000000001")
    a.customer_id = kwargs.get("customer_id", 1)
    a.account_type = kwargs.get("account_type", "checking")
    a.currency = kwargs.get("currency", "USD")
    a.balance = kwargs.get("balance", 0.0)
    a.status = kwargs.get("status", "active")
    a.opened_date = date.today()
    a.country = kwargs.get("country", "US")
    return a


def _make_user(**kwargs) -> MagicMock:
    u = MagicMock()
    u.id = kwargs.get("id", 1)
    u.username = "admin"
    u.role = "admin"
    return u


def _make_customer_create(**kwargs):
    data = MagicMock()
    data.full_name = kwargs.get("full_name", "New Customer")
    data.email = kwargs.get("email", "new@example.com")
    data.phone = kwargs.get("phone", None)
    data.date_of_birth = kwargs.get("date_of_birth", None)
    data.nationality = kwargs.get("nationality", "US")
    data.id_type = kwargs.get("id_type", "passport")
    data.id_number = kwargs.get("id_number", "X9999999")
    data.address = kwargs.get("address", "456 Elm St")
    data.country = kwargs.get("country", "US")
    data.risk_level = kwargs.get("risk_level", "low")
    data.pep_status = kwargs.get("pep_status", False)
    data.occupation = kwargs.get("occupation", "Teacher")
    data.annual_income = kwargs.get("annual_income", 55000.0)
    data.source_of_funds = kwargs.get("source_of_funds", "Salary")
    return data


def _make_customer_update(**kwargs):
    data = MagicMock()
    data.model_dump = MagicMock(return_value={
        k: v for k, v in kwargs.items() if v is not None
    })
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    return CustomerService()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    return _make_user()


# ---------------------------------------------------------------------------
# Tests: _generate_customer_number
# ---------------------------------------------------------------------------

class TestGenerateCustomerNumber:
    """Tests for the customer number generation helper."""

    def test_format_starts_with_CUS(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_customer_number(db)
        assert number.startswith("CUS-")

    def test_sequential_numbering(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 5
        number = _generate_customer_number(db)
        assert number == "CUS-000006"

    def test_zero_based_count(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_customer_number(db)
        assert number == "CUS-000001"

    def test_large_count_pads_correctly(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 999999
        number = _generate_customer_number(db)
        assert number == "CUS-1000000"


# ---------------------------------------------------------------------------
# Tests: create_customer
# ---------------------------------------------------------------------------

class TestCreateCustomer:
    """Tests for CustomerService.create_customer."""

    def test_creates_customer_and_returns(self, service, mock_db, mock_user):
        """Customer is added to DB and returned."""
        data = _make_customer_create(full_name="Jane Doe", risk_level="low")
        mock_db.query.return_value.count.return_value = 0

        with patch("services.customer_service.audit_service") as mock_audit:
            result = service.create_customer(data, mock_db, mock_user)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_audit_log_created_on_customer_creation(self, service, mock_db, mock_user):
        """Audit log is called with CREATE_CUSTOMER action."""
        data = _make_customer_create()
        mock_db.query.return_value.count.return_value = 0

        with patch("services.customer_service.audit_service") as mock_audit:
            service.create_customer(data, mock_db, mock_user)
            mock_audit.log.assert_called_once()
            call_kwargs = mock_audit.log.call_args[1]
            assert call_kwargs["action"] == "CREATE_CUSTOMER"

    def test_creates_pep_customer(self, service, mock_db, mock_user):
        """PEP customer is created with pep_status=True."""
        data = _make_customer_create(pep_status=True, risk_level="high")
        mock_db.query.return_value.count.return_value = 10

        with patch("services.customer_service.audit_service"):
            service.create_customer(data, mock_db, mock_user)

        added_customer = mock_db.add.call_args[0][0]
        assert added_customer.pep_status is True

    def test_creates_customer_with_high_risk_level(self, service, mock_db, mock_user):
        """High-risk customer is stored with correct risk level."""
        data = _make_customer_create(risk_level="high")
        mock_db.query.return_value.count.return_value = 0

        with patch("services.customer_service.audit_service"):
            service.create_customer(data, mock_db, mock_user)

        added = mock_db.add.call_args[0][0]
        assert added.risk_level == "high"

    def test_customer_number_is_assigned(self, service, mock_db, mock_user):
        """Customer receives a generated customer_number."""
        data = _make_customer_create()
        mock_db.query.return_value.count.return_value = 42

        with patch("services.customer_service.audit_service"):
            service.create_customer(data, mock_db, mock_user)

        added = mock_db.add.call_args[0][0]
        assert added.customer_number == "CUS-000043"


# ---------------------------------------------------------------------------
# Tests: get_customer
# ---------------------------------------------------------------------------

class TestGetCustomer:
    """Tests for CustomerService.get_customer."""

    def test_returns_customer_when_found(self, service, mock_db):
        """Existing customer is returned."""
        customer = _make_customer(id=5)
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        result = service.get_customer(5, mock_db)
        assert result == customer

    def test_raises_404_when_not_found(self, service, mock_db):
        """Non-existent customer ID raises 404 HTTPException."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.get_customer(9999, mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Tests: list_customers
# ---------------------------------------------------------------------------

class TestListCustomers:
    """Tests for CustomerService.list_customers with filters."""

    def _setup_query(self, mock_db, items):
        q = mock_db.query.return_value
        q.filter.return_value = q
        q.count.return_value = len(items)
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = items
        return mock_db

    def test_list_all_no_filters(self, service, mock_db):
        """Listing without filters returns all customers."""
        customers = [_make_customer(id=i) for i in range(3)]
        self._setup_query(mock_db, customers)

        result = service.list_customers(mock_db)
        assert result["total"] == 3

    def test_filter_by_risk_level(self, service, mock_db):
        """risk_level filter applies WHERE clause."""
        high_risk = [_make_customer(id=1, risk_level="high")]
        self._setup_query(mock_db, high_risk)

        result = service.list_customers(mock_db, risk_level="high")
        assert result["total"] == 1

    def test_filter_by_pep_status(self, service, mock_db):
        """pep_status filter is applied."""
        pep = [_make_customer(id=2, pep_status=True)]
        self._setup_query(mock_db, pep)

        result = service.list_customers(mock_db, pep_status=True)
        assert result["total"] == 1

    def test_filter_by_sanctions_flag(self, service, mock_db):
        """sanctions_flag filter is applied."""
        sanctioned = [_make_customer(id=3, sanctions_flag=True)]
        self._setup_query(mock_db, sanctioned)

        result = service.list_customers(mock_db, sanctions_flag=True)
        assert result["total"] == 1

    def test_search_by_name(self, service, mock_db):
        """Name search returns matching customers."""
        matched = [_make_customer(id=4, full_name="Maria Garcia")]
        self._setup_query(mock_db, matched)

        result = service.list_customers(mock_db, search="Maria")
        assert result["total"] == 1

    def test_pagination_fields_present(self, service, mock_db):
        """Response includes pagination metadata."""
        self._setup_query(mock_db, [])

        result = service.list_customers(mock_db, page=2, page_size=10)
        assert result["page"] == 2
        assert result["page_size"] == 10

    def test_empty_result(self, service, mock_db):
        """No matching customers returns total=0."""
        self._setup_query(mock_db, [])

        result = service.list_customers(mock_db, risk_level="nonexistent")
        assert result["total"] == 0
        assert result["items"] == []


# ---------------------------------------------------------------------------
# Tests: update_customer
# ---------------------------------------------------------------------------

class TestUpdateCustomer:
    """Tests for CustomerService.update_customer."""

    def test_updates_risk_level(self, service, mock_db, mock_user):
        """Risk level is updated and persisted."""
        customer = _make_customer(id=1, risk_level="low")
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        data = _make_customer_update(risk_level="high")

        with patch("services.customer_service.audit_service"):
            service.update_customer(1, data, mock_db, mock_user)

        assert customer.risk_level == "high"

    def test_update_calls_commit(self, service, mock_db, mock_user):
        """DB commit is called after update."""
        customer = _make_customer(id=2)
        mock_db.query.return_value.filter.return_value.first.return_value = customer
        data = _make_customer_update(email="updated@email.com")

        with patch("services.customer_service.audit_service"):
            service.update_customer(2, data, mock_db, mock_user)

        mock_db.commit.assert_called_once()

    def test_update_nonexistent_customer_raises_404(self, service, mock_db, mock_user):
        """Updating missing customer raises 404."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        data = _make_customer_update(risk_level="high")

        with pytest.raises(HTTPException) as exc:
            service.update_customer(9999, data, mock_db, mock_user)

        assert exc.value.status_code == 404

    def test_sanctions_flag_set_to_true(self, service, mock_db, mock_user):
        """Customer can be flagged with a sanctions hit."""
        customer = _make_customer(id=3, sanctions_flag=False)
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        data = _make_customer_update(sanctions_flag=True)

        with patch("services.customer_service.audit_service"):
            service.update_customer(3, data, mock_db, mock_user)

        assert customer.sanctions_flag is True

    def test_audit_log_on_update(self, service, mock_db, mock_user):
        """Audit log records the update action."""
        customer = _make_customer(id=4)
        mock_db.query.return_value.filter.return_value.first.return_value = customer
        data = _make_customer_update(risk_level="critical")

        with patch("services.customer_service.audit_service") as mock_audit:
            service.update_customer(4, data, mock_db, mock_user)
            mock_audit.log.assert_called_once()
            assert mock_audit.log.call_args[1]["action"] == "UPDATE_CUSTOMER"


# ---------------------------------------------------------------------------
# Tests: Sanctions Flag Behavior
# ---------------------------------------------------------------------------

class TestSanctionsFlagBehavior:
    """Tests verifying that customers with sanctions hits are flagged."""

    def test_customer_with_sanctions_is_flagged(self, service, mock_db, mock_user):
        """Setting sanctions_flag=True marks customer as sanctioned."""
        customer = _make_customer(id=10, sanctions_flag=False)
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        data = _make_customer_update(sanctions_flag=True)
        with patch("services.customer_service.audit_service"):
            service.update_customer(10, data, mock_db, mock_user)

        assert customer.sanctions_flag is True

    def test_sanctioned_customer_risk_level_can_be_raised(self, service, mock_db, mock_user):
        """Sanctioned customer risk level can be escalated to critical."""
        customer = _make_customer(id=11, sanctions_flag=True, risk_level="high")
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        data = _make_customer_update(risk_level="critical")
        with patch("services.customer_service.audit_service"):
            service.update_customer(11, data, mock_db, mock_user)

        assert customer.risk_level == "critical"

    def test_pep_customer_can_be_sanctions_flagged(self, service, mock_db, mock_user):
        """A PEP customer can simultaneously be sanctions flagged."""
        customer = _make_customer(id=12, pep_status=True, sanctions_flag=False)
        mock_db.query.return_value.filter.return_value.first.return_value = customer

        data = _make_customer_update(sanctions_flag=True)
        with patch("services.customer_service.audit_service"):
            service.update_customer(12, data, mock_db, mock_user)

        assert customer.pep_status is True
        assert customer.sanctions_flag is True


# ---------------------------------------------------------------------------
# Tests: get_customer_accounts
# ---------------------------------------------------------------------------

class TestGetCustomerAccounts:
    """Tests for CustomerService.get_customer_accounts."""

    def test_returns_accounts(self, service, mock_db):
        """Returns list of accounts for a valid customer."""
        accounts = [_make_account(id=1, customer_id=5), _make_account(id=2, customer_id=5)]
        mock_db.query.return_value.filter.return_value.all.return_value = accounts

        result = service.get_customer_accounts(5, mock_db)
        assert len(result) == 2

    def test_returns_empty_list_for_no_accounts(self, service, mock_db):
        """Customer with no accounts returns empty list."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service.get_customer_accounts(99, mock_db)
        assert result == []
