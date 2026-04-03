"""Tests for head-to-head (H2H) feature generation (P1.B5)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from japredictbet.features.matchup import add_h2h_features


def _make_h2h_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a small DataFrame with required columns."""
    return pd.DataFrame(rows)


class TestAddH2hFeatures:
    """Tests for add_h2h_features()."""

    def test_basic_h2h_computed(self):
        """H2H features are created when raw stat columns exist."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 2, "away_goals": 1, "home_shots": 10, "away_shots": 8},
            {"home_team": "A", "away_team": "B", "home_corners": 6, "away_corners": 4, "home_goals": 1, "away_goals": 0, "home_shots": 12, "away_shots": 6},
            {"home_team": "A", "away_team": "B", "home_corners": 7, "away_corners": 5, "home_goals": 3, "away_goals": 2, "home_shots": 14, "away_shots": 10},
            {"home_team": "A", "away_team": "B", "home_corners": 4, "away_corners": 2, "home_goals": 0, "away_goals": 0, "home_shots": 8, "away_shots": 4},
        ])
        result = add_h2h_features(df, h2h_window=3)
        assert "total_corners_h2h_last3" in result.columns
        assert "total_goals_h2h_last3" in result.columns
        assert "total_shots_h2h_last3" in result.columns

    def test_first_row_is_nan(self):
        """First meeting between a pair has no history → NaN."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 2, "away_goals": 1, "home_shots": 10, "away_shots": 8},
        ])
        result = add_h2h_features(df, h2h_window=3)
        assert np.isnan(result["total_corners_h2h_last3"].iloc[0])

    def test_shift_excludes_current_match(self):
        """Current match stats are not included in the H2H rolling average."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 10, "away_corners": 10, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=3)
        # Second row should see only the first match: 5+3 = 8
        assert result["total_corners_h2h_last3"].iloc[1] == pytest.approx(8.0)

    def test_reversed_venue_same_pair(self):
        """A-vs-B and B-vs-A are treated as the same pair."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "B", "away_team": "A", "home_corners": 6, "away_corners": 4, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 7, "away_corners": 5, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=3)
        # Row 2 (index 2): average of match0 (5+3=8) and match1 (6+4=10) → 9.0
        assert result["total_corners_h2h_last3"].iloc[2] == pytest.approx(9.0)

    def test_independent_pairs(self):
        """Different team pairs have independent H2H histories."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "C", "away_team": "D", "home_corners": 10, "away_corners": 10, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 7, "away_corners": 5, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "C", "away_team": "D", "home_corners": 2, "away_corners": 2, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=3)
        # A-vs-B row 2 should only see A-vs-B row 0: 5+3 = 8
        assert result["total_corners_h2h_last3"].iloc[2] == pytest.approx(8.0)
        # C-vs-D row 3 should only see C-vs-D row 1: 10+10 = 20
        assert result["total_corners_h2h_last3"].iloc[3] == pytest.approx(20.0)

    def test_rolling_window_respected(self):
        """Only last h2h_window meetings are averaged (window=2)."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 4, "away_corners": 2, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 6, "away_corners": 4, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 8, "away_corners": 2, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 0, "away_corners": 0, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=2)
        # Row 3 (window=2): sees row1 (6+4=10), row2 (8+2=10) → mean = 10
        assert result["total_corners_h2h_last2"].iloc[3] == pytest.approx(10.0)

    def test_missing_columns_skipped(self):
        """If stat columns are absent, no H2H features are added."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "some_col": 1},
            {"home_team": "A", "away_team": "B", "some_col": 2},
        ])
        result = add_h2h_features(df, h2h_window=3)
        assert "total_corners_h2h_last3" not in result.columns
        assert "total_goals_h2h_last3" not in result.columns
        assert "total_shots_h2h_last3" not in result.columns

    def test_no_helper_columns_leaked(self):
        """Internal _h2h_pair column is dropped."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=3)
        assert "_h2h_pair" not in result.columns

    def test_original_df_not_mutated(self):
        """Input DataFrame is not modified."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        cols_before = list(df.columns)
        add_h2h_features(df, h2h_window=3)
        assert list(df.columns) == cols_before

    def test_min_periods_partial_window(self):
        """With fewer meetings than h2h_window, uses available data (min_periods=1)."""
        df = _make_h2h_df([
            {"home_team": "A", "away_team": "B", "home_corners": 5, "away_corners": 3, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
            {"home_team": "A", "away_team": "B", "home_corners": 10, "away_corners": 10, "home_goals": 0, "away_goals": 0, "home_shots": 0, "away_shots": 0},
        ])
        result = add_h2h_features(df, h2h_window=5)
        # Row 1 with window=5: only 1 past meeting (row 0: 5+3=8), min_periods=1 → 8.0
        assert result["total_corners_h2h_last5"].iloc[1] == pytest.approx(8.0)
