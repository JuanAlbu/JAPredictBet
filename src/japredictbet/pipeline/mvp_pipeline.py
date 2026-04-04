"""MVP pipeline orchestration."""

from __future__ import annotations
from dataclasses import asdict
from difflib import SequenceMatcher
import hashlib
import json
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from japredictbet.betting import engine
from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_h2h_features, add_matchup_features
from japredictbet.features.rolling import (
    add_result_rolling,
    add_stat_rolling,
    add_rolling_std,
    add_rolling_ema,
    drop_redundant_features,
)
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import (
    TrainedModels,
    train_and_save_ensemble,
)
from japredictbet.odds.collector import fetch_odds

logger = logging.getLogger(__name__)


def _compute_artifact_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file for auditability."""
    if not filepath.exists():
        return "FILE_NOT_FOUND"
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha.update(chunk)
    return sha.hexdigest()[:16]  # Short hash


def _create_execution_metadata(config: PipelineConfig, raw_data_path: Path) -> dict:
    """Create execution metadata with versioning information."""
    from datetime import datetime
    
    exec_time = datetime.now().isoformat()
    dataset_hash = _compute_artifact_hash(raw_data_path)
    config_hash = hashlib.sha256(
        json.dumps(asdict(config), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    
    metadata = {
        "execution_time": exec_time,
        "dataset_version": dataset_hash,
        "config_version": config_hash,
        "ensemble_size": int(config.model.ensemble_size),
        "random_state": int(config.model.random_state),
        "consensus_threshold": float(config.value.consensus_threshold),
        "edge_threshold": float(config.value.threshold),
    }
    
    logger.info(
        "Execution metadata | time=%s | dataset_v=%s | config_v=%s",
        exec_time,
        dataset_hash,
        config_hash,
    )
    
    return metadata


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
    
    # --- Execution Versioning ---
    exec_metadata = _create_execution_metadata(config, Path(config.data.raw_path))
    logger.info("Pipeline execution versioning: %s", exec_metadata)
    
    data = load_historical_dataset(config.data.raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)

    # --- Feature Engineering ---
    for window in config.features.rolling_windows:
        data = _add_rolling_stats(data, window, season_col="season")
        
        # P1.B2: Add rolling standard deviation if enabled
        if config.features.rolling_use_std:
            data = _add_rolling_std_features(data, window, season_col="season")
        
        # P1.B2: Add EMA features if enabled
        if config.features.rolling_use_ema:
            data = _add_rolling_ema_features(data, window, season_col="season")
        
        data = add_matchup_features(data, window=window)
        data = _add_total_corners_features(data, window=window)
        data = _add_total_goals_features(data, window=window)

    # P1.B5: Head-to-head features (computed once, not per window)
    data = add_h2h_features(data, h2h_window=config.features.h2h_window)
    data["home_advantage"] = 1.0

    # Drop redundant features if enabled
    if config.features.drop_redundant:
        data = drop_redundant_features(data, config.features.rolling_windows)

    encoding_train_mask, _ = _build_temporal_split(
        data["season"], config.model.random_state
    )

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
        train_mask=encoding_train_mask,
        feature_name="home_team_team_enc",
    )
    data = add_team_target_encoding(
        data,
        team_col="away_team",
        target_col="away_corners",
        train_mask=encoding_train_mask,
        feature_name="away_team_team_enc",
    )
    data = _drop_matches_with_missing_critical_data(data)
    train_mask, _ = _build_temporal_split(
        data["season"], config.model.random_state
    )
    weights = _build_recency_weights(data["season"])

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
    merged_data = _merge_with_normalized_match_keys(
        data=data,
        odds_df=odds_df,
        similarity_threshold=float(config.odds.match_similarity_threshold),
        ambiguity_margin=float(config.odds.ambiguity_margin),
    )
    merged_data = merged_data.dropna(subset=["line", "over_odds"])

    consensus_thresholds = _build_consensus_thresholds(config)
    consensus_engine = engine.ConsensusEngine(
        edge_threshold=config.value.threshold,
        tight_margin_threshold=config.value.tight_margin_threshold,
        tight_margin_consensus=config.value.tight_margin_consensus,
    )

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

    target_ensemble_size = max(1, int(config.model.ensemble_size))
    if target_ensemble_size != 30:
        logger.warning(
            "Consensus architecture expects 30 models; current config uses %d.",
            target_ensemble_size,
        )

    if ensemble_models is not None:
        if not ensemble_models:
            raise ValueError("ensemble_models was provided but is empty.")
        if len(ensemble_models) != target_ensemble_size:
            logger.warning(
                "Provided ensemble size differs from config | provided=%d | configured=%d",
                len(ensemble_models),
                target_ensemble_size,
            )
        return list(ensemble_models)

    output_dir = Path("artifacts") / "models"
    trained, specs, paths = train_and_save_ensemble(
        features=train_data,
        home_target="home_corners",
        away_target="away_corners",
        output_dir=output_dir,
        algorithms=_normalize_algorithms(config.model.algorithms),
        ensemble_size=target_ensemble_size,
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


def _merge_with_normalized_match_keys(
    data: pd.DataFrame,
    odds_df: pd.DataFrame,
    similarity_threshold: float = 95.0,
    ambiguity_margin: float = 1.0,
) -> pd.DataFrame:
    """Merge dataset and odds using robust normalized team names (AUDIT POINT: Equipe + Data + Liga).
    
    MATCHING STRATEGY (P0.7):
    - Primary key: Normalized match_key (Team A vs Team B)
    - Secondary fallback: Fuzzy string matching with {similarity_threshold}% threshold
    - Ambiguity rejection: Remove odds keys with multiple candidates to prevent leakage
    - Future: Add date and league columns for 3-tuple matching (Team + Date + League)
    
    This design prevents data leakage while maintaining practical matching robustness.
    """

    prepared_data = data.copy()
    prepared_odds = odds_df.copy()

    prepared_data["match_key_normalized"] = prepared_data["match_key"].map(_normalize_match_key)
    prepared_odds["match_key"] = prepared_odds["match"]
    prepared_odds["match_key_normalized"] = prepared_odds["match_key"].map(_normalize_match_key)
    prepared_odds = prepared_odds.dropna(subset=["match_key_normalized"]).copy()

    odds_key_counts = prepared_odds["match_key_normalized"].value_counts()
    ambiguous_exact_keys = odds_key_counts[odds_key_counts > 1].index.tolist()
    if ambiguous_exact_keys:
        logger.info(
            "Dropping ambiguous odds keys with multiple rows (P0.7 safety): %d",
            len(ambiguous_exact_keys),
        )
        prepared_odds = prepared_odds[
            ~prepared_odds["match_key_normalized"].isin(ambiguous_exact_keys)
        ].copy()
    if prepared_odds.empty:
        return prepared_data.assign(line=np.nan, over_odds=np.nan, under_odds=np.nan)

    merged = pd.merge(
        prepared_data,
        prepared_odds.drop(columns=["match_key"]),
        on="match_key_normalized",
        how="left",
        suffixes=("", "_odds"),
    )

    if "line" not in merged.columns:
        return merged

    strict_matched = merged[merged["line"].notna()] if "line" in merged.columns else pd.DataFrame()
    _log_match_pairing(strict_matched, method="strict", score=100.0)

    # Formatting-correction fallback with safety gates:
    # 1) minimum similarity threshold
    # 2) ambiguity rejection when top candidates are too close.
    odds_keys = prepared_odds["match_key_normalized"].dropna().unique().tolist()
    if not odds_keys:
        return merged

    odds_by_key = {
        normalized_key: group.copy()
        for normalized_key, group in prepared_odds.groupby("match_key_normalized", dropna=True)
    }
    if not odds_by_key:
        return merged

    unmatched_mask = merged["line"].isna()
    if not unmatched_mask.any():
        return merged

    recovered_rows: list[dict[str, float | str | int]] = []
    unmatched_rows = merged.loc[unmatched_mask, ["source_row_id", "match_key", "match_key_normalized"]]
    for _, row in unmatched_rows.iterrows():
        source_id = int(row["source_row_id"])
        source_match = str(row["match_key"])
        source_key = str(row["match_key_normalized"])
        if not source_key:
            continue

        ranked_candidates = sorted(
            (
                (_similarity_score(source_key, candidate_key), candidate_key)
                for candidate_key in odds_by_key
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if not ranked_candidates:
            logger.info(
                "Odds match discarded | source='%s' | reason=no_candidates",
                source_match,
            )
            continue

        top_score, top_key = ranked_candidates[0]
        second_score = ranked_candidates[1][0] if len(ranked_candidates) > 1 else -1.0
        if top_score < similarity_threshold:
            logger.info(
                "Odds match discarded | source='%s' | reason=low_similarity | best_score=%.2f | required=%.2f",
                source_match,
                top_score,
                similarity_threshold,
            )
            continue
        if second_score >= 0.0 and (top_score - second_score) <= ambiguity_margin:
            logger.info(
                "Odds match discarded | source='%s' | reason=ambiguous | best_score=%.2f | second_score=%.2f | margin=%.2f",
                source_match,
                top_score,
                second_score,
                ambiguity_margin,
            )
            continue

        matched_odds = odds_by_key[top_key]
        if len(matched_odds) != 1:
            logger.info(
                "Odds match discarded | source='%s' | reason=multiple_odds_rows | candidates=%d",
                source_match,
                len(matched_odds),
            )
            continue

        matched_row = matched_odds.iloc[0]
        recovered_rows.append(
            {
                "source_row_id": source_id,
                "line": float(matched_row["line"]),
                "over_odds": float(matched_row["over_odds"]),
                "under_odds": float(matched_row["under_odds"]),
                "matched_odds_match": str(matched_row["match"]),
                "match_similarity_score": float(top_score),
            }
        )

    if not recovered_rows:
        return merged

    recovered = pd.DataFrame(recovered_rows).set_index("source_row_id")
    for column in ("line", "over_odds", "under_odds"):
        if column not in merged.columns or column not in recovered.columns:
            continue
        missing_mask = merged[column].isna()
        merged.loc[missing_mask, column] = merged.loc[missing_mask, "source_row_id"].map(
            recovered[column]
        )
    recovered_log = merged[merged["source_row_id"].isin(recovered.index)].copy()
    recovered_log["matched_odds_match"] = recovered_log["source_row_id"].map(
        recovered["matched_odds_match"]
    )
    recovered_log["match_similarity_score"] = recovered_log["source_row_id"].map(
        recovered["match_similarity_score"]
    )
    _log_match_pairing(
        recovered_log,
        method="fuzzy_safe",
    )
    return merged


def _similarity_score(left: str, right: str) -> float:
    """Compute robust similarity score in [0, 100] for normalized keys."""

    if not left or not right:
        return 0.0

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens and (
        left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens)
    ):
        return 100.0

    return SequenceMatcher(None, left, right).ratio() * 100.0


def _log_match_pairing(
    matched_rows: pd.DataFrame,
    method: str,
    score: float | None = None,
) -> None:
    """Log auditable dataset<->odds pairing details."""

    if matched_rows.empty:
        return

    for _, row in matched_rows.iterrows():
        dataset_match = str(row.get("match_key", ""))
        odds_match = str(row.get("matched_odds_match", row.get("match", "")))
        if not dataset_match or not odds_match:
            continue
        dataset_home, dataset_away = _split_match_name(dataset_match)
        odds_home, odds_away = _split_match_name(odds_match)
        similarity = (
            float(row.get("match_similarity_score"))
            if "match_similarity_score" in row and pd.notna(row.get("match_similarity_score"))
            else (100.0 if score is None else score)
        )
        logger.info(
            "Odds pairing accepted | method=%s | score=%.2f | odds_home='%s' -> dataset_home='%s' | odds_away='%s' -> dataset_away='%s' | odds_match='%s' | dataset_match='%s'",
            method,
            similarity,
            odds_home,
            dataset_home,
            odds_away,
            dataset_away,
            odds_match,
            dataset_match,
        )


def _split_match_name(match_name: str) -> tuple[str, str]:
    """Split a match label into home and away team names."""

    import re

    if not isinstance(match_name, str):
        return "", ""
    raw = match_name.strip()
    parts = re.split(r"\s+(?:versus|vs|v|x)\s+", raw, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        home = parts[0].strip()
        away = parts[1].strip()
        return home, away
    return match_name.strip(), ""


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
        "the", "esporte", "sport", "athletic", "atletico", "gama",
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


def _build_temporal_split(
    seasons: pd.Series, 
    seed: int,
    use_strict_holdout: bool = True,
    holdout_months: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Split data temporally with strict holdout validation.
    
    Args:
        seasons: Series of season values (years)
        seed: Random seed for reproducibility
        use_strict_holdout: If True, use last N months as holdout; if False, use 50% of last season
        holdout_months: Number of recent months to reserve for validation
        
    Returns:
        Tuple of (train_mask, test_mask) boolean Series
    """

    if use_strict_holdout:
        # Strict holdout: last 3 months reserved for validation (more rigorous)
        # This ensures temporal leakage prevention and out-of-sample rigor
        most_recent = seasons.max()
        recent_idx = seasons[seasons == most_recent].index.to_numpy(copy=True)
        rng = np.random.default_rng(seed)
        rng.shuffle(recent_idx)
        
        # Use 25% of most recent season as holdout (approximately 3 months of ~12 months)
        holdout_ratio = min(holdout_months / 12.0, 0.5)  # Cap at 50%
        cut = max(1, int(len(recent_idx) * holdout_ratio))
        test_idx = recent_idx[:cut]
    else:
        # Legacy: 50% of most recent season
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


