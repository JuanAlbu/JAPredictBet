"""MVP pipeline orchestration."""

from __future__ import annotations
from dataclasses import asdict
import logging
from typing import Sequence

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
from japredictbet.models.train import TrainedModels, train_models
from japredictbet.odds.collector import fetch_odds

logger = logging.getLogger(__name__)


def run_mvp_pipeline(
    config: PipelineConfig,
    ensemble_models: Sequence[TrainedModels] | None = None,
) -> pd.DataFrame:
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

    models_ensemble = _get_or_train_ensemble_models(
        config=config,
        train_data=train_data,
        train_weights=train_weights,
        ensemble_models=ensemble_models,
    )

    predictions_by_model = _predict_ensemble(models_ensemble, data)

    # --- Odds and Value Evaluation using the new Engine ---
    odds_df = fetch_odds(config.odds.provider_name)

    # Prepare data for joining
    data["source_row_id"] = data.index
    data["match_key"] = data["home_team"] + " vs " + data["away_team"]

    # For simplicity, we assume the fetched odds are for the 'total' market
    # A real implementation would require more robust joining and market handling
    odds_df = odds_df.rename(columns={"match": "match_key"})
    merged_data = pd.merge(data, odds_df, on="match_key", how="left")
    merged_data = merged_data.dropna(subset=["line", "over_odds"])

    consensus_thresholds = _build_consensus_thresholds(config)
    consensus_engine = engine.ConsensusEngine(edge_threshold=config.value.threshold)

    all_bets = []
    for _, row in merged_data.iterrows():
        model_predictions = [
            {
                "lambda_home": float(pred_home.loc[row["source_row_id"]]),
                "lambda_away": float(pred_away.loc[row["source_row_id"]]),
            }
            for pred_home, pred_away in predictions_by_model
        ]

        consensus_odds = {
            "line": float(row["line"]),
            "odds": float(row["over_odds"]),
            "type": "over",
        }

        for threshold in consensus_thresholds:
            decision = consensus_engine.evaluate_with_consensus(
                predictions_list=model_predictions,
                odds_data=consensus_odds,
                threshold=threshold,
            )
            realized_total = (
                float(row["home_corners"] + row["away_corners"])
                if "home_corners" in row.index and "away_corners" in row.index
                else np.nan
            )
            bet_result = (
                engine.evaluate_result(
                    real_value=int(realized_total),
                    line=decision["line"],
                    bet_type=decision["bet_type"],
                )
                if not np.isnan(realized_total)
                else None
            )
            stake = 1.0 if decision["bet"] else 0.0
            decision_profit = (
                engine.compute_profit(result=bet_result, odds=decision["odds"], stake=stake)
                if decision["bet"]
                else 0.0
            )
            decision["match"] = row["match_key"]
            decision["realized_total"] = realized_total
            decision["bet_result"] = bet_result
            decision["stake"] = stake
            decision["profit"] = decision_profit
            all_bets.append(decision)

    if not all_bets:
        return pd.DataFrame()

    decisions_df = pd.DataFrame(all_bets)
    return _attach_threshold_performance(decisions_df)


def _get_or_train_ensemble_models(
    config: PipelineConfig,
    train_data: pd.DataFrame,
    train_weights: pd.Series,
    ensemble_models: Sequence[TrainedModels] | None,
) -> list[TrainedModels]:
    """Use provided ensemble models or train an ensemble from config."""

    if ensemble_models is not None:
        if not ensemble_models:
            raise ValueError("ensemble_models was provided but is empty.")
        return list(ensemble_models)

    size = max(1, int(config.model.ensemble_size))
    stride = max(1, int(config.model.ensemble_seed_stride))
    algorithms = _normalize_algorithms(config.model.algorithms)
    schedule = _build_ensemble_schedule(size=size, algorithms=algorithms)

    trained: list[TrainedModels] = []
    for idx, algorithm in enumerate(schedule):
        seed = config.model.random_state + (idx * stride)
        params = _build_variation_params(
            algorithm=algorithm,
            variation_index=idx,
        )
        model = train_models(
            train_data,
            home_target="home_corners",
            away_target="away_corners",
            sample_weight=train_weights,
            random_state=seed,
            algorithm=algorithm,
            model_params=params,
        )
        trained.append(model)
    return trained


