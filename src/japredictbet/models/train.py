"""Model training routines."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge

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
    feature_fill_values: dict[str, float] | None = None


@dataclass(frozen=True)
class EnsembleModelSpec:
    """Metadata for an ensemble member."""

    algorithm: str
    variation_index: int
    random_state: int
    model_name: str
    params: dict[str, Any]


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

    x = features[feature_cols].copy()
    y_home = features[home_target]
    y_away = features[away_target]
    weights = sample_weight if sample_weight is not None else None

    x, feature_cols = _drop_unusable_feature_columns(x, feature_cols)
    if not feature_cols:
        raise ValueError("No usable feature columns after removing empty features.")

    mask = _valid_training_mask(y_home, y_away)
    x = x.loc[mask].copy()
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

    feature_fill_values = {
        col: float(x[col].median()) if x[col].notna().any() else 0.0
        for col in feature_cols
    }
    x = x.fillna(feature_fill_values)

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
        feature_fill_values=feature_fill_values,
    )


def train_ensemble_models(
    features: pd.DataFrame,
    home_target: str,
    away_target: str,
    algorithms: tuple[str, ...] = ("xgboost", "lightgbm", "randomforest"),
    ensemble_size: int = 30,
    sample_weight: pd.Series | None = None,
    random_state: int = 42,
    ensemble_seed_stride: int = 1,
) -> tuple[list[TrainedModels], list[EnsembleModelSpec]]:
    """Train an ensemble with deterministic algorithm/variation scheduling.

    For the default 30-model council this yields 10 models per algorithm
    (XGBoost, LightGBM and RandomForest), each with deterministic parameter
    variations.
    """

    normalized_algorithms = _normalize_algorithms(algorithms)
    schedule = _build_ensemble_schedule(ensemble_size, normalized_algorithms)

    trained: list[TrainedModels] = []
    specs: list[EnsembleModelSpec] = []
    algo_counter: dict[str, int] = {algo: 0 for algo in normalized_algorithms}

    for idx, algorithm in enumerate(schedule):
        variation_index = algo_counter[algorithm]
        algo_counter[algorithm] += 1
        seed = random_state + (idx * max(1, ensemble_seed_stride))
        params = build_variation_params(algorithm=algorithm, variation_index=variation_index)
        model_name = _build_model_filename(algorithm, variation_index)

        trained_model = train_models(
            features=features,
            home_target=home_target,
            away_target=away_target,
            sample_weight=sample_weight,
            random_state=seed,
            algorithm=algorithm,
            model_params=params,
        )
        trained.append(trained_model)
        specs.append(
            EnsembleModelSpec(
                algorithm=algorithm,
                variation_index=variation_index,
                random_state=seed,
                model_name=model_name,
                params=params,
            )
        )

    return trained, specs


def save_ensemble_models(
    models: list[TrainedModels],
    specs: list[EnsembleModelSpec],
    output_dir: Path | str,
) -> list[Path]:
    """Persist trained ensemble members to disk with standard names.
    
    Each model is saved as a .pkl file alongside a .json metadata file
    containing auditable hyperparameters (P1.C3).
    """

    if len(models) != len(specs):
        raise ValueError("models and specs must have the same length.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    for model, spec in zip(models, specs):
        output_path = out_dir / spec.model_name
        with open(output_path, "wb") as handle:
            pickle.dump(model, handle)
        saved_paths.append(output_path)

        # P1.C3: Save auditable hyperparameter metadata as JSON
        meta_path = output_path.with_suffix(".json")
        metadata = {
            "algorithm": spec.algorithm,
            "variation_index": spec.variation_index,
            "random_state": spec.random_state,
            "model_name": spec.model_name,
            "params": _serialize_params(spec.params),
            "feature_columns": list(model.feature_columns),
            "n_features": len(model.feature_columns),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    return saved_paths


def _serialize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Serialize model params to JSON-safe types."""
    result = {}
    for k, v in params.items():
        if isinstance(v, (int, float, str, bool, type(None))):
            result[k] = v
        else:
            result[k] = str(v)
    return result


def train_and_save_ensemble(
    features: pd.DataFrame,
    home_target: str,
    away_target: str,
    output_dir: Path | str,
    algorithms: tuple[str, ...] = ("xgboost", "lightgbm", "randomforest", "ridge", "elasticnet"),
    ensemble_size: int = 30,
    sample_weight: pd.Series | None = None,
    random_state: int = 42,
    ensemble_seed_stride: int = 1,
) -> tuple[list[TrainedModels], list[EnsembleModelSpec], list[Path]]:
    """Train and persist the full ensemble for consensus evaluation."""

    models, specs = train_ensemble_models(
        features=features,
        home_target=home_target,
        away_target=away_target,
        algorithms=algorithms,
        ensemble_size=ensemble_size,
        sample_weight=sample_weight,
        random_state=random_state,
        ensemble_seed_stride=ensemble_seed_stride,
    )
    paths = save_ensemble_models(models=models, specs=specs, output_dir=output_dir)
    return models, specs, paths


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
    y_home: pd.Series,
    y_away: pd.Series,
) -> pd.Series:
    """Filter rows with valid targets.

    Feature NaNs are handled by deterministic median imputation per feature.
    """

    y_valid = y_home.notna() & y_away.notna()
    return y_valid


