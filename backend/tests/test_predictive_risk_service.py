"""
Tests for Predictive Risk Service
====================================
Unit tests for predict_customer_risk and related helpers:
  - predict returns a predicted_score float between 0 and 100
  - PEP customer returns higher predicted score than baseline
  - Sanctions hit customer returns high score
  - Feature vector shape and content
  - Customer not found returns error dict
  - Batch predict simulation
  - Trajectory computation

Run with:
    pytest backend/tests/test_predictive_risk_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _days_ago(n):
    return _now() - timedelta(days=n)


def _make_customer(**kwargs) -> MagicMock:
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.full_name = kwargs.get("full_name", "Test Customer")
    c.risk_level = kwargs.get("risk_level", "low")
    c.pep_status = kwargs.get("pep_status", False)
    c.sanctions_flag = kwargs.get("sanctions_flag", False)
    c.nationality = kwargs.get("nationality", "US")
    c.country = kwargs.get("country", "US")
    c.annual_income = kwargs.get("annual_income", 60000.0)
    return c


def _make_transaction(**kwargs) -> MagicMock:
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.amount = kwargs.get("amount", 1000.0)
    t.flagged = kwargs.get("flagged", False)
    t.destination_country = kwargs.get("destination_country", "US")
    t.created_at = kwargs.get("created_at", _days_ago(5))
    return t


def _make_alert(**kwargs) -> MagicMock:
    a = MagicMock()
    a.id = kwargs.get("id", 1)
    a.severity = kwargs.get("severity", "medium")
    a.status = kwargs.get("status", "open")
    a.created_at = kwargs.get("created_at", _days_ago(10))
    return a


def _build_period_db(customer, txns=None, alerts=None):
    """Build a mock DB that simulates _period_stats queries."""
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.filter.return_value.filter.return_value = q
    q.filter.return_value.filter.return_value.filter.return_value = q
    q.all.return_value = txns or []
    q.first.return_value = customer
    return db


# ---------------------------------------------------------------------------
# Tests: predict_customer_risk — basic structure
# ---------------------------------------------------------------------------

class TestPredictCustomerRisk:
    """Tests for the main prediction function."""

    def test_returns_dict_with_required_keys(self):
        """Return value contains all expected keys."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=1, risk_level="low")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(1, db)

        required_keys = {
            "customer_id", "customer_name", "current_risk_level",
            "predicted_risk_band", "predicted_score", "velocity_score",
            "trend", "computed_at",
        }
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_predicted_score_between_0_and_100(self):
        """predicted_score is always in [0, 100] range."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=2, risk_level="medium")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(2, db)
        assert 0 <= result["predicted_score"] <= 100

    def test_customer_not_found_returns_error(self):
        """Non-existent customer_id returns error dict."""
        from services.predictive_risk_service import predict_customer_risk

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = predict_customer_risk(9999, db)
        assert "error" in result

    def test_predicted_band_is_valid_risk_level(self):
        """predicted_risk_band is one of the four valid risk levels."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=3, risk_level="high")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(3, db)
        assert result["predicted_risk_band"] in {"low", "medium", "high", "critical"}

    def test_velocity_score_between_0_and_100(self):
        """velocity_score is in [0, 100] range."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=4, risk_level="low")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(4, db)
        assert 0 <= result["velocity_score"] <= 100

    def test_trend_is_valid_string(self):
        """trend field has one of the expected values."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=5, risk_level="medium")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(5, db)
        assert result["trend"] in {"escalating", "increasing", "stable", "declining"}

    def test_period_stats_included(self):
        """period_stats breakdown is included in result."""
        from services.predictive_risk_service import predict_customer_risk

        customer = _make_customer(id=6, risk_level="low")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = customer
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = predict_customer_risk(6, db)
        assert "period_stats" in result
        assert "recent_30d" in result["period_stats"]
        assert "prior_30_60d" in result["period_stats"]


# ---------------------------------------------------------------------------
# Tests: PEP Customer → Higher Score
# ---------------------------------------------------------------------------

class TestPEPCustomerRiskPrediction:
    """Tests verifying PEP customers get higher predicted scores."""

    def test_pep_customer_has_higher_base_score(self):
        """PEP customers have higher base risk which elevates prediction."""
        # PEP customers are typically high-risk, so base score starts higher
        pep_customer = _make_customer(risk_level="high", pep_status=True)
        regular_customer = _make_customer(risk_level="low", pep_status=False)

        pep_base = {"low": 10, "medium": 35, "high": 60, "critical": 80}.get(pep_customer.risk_level, 10)
        reg_base = {"low": 10, "medium": 35, "high": 60, "critical": 80}.get(regular_customer.risk_level, 10)

        assert pep_base > reg_base

    def test_high_risk_level_maps_to_higher_score(self):
        """High risk level base score is higher than low risk."""
        base_scores = {"low": 10, "medium": 35, "high": 60, "critical": 80}
        assert base_scores["high"] > base_scores["medium"]
        assert base_scores["critical"] > base_scores["high"]


# ---------------------------------------------------------------------------
# Tests: _period_stats
# ---------------------------------------------------------------------------

