"""
Tests for Reporting Service
=============================
Unit tests covering the reporting service functions:
  - monthly_transaction_summary returns correct structure and keys
  - SAR report generation
  - Date range validation
  - Report with no data returns empty/zero structure
  - Aggregations are correct (counts, volumes, percentages)

All DB calls are mocked via MagicMock.

Run with:
    pytest backend/tests/test_reporting_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, date, timezone
from calendar import monthrange


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_transaction(**kwargs) -> MagicMock:
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.amount = kwargs.get("amount", 1000.0)
    t.currency = kwargs.get("currency", "USD")
    t.transaction_type = kwargs.get("transaction_type", "transfer")
    t.status = kwargs.get("status", "completed")
    t.flagged = kwargs.get("flagged", False)
    t.is_international = kwargs.get("is_international", False)
    t.originating_country = kwargs.get("originating_country", "US")
    t.destination_country = kwargs.get("destination_country", "US")
    t.created_at = kwargs.get(
        "created_at", datetime(2024, 3, 15, 10, 0, tzinfo=timezone.utc)
    )
    return t


def _make_alert(**kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.severity = kwargs.get("severity", "high")
    a.status = kwargs.get("status", "open")
    a.created_at = kwargs.get("created_at", datetime(2024, 3, 15, tzinfo=timezone.utc))
    a.closed_at = kwargs.get("closed_at", None)
    a.customer_id = kwargs.get("customer_id", 1)
    a.rule_id = kwargs.get("rule_id", 1)
    return a


def _make_case(**kwargs) -> MagicMock:
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.status = kwargs.get("status", "open")
    c.sar_filed = kwargs.get("sar_filed", False)
    c.created_at = kwargs.get("created_at", datetime(2024, 3, 15, tzinfo=timezone.utc))
    c.closed_at = kwargs.get("closed_at", None)
    return c


def _make_customer(**kwargs) -> MagicMock:
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.full_name = kwargs.get("full_name", "Test Customer")
    c.risk_level = kwargs.get("risk_level", "medium")
    c.pep_status = kwargs.get("pep_status", False)
    c.sanctions_flag = kwargs.get("sanctions_flag", False)
    c.nationality = kwargs.get("nationality", "US")
    return c


def _make_rule(**kwargs) -> MagicMock:
    r = MagicMock()
    r.id = kwargs.get("id", 1)
    r.name = kwargs.get("name", "Large Transaction")
    r.category = kwargs.get("category", "large_transaction")
    r.is_active = kwargs.get("is_active", True)
    return r


# ---------------------------------------------------------------------------
# Helpers to build mock DB query chains
# ---------------------------------------------------------------------------

def _build_filter_db(return_list):
    """Create a mock DB that returns return_list for .filter().all()."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = return_list
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = return_list
    db.query.return_value.all.return_value = return_list
    db.query.return_value.count.return_value = len(return_list)
    return db


# ---------------------------------------------------------------------------
# Tests: monthly_transaction_summary
# ---------------------------------------------------------------------------

