"""Risk management utilities: Kelly staking, drawdown simulation (P1.D3).

This module provides bankroll management tools for analytics purposes only.
It does NOT place bets or connect to bookmaker accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class KellyResult:
    """Result of Kelly Criterion calculation."""

    full_kelly: float
    quarter_kelly: float
    half_kelly: float
    edge: float
    odds: float


def kelly_fraction(p_model: float, odds: float) -> float:
    """Compute full Kelly fraction.

    Kelly% = (p * b - q) / b
    where b = odds - 1, p = win probability, q = 1 - p.

    Args:
        p_model: Model's estimated win probability.
        odds: Decimal odds offered.

    Returns:
        Optimal fraction of bankroll to wager. Clamped to [0, 1].
    """
    if odds <= 1.0 or p_model <= 0.0 or p_model >= 1.0:
        return 0.0

    b = odds - 1.0
    q = 1.0 - p_model
    fraction = (p_model * b - q) / b
    return max(0.0, min(fraction, 1.0))


def kelly_stake(
    p_model: float,
    odds: float,
    bankroll: float,
    fraction: float = 0.25,
) -> KellyResult:
    """Compute Kelly-based stake with configurable fraction.

    Args:
        p_model: Model's estimated win probability.
        odds: Decimal odds.
        bankroll: Current bankroll.
        fraction: Kelly fraction (0.25 = Quarter Kelly, default).

    Returns:
        KellyResult with full, quarter, and half Kelly stakes.
    """
    full = kelly_fraction(p_model, odds)
    edge = p_model - (1.0 / odds) if odds > 0 else 0.0

    return KellyResult(
        full_kelly=full * bankroll,
        quarter_kelly=full * 0.25 * bankroll,
        half_kelly=full * 0.50 * bankroll,
        edge=edge,
        odds=odds,
    )


@dataclass(frozen=True)
class DrawdownResult:
    """Result of Monte Carlo drawdown simulation."""

    max_drawdown_mean: float
    max_drawdown_median: float
    max_drawdown_95th: float
    final_bankroll_mean: float
    final_bankroll_median: float
    ruin_probability: float
    n_simulations: int
    n_bets: int


def simulate_drawdown(
    win_probs: Sequence[float],
    odds_list: Sequence[float],
    bankroll: float = 1000.0,
    kelly_fraction: float = 0.25,
    n_simulations: int = 500,
    ruin_threshold: float = 0.1,
    random_state: int = 42,
) -> DrawdownResult:
    """Run Monte Carlo drawdown simulation.

    Simulates n_simulations bankroll paths using Kelly staking
    with the given win probabilities and odds sequence.

    Args:
        win_probs: Estimated win probability per bet.
        odds_list: Decimal odds per bet.
        bankroll: Starting bankroll.
        kelly_fraction: Kelly fraction to use (0.25 = Quarter Kelly).
        n_simulations: Number of Monte Carlo paths.
        ruin_threshold: Fraction of initial bankroll below which = ruin.
        random_state: RNG seed for reproducibility.

    Returns:
        DrawdownResult with summary statistics.
    """
    rng = np.random.default_rng(random_state)
    n_bets = min(len(win_probs), len(odds_list))

    if n_bets == 0:
        return DrawdownResult(
            max_drawdown_mean=0.0,
            max_drawdown_median=0.0,
            max_drawdown_95th=0.0,
            final_bankroll_mean=bankroll,
            final_bankroll_median=bankroll,
            ruin_probability=0.0,
            n_simulations=n_simulations,
            n_bets=0,
        )

    probs = np.array(win_probs[:n_bets], dtype=float)
    odds = np.array(odds_list[:n_bets], dtype=float)

    max_drawdowns = np.zeros(n_simulations)
    final_bankrolls = np.zeros(n_simulations)
    ruins = 0

    for sim in range(n_simulations):
        br = bankroll
        peak = bankroll

        for i in range(n_bets):
            if br <= bankroll * ruin_threshold:
                ruins += 1
                break

            # Compute Kelly stake
            b = odds[i] - 1.0
            q = 1.0 - probs[i]
            full_k = max(0.0, (probs[i] * b - q) / b) if b > 0 else 0.0
            stake = full_k * kelly_fraction * br

            # Simulate outcome
            won = rng.random() < probs[i]
            if won:
                br += stake * (odds[i] - 1.0)
            else:
                br -= stake

            peak = max(peak, br)

        drawdown = (peak - br) / peak if peak > 0 else 0.0
        max_drawdowns[sim] = drawdown
        final_bankrolls[sim] = br

    return DrawdownResult(
        max_drawdown_mean=float(max_drawdowns.mean()),
        max_drawdown_median=float(np.median(max_drawdowns)),
        max_drawdown_95th=float(np.percentile(max_drawdowns, 95)),
        final_bankroll_mean=float(final_bankrolls.mean()),
        final_bankroll_median=float(np.median(final_bankrolls)),
        ruin_probability=ruins / n_simulations,
        n_simulations=n_simulations,
        n_bets=n_bets,
    )


def apply_slippage(odds: float, slippage_pct: float = 0.02) -> float:
    """Apply slippage to odds to simulate execution risk.

    Args:
        odds: Original decimal odds.
        slippage_pct: Slippage percentage (default 2%).

    Returns:
        Adjusted odds after slippage.
    """
    if odds <= 1.0:
        return odds
    return 1.0 + (odds - 1.0) * (1.0 - slippage_pct)
