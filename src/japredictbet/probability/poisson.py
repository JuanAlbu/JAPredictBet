"""Poisson probability functions for betting evaluation.

Migrated from ``japredictbet.betting.engine`` (P2.C2).  These functions
compute the probability of OVER / UNDER a given line under a Poisson
distribution with rate *lambda_*.

Usage::

    from japredictbet.probability.poisson import poisson_over_prob, poisson_under_prob

    p_over = poisson_over_prob(lambda_=9.5, line=8.5)
    p_under = poisson_under_prob(lambda_=9.5, line=8.5)
"""

from __future__ import annotations

import math

from scipy.stats import poisson


def poisson_over_prob(lambda_: float, line: float) -> float:
    """Probability of OVER *line* under Poisson(lambda_).

    Computes P(X > line), i.e. P(X >= floor(line) + 1).

    Parameters
    ----------
    lambda_:
        Poisson rate parameter (expected value).
    line:
        Market line (e.g. 8.5 for Over 8.5 corners).

    Returns
    -------
    Probability as a float in [0, 1].
    """
    k = math.floor(line)
    return 1.0 - poisson.cdf(k, lambda_)


def poisson_under_prob(lambda_: float, line: float) -> float:
    """Probability of UNDER *line* under Poisson(lambda_).

    Computes P(X < line), i.e. P(X <= floor(line)).

    Parameters
    ----------
    lambda_:
        Poisson rate parameter (expected value).
    line:
        Market line (e.g. 8.5 for Under 8.5 corners).

    Returns
    -------
    Probability as a float in [0, 1].
    """
    k = math.floor(line)
    return poisson.cdf(k, lambda_)
