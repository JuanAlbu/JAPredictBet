"""Matchup and difference feature generation."""

from __future__ import annotations

import pandas as pd


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
