"""Tests for risk management: Kelly staking, drawdown, slippage (P1.D3)."""

from __future__ import annotations

import pytest

from japredictbet.betting.risk import (
    DrawdownResult,
    KellyResult,
    apply_slippage,
    kelly_fraction,
    kelly_stake,
    simulate_drawdown,
)


class TestKellyFraction:
    """Tests for kelly_fraction()."""

    def test_positive_edge(self):
        """With positive edge, Kelly fraction is positive."""
        # p=0.55, odds=2.0: b=1, Kelly = (0.55*1 - 0.45)/1 = 0.10
        assert kelly_fraction(0.55, 2.0) == pytest.approx(0.10)

    def test_no_edge(self):
        """Fair odds → zero fraction."""
        # p=0.5, odds=2.0: (0.5*1 - 0.5)/1 = 0
        assert kelly_fraction(0.5, 2.0) == pytest.approx(0.0)

    def test_negative_edge(self):
        """Negative edge → clamped to 0."""
        assert kelly_fraction(0.3, 2.0) == pytest.approx(0.0)

    def test_high_probability(self):
        """Very high probability doesn't exceed 1.0."""
        result = kelly_fraction(0.99, 1.5)
        assert 0.0 <= result <= 1.0

    def test_invalid_inputs(self):
        """Edge cases: odds <= 1 or p out of range."""
        assert kelly_fraction(0.5, 1.0) == pytest.approx(0.0)
        assert kelly_fraction(0.0, 2.0) == pytest.approx(0.0)
        assert kelly_fraction(1.0, 2.0) == pytest.approx(0.0)


class TestKellyStake:
    """Tests for kelly_stake()."""

    def test_quarter_kelly(self):
        """Quarter Kelly is 25% of full Kelly."""
        result = kelly_stake(p_model=0.55, odds=2.0, bankroll=1000)
        assert isinstance(result, KellyResult)
        assert result.quarter_kelly == pytest.approx(result.full_kelly * 0.25)
        assert result.half_kelly == pytest.approx(result.full_kelly * 0.50)

    def test_bankroll_scaling(self):
        """Stakes scale linearly with bankroll."""
        r1 = kelly_stake(0.55, 2.0, bankroll=1000)
        r2 = kelly_stake(0.55, 2.0, bankroll=2000)
        assert r2.full_kelly == pytest.approx(r1.full_kelly * 2)

    def test_edge_computed(self):
        """Edge is stored in result."""
        result = kelly_stake(0.55, 2.0, bankroll=1000)
        assert result.edge == pytest.approx(0.55 - 0.5)

    def test_no_edge_zero_stake(self):
        """No edge → zero stakes."""
        result = kelly_stake(0.4, 2.0, bankroll=1000)
        assert result.full_kelly == pytest.approx(0.0)
        assert result.quarter_kelly == pytest.approx(0.0)


class TestSimulateDrawdown:
    """Tests for simulate_drawdown()."""

    def test_deterministic_with_seed(self):
        """Same seed → identical results."""
        probs = [0.55] * 100
        odds = [2.0] * 100
        r1 = simulate_drawdown(probs, odds, random_state=42)
        r2 = simulate_drawdown(probs, odds, random_state=42)
        assert r1.max_drawdown_mean == pytest.approx(r2.max_drawdown_mean)
        assert r1.final_bankroll_mean == pytest.approx(r2.final_bankroll_mean)

    def test_result_structure(self):
        """Result contains all expected fields."""
        result = simulate_drawdown([0.55] * 50, [2.0] * 50, n_simulations=10)
        assert isinstance(result, DrawdownResult)
        assert result.n_simulations == 10
        assert result.n_bets == 50
        assert 0.0 <= result.ruin_probability <= 1.0
        assert result.max_drawdown_mean >= 0.0

    def test_empty_bets(self):
        """No bets → no drawdown."""
        result = simulate_drawdown([], [], bankroll=1000)
        assert result.n_bets == 0
        assert result.final_bankroll_mean == pytest.approx(1000.0)
        assert result.max_drawdown_mean == pytest.approx(0.0)

    def test_certain_wins_grow_bankroll(self):
        """With p=1.0, bankroll should always grow."""
        result = simulate_drawdown(
            [0.99] * 50, [1.5] * 50,
            bankroll=1000, n_simulations=100, random_state=42
        )
        assert result.final_bankroll_mean > 1000.0
        assert result.ruin_probability == pytest.approx(0.0)

    def test_drawdown_95th_gte_median(self):
        """95th percentile drawdown >= median drawdown."""
        result = simulate_drawdown(
            [0.55] * 100, [2.0] * 100, n_simulations=200, random_state=42
        )
        assert result.max_drawdown_95th >= result.max_drawdown_median


class TestApplySlippage:
    """Tests for apply_slippage()."""

    def test_slippage_reduces_odds(self):
        """Slippage reduces effective odds."""
        result = apply_slippage(2.0, slippage_pct=0.02)
        assert result < 2.0
        assert result > 1.0

    def test_exact_slippage(self):
        """Verify exact slippage computation."""
        # odds=2.0, slip=5%: 1 + (2-1)*0.95 = 1.95
        assert apply_slippage(2.0, 0.05) == pytest.approx(1.95)

    def test_zero_slippage(self):
        """No slippage → same odds."""
        assert apply_slippage(2.0, 0.0) == pytest.approx(2.0)

    def test_odds_at_boundary(self):
        """Odds <= 1.0 returned unchanged."""
        assert apply_slippage(1.0, 0.05) == pytest.approx(1.0)
        assert apply_slippage(0.5, 0.05) == pytest.approx(0.5)
