"""Tests for drop_redundant_features (feature correlation cleanup)."""
import pandas as pd
import pytest

from japredictbet.features.rolling import drop_redundant_features


def _make_df_with_features(windows=(10, 5), include_ema=True):
    """Create a DataFrame with typical feature columns for testing."""
    cols = {}
    for w in windows:
        for prefix in ("home", "away"):
            cols[f"{prefix}_wins_last{w}"] = [1.0]
            cols[f"{prefix}_draws_last{w}"] = [0.0]
            cols[f"{prefix}_losses_last{w}"] = [1.0]
            cols[f"{prefix}_points_last{w}"] = [3.0]
            cols[f"{prefix}_win_rate_last{w}"] = [0.5]
            cols[f"{prefix}_points_per_game_last{w}"] = [1.5]
            cols[f"{prefix}_corners_for_last{w}"] = [5.0]
            cols[f"{prefix}_corners_against_last{w}"] = [4.0]
            cols[f"{prefix}_corners_for_std_last{w}"] = [1.0]
            cols[f"{prefix}_corners_against_std_last{w}"] = [0.8]
            if include_ema:
                cols[f"{prefix}_corners_for_ema_last{w}"] = [5.2]
                cols[f"{prefix}_corners_against_ema_last{w}"] = [3.9]
                cols[f"{prefix}_goals_for_ema_last{w}"] = [1.5]
                cols[f"{prefix}_goals_against_ema_last{w}"] = [1.2]
    return pd.DataFrame(cols)


class TestDropRedundantFeatures:
    def test_drops_wins_columns(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_wins_last{w}" not in result.columns

    def test_drops_points_columns(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_points_last{w}" not in result.columns

    def test_keeps_win_rate(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_win_rate_last{w}" in result.columns

    def test_keeps_points_per_game(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_points_per_game_last{w}" in result.columns

    def test_drops_ema_larger_window_keeps_smaller(self):
        df = _make_df_with_features(windows=(10, 5))
        result = drop_redundant_features(df, [10, 5])
        # EMA last10 should be dropped
        for prefix in ("home", "away"):
            assert f"{prefix}_corners_for_ema_last10" not in result.columns
            assert f"{prefix}_goals_for_ema_last10" not in result.columns
        # EMA last5 should be kept
        for prefix in ("home", "away"):
            assert f"{prefix}_corners_for_ema_last5" in result.columns
            assert f"{prefix}_goals_for_ema_last5" in result.columns

    def test_keeps_draws_and_losses(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_draws_last{w}" in result.columns
                assert f"{prefix}_losses_last{w}" in result.columns

    def test_keeps_rolling_mean_and_std(self):
        df = _make_df_with_features()
        result = drop_redundant_features(df, [10, 5])
        for w in (10, 5):
            for prefix in ("home", "away"):
                assert f"{prefix}_corners_for_last{w}" in result.columns
                assert f"{prefix}_corners_for_std_last{w}" in result.columns

    def test_single_window_no_ema_dropped(self):
        """With a single window, no EMA should be dropped."""
        df = _make_df_with_features(windows=(5,))
        result = drop_redundant_features(df, [5])
        for prefix in ("home", "away"):
            assert f"{prefix}_corners_for_ema_last5" in result.columns

    def test_no_ema_columns_graceful(self):
        """Works even if EMA columns don't exist."""
        df = _make_df_with_features(include_ema=False)
        result = drop_redundant_features(df, [10, 5])
        assert len(result.columns) == len(df.columns) - 8  # only wins/points dropped

    def test_count_dropped_columns(self):
        """With windows=[10,5] and EMA, should drop 8 result + 8 EMA = 16 columns."""
        df = _make_df_with_features(windows=(10, 5))
        result = drop_redundant_features(df, [10, 5])
        # 8 wins/points (4 per window × 2 windows)
        # + 8 EMA last10 (4 stats × 2 prefixes)
        expected_dropped = 8 + 8
        assert len(df.columns) - len(result.columns) == expected_dropped
