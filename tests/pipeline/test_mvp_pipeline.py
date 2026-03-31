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
from japredictbet.pipeline.mvp_pipeline import (
    _merge_with_normalized_match_keys,
    run_mvp_pipeline,
)


@pytest.fixture
def minimal_config() -> PipelineConfig:
    """A minimal, valid PipelineConfig for testing."""
    return PipelineConfig(
        data=DataConfig(raw_path="dummy/path", processed_path="dummy/processed"),
        features=FeatureConfig(rolling_windows=[10, 5]),
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
@patch("japredictbet.pipeline.mvp_pipeline.train_and_save_ensemble")
@patch("japredictbet.pipeline.mvp_pipeline.load_historical_dataset")
def test_pipeline_end_to_end_logic(
    mock_load_data: MagicMock,
    mock_train_and_save_ensemble: MagicMock,
    mock_predict: MagicMock,
    mock_fetch_odds: MagicMock,
    minimal_config: PipelineConfig,
):
    """Test the full pipeline logic using the new engine."""
    # 1. Setup - Mock all external dependencies
    num_matches = 24
    dates = pd.date_range("2023-01-01", periods=num_matches, freq="D")
    mock_load_data.return_value = pd.DataFrame({
        "date": dates,
        "home_team": ["Team A"] * num_matches,
        "away_team": ["Team B"] * num_matches,
        "home_goals": [1 + (idx % 3) for idx in range(num_matches)],
        "away_goals": [idx % 2 for idx in range(num_matches)],
        "home_corners": [6 + (idx % 4) for idx in range(num_matches)],
        "away_corners": [4 + (idx % 3) for idx in range(num_matches)],
    })

    # Mock predictions aligned to the current filtered dataset index.
    mock_predict.side_effect = lambda _models, features: (
        pd.Series(7.0, index=features.index),
        pd.Series(4.0, index=features.index),
    )

    # Mock odds data. We will engineer the second bet to be a value bet.
    # For Match 2, lambda_total=10.0. Let's use line 8.5.
    # P(X > 8.5) = 1 - P(X<=8) = 1 - cdf(8, 10) = 0.6967
    # Let's set odds at 2.0 (implied prob = 0.5). Edge = 0.6967 - 0.5 = 0.1967 > 0.05
    mock_fetch_odds.return_value = pd.DataFrame({
        "match": ["Team A vs Team B"],
        "line": [8.5],
        "over_odds": [2.0],
        "under_odds": [1.8],
    })
    mock_train_and_save_ensemble.return_value = (
        [MagicMock(), MagicMock(), MagicMock()],
        [],
        [],
    )

    # 2. Execution
    results_df = run_mvp_pipeline(minimal_config)

    # 3. Assertions
    assert not results_df.empty
    assert "bet" in results_df.columns
    assert "edge_mean" in results_df.columns
    assert "vote_distribution" in results_df.columns
    assert "status_message" in results_df.columns
    assert "audit_report" in results_df.columns
    assert "roi" in results_df.columns
    assert "yield" in results_df.columns
    assert "hit_rate" in results_df.columns

    # Find the row for our engineered value bet.
    value_bet_row = results_df[results_df["match"] == "Team A vs Team B"]
    assert not value_bet_row.empty
    
    # Check that it was correctly identified as a bet
    assert value_bet_row.iloc[0]["bet"]

    # Check the calculations
    expected_p_model = 1 - poisson.cdf(8, 11.0)
    assert np.isclose(value_bet_row.iloc[0]["p_model_mean"], expected_p_model)
    assert np.isclose(value_bet_row.iloc[0]["edge_mean"], expected_p_model - 0.5)
    assert value_bet_row.iloc[0]["vote_distribution"] == "3/3 modelos concordam"
    assert "ESTATISTICAS DO ENSEMBLE" in value_bet_row.iloc[0]["audit_report"]
    assert value_bet_row.iloc[0]["bets_placed"] > 0.0
    assert value_bet_row.iloc[0]["profit_total"] > 0.0
    assert value_bet_row.iloc[0]["yield"] > 0.0
    assert value_bet_row.iloc[0]["roi"] > 0.0
    assert 0.0 <= value_bet_row.iloc[0]["hit_rate"] <= 1.0


@patch("japredictbet.pipeline.mvp_pipeline.fetch_odds")
@patch("japredictbet.pipeline.mvp_pipeline.predict_expected_corners")
@patch("japredictbet.pipeline.mvp_pipeline.train_and_save_ensemble")
@patch("japredictbet.pipeline.mvp_pipeline.load_historical_dataset")
def test_pipeline_robust_match_normalization(
    mock_load_data: MagicMock,
    mock_train_and_save_ensemble: MagicMock,
    mock_predict: MagicMock,
    mock_fetch_odds: MagicMock,
    minimal_config: PipelineConfig,
):
    """Pipeline should match odds even with naming variants."""

    num_matches = 24
    mock_load_data.return_value = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=num_matches, freq="D"),
        "home_team": ["Flamengo"] * num_matches,
        "away_team": ["Vasco"] * num_matches,
        "home_goals": [1 + (idx % 2) for idx in range(num_matches)],
        "away_goals": [idx % 2 for idx in range(num_matches)],
        "home_corners": [5 + (idx % 3) for idx in range(num_matches)],
        "away_corners": [4 + (idx % 2) for idx in range(num_matches)],
    })
    mock_predict.side_effect = lambda _models, features: (
        pd.Series(7.0, index=features.index),
        pd.Series(4.0, index=features.index),
    )
    mock_fetch_odds.return_value = pd.DataFrame({
        "match": ["CR Flamengo vs Vasco da Gama"],
        "line": [8.5],
        "over_odds": [2.0],
        "under_odds": [1.8],
    })
    mock_train_and_save_ensemble.return_value = (
        [MagicMock(), MagicMock(), MagicMock()],
        [],
        [],
    )

    results_df = run_mvp_pipeline(minimal_config)

    assert not results_df.empty
    assert results_df.iloc[0]["match"] == "Flamengo vs Vasco"


