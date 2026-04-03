"""Tests for Closing Line Value (CLV) audit functions (P1.D2)."""

from __future__ import annotations

import pytest

from japredictbet.betting.engine import (
    closing_line_value,
    clv_hit_rate,
    clv_summary,
)


class TestClosingLineValue:
    """Tests for closing_line_value()."""

    def test_positive_clv_better_odds(self):
        """Entry odds higher than closing → positive CLV (beat the market)."""
        # Entry at 2.0 (implied 50%), closing at 1.8 (implied 55.6%)
        clv = closing_line_value(entry_odds=2.0, closing_odds=1.8)
        assert clv > 0  # 0.556 - 0.500 = 0.056

    def test_negative_clv_worse_odds(self):
        """Entry odds lower than closing → negative CLV."""
        # Entry at 1.8 (implied 55.6%), closing at 2.0 (implied 50%)
        clv = closing_line_value(entry_odds=1.8, closing_odds=2.0)
        assert clv < 0  # 0.500 - 0.556 = -0.056

    def test_zero_clv_same_odds(self):
        """Same entry and closing odds → CLV = 0."""
        clv = closing_line_value(entry_odds=1.9, closing_odds=1.9)
        assert clv == pytest.approx(0.0)

    def test_clv_exact_value(self):
        """Verify exact CLV computation."""
        # Entry at 2.0 (prob=0.5), Close at 1.5 (prob=0.667)
        clv = closing_line_value(entry_odds=2.0, closing_odds=1.5)
        expected = (1 / 1.5) - (1 / 2.0)  # 0.667 - 0.5 = 0.167
        assert clv == pytest.approx(expected)


class TestClvHitRate:
    """Tests for clv_hit_rate()."""

    def test_all_positive(self):
        """All positive CLVs → 100% hit rate."""
        assert clv_hit_rate([0.05, 0.10, 0.02]) == pytest.approx(1.0)

    def test_all_negative(self):
        """All negative CLVs → 0% hit rate."""
        assert clv_hit_rate([-0.05, -0.10, -0.02]) == pytest.approx(0.0)

    def test_mixed(self):
        """Mixed CLVs → correct fraction."""
        assert clv_hit_rate([0.05, -0.03, 0.01, -0.01]) == pytest.approx(0.5)

    def test_zero_counts_as_positive(self):
        """CLV = 0 counts as 'not worse' (hit)."""
        assert clv_hit_rate([0.0, -0.01]) == pytest.approx(0.5)

    def test_empty_returns_zero(self):
        """Empty list → 0.0."""
        assert clv_hit_rate([]) == pytest.approx(0.0)


class TestClvSummary:
    """Tests for clv_summary()."""

    def test_basic_summary(self):
        """Summary computes correct statistics."""
        values = [0.05, -0.03, 0.10, -0.01, 0.02]
        result = clv_summary(values)
        assert result["n_bets"] == 5
        assert result["hit_rate"] == pytest.approx(0.6)
        assert result["mean_clv"] == pytest.approx(0.026)
        assert result["median_clv"] == pytest.approx(0.02)

    def test_empty_summary(self):
        """Empty input → zero stats."""
        result = clv_summary([])
        assert result["n_bets"] == 0
        assert result["mean_clv"] == pytest.approx(0.0)
        assert result["hit_rate"] == pytest.approx(0.0)