def _predict_ensemble(
    models_ensemble: Sequence[TrainedModels],
    data: pd.DataFrame,
) -> list[tuple[pd.Series, pd.Series]]:
    """Run inference for each model in the ensemble."""

    predictions: list[tuple[pd.Series, pd.Series]] = []
    for models in models_ensemble:
        predictions.append(predict_expected_corners(models, data))
    return predictions


def _build_consensus_thresholds(config: PipelineConfig) -> list[float]:
    """Build threshold list for consensus backtesting."""

    if not config.value.run_consensus_sweep:
        return [float(config.value.consensus_threshold)]

    start = float(config.value.consensus_start)
    end = float(config.value.consensus_end)
    step = float(config.value.consensus_step)
    if step <= 0:
        raise ValueError("consensus_step must be greater than zero.")
    if end < start:
        raise ValueError("consensus_end must be >= consensus_start.")

    thresholds = np.arange(start, end + (step / 2), step)
    return [float(np.clip(round(threshold, 4), 0.0, 1.0)) for threshold in thresholds]


def _normalize_algorithms(algorithms: Sequence[str]) -> tuple[str, ...]:
    """Normalize configured algorithm names."""

    if not algorithms:
        return ("xgboost",)
    normalized = tuple(algo.strip().lower() for algo in algorithms if algo)
    return normalized if normalized else ("xgboost",)


def _build_ensemble_schedule(size: int, algorithms: Sequence[str]) -> list[str]:
    """Create a balanced algorithm schedule for ensemble training."""

    if size <= 0:
        return ["xgboost"]
    algo_list = list(algorithms) if algorithms else ["xgboost"]
    schedule: list[str] = []
    idx = 0
    while len(schedule) < size:
        schedule.append(algo_list[idx % len(algo_list)])
        idx += 1
    return schedule


def _build_variation_params(algorithm: str, variation_index: int) -> dict:
    """Generate deterministic hyperparameter variations per algorithm."""

    algo = algorithm.strip().lower()
    idx = variation_index % 10

    if algo == "xgboost":
        return {
            "n_estimators": 320 + (idx * 35),
            "learning_rate": max(0.03, 0.12 - (idx * 0.008)),
            "max_depth": 4 + (idx % 4),
            "min_child_weight": 1 + (idx % 3),
            "subsample": 0.72 + ((idx % 3) * 0.08),
            "colsample_bytree": 0.68 + ((idx % 4) * 0.06),
        }

    if algo == "lightgbm":
        return {
            "n_estimators": 300 + (idx * 30),
            "learning_rate": max(0.02, 0.10 - (idx * 0.007)),
            "num_leaves": 24 + (idx * 2),
            "subsample": 0.75 + ((idx % 3) * 0.08),
            "colsample_bytree": 0.72 + ((idx % 4) * 0.06),
        }

    if algo == "randomforest":
        return {
            "n_estimators": 250 + (idx * 30),
            "max_depth": 7 + (idx % 6),
            "min_samples_leaf": 1 + (idx % 3),
            "max_features": 0.55 + ((idx % 4) * 0.1),
        }

    return {}


def _attach_threshold_performance(decisions_df: pd.DataFrame) -> pd.DataFrame:
    """Attach ROI/Yield summary per consensus threshold."""

    if decisions_df.empty:
        return decisions_df

    grouped = decisions_df.groupby("consensus_threshold", dropna=False)
    summary = grouped.agg(
        bets_placed=("stake", "sum"),
        profit_total=("profit", "sum"),
    ).reset_index()

    summary["yield"] = np.where(
        summary["bets_placed"] > 0,
        summary["profit_total"] / summary["bets_placed"],
        0.0,
    )
    summary["roi"] = summary["yield"]

    return decisions_df.merge(summary, on="consensus_threshold", how="left")


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