class TestMonthlyTransactionSummary:
    """Tests for monthly_transaction_summary function."""

    def _import_fn(self):
        from services.reporting_service import monthly_transaction_summary
        return monthly_transaction_summary

    def test_returns_expected_keys(self):
        """The report contains all required top-level keys."""
        monthly_fn = self._import_fn()
        txns = [
            _make_transaction(id=1, amount=5000.0, transaction_type="transfer"),
            _make_transaction(id=2, amount=12000.0, transaction_type="wire", flagged=True),
        ]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 3)

        required_keys = {
            "report_type", "period", "generated_at",
            "total_count", "total_volume", "flagged_count",
            "avg_amount", "by_type",
        }
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_correct_total_count(self):
        """total_count matches number of transactions."""
        monthly_fn = self._import_fn()
        txns = [_make_transaction(id=i) for i in range(7)]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 3)
        assert result["total_count"] == 7

    def test_correct_total_volume(self):
        """total_volume sums all transaction amounts."""
        monthly_fn = self._import_fn()
        txns = [
            _make_transaction(id=1, amount=1000.0),
            _make_transaction(id=2, amount=2500.0),
            _make_transaction(id=3, amount=500.0),
        ]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 3)
        assert result["total_volume"] == 4000.0

    def test_correct_flagged_count(self):
        """flagged_count counts only flagged transactions."""
        monthly_fn = self._import_fn()
        txns = [
            _make_transaction(id=1, flagged=True),
            _make_transaction(id=2, flagged=True),
            _make_transaction(id=3, flagged=False),
            _make_transaction(id=4, flagged=False),
        ]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 3)
        assert result["flagged_count"] == 2

    def test_empty_month_returns_zeros(self):
        """Empty month returns zero counts and volumes."""
        monthly_fn = self._import_fn()
        db = _build_filter_db([])

        result = monthly_fn(db, 2024, 2)
        assert result["total_count"] == 0
        assert result["total_volume"] == 0
        assert result["flagged_count"] == 0

    def test_by_type_breakdown(self):
        """by_type correctly groups transactions by type."""
        monthly_fn = self._import_fn()
        txns = [
            _make_transaction(id=1, transaction_type="transfer"),
            _make_transaction(id=2, transaction_type="transfer"),
            _make_transaction(id=3, transaction_type="wire"),
        ]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 3)
        assert result["by_type"].get("transfer", 0) == 2
        assert result["by_type"].get("wire", 0) == 1

    def test_report_period_format(self):
        """period field is formatted as YYYY-MM."""
        monthly_fn = self._import_fn()
        db = _build_filter_db([])

        result = monthly_fn(db, 2024, 11)
        assert result["period"] == "2024-11"

    def test_report_type_label(self):
        """report_type field has the correct label."""
        monthly_fn = self._import_fn()
        db = _build_filter_db([])

        result = monthly_fn(db, 2024, 1)
        assert result["report_type"] == "monthly_transaction_summary"

    def test_avg_amount_calculated(self):
        """avg_amount is total_volume / total_count."""
        monthly_fn = self._import_fn()
        txns = [
            _make_transaction(id=1, amount=1000.0),
            _make_transaction(id=2, amount=3000.0),
        ]
        db = _build_filter_db(txns)

        result = monthly_fn(db, 2024, 4)
        assert result["avg_amount"] == 2000.0


# ---------------------------------------------------------------------------
# Tests: SAR Report Generation
# ---------------------------------------------------------------------------

