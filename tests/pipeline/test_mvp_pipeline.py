"""Tests for the MVP pipeline orchestration."""

from __future__ import annotations
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from japredictbet.config import (
    DataConfig,
    FeatureConfig,
    ModelConfig,
    OddsConfig,
    PipelineConfig,
    ValueConfig,
)
from japredictbet.pipeline.mvp_pipeline import run_mvp_pipeline


@pytest.fixture
def minimal_config() -> PipelineConfig:
    """A minimal, valid PipelineConfig for testing."""
    return PipelineConfig(
        data=DataConfig(raw_path="dummy/path", processed_path="dummy/processed"),
        features=FeatureConfig(rolling_window=10),
        model=ModelConfig(random_state=42, ensemble_size=3),
        value=ValueConfig(
            threshold=0.05,
            consensus_threshold=0.7,
            run_consensus_sweep=False,
        ),
        odds=OddsConfig(provider_name="http://fake-odds-api.com"),
    )


@patch("japredictbet.pipeline.mvp_pipeline.fetch_odds")
@patch("japredictbet.pipeline.mvp_pipeline.predict_expected_corners")
@patch("japredictbet.pipeline.mvp_pipeline.train_models")
@patch("japredictbet.pipeline.mvp_pipeline.load_historical_dataset")
def test_pipeline_end_to_end_logic(
    mock_load_data: MagicMock,
    mock_train: MagicMock,
    mock_predict: MagicMock,
    mock_fetch_odds: MagicMock,
    minimal_config: PipelineConfig,
):
    """Test the full pipeline logic using the new engine."""
    # 1. Setup - Mock all external dependencies
    mock_load_data.return_value = pd.DataFrame({
        "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
        "home_team": ["Team A", "Team C"],
        "away_team": ["Team B", "Team D"],
        "home_goals": [1, 2], "away_goals": [1, 0],
        "home_corners": [5, 6], "away_corners": [4, 7],
    })

    # Mock predictions: (lambda_home, lambda_away)
    # Match 1: 7.0 + 4.0 = 11.0. Match 2: 5.0 + 5.0 = 10.0
    mock_predict.return_value = (pd.Series([7.0, 5.0]), pd.Series([4.0, 5.0]))

    # Mock odds data. We will engineer the second bet to be a value bet.
    # For Match 2, lambda_total=10.0. Let's use line 8.5.
    # P(X > 8.5) = 1 - P(X<=8) = 1 - cdf(8, 10) = 0.6967
    # Let's set odds at 2.0 (implied prob = 0.5). Edge = 0.6967 - 0.5 = 0.1967 > 0.05
    mock_fetch_odds.return_value = pd.DataFrame({
        "match": ["Team A vs Team B", "Team C vs Team D"],
        "line": [10.5, 8.5],
        "over_odds": [1.9, 2.0], # This will be the value bet
        "under_odds": [1.9, 1.8],
    })

    # 2. Execution
    results_df = run_mvp_pipeline(minimal_config)

    # 3. Assertions
    assert not results_df.empty
    assert "bet" in results_df.columns
    assert "edge_mean" in results_df.columns
    assert "vote_distribution" in results_df.columns
    assert "status_message" in results_df.columns
    assert "roi" in results_df.columns
    assert "yield" in results_df.columns

    # Find the row for our engineered value bet
    value_bet_row = results_df[results_df["match"] == "Team C vs Team D"]
    assert not value_bet_row.empty
    
    # Check that it was correctly identified as a bet
    assert value_bet_row.iloc[0]["bet"]

    # Check the calculations
    expected_p_model = 1 - poisson.cdf(8, 10.0)
    assert np.isclose(value_bet_row.iloc[0]["p_model_mean"], expected_p_model)
    assert np.isclose(value_bet_row.iloc[0]["edge_mean"], expected_p_model - 0.5)
    assert value_bet_row.iloc[0]["vote_distribution"] == "3/3 modelos concordam"
    assert np.isclose(value_bet_row.iloc[0]["bets_placed"], 1.0)
    assert np.isclose(value_bet_row.iloc[0]["profit_total"], 1.0)
    assert np.isclose(value_bet_row.iloc[0]["yield"], 1.0)
    assert np.isclose(value_bet_row.iloc[0]["roi"], 1.0)