def test_safe_fuzzy_discards_ambiguous_matches(caplog: pytest.LogCaptureFixture):
    """Ambiguous fuzzy candidates must be discarded (no automatic imputation)."""

    data = pd.DataFrame({
        "source_row_id": [1],
        "match_key": ["Alpha Beta vs Delta"],
    })
    odds = pd.DataFrame({
        "match": ["Alpha Beto vs Delta", "Alpha Betaa vs Delta"],
        "line": [8.5, 8.5],
        "over_odds": [2.0, 2.0],
        "under_odds": [1.8, 1.8],
    })

    with caplog.at_level("INFO", logger="japredictbet.pipeline.mvp_pipeline"):
        merged = _merge_with_normalized_match_keys(
            data=data,
            odds_df=odds,
            similarity_threshold=80.0,
            ambiguity_margin=5.0,
        )

    assert merged["line"].isna().all()
    assert any("reason=ambiguous" in message for message in caplog.messages)


def test_safe_fuzzy_logs_explicit_pairing(caplog: pytest.LogCaptureFixture):
    """Accepted pairing must log explicit odds->dataset team mapping."""

    data = pd.DataFrame({
        "source_row_id": [10],
        "match_key": ["Flamengo vs Vasco"],
    })
    odds = pd.DataFrame({
        "match": ["CR Flamengo vs Vasco da Gama"],
        "line": [8.5],
        "over_odds": [2.0],
        "under_odds": [1.8],
    })

    with caplog.at_level("INFO", logger="japredictbet.pipeline.mvp_pipeline"):
        merged = _merge_with_normalized_match_keys(
            data=data,
            odds_df=odds,
            similarity_threshold=95.0,
            ambiguity_margin=1.0,
        )

    assert merged["line"].notna().all()
    assert any(
        "odds_home='CR Flamengo' -> dataset_home='Flamengo'" in message
        for message in caplog.messages
    )
