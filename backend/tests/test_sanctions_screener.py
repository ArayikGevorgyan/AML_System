"""
Tests for SanctionsScreener
============================
Tests the core scoring and normalization logic of the sanctions screener.
No database required — all DB-dependent methods are tested with mocks.

Run with:
    pytest backend/tests/test_sanctions_screener.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from services.sanctions_screener import SanctionsScreener


@pytest.fixture
def screener():
    return SanctionsScreener()


# ── Normalization ──────────────────────────────────────────────────────────

class TestNormalize:
    def test_lowercase(self, screener):
        assert screener._normalize("OSAMA") == "osama"

    def test_strips_noise_words(self, screener):
        assert screener._normalize("Mr John Smith") == "john smith"
        assert screener._normalize("Dr Jane Doe") == "jane doe"
        assert screener._normalize("Prof Ali Hassan") == "ali hassan"

    def test_keeps_arabic_particles(self, screener):
        """al, bin, abu, ibn must NOT be stripped — they are name particles."""
        result = screener._normalize("Osama bin Laden")
        assert "bin" in result
        assert "laden" in result
        assert "osama" in result

    def test_unicode_to_ascii(self, screener):
        result = screener._normalize("Müller")
        assert result == "muller"

    def test_removes_punctuation(self, screener):
        result = screener._normalize("Al-Shabaab")
        assert "-" not in result

    def test_empty_string(self, screener):
        assert screener._normalize("") == ""

    def test_none_like_empty(self, screener):
        assert screener._normalize("   ") == ""

    def test_multiple_spaces_collapsed(self, screener):
        result = screener._normalize("John   Smith")
        assert result == "john smith"


# ── Scoring ────────────────────────────────────────────────────────────────

class TestComputeScore:
    def test_identical_strings_score_100(self, screener):
        assert screener._compute_score("osama", {"osama"}, "osama") == 100.0

    def test_exact_token_subset_scores_100(self, screener):
        """Query tokens are a subset of candidate tokens → score 100."""
        score = screener._compute_score(
            "osama", {"osama"},
            "osama bin laden"
        )
        assert score == 100.0

    def test_empty_query_scores_zero(self, screener):
        assert screener._compute_score("", set(), "osama bin laden") == 0.0

    def test_empty_candidate_scores_zero(self, screener):
        assert screener._compute_score("osama", {"osama"}, "") == 0.0

    def test_fuzzy_match_below_100(self, screener):
        """'Laden' vs 'Ladin' — fuzzy, should be high but below 100."""
        score = screener._compute_score("laden", {"laden"}, "ladin")
        assert 70 <= score < 100

    def test_completely_different_names_low_score(self, screener):
        score = screener._compute_score("john smith", {"john", "smith"}, "vladimir putin")
        assert score < 50

    def test_partial_token_match_scores_reasonably(self, screener):
        """Searching 'Putin' against 'Vladimir Putin' — one token matches."""
        score = screener._compute_score("putin", {"putin"}, "vladimir putin")
        assert score == 100.0  # token subset match

    def test_score_capped_at_99_9_for_fuzzy(self, screener):
        """Fuzzy matches must never reach 100.0."""
        score = screener._compute_score("osama", {"osama"}, "osamaa")
        assert score < 100.0
        assert score > 80.0

    def test_multi_token_query_all_match(self, screener):
        score = screener._compute_score(
            "bin laden", {"bin", "laden"},
            "osama bin laden al qaeda"
        )
        assert score == 100.0

    def test_multi_token_partial_match(self, screener):
        score = screener._compute_score(
            "bin laden", {"bin", "laden"},
            "mohammed laden"
        )
        assert 60 <= score < 100


# ── Score Labels ───────────────────────────────────────────────────────────

class TestScoreLabel:
    def test_strong(self, screener):
        assert screener._score_label(90) == "STRONG"
        assert screener._score_label(85) == "STRONG"

    def test_possible(self, screener):
        assert screener._score_label(75) == "POSSIBLE"
        assert screener._score_label(70) == "POSSIBLE"

    def test_weak(self, screener):
        assert screener._score_label(69) == "WEAK"
        assert screener._score_label(50) == "WEAK"

    def test_exact_100_is_strong(self, screener):
        assert screener._score_label(100) == "STRONG"


# ── Address Formatting ─────────────────────────────────────────────────────

class TestFormatAddress:
    def test_full_address(self, screener):
        location = MagicMock()
        location.address = "123 Main St"
        location.city = "Tehran"
        location.state_province = None
        location.postal_code = "12345"
        location.country = "Iran"
        result = screener._format_address(location)
        assert "Tehran" in result
        assert "Iran" in result
        assert "123 Main St" in result

    def test_none_location_returns_none(self, screener):
        assert screener._format_address(None) is None

    def test_empty_parts_omitted(self, screener):
        location = MagicMock()
        location.address = None
        location.city = "Moscow"
        location.state_province = None
        location.postal_code = None
        location.country = "Russia"
        result = screener._format_address(location)
        assert result == "Moscow, Russia"


# ── Known OFAC Name Pairs ──────────────────────────────────────────────────

class TestKnownOFACPairs:
    """Regression tests based on known OFAC name variants."""

    @pytest.mark.parametrize("query,candidate,min_score", [
        ("osama",        "osama bin laden",            100.0),
        ("bin laden",    "osama bin laden",            100.0),
        ("al shabaab",   "al-shabaab",                  80.0),
        ("irisl",        "irisl",                      100.0),
        ("putin",        "vladimir vladimirovich putin", 100.0),
        ("kim jong un",  "kim jong-un",                 80.0),
    ])
    def test_known_pair(self, screener, query, candidate, min_score):
        normalized_q = screener._normalize(query)
        tokens = set(normalized_q.split())
        normalized_c = screener._normalize(candidate)
        score = screener._compute_score(normalized_q, tokens, normalized_c)
        assert score >= min_score, (
            f"Expected score >= {min_score} for '{query}' vs '{candidate}', got {score}"
        )
