"""MVP pipeline orchestration."""

from __future__ import annotations
from dataclasses import asdict
import logging
from pathlib import Path
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
from japredictbet.models.train import (
    TrainedModels,
    train_and_save_ensemble,
)
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

    # Prepare data for robust matching
    data["source_row_id"] = data.index
    data["match_key"] = data["home_team"] + " vs " + data["away_team"]
    merged_data = _merge_with_normalized_match_keys(data=data, odds_df=odds_df)
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
            decision = consensus_engine.evaluate_match_with_consensus(
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

    output_dir = Path("artifacts") / "models"
    trained, specs, paths = train_and_save_ensemble(
        features=train_data,
        home_target="home_corners",
        away_target="away_corners",
        output_dir=output_dir,
        algorithms=_normalize_algorithms(config.model.algorithms),
        ensemble_size=max(1, int(config.model.ensemble_size)),
        sample_weight=train_weights,
        random_state=config.model.random_state,
        ensemble_seed_stride=max(1, int(config.model.ensemble_seed_stride)),
    )
    logger.info(
        "Ensemble trained and saved | models=%d | output_dir=%s | files=%d",
        len(trained),
        output_dir,
        len(paths),
    )
    if specs:
        logger.info(
            "Ensemble composition: %s",
            ", ".join(
                f"{spec.algorithm}:{spec.variation_index + 1}"
                for spec in specs
            ),
        )
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

    span = end - start
    steps = int(round(span / step))
    thresholds = [round(start + (idx * step), 4) for idx in range(steps + 1)]
    if thresholds[-1] < round(end, 4):
        thresholds.append(round(end, 4))

    # Keep deterministic ordering and remove float duplicates.
    normalized = sorted({float(np.clip(value, 0.0, 1.0)) for value in thresholds})
    return normalized


def _normalize_algorithms(algorithms: Sequence[str]) -> tuple[str, ...]:
    """Normalize configured algorithm names."""

    if not algorithms:
        return ("xgboost",)
    normalized = tuple(algo.strip().lower() for algo in algorithms if algo)
    return normalized if normalized else ("xgboost",)


def _merge_with_normalized_match_keys(data: pd.DataFrame, odds_df: pd.DataFrame) -> pd.DataFrame:
    """Merge dataset and odds using robust normalized team names."""

    prepared_data = data.copy()
    prepared_odds = odds_df.copy()

    prepared_data["match_key_normalized"] = prepared_data["match_key"].map(_normalize_match_key)
    prepared_odds["match_key"] = prepared_odds["match"]
    prepared_odds["match_key_normalized"] = prepared_odds["match_key"].map(_normalize_match_key)

    merged = pd.merge(
        prepared_data,
        prepared_odds.drop(columns=["match_key"]),
        on="match_key_normalized",
        how="left",
        suffixes=("", "_odds"),
    )

    # Fuzzy fallback to recover rows still unmatched after strict normalization.
    odds_key_lookup = {
        _normalize_match_key(raw_key): raw_key
        for raw_key in prepared_odds["match_key"].dropna().tolist()
    }

    normalized_odds_keys = list(odds_key_lookup.keys())
    if not normalized_odds_keys:
        return merged

    from difflib import get_close_matches

    fuzzy_map: dict[str, str] = {}
    for key in prepared_data["match_key_normalized"].dropna().unique().tolist():
        close = get_close_matches(key, normalized_odds_keys, n=1, cutoff=0.82)
        if close:
            fuzzy_map[key] = close[0]

    if not fuzzy_map:
        return merged

    prepared_data["fuzzy_odds_key"] = prepared_data["match_key_normalized"].map(fuzzy_map)
    prepared_odds["fuzzy_odds_key"] = prepared_odds["match_key_normalized"]
    fuzzy_merged = pd.merge(
        prepared_data,
        prepared_odds.drop(columns=["match_key_normalized", "match"]),
        on="fuzzy_odds_key",
        how="left",
    )
    # Fill only rows missing from strict merge using fuzzy merge values.
    fill_columns = [col for col in ["line", "over_odds", "under_odds"] if col in merged.columns]
    if not fill_columns:
        return merged

    fuzzy_lookup = fuzzy_merged.set_index("source_row_id")
    for column in fill_columns:
        if column not in fuzzy_lookup.columns:
            continue
        merged[column] = merged[column].fillna(
            merged["source_row_id"].map(fuzzy_lookup[column])
        )
    return merged


def _normalize_match_key(match_name: str) -> str:
    """Normalize match key to improve odds matching robustness."""

    if not isinstance(match_name, str):
        return ""

    raw = match_name.lower().strip()
    replacements = [
        (" versus ", " vs "),
        (" v ", " vs "),
        (" x ", " vs "),
        ("-", " "),
        (".", " "),
        ("'", ""),
    ]
    for old, new in replacements:
        raw = raw.replace(old, new)

    if " vs " not in raw:
        return _normalize_team_name(raw)

    home, away = raw.split(" vs ", maxsplit=1)
    return f"{_normalize_team_name(home)} vs {_normalize_team_name(away)}"


def _normalize_team_name(team_name: str) -> str:
    """Normalize team names by removing aliases and noise tokens."""

    import re
    import unicodedata

    if not isinstance(team_name, str):
        return ""
    name = unicodedata.normalize("NFKD", team_name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.lower()
    name = re.sub(r"[^a-z0-9\\s]", " ", name)
    tokens = [token for token in name.split() if token]

    stop_tokens = {
        "fc", "cf", "sc", "ac", "cr", "cd", "club", "clube", "de", "do", "da",
        "the", "esporte", "sport", "athletic", "atletico",
    }
    filtered = [token for token in tokens if token not in stop_tokens]
    return " ".join(filtered) if filtered else " ".join(tokens)


def _attach_threshold_performance(decisions_df: pd.DataFrame) -> pd.DataFrame:
    """Attach ROI/Yield summary per consensus threshold."""

    if decisions_df.empty:
        return decisions_df

    grouped = decisions_df.groupby("consensus_threshold", dropna=False)
    summary = grouped.agg(
        bets_placed=("stake", "sum"),
        profit_total=("profit", "sum"),
    ).reset_index()

    # Hit rate (accuracy of placed bets excluding pushes)
    settled = decisions_df[
        (decisions_df["stake"] > 0.0) & (decisions_df["bet_result"].notna())
    ].copy()
    if settled.empty:
        hit_rate_summary = summary[["consensus_threshold"]].copy()
        hit_rate_summary["hit_rate"] = 0.0
    else:
        settled["is_win"] = settled["bet_result"].astype(bool)
        hit_rate_summary = (
            settled.groupby("consensus_threshold", dropna=False)["is_win"]
            .mean()
            .reset_index()
            .rename(columns={"is_win": "hit_rate"})
        )

    summary["yield"] = np.where(
        summary["bets_placed"] > 0,
        summary["profit_total"] / summary["bets_placed"],
        0.0,
    )
    summary["roi"] = summary["yield"]
    summary["yield_pct"] = summary["yield"] * 100.0
    summary["roi_pct"] = summary["roi"] * 100.0
    summary = summary.merge(hit_rate_summary, on="consensus_threshold", how="left")
    summary["hit_rate"] = summary["hit_rate"].fillna(0.0)
    summary["hit_rate_pct"] = summary["hit_rate"] * 100.0

    # Rank thresholds by financial quality (ROI first, then profit, then volume).
    ordered = summary.sort_values(
        by=["roi", "profit_total", "bets_placed", "consensus_threshold"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    rank_map = {
        float(row["consensus_threshold"]): int(idx + 1)
        for idx, (_, row) in enumerate(ordered.iterrows())
    }
    best_threshold = float(ordered.iloc[0]["consensus_threshold"])
    summary["threshold_rank"] = summary["consensus_threshold"].map(rank_map).astype(int)
    summary["is_best_threshold"] = summary["consensus_threshold"] == best_threshold

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
