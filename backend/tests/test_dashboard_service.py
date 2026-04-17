"""
Tests for Dashboard Service
=============================
Verifies that each KPI returned by the dashboard service has the correct
Python type and satisfies basic sanity constraints (non-negative integers
and floats, expected dictionary keys, etc.).

The database session is fully mocked so the tests run without a live DB.

Run with:
    pytest backend/tests/test_dashboard_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.dashboard_service import DashboardService


@pytest.fixture
def service():
    return DashboardService()


def _make_db(scalar_value: int = 5, sum_value: float = 12_500.0):
    """
    Return a MagicMock DB session whose scalar() / all() return sensible
    stub values so every branch of DashboardService.get_dashboard() runs.
    """
    db = MagicMock()

    # Chain for scalar-returning queries
    scalar_chain = (
        db.query.return_value
          .filter.return_value
          .scalar
    )
    scalar_chain.return_value = scalar_value

    # Nested filter chains (e.g. filter(...).filter(...).scalar())
    nested = (
        db.query.return_value
          .filter.return_value
          .filter.return_value
          .scalar
    )
    nested.return_value = scalar_value

    # sum() queries
    sum_chain = (
        db.query.return_value
          .filter.return_value
          .scalar
    )
    sum_chain.return_value = sum_value

    # group_by / order_by / limit chains (top rules, alert series)
    db.query.return_value.filter.return_value.group_by.return_value \
        .order_by.return_value.limit.return_value.all.return_value = []

    # join chain (recent alerts)
    db.query.return_value.join.return_value.filter.return_value \
        .order_by.return_value.limit.return_value.all.return_value = []

    # 30-day loop queries
    db.query.return_value.filter.return_value \
        .filter.return_value.scalar.return_value = scalar_value

    return db


# ── KPI Types ──────────────────────────────────────────────────────────────

class TestKPITypes:
    """Every KPI field must be the right Python type."""

    def _get_kpis(self, service):
        db = _make_db(scalar_value=3, sum_value=9_999.0)
        result = service.get_dashboard(db)
        return result.kpis

    def test_open_alerts_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.open_alerts, int)

    def test_high_critical_alerts_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.high_critical_alerts, int)

    def test_total_transactions_today_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.total_transactions_today, int)

    def test_flagged_transactions_today_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.flagged_transactions_today, int)

    def test_total_volume_today_is_numeric(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.total_volume_today, (int, float))

    def test_open_cases_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.open_cases, int)

    def test_high_risk_customers_is_int(self, service):
        kpis = self._get_kpis(service)
        assert isinstance(kpis.high_risk_customers, int)


# ── Non-Negative Invariants ────────────────────────────────────────────────

class TestKPINonNegative:
    """Every KPI must be >= 0 regardless of DB stub values."""

    def _get_kpis(self, service, scalar_value=0, sum_value=0.0):
        db = _make_db(scalar_value=scalar_value, sum_value=sum_value)
        return service.get_dashboard(db).kpis

    def test_open_alerts_non_negative(self, service):
        assert self._get_kpis(service).open_alerts >= 0

    def test_high_critical_non_negative(self, service):
        assert self._get_kpis(service).high_critical_alerts >= 0

    def test_transactions_today_non_negative(self, service):
        assert self._get_kpis(service).total_transactions_today >= 0

    def test_flagged_today_non_negative(self, service):
        assert self._get_kpis(service).flagged_transactions_today >= 0

    def test_volume_today_non_negative(self, service):
        assert self._get_kpis(service).total_volume_today >= 0

    def test_open_cases_non_negative(self, service):
        assert self._get_kpis(service).open_cases >= 0

    def test_high_risk_customers_non_negative(self, service):
        assert self._get_kpis(service).high_risk_customers >= 0

    def test_all_zeros_when_db_returns_none(self, service):
        """Scalar returning None must be converted to 0, not crash."""
        db = _make_db(scalar_value=None, sum_value=None)
        kpis = service.get_dashboard(db).kpis
        assert kpis.open_alerts >= 0
        assert kpis.total_volume_today >= 0


# ── Alerts By Severity ─────────────────────────────────────────────────────

class TestAlertsBySeverity:
    def test_all_four_severity_levels_present(self, service):
        db = _make_db()
        result = service.get_dashboard(db)
        sev = result.alerts_by_severity
        assert hasattr(sev, "low")
        assert hasattr(sev, "medium")
        assert hasattr(sev, "high")
        assert hasattr(sev, "critical")

    def test_severity_counts_non_negative(self, service):
        db = _make_db()
        sev = service.get_dashboard(db).alerts_by_severity
        assert sev.low >= 0
        assert sev.medium >= 0
        assert sev.high >= 0
        assert sev.critical >= 0


# ── Time Series ────────────────────────────────────────────────────────────

class TestTimeSeries:
    def test_transaction_series_has_30_days(self, service):
        db = _make_db()
        series = service.get_dashboard(db).transaction_series
        assert len(series.dates) == 30
        assert len(series.amounts) == 30
        assert len(series.counts) == 30

    def test_alert_series_has_30_days(self, service):
        db = _make_db()
        series = service.get_dashboard(db).alerts_series
        assert len(series.dates) == 30
        assert len(series.counts) == 30

    def test_dates_are_strings(self, service):
        db = _make_db()
        series = service.get_dashboard(db).transaction_series
        for d in series.dates:
            assert isinstance(d, str)
            assert len(d) == 10  # YYYY-MM-DD


# ── Cases By Status ────────────────────────────────────────────────────────

class TestCasesByStatus:
    def test_cases_by_status_is_dict(self, service):
        db = _make_db()
        result = service.get_dashboard(db)
        assert isinstance(result.cases_by_status, dict)

    def test_open_status_present(self, service):
        db = _make_db()
        result = service.get_dashboard(db)
        assert "open" in result.cases_by_status
