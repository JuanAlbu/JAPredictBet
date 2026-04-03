"""Matchup and difference feature generation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_h2h_features(df: pd.DataFrame, h2h_window: int = 3) -> pd.DataFrame:
    """Add head-to-head features from last N meetings between the same pair.

    For each match, looks up previous encounters between the same two teams
    (regardless of venue) and computes rolling averages of match totals.

    Args:
        df: DataFrame with columns home_team, away_team, and raw match stats.
        h2h_window: Number of past H2H meetings to average over.

    Returns:
        DataFrame with new H2H feature columns.
    """
    df = df.copy()

    # Canonical pair key (alphabetical order so A-vs-B == B-vs-A)
    team_a = df["home_team"].values
    team_b = df["away_team"].values
    pair_key = np.where(
        team_a < team_b,
        team_a + " vs " + team_b,
        team_b + " vs " + team_a,
    )
    df["_h2h_pair"] = pair_key

    suffix = f"_h2h_last{h2h_window}"

    stat_pairs = [
        ("home_corners", "away_corners", f"total_corners{suffix}"),
        ("home_goals", "away_goals", f"total_goals{suffix}"),
        ("home_shots", "away_shots", f"total_shots{suffix}"),
    ]

    for home_col, away_col, feature_name in stat_pairs:
        if home_col in df.columns and away_col in df.columns:
            total = df[home_col] + df[away_col]
            # Shift by 1 to exclude current match, then rolling mean
            df[feature_name] = (
                total
                .groupby(df["_h2h_pair"])
                .transform(
                    lambda x: x.shift(1).rolling(h2h_window, min_periods=1).mean()
                )
            )

    df.drop(columns=["_h2h_pair"], inplace=True)
    return df


def add_matchup_features(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Add matchup interaction and difference features when possible."""

    df = df.copy()
    suffix = f"_last{window}"

    _add_attack_vs_defense(
        df,
        f"home_corners_for{suffix}",
        f"away_corners_against{suffix}",
        f"home_attack_vs_away_defense_corners{suffix}",
    )
    _add_attack_vs_defense(
        df,
        f"away_corners_for{suffix}",
        f"home_corners_against{suffix}",
        f"away_attack_vs_home_defense_corners{suffix}",
    )
    _add_diff(
        df,
        f"home_corners_for{suffix}",
        f"away_corners_for{suffix}",
        f"corners{suffix}_diff",
    )
    _add_diff(
        df,
        f"home_shots_for{suffix}",
        f"away_shots_for{suffix}",
        f"shots{suffix}_diff",
    )
    _add_diff(
        df,
        f"home_shots_on_target_for{suffix}",
        f"away_shots_on_target_for{suffix}",
        f"shots_on_target{suffix}_diff",
    )
    _add_diff(
        df,
        f"home_fouls_for{suffix}",
        f"away_fouls_for{suffix}",
        f"fouls{suffix}_diff",
    )
    _add_card_diff(df, suffix)
    _add_ratio(
        df,
        f"home_corners_for{suffix}",
        f"away_corners_against{suffix}",
        f"corners_pressure_index{suffix}",
    )

    return df


def _add_attack_vs_defense(
    df: pd.DataFrame,
    attack_col: str,
    defense_col: str,
    feature_name: str,
) -> None:
    if attack_col in df.columns and defense_col in df.columns:
        df[feature_name] = (df[attack_col] + df[defense_col]) / 2.0


def _add_diff(df: pd.DataFrame, left_col: str, right_col: str, feature_name: str) -> None:
    if left_col in df.columns and right_col in df.columns:
        df[feature_name] = df[left_col] - df[right_col]


def _add_ratio(
    df: pd.DataFrame,
    numerator_col: str,
    denominator_col: str,
    feature_name: str,
) -> None:
    if numerator_col in df.columns and denominator_col in df.columns:
        denom = df[denominator_col].replace(0, pd.NA)
        df[feature_name] = df[numerator_col] / denom


def _add_card_diff(df: pd.DataFrame, suffix: str) -> None:
    home_cols = [
        col
        for col in (
            f"home_yellow_cards_for{suffix}",
            f"home_red_cards_for{suffix}",
        )
        if col in df.columns
    ]
    away_cols = [
        col
        for col in (
            f"away_yellow_cards_for{suffix}",
            f"away_red_cards_for{suffix}",
        )
        if col in df.columns
    ]
    if home_cols and away_cols:
        df[f"cards{suffix}_diff"] = df[home_cols].sum(axis=1) - df[away_cols].sum(axis=1)
