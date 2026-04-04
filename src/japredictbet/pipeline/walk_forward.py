"""Walk-forward evaluation with optional feature pruning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_h2h_features, add_matchup_features
from japredictbet.features.rolling import (
    add_result_rolling,
    add_rolling_ema,
    add_rolling_std,
    add_stat_rolling,
    drop_redundant_features,
)
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.importance import compute_feature_importance, select_top_features
from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import train_models
from japredictbet.pipeline.mvp_pipeline import _build_recency_weights, _ensure_season_column


@dataclass(frozen=True)
class WalkForwardConfig:
    """Configuration for walk-forward evaluation."""

    rolling_windows: tuple[int, ...] = (10, 5)
    top_n_features: int | None = 40
    rolling_use_std: bool = True
    rolling_use_ema: bool = True
    drop_redundant: bool = True
    h2h_window: int = 3


def evaluate_walk_forward(
    data: pd.DataFrame,
    config: WalkForwardConfig | None = None,
) -> pd.DataFrame:
    """Run walk-forward evaluation with pruning per fold."""

    cfg = config or WalkForwardConfig()
    data = _build_features(data, cfg)
    data = _ensure_season_column(data, "date")

    seasons = sorted(data["season"].unique())
    if len(seasons) < 2:
        raise ValueError("Walk-forward requires at least two seasons.")

    results = []
    for idx in range(1, len(seasons)):
        train_seasons = set(seasons[:idx])
        test_season = seasons[idx]

        train_mask = data["season"].isin(train_seasons)
        test_mask = data["season"] == test_season
        weights = _build_recency_weights(data.loc[train_mask, "season"])
        weights = weights.reindex(data.index, fill_value=np.nan)

        fold_data = _add_team_encoding(data, train_mask)
        train_data = fold_data.loc[train_mask].copy()

        models = train_models(
            train_data,
            home_target="home_corners",
            away_target="away_corners",
            sample_weight=weights.loc[train_mask],
        )

        importance = compute_feature_importance(models)
        selected = select_top_features(
            importance,
            top_n=cfg.top_n_features,
        )

        pruned_train = train_data[selected + ["home_corners", "away_corners"]].copy()
        pruned_models = train_models(
            pruned_train,
            home_target="home_corners",
            away_target="away_corners",
            sample_weight=weights.loc[train_mask],
        )

        pred_home, pred_away = predict_expected_corners(pruned_models, fold_data)

        metrics = _compute_metrics(
            fold_data.loc[test_mask],
            pred_home.loc[test_mask],
            pred_away.loc[test_mask],
        )
        metrics["train_seasons"] = ",".join(sorted(train_seasons))
        metrics["test_season"] = test_season
        metrics["features_used"] = len(pruned_models.feature_columns)
        results.append(metrics)

    return pd.DataFrame(results)


def _build_features(data: pd.DataFrame, config: WalkForwardConfig) -> pd.DataFrame:
    df = data.copy()
    df = _ensure_season_column(df, "date")

    stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
        ("shots_on_target", "home_shots_on_target", "away_shots_on_target"),
        ("fouls", "home_fouls", "away_fouls"),
        ("yellow_cards", "home_yellow_cards", "away_yellow_cards"),
        ("red_cards", "home_red_cards", "away_red_cards"),
    ]

    std_stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
    ]

    for window in config.rolling_windows:
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
                    season_col="season",
                )
                df = add_stat_rolling(
                    df,
                    team_col="away_team",
                    for_col=away_col,
                    against_col=home_col,
                    window=window,
                    prefix="away",
                    stat_name=stat_name,
                    season_col="season",
                )

        # Rolling STD (P2.A11 — sync with production pipeline)
        if config.rolling_use_std:
            for stat_name, home_col, away_col in std_stats:
                if home_col in df.columns and away_col in df.columns:
                    df = add_rolling_std(
                        df,
                        team_col="home_team",
                        for_col=home_col,
                        against_col=away_col,
                        window=window,
                        prefix="home",
                        stat_name=stat_name,
                        season_col="season",
                    )
                    df = add_rolling_std(
                        df,
                        team_col="away_team",
                        for_col=away_col,
                        against_col=home_col,
                        window=window,
                        prefix="away",
                        stat_name=stat_name,
                        season_col="season",
                    )

        # Rolling EMA (P2.A11 — sync with production pipeline)
        if config.rolling_use_ema:
            for stat_name, home_col, away_col in std_stats:
                if home_col in df.columns and away_col in df.columns:
                    df = add_rolling_ema(
                        df,
                        team_col="home_team",
                        for_col=home_col,
                        against_col=away_col,
                        window=window,
                        prefix="home",
                        stat_name=stat_name,
                        season_col="season",
                    )
                    df = add_rolling_ema(
                        df,
                        team_col="away_team",
                        for_col=away_col,
                        against_col=home_col,
                        window=window,
                        prefix="away",
                        stat_name=stat_name,
                        season_col="season",
                    )

        if "home_goals" in df.columns and "away_goals" in df.columns:
            df = add_result_rolling(
                df,
                team_col="home_team",
                goals_for_col="home_goals",
                goals_against_col="away_goals",
                window=window,
                prefix="home",
                season_col="season",
            )
            df = add_result_rolling(
                df,
                team_col="away_team",
                goals_for_col="away_goals",
                goals_against_col="home_goals",
                window=window,
                prefix="away",
                season_col="season",
            )
        df = add_matchup_features(df, window=window)
        df = _add_total_corners_features(df, window)
        df = _add_total_goals_features(df, window)

    # H2H features (P2.A11 — sync with production pipeline)
    df = add_h2h_features(df, h2h_window=config.h2h_window)

    df["home_advantage"] = 1.0

    # Drop redundant features (P2.A11 — sync with production pipeline)
    if config.drop_redundant:
        df = drop_redundant_features(df, config.rolling_windows)

    df = add_elo_ratings(
        df,
        home_team_col="home_team",
        away_team_col="away_team",
        home_score_col="home_goals",
        away_score_col="away_goals",
        season_col="season",
        config=EloConfig(),
    )
    return df


def _add_team_encoding(df: pd.DataFrame, train_mask: pd.Series) -> pd.DataFrame:
    data = df.copy()
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
    return data


def _add_total_corners_features(data: pd.DataFrame, window: int) -> pd.DataFrame:
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


def _compute_metrics(
    actual: pd.DataFrame,
    pred_home: pd.Series,
    pred_away: pd.Series,
) -> dict[str, float]:
    mask = (
        actual["home_corners"].notna()
        & actual["away_corners"].notna()
        & pred_home.notna()
        & pred_away.notna()
    )

    actual_home = actual.loc[mask, "home_corners"].astype(float)
    actual_away = actual.loc[mask, "away_corners"].astype(float)
    pred_home = pred_home.loc[mask]
    pred_away = pred_away.loc[mask]

    mae_home = float(np.mean(np.abs(pred_home - actual_home)))
    mae_away = float(np.mean(np.abs(pred_away - actual_away)))
    rmse_home = float(np.sqrt(np.mean((pred_home - actual_home) ** 2)))
    rmse_away = float(np.sqrt(np.mean((pred_away - actual_away) ** 2)))

    actual_total = actual_home + actual_away
    pred_total = pred_home + pred_away
    mae_total = float(np.mean(np.abs(pred_total - actual_total)))
    rmse_total = float(np.sqrt(np.mean((pred_total - actual_total) ** 2)))

    return {
        "mae_home": mae_home,
        "mae_away": mae_away,
        "rmse_home": rmse_home,
        "rmse_away": rmse_away,
        "mae_total": mae_total,
        "rmse_total": rmse_total,
    }