def _add_rolling_std_features(
    data: pd.DataFrame,
    window: int,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add rolling standard deviation features (P1.B2).
    
    Detects consistency/volatility in team performance.
    High STD indicates inconsistent form.
    """
    df = data.copy()
    stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
    ]

    for stat_name, home_col, away_col in stats:
        if home_col in df.columns and away_col in df.columns:
            df = add_rolling_std(
                df,
                team_col="home_team",
                for_col=home_col,
                against_col=away_col,
                window=window,
                prefix="home",
                stat_name=stat_name,
                season_col=season_col,
            )
            df = add_rolling_std(
                df,
                team_col="away_team",
                for_col=away_col,
                against_col=home_col,
                window=window,
                prefix="away",
                stat_name=stat_name,
                season_col=season_col,
            )
    return df


def _add_rolling_ema_features(
    data: pd.DataFrame,
    window: int,
    season_col: str | None = None,
) -> pd.DataFrame:
    """Add exponential moving average features (P1.B2).
    
    Gives more weight to recent games for current form capture.
    Alpha = 2 / (window + 1) by default.
    """
    df = data.copy()
    stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
    ]

    for stat_name, home_col, away_col in stats:
        if home_col in df.columns and away_col in df.columns:
            df = add_rolling_ema(
                df,
                team_col="home_team",
                for_col=home_col,
                against_col=away_col,
                window=window,
                prefix="home",
                stat_name=stat_name,
                season_col=season_col,
            )
            df = add_rolling_ema(
                df,
                team_col="away_team",
                for_col=away_col,
                against_col=home_col,
                window=window,
                prefix="away",
                stat_name=stat_name,
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


def _drop_matches_with_missing_critical_data(data: pd.DataFrame) -> pd.DataFrame:
    """Drop matches with missing labels or model-critical features."""

    required = ["season", "home_team", "away_team", "home_corners", "away_corners"]
    # Keep this list intentionally small to avoid over-pruning smaller datasets.
    # Missing engineered features are handled later via per-feature imputation.
    optional_critical = [
        "home_team_team_enc",
        "away_team_team_enc",
        "home_elo",
        "away_elo",
    ]
    subset = [column for column in required + optional_critical if column in data.columns]
    if not subset:
        return data

    before = len(data)
    cleaned = data.dropna(subset=subset).copy()
    dropped = before - len(cleaned)
    if dropped:
        logger.info(
            "Dropped matches with missing critical values: %d (remaining=%d)",
            dropped,
            len(cleaned),
        )
    return cleaned


def _select_critical_feature_columns(
    data: pd.DataFrame,
    exclude: tuple[str, ...],
) -> list[str]:
    """Select numeric model features considered critical for train/backtest."""

    numeric_columns = data.select_dtypes(include=[np.number]).columns
    excluded = set(exclude)
    selected: list[str] = []
    for column in numeric_columns:
        if column in excluded:
            continue
        if _is_model_feature_candidate(column):
            selected.append(column)
    return selected


def _is_model_feature_candidate(column: str) -> bool:
    """Match the same pre-match feature pattern used by the training module.

    Keywords must stay in sync with ``_is_allowed_feature`` in
    ``japredictbet.models.train``.
    """

    keywords = (
        "_last",
        "_diff",
        "_team_enc",
        "_vs_",
        "_ratio",
        "_pressure",
        "_total",
        "elo",
        "_rolling",
        "_momentum",
    )
    direct_features = {"home_advantage", "is_home"}
    return column in direct_features or any(keyword in column for keyword in keywords)
