"""MVP pipeline orchestration."""

from __future__ import annotations
from dataclasses import asdict

import numpy as np
import pandas as pd

from japredictbet.betting import engine
from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_matchup_features
from japredictbet.features.rolling import add_result_rolling, add_stat_rolling
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import train_models
from japredictbet.odds.collector import fetch_odds


def run_mvp_pipeline(config: PipelineConfig) -> pd.DataFrame:
    """Orchestrate the end-to-end backtesting pipeline.

    This function performs the following steps:
    1. Loads historical match data.
    2. Engineers a rich set of features (rolling stats, ELO, etc.).
    3. Splits data temporally for training and testing.
    4. Trains ML models to predict home and away corner lambdas.
    5. Fetches odds data from a configured provider.
    6. Merges predictions with odds.
    7. Iterates through each match, calling the core betting engine
       to evaluate value opportunities.
    8. Returns a DataFrame containing all identified betting opportunities.

    Args:
        config: A PipelineConfig object with all necessary configurations.

    Returns:
        A pandas DataFrame containing the results of the value bet analysis,
        with one row per identified opportunity.
    """

    _ = asdict(config)
    data = load_historical_dataset(config.data.raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)

    # --- Feature Engineering ---
    data = _add_rolling_stats(data, config.features.rolling_window, season_col="season")
    data = _add_rolling_stats(data, 5, season_col="season")
    data = add_matchup_features(data, window=config.features.rolling_window)
    data = add_matchup_features(data, window=5)
    data = _add_total_corners_features(data, window=config.features.rolling_window)
    data = _add_total_corners_features(data, window=5)
    data = _add_total_goals_features(data, window=config.features.rolling_window)
    data = _add_total_goals_features(data, window=5)
    data["home_advantage"] = 1.0

    train_mask, _ = _build_temporal_split(
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

    # --- Model Training and Prediction ---
    train_data = data.loc[train_mask].copy()
    train_weights = weights.loc[train_mask]

    models = train_models(
        train_data,
        home_target="home_corners",
        away_target="away_corners",
        sample_weight=train_weights,
        random_state=config.model.random_state,
    )
    expected_home, expected_away = predict_expected_corners(models, data)

    # --- Odds and Value Evaluation using the new Engine ---
    odds_df = fetch_odds(config.odds.provider_name)

    # Prepare data for joining
    data["match_key"] = data["home_team"] + " vs " + data["away_team"]
    data["lambda_home"] = expected_home
    data["lambda_away"] = expected_away

    # For simplicity, we assume the fetched odds are for the 'total' market
    # A real implementation would require more robust joining and market handling
    odds_df = odds_df.rename(columns={"match": "match_key"})
    merged_data = pd.merge(data, odds_df, on="match_key", how="left")
    merged_data = merged_data.dropna(subset=["line", "over_odds"])

    all_bets = []
    for _, row in merged_data.iterrows():
        # This assumes a simple 'total' market for now
        # The engine's evaluate_match is more flexible than this
        odds_data = {"total": {"line": row["line"], "odds": row["over_odds"]}}

        bet_evaluations = engine.evaluate_match(
            lambda_home=row["lambda_home"],
            lambda_away=row["lambda_away"],
            odds_data=odds_data,
            edge_threshold=config.value.threshold,
        )
        # Add match context to each bet evaluation
        for bet in bet_evaluations:
            bet["match"] = row["match_key"]
            all_bets.append(bet)

    if not all_bets:
        return pd.DataFrame()

    return pd.DataFrame(all_bets)


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
