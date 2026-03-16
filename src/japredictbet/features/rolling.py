"""Rolling feature generation for corners modeling."""

from __future__ import annotations

import pandas as pd


def add_rolling_features(
    df: pd.DataFrame,
    team_col: str,
    opponent_col: str,
    for_col: str,
    against_col: str,
    window: int,
    prefix: str,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling mean features for a team perspective.

    Args:
        df: Input matches DataFrame sorted by date.
        team_col: Column with team name.
        opponent_col: Column with opponent name.
        for_col: Column with the team's corners for.
        against_col: Column with the team's corners against.
        window: Rolling window size.
        prefix: Prefix for generated feature columns.

    Returns:
        DataFrame with rolling features appended.
    """

    df = df.copy()
    if season_col and season_col in df.columns:
        group = df.groupby([team_col, season_col], sort=False)
    else:
        group = df.groupby(team_col, sort=False)

    df[f"{prefix}_corners_for_last{window}"] = (
        group[for_col].shift(1).rolling(window).mean()
    )
    df[f"{prefix}_corners_against_last{window}"] = (
        group[against_col].shift(1).rolling(window).mean()
    )

    return df


def add_stat_rolling(
    df: pd.DataFrame,
    team_col: str,
    for_col: str,
    against_col: str,
    window: int,
    prefix: str,
    stat_name: str,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling mean features for a given stat."""

    df = df.copy()
    if season_col and season_col in df.columns:
        group = df.groupby([team_col, season_col], sort=False)
    else:
        group = df.groupby(team_col, sort=False)

    df[f"{prefix}_{stat_name}_for_last{window}"] = (
        group[for_col].shift(1).rolling(window).mean()
    )
    df[f"{prefix}_{stat_name}_against_last{window}"] = (
        group[against_col].shift(1).rolling(window).mean()
    )
    return df
