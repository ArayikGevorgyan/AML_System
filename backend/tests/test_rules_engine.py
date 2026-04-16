"""
Tests for Rules Engine
========================
Tests each AML detection rule in isolation using mock DB queries.

Run with:
    pytest backend/tests/test_rules_engine.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from services.rules_engine import RulesEngine, RuleMatch


@pytest.fixture
def engine():
    return RulesEngine()


def make_rule(**kwargs):
    rule = MagicMock()
    rule.id = kwargs.get("id", 1)
    rule.name = kwargs.get("name", "Test Rule")
    rule.category = kwargs.get("category", "large_transaction")
    rule.severity = kwargs.get("severity", "high")
    rule.threshold_amount = kwargs.get("threshold_amount", None)
    rule.threshold_count = kwargs.get("threshold_count", None)
    rule.time_window_hours = kwargs.get("time_window_hours", None)
    rule.high_risk_countries = kwargs.get("high_risk_countries", None)
    rule.is_active = True
    return rule


def make_transaction(**kwargs):
    txn = MagicMock()
    txn.id = kwargs.get("id", 1)
    txn.amount = kwargs.get("amount", 100.0)
    txn.currency = kwargs.get("currency", "USD")
    txn.from_customer_id = kwargs.get("from_customer_id", 1)
    txn.to_customer_id = kwargs.get("to_customer_id", 2)
    txn.originating_country = kwargs.get("originating_country", "US")
    txn.destination_country = kwargs.get("destination_country", "US")
    txn.transaction_type = kwargs.get("transaction_type", "transfer")
    txn.flagged = False
    return txn


def make_customer(**kwargs):
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.full_name = kwargs.get("full_name", "Test Customer")
    c.pep_status = kwargs.get("pep_status", False)
    c.country = kwargs.get("country", "US")
    return c


def make_db_count(count):
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.scalar.return_value = count
    db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = count
    db.query.return_value.filter.return_value.scalar.return_value = count
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.scalar.return_value = count
    return db


# ── Large Transaction ──────────────────────────────────────────────────────

class TestLargeTransaction:
    def test_above_threshold_triggers(self, engine):
        rule = make_rule(category="large_transaction", threshold_amount=10_000)
        txn = make_transaction(amount=15_000)
        match = engine._check_large_transaction(rule, txn, None, None)
        assert match is not None
        assert match.risk_score > 50

    def test_below_threshold_no_match(self, engine):
        rule = make_rule(category="large_transaction", threshold_amount=10_000)
        txn = make_transaction(amount=5_000)
        match = engine._check_large_transaction(rule, txn, None, None)
        assert match is None

    def test_exactly_at_threshold_triggers(self, engine):
        rule = make_rule(threshold_amount=10_000)
        txn = make_transaction(amount=10_000)
        match = engine._check_large_transaction(rule, txn, None, None)
        assert match is not None

    def test_risk_score_increases_with_amount(self, engine):
        rule = make_rule(threshold_amount=10_000)
        match_low = engine._check_large_transaction(rule, make_transaction(amount=11_000), None, None)
        match_high = engine._check_large_transaction(rule, make_transaction(amount=100_000), None, None)
        assert match_high.risk_score > match_low.risk_score


# ── Structuring ────────────────────────────────────────────────────────────

class TestStructuring:
    def test_just_below_threshold_triggers(self, engine):
        rule = make_rule(category="structuring", threshold_amount=10_000, time_window_hours=72)
        txn = make_transaction(amount=9_500)
        db = make_db_count(2)
        match = engine._check_structuring(rule, txn, None, db)
        assert match is not None

    def test_far_below_threshold_no_match(self, engine):
        rule = make_rule(category="structuring", threshold_amount=10_000, time_window_hours=72)
        txn = make_transaction(amount=5_000)
        db = make_db_count(0)
        match = engine._check_structuring(rule, txn, None, db)
        assert match is None

    def test_above_threshold_no_match(self, engine):
        rule = make_rule(category="structuring", threshold_amount=10_000, time_window_hours=72)
        txn = make_transaction(amount=10_500)
        db = make_db_count(0)
        match = engine._check_structuring(rule, txn, None, db)
        assert match is None


# ── High Risk Country ──────────────────────────────────────────────────────

class TestHighRiskCountry:
    def test_originating_high_risk_triggers(self, engine):
        rule = make_rule(category="high_risk_country", high_risk_countries=None)
        txn = make_transaction(originating_country="IR", destination_country="US")
        customer = make_customer(country="US")
        match = engine._check_high_risk_country(rule, txn, customer, None)
        assert match is not None
        assert "IR" in match.reason

    def test_destination_high_risk_triggers(self, engine):
        rule = make_rule(high_risk_countries=None)
        txn = make_transaction(originating_country="US", destination_country="KP")
        customer = make_customer(country="US")
        match = engine._check_high_risk_country(rule, txn, customer, None)
        assert match is not None

    def test_clean_countries_no_match(self, engine):
        rule = make_rule(high_risk_countries=None)
        txn = make_transaction(originating_country="US", destination_country="DE")
        customer = make_customer(country="US")
        match = engine._check_high_risk_country(rule, txn, customer, None)
        assert match is None

    def test_multiple_risk_countries_higher_score(self, engine):
        rule = make_rule(high_risk_countries=None)
        txn_one = make_transaction(originating_country="IR", destination_country="US")
        txn_two = make_transaction(originating_country="IR", destination_country="KP")
        customer = make_customer(country="US")
        match_one = engine._check_high_risk_country(rule, txn_one, customer, None)
        match_two = engine._check_high_risk_country(rule, txn_two, customer, None)
        assert match_two.risk_score >= match_one.risk_score


# ── PEP Transaction ────────────────────────────────────────────────────────

class TestPEPTransaction:
    def test_pep_customer_triggers(self, engine):
        rule = make_rule(category="pep_transaction", threshold_amount=0)
        txn = make_transaction(amount=50_000)
        customer = make_customer(pep_status=True, full_name="John Doe")
        match = engine._check_pep_transaction(rule, txn, customer, None)
        assert match is not None
        assert "John Doe" in match.reason

    def test_non_pep_customer_no_match(self, engine):
        rule = make_rule(threshold_amount=0)
        txn = make_transaction(amount=50_000)
        customer = make_customer(pep_status=False)
        match = engine._check_pep_transaction(rule, txn, customer, None)
        assert match is None

    def test_no_customer_no_match(self, engine):
        rule = make_rule(threshold_amount=0)
        txn = make_transaction(amount=50_000)
        match = engine._check_pep_transaction(rule, txn, None, None)
        assert match is None


# ── Round Amount ───────────────────────────────────────────────────────────

class TestRoundAmount:
    def test_round_large_amount_triggers(self, engine):
        rule = make_rule(category="round_amount", threshold_amount=1_000, time_window_hours=48)
        txn = make_transaction(amount=10_000.0)
        db = make_db_count(2)
        match = engine._check_round_amount(rule, txn, None, db)
        assert match is not None

    def test_non_round_amount_no_match(self, engine):
        rule = make_rule(threshold_amount=1_000, time_window_hours=48)
        txn = make_transaction(amount=9_876.54)
        db = make_db_count(0)
        match = engine._check_round_amount(rule, txn, None, db)
        assert match is None

    def test_small_round_below_threshold_no_match(self, engine):
        rule = make_rule(threshold_amount=1_000, time_window_hours=48)
        txn = make_transaction(amount=500.0)
        db = make_db_count(0)
        match = engine._check_round_amount(rule, txn, None, db)
        assert match is None


# ── Rule Match Dataclass ───────────────────────────────────────────────────

class TestRuleMatch:
    def test_rule_match_creation(self):
        match = RuleMatch(
            rule_id=1,
            rule_name="Test",
            category="large_transaction",
            severity="high",
            reason="Test reason",
            risk_score=75.0,
        )
        assert match.rule_id == 1
        assert match.details == {}

    def test_rule_match_with_details(self):
        match = RuleMatch(
            rule_id=1, rule_name="Test", category="structuring",
            severity="critical", reason="Structuring detected",
            risk_score=88.0, details={"amount": 9500, "count": 3}
        )
        assert match.details["count"] == 3
