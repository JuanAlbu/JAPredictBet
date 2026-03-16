"""Value detection utilities."""

from __future__ import annotations

import pandas as pd


def implied_probability(odds: float) -> float:
    """Convert decimal odds into implied probability."""

    if odds <= 0:
        raise ValueError("Odds must be positive.")
    return 1.0 / odds


def detect_value_bets(
    odds_df: pd.DataFrame,
    model_probs: pd.Series,
    threshold: float,
) -> pd.DataFrame:
    """Compare model probabilities with bookmaker implied probabilities.

    Args:
        odds_df: DataFrame with odds columns.
        model_probs: Series with model probabilities aligned to odds_df.
        threshold: Minimum value edge required.

    Returns:
        DataFrame with value calculations.
    """

    df = odds_df.copy()
    df["implied_prob"] = df["over_odds"].map(implied_probability)
    df["model_prob"] = model_probs
    df["value"] = df["model_prob"] - df["implied_prob"]
    df["is_value"] = df["value"] >= threshold
    return df