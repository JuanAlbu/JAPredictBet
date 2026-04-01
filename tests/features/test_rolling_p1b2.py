"""Tests for P1.B2 — Rolling feature expansions (STD and EMA)."""

import pandas as pd
import numpy as np
import pytest
from src.japredictbet.features.rolling import (
    add_rolling_std,
    add_rolling_ema,
)


class TestRollingStd:
    """Tests for rolling standard deviation features."""

    def test_add_rolling_std_basic(self):
        """Test basic rolling STD calculation."""
        df = pd.DataFrame({
            "team": ["A", "A", "A", "B", "B", "B"],
            "corners_for": [5, 6, 5, 4, 6, 8],
            "corners_against": [3, 2, 4, 5, 3, 2],
        })
        
        result = add_rolling_std(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test",
            stat_name="corners",
        )
        
        # Check that new columns were created
        assert "test_corners_for_std_last2" in result.columns
        assert "test_corners_against_std_last2" in result.columns

    def test_add_rolling_std_with_season(self):
        """Test rolling STD with season column for grouping."""
        df = pd.DataFrame({
            "team": ["A", "A", "B", "B", "A", "A"],
            "season": [1, 1, 1, 1, 2, 2],
            "corners_for": [5, 6, 4, 6, 5, 7],
            "corners_against": [3, 2, 5, 3, 4, 3],
        })
        
        result = add_rolling_std(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test",
            stat_name="corners",
            season_col="season",
        )
        
        # Should not raise and should have new columns
        assert "test_corners_for_std_last2" in result.columns
        assert result.shape[0] == len(df)

    def test_rolling_std_detects_volatility(self):
        """Test that rolling STD captures variance in performance."""
        # Consistent team
        consistent = pd.DataFrame({
            "team": ["Consistent"] * 5,
            "corners_for": [5, 5, 5, 5, 5],
        }).assign(corners_against=[3, 3, 3, 3, 3])
        
        # Volatile team
        volatile = pd.DataFrame({
            "team": ["Volatile"] * 5,
            "corners_for": [2, 8, 3, 7, 4],
        }).assign(corners_against=[1, 5, 2, 6, 3])
        
        df = pd.concat([consistent, volatile], ignore_index=True)
        
        result = add_rolling_std(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=3,
            prefix="test",
            stat_name="corners",
        )
        
        # Volatile team should have higher STD
        consistent_std = result.loc[result["team"] == "Consistent", "test_corners_for_std_last3"]
        volatile_std = result.loc[result["team"] == "Volatile", "test_corners_for_std_last3"]
        
        # At least one non-null value should be higher for volatile
        c_non_null = consistent_std.dropna()
        v_non_null = volatile_std.dropna()
        if len(c_non_null) > 0 and len(v_non_null) > 0:
            assert v_non_null.iloc[-1] > c_non_null.iloc[-1]


class TestRollingEma:
    """Tests for exponential moving average features."""

    def test_add_rolling_ema_basic(self):
        """Test basic EMA calculation."""
        df = pd.DataFrame({
            "team": ["A", "A", "A", "B", "B", "B"],
            "corners_for": [5, 6, 7, 4, 6, 8],
            "corners_against": [3, 2, 4, 5, 3, 2],
        })
        
        result = add_rolling_ema(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test",
            stat_name="corners",
        )
        
        # Check that new columns were created
        assert "test_corners_for_ema_last2" in result.columns
        assert "test_corners_against_ema_last2" in result.columns

    def test_add_rolling_ema_with_custom_alpha(self):
        """Test EMA with custom alpha parameter."""
        df = pd.DataFrame({
            "team": ["A", "A", "A"],
            "corners_for": [5, 10, 5],
            "corners_against": [3, 4, 3],
        })
        
        # Use high alpha (more weight to recent)
        result_high_alpha = add_rolling_ema(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test_high",
            stat_name="corners",
            alpha=0.8,
        )
        
        # Use low alpha (more weight to history)
        result_low_alpha = add_rolling_ema(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test_low",
            stat_name="corners",
            alpha=0.2,
        )
        
        assert "test_high_corners_for_ema_last2" in result_high_alpha.columns
        assert "test_low_corners_for_ema_last2" in result_low_alpha.columns

    def test_rolling_ema_alpha_validation(self):
        """Test that invalid alpha raises error."""
        df = pd.DataFrame({
            "team": ["A"],
            "corners_for": [5],
            "corners_against": [3],
        })
        
        # Alpha must be in (0, 1]
        with pytest.raises(ValueError, match="alpha must be in"):
            add_rolling_ema(
                df,
                team_col="team",
                for_col="corners_for",
                against_col="corners_against",
                window=2,
                prefix="test",
                stat_name="corners",
                alpha=1.5,  # Invalid
            )
        
        with pytest.raises(ValueError, match="alpha must be in"):
            add_rolling_ema(
                df,
                team_col="team",
                for_col="corners_for",
                against_col="corners_against",
                window=2,
                prefix="test",
                stat_name="corners",
                alpha=-0.5,  # Invalid
            )

    def test_rolling_ema_recency_bias(self):
        """Test that EMA gives more weight to recent values than simple average."""
        df = pd.DataFrame({
            "team": ["A"] * 5,
            "corners_for": [1, 1, 1, 10, 10],  # Recent spike to 10
            "corners_against": [1, 1, 1, 2, 2],
        })
        
        result = add_rolling_ema(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=3,
            prefix="test",
            stat_name="corners",
            alpha=0.5,  # Standard EMA
        )
        
        # EMA at last row should be closer to 10 (recent values)
        # than simple average would be
        ema_last = result["test_corners_for_ema_last3"].iloc[-1]
        
        # For a spike at the end, EMA should reflect recent high
        # Simple average of [1, 1, 1] before shift + [1, 10, 10] after would be lower
        assert ema_last > 2, "EMA should be higher due to recent spike"

    def test_rolling_ema_with_season(self):
        """Test EMA with season column for grouping."""
        df = pd.DataFrame({
            "team": ["A", "A", "B", "B", "A", "A"],
            "season": [1, 1, 1, 1, 2, 2],
            "corners_for": [5, 6, 4, 6, 5, 7],
            "corners_against": [3, 2, 5, 3, 4, 3],
        })
        
        result = add_rolling_ema(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=2,
            prefix="test",
            stat_name="corners",
            season_col="season",
        )
        
        # Should not raise and should have new columns
        assert "test_corners_for_ema_last2" in result.columns
        assert result.shape[0] == len(df)


class TestRollingFeatureIntegration:
    """Integration tests for rolling features."""

    def test_std_and_ema_together(self):
        """Test that STD and EMA can be used together without conflicts."""
        df = pd.DataFrame({
            "team": ["A"] * 6 + ["B"] * 6,
            "corners_for": [5, 6, 5, 7, 6, 8, 4, 5, 3, 6, 5, 7],
            "corners_against": [3, 2, 4, 3, 4, 2, 5, 3, 4, 2, 3, 3],
        })
        
        # Add both STD and EMA
        result = add_rolling_std(
            df,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=3,
            prefix="test",
            stat_name="corners",
        )
        
        result = add_rolling_ema(
            result,
            team_col="team",
            for_col="corners_for",
            against_col="corners_against",
            window=3,
            prefix="test",
            stat_name="corners",
        )
        
        # Should have both types of features
        assert "test_corners_for_std_last3" in result.columns
        assert "test_corners_for_ema_last3" in result.columns
        
        # No rows should be fully NaN (some data loss is expected but not complete)
        assert not result.isna().all().all()
