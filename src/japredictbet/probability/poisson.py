"""Poisson probability utilities."""

from __future__ import annotations

from math import exp, factorial


def poisson_pmf(k: int, rate: float) -> float:
    """Compute Poisson PMF for integer k."""

    if k < 0:
        return 0.0
    return exp(-rate) * (rate ** k) / factorial(k)


def prob_total_over(line: float, rate: float, max_goals: int = 20) -> float:
    """Probability that total corners is over a line.

    Args:
        line: Market line (e.g., 9.5).
        rate: Expected total corners.
        max_goals: Upper bound for truncation.

    Returns:
        Probability of total corners being over the line.
    """

    threshold = int(line)
    prob = 0.0
    for k in range(threshold + 1, max_goals + 1):
        prob += poisson_pmf(k, rate)
    return prob