def _drop_unusable_feature_columns(
    x: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Drop feature columns that are entirely NaN in the training sample."""

    usable = [col for col in feature_cols if x[col].notna().any()]
    return x[usable].copy(), usable


def _is_allowed_feature(column: str, allowed_prefixes: tuple[str, ...] | None = None) -> bool:
    """Determine if a column should be included in training (dynamic feature selection).
    
    This function prevents data leakage by restricting to engineered, pre-match safe features
    that are inherently temporally valid (rolling stats, ratios, team identity, etc).
    
    Args:
        column: Feature column name to validate
        allowed_prefixes: Custom tuple of allowed prefixes/keywords; if None, uses defaults
        
    Returns:
        True if feature is safe to use in training, False otherwise
    """
    
    # Default engineered feature keywords (expandable via parameter)
    if allowed_prefixes is None:
        allowed_prefixes = (
            "_last",           # Rolling window features
            "_diff",           # Difference features
            "_team_enc",       # Team encoding features
            "_vs_",            # Matchup features
            "_ratio",          # Ratio features
            "_pressure",       # Pressure metrics
            "_total",          # Total count features
            "elo",             # ELO ratings
            "_rolling",        # Explicit rolling features
            "_momentum",       # Momentum metrics
        )
    
    # Direct features always allowed (static, non-leaking)
    direct_features = {"home_advantage", "is_home"}
    
    if column in direct_features:
        return True
    
    return any(key in column for key in allowed_prefixes)


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
            "n_jobs": -1,
            "verbosity": 0,
            "eval_metric": "poisson-nloglik",
        }
        params.update(overrides)
        return xgb.XGBRegressor(**params)

    if algo == "randomforest":
        params = {
            "criterion": "poisson",
            "n_estimators": 400,
            "max_depth": 10,
            "min_samples_leaf": 2,
            "max_features": 0.8,
            "random_state": random_state,
            "n_jobs": -1,
        }
        params.update(overrides)
        return RandomForestRegressor(**params)

    if algo == "ridge":
        params = {
            "alpha": 1.0,
            "random_state": random_state,
        }
        params.update(overrides)
        return Ridge(**params)

    if algo == "elasticnet":
        params = {
            "alpha": 0.1,
            "l1_ratio": 0.5,
            "max_iter": 10000,
            "random_state": random_state,
        }
        params.update(overrides)
        return ElasticNet(**params)

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
            "n_jobs": -1,
            "verbosity": -1,
        }
        params.update(overrides)
        return lgb.LGBMRegressor(**params)

    raise ValueError(
        f"Unsupported algorithm '{algorithm}'. "
        "Expected one of: xgboost, lightgbm, randomforest, ridge, elasticnet."
    )


def _normalize_algorithms(algorithms: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize configured algorithm names."""

    if not algorithms:
        return ("xgboost",)
    normalized = tuple(algo.strip().lower() for algo in algorithms if algo)
    return normalized if normalized else ("xgboost",)


def _build_ensemble_schedule(size: int, algorithms: tuple[str, ...]) -> list[str]:
    """Build deterministic and balanced algorithm schedule.
    
    For 30 models with hybrid mode enabled, will build 70% boosting + 30% linear
    using only the algorithms specified in the ``algorithms`` parameter.
    Otherwise maintains legacy balanced distribution.
    """

    if size <= 0:
        return ["xgboost"]
    
    # Hybrid mode for ~30 models — only if algorithms include both boosters and linear
    if size >= 25 and size <= 35:
        boosters = [a for a in algorithms if a in ("xgboost", "lightgbm")]
        linear = [a for a in algorithms if a in ("ridge", "elasticnet")]
        if boosters and linear:
            return _build_hybrid_ensemble_schedule(size, boosters, linear)
    
    algo_list = list(algorithms) if algorithms else ["xgboost"]

    # Keep exact balance whenever size is divisible by algorithm count.
    if size % len(algo_list) == 0:
        per_algorithm = size // len(algo_list)
        schedule: list[str] = []
        for _ in range(per_algorithm):
            for algorithm in algo_list:
                schedule.append(algorithm)
        return schedule

    schedule: list[str] = []
    idx = 0
    while len(schedule) < size:
        schedule.append(algo_list[idx % len(algo_list)])
        idx += 1
    return schedule


def _build_hybrid_ensemble_schedule(
    size: int,
    boosters: list[str] | None = None,
    linear: list[str] | None = None,
) -> list[str]:
    """Build 70% boosting + 30% linear hybrid schedule (e.g., 21 boosters + 9 linear for 30 models).
    
    This implements the experimental consensus architecture:
    - 70% Boosting algorithms (alternating from ``boosters`` list)
    - 30% Linear models (alternating from ``linear`` list)
    """
    if boosters is None:
        boosters = ["xgboost", "lightgbm"]
    if linear is None:
        linear = ["ridge", "elasticnet"]

    n_models = max(1, int(size))
    n_boosters = max(1, int(round(n_models * 0.70)))
    n_linear = n_models - n_boosters
    
    # Ensure at least 1 linear if more than 1 model
    if n_linear == 0 and n_models > 1:
        n_linear = 1
        n_boosters = n_models - 1
    
    schedule: list[str] = []
    
    # Boosters: alternate through provided booster algorithms
    for idx in range(n_boosters):
        schedule.append(boosters[idx % len(boosters)])
    
    # Linear: alternate through provided linear algorithms
    for idx in range(n_linear):
        schedule.append(linear[idx % len(linear)])
    
    return schedule



def build_variation_params(algorithm: str, variation_index: int) -> dict[str, Any]:
    """Generate deterministic hyperparameter variations (10 per algorithm)."""

    algo = algorithm.strip().lower()
    idx = variation_index % 10

    if algo == "xgboost":
        # Diversificacao guiada por seed/variacao:
        # 1) max_depth alterna especialistas/generalistas
        # 2) colsample_bytree varia combinacoes de estatisticas
        # 3) subsample varia fatias do historico
        rng = np.random.default_rng(10_000 + variation_index)
        return {
            "objective": "count:poisson",
            "n_estimators": 100,
            "learning_rate": 0.05,
            "max_depth": int(rng.choice([3, 4, 5, 6])),
            "subsample": float(rng.uniform(0.7, 0.9)),
            "colsample_bytree": float(rng.uniform(0.7, 0.9)),
            # Mantem leve variacao de regularizacao entre membros.
            "min_child_weight": [1, 2, 3, 1, 2, 3, 2, 1, 3, 2][idx],
        }

    if algo == "lightgbm":
        return {
            "objective": "poisson",
            "n_estimators": [300, 340, 380, 420, 460, 500, 540, 580, 620, 660][idx],
            "learning_rate": [0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.045, 0.04, 0.03, 0.02][idx],
            "num_leaves": [24, 28, 32, 36, 40, 30, 34, 38, 42, 46][idx],
            "subsample": [0.75, 0.83, 0.91, 0.79, 0.87, 0.95, 0.77, 0.85, 0.93, 0.81][idx],
            "colsample_bytree": [0.72, 0.78, 0.84, 0.90, 0.76, 0.82, 0.88, 0.74, 0.80, 0.86][idx],
        }

    if algo == "randomforest":
        return {
            "n_estimators": [250, 280, 310, 340, 370, 400, 430, 460, 490, 520][idx],
            "max_depth": [7, 8, 9, 10, 11, 12, 8, 9, 10, 11][idx],
            "min_samples_leaf": [1, 2, 3, 1, 2, 3, 1, 2, 3, 2][idx],
            "max_features": [0.55, 0.65, 0.75, 0.85, 0.60, 0.70, 0.80, 0.90, 0.58, 0.68][idx],
        }

    if algo == "ridge":
        # Ridge regression with variable alpha (regularization strength)
        return {
            "alpha": [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 0.02, 0.08, 2.0][idx],
            "solver": "auto",
            "max_iter": 10000,
        }

    if algo == "elasticnet":
        # ElasticNet with variable alpha and l1_ratio
        rng = np.random.default_rng(20_000 + variation_index)
        return {
            "alpha": [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 0.02, 0.08, 2.0][idx],
            "l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4, 0.6, 0.8, 0.5][idx],
            "max_iter": 20000,
        }

    return {}


def _build_model_filename(algorithm: str, variation_index: int) -> str:
    """Build standardized artifact name."""

    algo = algorithm.strip().lower()
    prefix_map = {
        "xgboost": "xgb",
        "lightgbm": "lgbm",
        "randomforest": "rf",
        "ridge": "ridge",
        "elasticnet": "elastic",
    }
    prefix = prefix_map.get(algo, algo)
    return f"{prefix}_model_{variation_index + 1}.pkl"
