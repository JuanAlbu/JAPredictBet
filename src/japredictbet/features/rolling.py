"""Rolling feature generation for corners modeling."""

from __future__ import annotations

import numpy as np
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


def add_result_rolling(
    df: pd.DataFrame,
    team_col: str,
    goals_for_col: str,
    goals_against_col: str,
    window: int,
    prefix: str,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling result-based features (wins/draws/losses/points)."""

    data = df.copy()
    if season_col and season_col in data.columns:
        group = data.groupby([team_col, season_col], sort=False)
    else:
        group = data.groupby(team_col, sort=False)

    goals_for = data[goals_for_col]
    goals_against = data[goals_against_col]
    has_score = goals_for.notna() & goals_against.notna()

    data["_tmp_win"] = pd.Series(np.nan, index=data.index, dtype="float")
    data["_tmp_draw"] = pd.Series(np.nan, index=data.index, dtype="float")
    data["_tmp_loss"] = pd.Series(np.nan, index=data.index, dtype="float")
    data["_tmp_points"] = pd.Series(np.nan, index=data.index, dtype="float")

    data.loc[has_score, "_tmp_win"] = (
        goals_for[has_score] > goals_against[has_score]
    ).astype(float)
    data.loc[has_score, "_tmp_draw"] = (
        goals_for[has_score] == goals_against[has_score]
    ).astype(float)
    data.loc[has_score, "_tmp_loss"] = (
        goals_for[has_score] < goals_against[has_score]
    ).astype(float)
    data.loc[has_score, "_tmp_points"] = (
        data.loc[has_score, "_tmp_win"].astype(float) * 3.0
        + data.loc[has_score, "_tmp_draw"].astype(float)
    )

    data[f"{prefix}_wins_last{window}"] = (
        group["_tmp_win"].shift(1).rolling(window).sum()
    )
    data[f"{prefix}_draws_last{window}"] = (
        group["_tmp_draw"].shift(1).rolling(window).sum()
    )
    data[f"{prefix}_losses_last{window}"] = (
        group["_tmp_loss"].shift(1).rolling(window).sum()
    )
    data[f"{prefix}_points_last{window}"] = (
        group["_tmp_points"].shift(1).rolling(window).sum()
    )
    data[f"{prefix}_win_rate_last{window}"] = (
        group["_tmp_win"].shift(1).rolling(window).mean()
    )
    data[f"{prefix}_points_per_game_last{window}"] = (
        group["_tmp_points"].shift(1).rolling(window).mean()
    )
    return data.drop(columns=["_tmp_win", "_tmp_draw", "_tmp_loss", "_tmp_points"])
