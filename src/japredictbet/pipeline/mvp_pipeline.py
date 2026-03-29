"""MVP pipeline orchestration."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_matchup_features
from japredictbet.features.rolling import add_result_rolling, add_stat_rolling
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.train import train_models
from japredictbet.models.predict import predict_expected_corners
from japredictbet.odds.collector import fetch_odds
from japredictbet.betting.value_detector import detect_value_bets
from japredictbet.probability.poisson import prob_total_over


def run_mvp_pipeline(config: PipelineConfig) -> pd.DataFrame:
    """Run the end-to-end MVP pipeline.

    This function wires the core components without implementing model
    training or odds ingestion yet.
    """

    _ = asdict(config)
    data = load_historical_dataset(config.data.raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)

    data = _add_rolling_stats(data, config.features.rolling_window, season_col="season")
    data = _add_rolling_stats(data, 5, season_col="season")
    data = add_matchup_features(data, window=config.features.rolling_window)
    data = add_matchup_features(data, window=5)
    data = _add_total_corners_features(data, window=config.features.rolling_window)
    data = _add_total_corners_features(data, window=5)
    data = _add_total_goals_features(data, window=config.features.rolling_window)
    data = _add_total_goals_features(data, window=5)
    data["home_advantage"] = 1.0

    train_mask, test_mask = _build_temporal_split(
        data["season"], config.model.random_state
    )
    weights = _build_recency_weights(data["season"])

    data = add_elo_ratings(
        data,
        home_team_col="home_team",
        away_team_col="away_team",
        home_score_col="home_goals",
        away_score_col="away_goals",
        season_col="season",
        config=EloConfig(),
    )

    data = add_team_target_encoding(
        data,
        team_col="home_team",
        target_col="home_corners",
        train_mask=train_mask,
        feature_name="home_team_team_enc",
    )
    data = add_team_target_encoding(
        data,
        team_col="away_team",
        target_col="away_corners",
        train_mask=train_mask,
        feature_name="away_team_team_enc",
    )

    train_data = data.loc[train_mask].copy()
    train_weights = weights.loc[train_mask]

    models = train_models(
        train_data,
        home_target="home_corners",
        away_target="away_corners",
        sample_weight=train_weights,
    )
    expected_home, expected_away = predict_expected_corners(models, data)
    expected_total = expected_home + expected_away

    try:
        odds = fetch_odds(config.odds.provider_name)
    except NotImplementedError:
        odds = _build_mock_odds(data)

    odds = odds.reset_index(drop=True)
    expected_total = expected_total.reset_index(drop=True)
    odds["model_prob"] = [
        prob_total_over(line, rate)
        for line, rate in zip(odds["line"], expected_total)
    ]

    results = detect_value_bets(odds, odds["model_prob"], config.value.threshold)
    return results


def _ensure_season_column(data: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Ensure the dataset has a season column for temporal splits."""

    if "season" in data.columns:
        return data
    date_col = date_column if date_column in data.columns else "date"
    df = data.copy()
    df["season"] = df[date_col].dt.year
    return df


def _build_temporal_split(seasons: pd.Series, seed: int) -> tuple[pd.Series, pd.Series]:
    """Split 50% of the most recent season for testing."""

    most_recent = seasons.max()
    recent_idx = seasons[seasons == most_recent].index.to_numpy(copy=True)
    rng = np.random.default_rng(seed)
    rng.shuffle(recent_idx)
    cut = len(recent_idx) // 2
    test_idx = recent_idx[:cut]
    test_mask = seasons.index.isin(test_idx)
    train_mask = ~test_mask
    return train_mask, test_mask


def _build_recency_weights(seasons: pd.Series) -> pd.Series:
    """Linearly scale weights from oldest to most recent season."""

    unique = sorted(seasons.unique())
    season_rank = {season: idx for idx, season in enumerate(unique)}
    max_rank = max(season_rank.values()) if season_rank else 1
    return seasons.map(
        lambda season: 1.0 + (season_rank[season] / max_rank if max_rank else 0.0)
    )


def _add_rolling_stats(
    data: pd.DataFrame,
    window: int,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling stats for available columns."""

    df = data.copy()
    stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
        ("shots_on_target", "home_shots_on_target", "away_shots_on_target"),
        ("fouls", "home_fouls", "away_fouls"),
        ("yellow_cards", "home_yellow_cards", "away_yellow_cards"),
        ("red_cards", "home_red_cards", "away_red_cards"),
    ]

    for stat_name, home_col, away_col in stats:
        if home_col in df.columns and away_col in df.columns:
            df = add_stat_rolling(
                df,
                team_col="home_team",
                for_col=home_col,
                against_col=away_col,
                window=window,
                prefix="home",
                stat_name=stat_name,
                season_col=season_col,
            )
            df = add_stat_rolling(
                df,
                team_col="away_team",
                for_col=away_col,
                against_col=home_col,
                window=window,
                prefix="away",
                stat_name=stat_name,
                season_col=season_col,
            )
    if "home_goals" in df.columns and "away_goals" in df.columns:
        df = add_result_rolling(
            df,
            team_col="home_team",
            goals_for_col="home_goals",
            goals_against_col="away_goals",
            window=window,
            prefix="home",
            season_col=season_col,
        )
        df = add_result_rolling(
            df,
            team_col="away_team",
            goals_for_col="away_goals",
            goals_against_col="home_goals",
            window=window,
            prefix="away",
            season_col=season_col,
        )
    return df


def _build_mock_odds(data: pd.DataFrame) -> pd.DataFrame:
    """Create a simple mock odds table aligned to the dataset."""

    return pd.DataFrame(
        {
            "match": data["home_team"].str.cat(data["away_team"], sep=" vs "),
            "line": 9.5,
            "over_odds": 1.9,
            "under_odds": 1.9,
        }
    )


def _add_total_corners_features(data: pd.DataFrame, window: int) -> pd.DataFrame:
    """Add total corners features from rolling stats."""

    df = data.copy()
    suffix = f"_last{window}"
    home_for = f"home_corners_for{suffix}"
    home_against = f"home_corners_against{suffix}"
    away_for = f"away_corners_for{suffix}"
    away_against = f"away_corners_against{suffix}"

    if home_for in df.columns and home_against in df.columns:
        df[f"home_total_corners{suffix}"] = df[home_for] + df[home_against]
    if away_for in df.columns and away_against in df.columns:
        df[f"away_total_corners{suffix}"] = df[away_for] + df[away_against]
    if home_for in df.columns and away_for in df.columns:
        df[f"total_corners_for{suffix}"] = df[home_for] + df[away_for]
    return df


def _add_total_goals_features(data: pd.DataFrame, window: int) -> pd.DataFrame:
    """Add total goals features from rolling stats."""

    df = data.copy()
    suffix = f"_last{window}"
    home_for = f"home_goals_for{suffix}"
    home_against = f"home_goals_against{suffix}"
    away_for = f"away_goals_for{suffix}"
    away_against = f"away_goals_against{suffix}"

    if home_for in df.columns and home_against in df.columns:
        df[f"home_total_goals{suffix}"] = df[home_for] + df[home_against]
    if away_for in df.columns and away_against in df.columns:
        df[f"away_total_goals{suffix}"] = df[away_for] + df[away_against]
    if home_for in df.columns and away_for in df.columns:
        df[f"total_goals_for{suffix}"] = df[home_for] + df[away_for]
    return df