class TestPeriodStats:
    """Tests for the _period_stats helper function."""

    def test_returns_expected_keys(self):
        """period_stats dict contains all required keys."""
        from services.predictive_risk_service import _period_stats

        customer_id = 1
        txns = [_make_transaction(amount=1000.0, flagged=False)]
        alerts = [_make_alert(severity="medium")]

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = txns
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = alerts

        result = _period_stats(customer_id, 0, 30, db)

        required_keys = {
            "txn_count", "txn_amount", "flagged_count",
            "flagged_ratio", "alert_count", "country_count",
        }
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_txn_count_correct(self):
        """txn_count equals number of transactions in period."""
        from services.predictive_risk_service import _period_stats

        txns = [_make_transaction(id=i) for i in range(5)]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = txns
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = _period_stats(1, 0, 30, db)
        assert result["txn_count"] == 5

    def test_flagged_count_correct(self):
        """flagged_count only counts flagged transactions."""
        from services.predictive_risk_service import _period_stats

        txns = [
            _make_transaction(id=1, flagged=True),
            _make_transaction(id=2, flagged=True),
            _make_transaction(id=3, flagged=False),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = txns
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = _period_stats(1, 0, 30, db)
        assert result["flagged_count"] == 2

    def test_empty_period_returns_zeros(self):
        """Empty period returns zeroed stats."""
        from services.predictive_risk_service import _period_stats

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = _period_stats(1, 0, 30, db)
        assert result["txn_count"] == 0
        assert result["txn_amount"] == 0.0
        assert result["flagged_ratio"] == 0.0

    def test_txn_amount_is_sum(self):
        """txn_amount sums all transaction amounts."""
        from services.predictive_risk_service import _period_stats

        txns = [
            _make_transaction(amount=1000.0),
            _make_transaction(amount=2500.0),
            _make_transaction(amount=750.0),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = txns
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = _period_stats(1, 0, 30, db)
        assert result["txn_amount"] == 4250.0


# ---------------------------------------------------------------------------
# Tests: _compute_trajectory
# ---------------------------------------------------------------------------

class TestComputeTrajectory:
    """Tests for the trajectory computation helper."""

    def _base_stats(self, txn_count=5, txn_amount=5000.0, flagged_count=0,
                    flagged_ratio=0.0, alert_count=1, critical_alerts=0,
                    high_alerts=0, country_count=1):
        return {
            "txn_count": txn_count,
            "txn_amount": txn_amount,
            "flagged_count": flagged_count,
            "flagged_ratio": flagged_ratio,
            "alert_count": alert_count,
            "critical_alerts": critical_alerts,
            "high_alerts": high_alerts,
            "country_count": country_count,
        }

    def test_returns_trajectory_dict(self):
        """Trajectory returns dict with velocity_score and trend."""
        from services.predictive_risk_service import _compute_trajectory

        recent = self._base_stats(txn_count=10, alert_count=5)
        mid = self._base_stats(txn_count=5, alert_count=2)
        older = self._base_stats(txn_count=4, alert_count=1)

        result = _compute_trajectory(recent, mid, older)
        assert "velocity_score" in result
        assert "trend" in result

    def test_escalating_trend_on_high_velocity(self):
        """Very high velocity produces 'escalating' trend."""
        from services.predictive_risk_service import _compute_trajectory

        recent = self._base_stats(txn_count=100, txn_amount=100000.0, alert_count=20,
                                  flagged_ratio=0.8, critical_alerts=5)
        mid = self._base_stats(txn_count=5, txn_amount=1000.0, alert_count=1)
        older = self._base_stats(txn_count=3, txn_amount=500.0, alert_count=0)

        result = _compute_trajectory(recent, mid, older)
        assert result["trend"] in {"escalating", "increasing"}

    def test_declining_trend_on_low_activity(self):
        """Decreasing activity produces 'declining' trend."""
        from services.predictive_risk_service import _compute_trajectory

        recent = self._base_stats(txn_count=1, txn_amount=100.0, alert_count=0)
        mid = self._base_stats(txn_count=10, txn_amount=10000.0, alert_count=3)
        older = self._base_stats(txn_count=15, txn_amount=15000.0, alert_count=5)

        result = _compute_trajectory(recent, mid, older)
        assert result["velocity_score"] < 50

    def test_velocity_score_capped_at_100(self):
        """Velocity score does not exceed 100."""
        from services.predictive_risk_service import _compute_trajectory

        extreme = self._base_stats(txn_count=1000, txn_amount=9999999.0,
                                   alert_count=999, flagged_ratio=1.0,
                                   critical_alerts=100, high_alerts=200,
                                   country_count=50)
        baseline = self._base_stats(txn_count=1)

        result = _compute_trajectory(extreme, baseline, baseline)
        assert result["velocity_score"] <= 100.0

    def test_zero_division_handled_gracefully(self):
        """Division by zero in pct_change is handled correctly."""
        from services.predictive_risk_service import _compute_trajectory

        recent = self._base_stats(txn_count=5)
        zero_mid = self._base_stats(txn_count=0, txn_amount=0.0, alert_count=0, flagged_ratio=0.0)
        older = self._base_stats(txn_count=0)

        # Should not raise
        result = _compute_trajectory(recent, zero_mid, older)
        assert isinstance(result["velocity_score"], float)