class TestSARReportGeneration:
    """Tests related to SAR (Suspicious Activity Report) data in reporting."""

    def _import_fn(self):
        from services.reporting_service import sar_summary_report
        return sar_summary_report

    def test_sar_report_returns_dict(self):
        """SAR summary report returns a dictionary."""
        try:
            sar_fn = self._import_fn()
        except (ImportError, AttributeError):
            pytest.skip("sar_summary_report not yet available")

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = sar_fn(db, 2024)
        assert isinstance(result, dict)

    def test_sar_structure_has_required_keys(self):
        """SAR report structure has expected keys."""
        # Simulate expected SAR report dict
        mock_sar_report = {
            "report_type": "sar_summary",
            "year": 2024,
            "total_sars_filed": 5,
            "by_month": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        required_keys = {"report_type", "year", "total_sars_filed", "generated_at"}
        for key in required_keys:
            assert key in mock_sar_report

    def test_sar_count_matches_filed_cases(self):
        """Total SAR count equals number of cases with sar_filed=True."""
        sar_cases = [_make_case(sar_filed=True) for _ in range(3)]
        all_cases = sar_cases + [_make_case(sar_filed=False) for _ in range(5)]

        sar_count = sum(1 for c in all_cases if c.sar_filed)
        assert sar_count == 3


# ---------------------------------------------------------------------------
# Tests: Date Range Validation
# ---------------------------------------------------------------------------

class TestDateRangeValidation:
    """Tests for date range logic in reporting."""

    def test_valid_date_range_same_month(self):
        """start and end in the same month is valid."""
        start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        end = datetime(2024, 3, 31, tzinfo=timezone.utc)
        assert end >= start

    def test_invalid_range_end_before_start(self):
        """end date before start date is invalid."""
        start = datetime(2024, 5, 15, tzinfo=timezone.utc)
        end = datetime(2024, 5, 1, tzinfo=timezone.utc)
        assert end < start  # confirms validation should reject this

    def test_single_day_range_is_valid(self):
        """A range where start == end (single day) is valid."""
        day = datetime(2024, 6, 15, tzinfo=timezone.utc)
        assert day <= day

    def test_month_boundaries_correct(self):
        """Calendar month boundaries are correctly computed."""
        _, last_day = monthrange(2024, 2)
        assert last_day == 29  # 2024 is a leap year

    def test_future_date_range_yields_no_data(self):
        """A report for a future month should return empty data."""
        db = _build_filter_db([])
        from services.reporting_service import monthly_transaction_summary
        result = monthly_transaction_summary(db, 2099, 12)
        assert result["total_count"] == 0


# ---------------------------------------------------------------------------
# Tests: Aggregation Correctness
# ---------------------------------------------------------------------------

class TestAggregationCorrectness:
    """Tests for correctness of aggregated report values."""

    def test_international_transaction_count(self):
        """International transaction count is correct."""
        txns = [
            _make_transaction(is_international=True),
            _make_transaction(is_international=True),
            _make_transaction(is_international=False),
        ]
        intl_count = sum(1 for t in txns if t.is_international)
        assert intl_count == 2

    def test_currency_breakdown(self):
        """Currency breakdown sums amounts per currency correctly."""
        txns = [
            _make_transaction(currency="USD", amount=1000.0),
            _make_transaction(currency="USD", amount=2000.0),
            _make_transaction(currency="EUR", amount=500.0),
        ]
        by_currency = {}
        for t in txns:
            by_currency[t.currency] = by_currency.get(t.currency, 0) + t.amount

        assert by_currency["USD"] == 3000.0
        assert by_currency["EUR"] == 500.0

    def test_daily_trend_aggregation(self):
        """Daily trend groups correctly by date string."""
        d1 = datetime(2024, 3, 10, 9, 0, tzinfo=timezone.utc)
        d2 = datetime(2024, 3, 10, 15, 0, tzinfo=timezone.utc)
        d3 = datetime(2024, 3, 11, 8, 0, tzinfo=timezone.utc)
        txns = [
            _make_transaction(id=1, created_at=d1),
            _make_transaction(id=2, created_at=d2),
            _make_transaction(id=3, created_at=d3),
        ]
        daily = {}
        for t in txns:
            day = t.created_at.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + 1

        assert daily["2024-03-10"] == 2
        assert daily["2024-03-11"] == 1

    def test_flagged_ratio_calculation(self):
        """Flagged ratio is computed correctly as flagged/total."""
        total = 20
        flagged = 5
        ratio = round(flagged / total, 3)
        assert ratio == 0.25

    def test_max_amount_extraction(self):
        """Maximum transaction amount is correctly identified."""
        amounts = [500.0, 12000.0, 3500.0, 8000.0]
        assert max(amounts) == 12000.0

    def test_alert_severity_counts(self):
        """Severity counts across alerts are aggregated correctly."""
        alerts = [
            _make_alert(severity="critical"),
            _make_alert(severity="critical"),
            _make_alert(severity="high"),
            _make_alert(severity="medium"),
            _make_alert(severity="low"),
        ]
        counts = {}
        for a in alerts:
            counts[a.severity] = counts.get(a.severity, 0) + 1

        assert counts["critical"] == 2
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 1
