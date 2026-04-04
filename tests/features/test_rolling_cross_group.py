"""Regression tests for cross-group contamination in rolling features."""

from __future__ import annotations

import math

import pandas as pd

from src.japredictbet.features.rolling import (
    add_result_rolling,
    add_rolling_features,
    add_rolling_std,
    add_stat_rolling,
)


def _interleaved_df() -> pd.DataFrame:
    """Build interleaved rows that expose rolling leakage when mis-implemented."""

    return pd.DataFrame(
        {
            "team": ["A", "B", "A", "B", "A", "B"],
            "opponent": ["B", "A", "B", "A", "B", "A"],
            "corners_for": [1.0, 10.0, 2.0, 20.0, 3.0, 30.0],
            "corners_against": [4.0, 40.0, 5.0, 50.0, 6.0, 60.0],
            "goals_for": [2.0, 1.0, 0.0, 2.0, 3.0, 1.0],
            "goals_against": [1.0, 2.0, 1.0, 1.0, 0.0, 2.0],
        }
    )


def test_add_stat_rolling_stays_within_team_group() -> None:
    df = _interleaved_df()

    result = add_stat_rolling(
        df,
        team_col="team",
        for_col="corners_for",
        against_col="corners_against",
        window=2,
        prefix="home",
        stat_name="corners",
    )

    # Team A at index 4 should use only its own shifted values [1, 2] => mean=1.5
    assert result.loc[4, "home_corners_for_last2"] == 1.5
    # Team B at index 5 should use only its own shifted values [10, 20] => mean=15
    assert result.loc[5, "home_corners_for_last2"] == 15.0


def test_add_rolling_features_stays_within_team_group() -> None:
    df = _interleaved_df()

    result = add_rolling_features(
        df,
        team_col="team",
        opponent_col="opponent",
        for_col="corners_for",
        against_col="corners_against",
        window=2,
        prefix="home",
    )

    assert result.loc[4, "home_corners_for_last2"] == 1.5
    assert result.loc[5, "home_corners_for_last2"] == 15.0


def test_add_result_rolling_stays_within_team_group() -> None:
    df = _interleaved_df()

    result = add_result_rolling(
        df,
        team_col="team",
        goals_for_col="goals_for",
        goals_against_col="goals_against",
        window=2,
        prefix="home",
    )

    # Team A win flags are [1, 0, 1]; at index 4, rolling(sum,2) over shifted [1,0] = 1
    assert result.loc[4, "home_wins_last2"] == 1.0
    assert result.loc[4, "home_win_rate_last2"] == 0.5
    # Team B win flags are [0, 1, 0]; at index 5, shifted [0,1] => sum=1, mean=0.5
    assert result.loc[5, "home_wins_last2"] == 1.0
    assert result.loc[5, "home_win_rate_last2"] == 0.5


def test_add_rolling_std_stays_within_team_group() -> None:
    df = _interleaved_df()

    result = add_rolling_std(
        df,
        team_col="team",
        for_col="corners_for",
        against_col="corners_against",
        window=2,
        prefix="home",
        stat_name="corners",
    )

    # std([1,2]) with sample std (ddof=1) = sqrt(0.5)
    assert math.isclose(
        result.loc[4, "home_corners_for_std_last2"],
        math.sqrt(0.5),
        rel_tol=1e-9,
    )
    # std([10,20]) with sample std (ddof=1) = sqrt(50)
    assert math.isclose(
        result.loc[5, "home_corners_for_std_last2"],
        math.sqrt(50.0),
        rel_tol=1e-9,
    )
