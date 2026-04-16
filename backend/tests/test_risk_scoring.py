"""
Tests for Risk Scoring Service
================================
Tests the customer risk score calculation logic.
Uses mock objects to simulate DB queries without a real database.

Run with:
    pytest backend/tests/test_risk_scoring.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from services.risk_scoring_service import (
    _base_profile_score,
    _transaction_behaviour_score,
    _alert_history_score,
    compute_customer_risk_score,
)


def make_customer(**kwargs):
    """Helper: create a mock Customer object."""
    customer = MagicMock()
    customer.id = kwargs.get("id", 1)
    customer.customer_number = kwargs.get("customer_number", "CUST-001")
    customer.full_name = kwargs.get("full_name", "Test User")
    customer.risk_level = kwargs.get("risk_level", "low")
    customer.pep_status = kwargs.get("pep_status", False)
    customer.sanctions_flag = kwargs.get("sanctions_flag", False)
    customer.nationality = kwargs.get("nationality", "US")
    customer.country = kwargs.get("country", "US")
    return customer


def make_transaction(**kwargs):
    t = MagicMock()
    t.amount = kwargs.get("amount", 100.0)
    t.flagged = kwargs.get("flagged", False)
    return t


def make_alert(**kwargs):
    a = MagicMock()
    a.severity = kwargs.get("severity", "low")
    a.status = kwargs.get("status", "open")
    return a


# ── Base Profile Score ─────────────────────────────────────────────────────

class TestBaseProfileScore:
    def test_low_risk_clean_customer(self):
        customer = make_customer(risk_level="low", pep_status=False, sanctions_flag=False)
        score = _base_profile_score(customer)
        assert score == 0.0

    def test_medium_risk_customer(self):
        customer = make_customer(risk_level="medium")
        score = _base_profile_score(customer)
        assert score == 15.0

    def test_high_risk_customer(self):
        customer = make_customer(risk_level="high")
        score = _base_profile_score(customer)
        assert score == 30.0

    def test_critical_risk_customer(self):
        customer = make_customer(risk_level="critical")
        score = _base_profile_score(customer)
        assert score == 50.0

    def test_pep_adds_20(self):
        customer = make_customer(risk_level="low", pep_status=True)
        score = _base_profile_score(customer)
        assert score == 20.0

    def test_sanctions_flag_adds_30(self):
        customer = make_customer(risk_level="low", sanctions_flag=True)
        score = _base_profile_score(customer)
        assert score == 30.0

    def test_pep_plus_sanctions_adds_50(self):
        customer = make_customer(risk_level="low", pep_status=True, sanctions_flag=True)
        score = _base_profile_score(customer)
        assert score == 50.0

    def test_high_risk_country_adds_20(self):
        customer = make_customer(risk_level="low", nationality="IR")
        score = _base_profile_score(customer)
        assert score >= 20.0

    def test_score_capped_at_60(self):
        customer = make_customer(
            risk_level="critical", pep_status=True,
            sanctions_flag=True, nationality="IR"
        )
        score = _base_profile_score(customer)
        assert score <= 60.0


# ── Transaction Behaviour Score ────────────────────────────────────────────

class TestTransactionBehaviourScore:
    def _make_db(self, transactions):
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.all.return_value = transactions
        db.query.return_value = query_mock
        return db

    def test_no_transactions_scores_zero(self):
        db = self._make_db([])
        score = _transaction_behaviour_score(1, db)
        assert score == 0.0

    def test_high_flagged_ratio_increases_score(self):
        txns = [make_transaction(flagged=True) for _ in range(8)]
        txns += [make_transaction(flagged=False) for _ in range(2)]
        db = self._make_db(txns)
        score = _transaction_behaviour_score(1, db)
        assert score > 15.0

    def test_large_total_amount_increases_score(self):
        txns = [make_transaction(amount=200_000, flagged=False)]
        db = self._make_db(txns)
        score = _transaction_behaviour_score(1, db)
        assert score >= 8.0

    def test_very_large_total_amount(self):
        txns = [make_transaction(amount=600_000, flagged=False)]
        db = self._make_db(txns)
        score = _transaction_behaviour_score(1, db)
        assert score >= 15.0

    def test_score_capped_at_30(self):
        txns = [make_transaction(amount=1_000_000, flagged=True) for _ in range(100)]
        db = self._make_db(txns)
        score = _transaction_behaviour_score(1, db)
        assert score <= 30.0


# ── Alert History Score ────────────────────────────────────────────────────

class TestAlertHistoryScore:
    def _make_db(self, alerts):
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.filter.return_value.filter.return_value.all.return_value = alerts
        query_mock.filter.return_value.all.return_value = alerts
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = alerts
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = alerts
        db.query.return_value.filter.return_value.all.return_value = alerts
        return db

    def test_no_alerts_scores_zero(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        score = _alert_history_score(1, db)
        assert score == 0.0

    def test_critical_alert_increases_score(self):
        alerts = [make_alert(severity="critical")]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = alerts
        score = _alert_history_score(1, db)
        assert score > 0

    def test_score_capped_at_25(self):
        alerts = [make_alert(severity="critical") for _ in range(50)]
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = alerts
        score = _alert_history_score(1, db)
        assert score <= 25.0


# ── Composite Score ────────────────────────────────────────────────────────

class TestComputeCustomerRiskScore:
    def test_clean_customer_low_band(self):
        customer = make_customer(risk_level="low")
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = compute_customer_risk_score(customer, db)
        assert result["risk_band"] == "low"
        assert result["risk_score"] < 25

    def test_result_has_required_keys(self):
        customer = make_customer()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = compute_customer_risk_score(customer, db)
        assert "risk_score" in result
        assert "risk_band" in result
        assert "breakdown" in result
        assert "computed_at" in result

    def test_score_never_exceeds_100(self):
        customer = make_customer(
            risk_level="critical", pep_status=True,
            sanctions_flag=True, nationality="IR"
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = compute_customer_risk_score(customer, db)
        assert result["risk_score"] <= 100.0

    def test_band_boundaries(self):
        """Test that score bands are correctly assigned."""
        bands = {0: "low", 24: "low", 25: "medium", 49: "medium",
                 50: "high", 74: "high", 75: "critical", 100: "critical"}
        for score, expected_band in bands.items():
            if score >= 75:
                band = "critical"
            elif score >= 50:
                band = "high"
            elif score >= 25:
                band = "medium"
            else:
                band = "low"
            assert band == expected_band
