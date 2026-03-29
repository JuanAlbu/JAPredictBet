"""Model training routines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor

try:
    import lightgbm as lgb
except ImportError:  # pragma: no cover - optional dependency
    lgb = None


@dataclass(frozen=True)
class TrainedModels:
    """Container for trained home and away models."""

    home_model: object
    away_model: object
    feature_columns: tuple[str, ...]


def train_models(
    features: pd.DataFrame,
    home_target: str,
    away_target: str,
    sample_weight: pd.Series | None = None,
    random_state: int = 42,
    algorithm: str = "xgboost",
    model_params: dict[str, Any] | None = None,
) -> TrainedModels:
    """Train separate models for home and away corner counts.

    The training uses XGBoost with a Poisson objective, aligned with the
    count-data assumptions for corners.
    """

    if home_target not in features.columns or away_target not in features.columns:
        missing = [
            target
            for target in (home_target, away_target)
            if target not in features.columns
        ]
        raise ValueError(f"Missing target columns: {missing}")

    feature_cols = _select_feature_columns(features, exclude=(home_target, away_target))
    if not feature_cols:
        raise ValueError("No numeric feature columns available for training.")

    x = features[feature_cols]
    y_home = features[home_target]
    y_away = features[away_target]
    weights = sample_weight if sample_weight is not None else None

    mask = _valid_training_mask(x, y_home, y_away)
    x = x.loc[mask]
    y_home = y_home.loc[mask]
    y_away = y_away.loc[mask]
    if weights is not None:
        weights = weights.loc[mask]

    if len(x) < 10:
        raise ValueError("Not enough training rows after filtering missing values.")

    home_model = _build_regressor(
        algorithm=algorithm,
        random_state=random_state,
        model_params=model_params,
    )
    away_model = _build_regressor(
        algorithm=algorithm,
        random_state=random_state,
        model_params=model_params,
    )

    if weights is not None:
        home_model.fit(x, y_home, sample_weight=weights)
        away_model.fit(x, y_away, sample_weight=weights)
    else:
        home_model.fit(x, y_home)
        away_model.fit(x, y_away)

    return TrainedModels(
        home_model=home_model,
        away_model=away_model,
        feature_columns=tuple(feature_cols),
    )


def _select_feature_columns(
    df: pd.DataFrame,
    exclude: Iterable[str],
) -> list[str]:
    """Select numeric feature columns excluding targets."""

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    exclude_set = set(exclude)
    allowed = []
    for col in numeric_cols:
        if col in exclude_set:
            continue
        if not _is_allowed_feature(col):
            continue
        if _has_invalid_xgb_name(col):
            continue
        allowed.append(col)
    return allowed


def _valid_training_mask(
    x: pd.DataFrame,
    y_home: pd.Series,
    y_away: pd.Series,
) -> pd.Series:
    """Filter rows with missing values in features or targets."""

    x_valid = x.notna().all(axis=1)
    y_valid = y_home.notna() & y_away.notna()
    return x_valid & y_valid


def _is_allowed_feature(column: str) -> bool:
    """Restrict training to engineered, pre-match safe features."""

    keywords = ("_last", "_diff", "_team_enc", "_vs_", "_ratio", "_pressure", "_total", "elo")
    direct_features = {"home_advantage", "is_home"}
    return column in direct_features or any(key in column for key in keywords)


def _has_invalid_xgb_name(column: str) -> bool:
    """XGBoost rejects feature names containing brackets or angle brackets."""

    return any(char in column for char in ("[", "]", "<", ">"))


def _build_regressor(
    algorithm: str,
    random_state: int,
    model_params: dict[str, Any] | None,
) -> object:
    """Build a regressor aligned with the selected algorithm."""

    algo = algorithm.strip().lower()
    overrides = model_params or {}

    if algo == "xgboost":
        params = {
            "objective": "count:poisson",
            "n_estimators": 507,
            "learning_rate": 0.08242879217471218,
            "max_depth": 6,
            "subsample": 0.7549913516120698,
            "colsample_bytree": 0.7153312415720976,
            "min_child_weight": 2,
            "gamma": 0.2795049672186196,
            "random_state": random_state,
            "n_jobs": 1,
            "verbosity": 0,
            "eval_metric": "poisson-nloglik",
        }
        params.update(overrides)
        return xgb.XGBRegressor(**params)

    if algo == "randomforest":
        params = {
            "n_estimators": 400,
            "max_depth": 10,
            "min_samples_leaf": 2,
            "max_features": 0.8,
            "random_state": random_state,
            "n_jobs": 1,
        }
        params.update(overrides)
        return RandomForestRegressor(**params)

    if algo == "lightgbm":
        if lgb is None:
            raise ValueError(
                "Algorithm 'lightgbm' was requested but lightgbm is not installed."
            )
        params = {
            "objective": "poisson",
            "n_estimators": 450,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "random_state": random_state,
            "n_jobs": 1,
            "verbosity": -1,
        }
        params.update(overrides)
        return lgb.LGBMRegressor(**params)

    raise ValueError(
        f"Unsupported algorithm '{algorithm}'. "
        "Expected one of: xgboost, lightgbm, randomforest."
    )
