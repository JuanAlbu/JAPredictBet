"""P1.C1 — Auditable Hyperparameter Optimization via Optuna.

Usage:
    python scripts/hyperopt_search.py --config config.yml
    python scripts/hyperopt_search.py --config config.yml --algorithm xgboost --n-trials 100
    python scripts/hyperopt_search.py --config config.yml --algorithm all --n-trials 50

Outputs:
    artifacts/hyperopt/<algorithm>_best_params.json  — best parameters per algorithm
    artifacts/hyperopt/study_summary.json            — full study results

This script is READ-ONLY: it does NOT modify train.py or build_variation_params().
To apply optimized params, manually update _build_regressor() base params.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import optuna
from japredictbet.config import (
    DataConfig,
    FeatureConfig,
    ModelConfig,
    OddsConfig,
    PipelineConfig,
    ValueConfig,
)
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.models.train import (
    _build_regressor,
    _select_feature_columns,
    _valid_training_mask,
)
from japredictbet.pipeline.mvp_pipeline import (
    _add_rolling_ema_features,
    _add_rolling_stats,
    _add_rolling_std_features,
    _add_total_corners_features,
    _add_total_goals_features,
    _build_temporal_split,
    _ensure_season_column,
)
from japredictbet.features.matchup import add_h2h_features, add_matchup_features
from japredictbet.features.rolling import drop_redundant_features

optuna.logging.set_verbosity(optuna.logging.WARNING)

# ---------------------------------------------------------------------------
# Search spaces per algorithm
# ---------------------------------------------------------------------------

ALGORITHMS = ("xgboost", "lightgbm", "randomforest", "ridge", "elasticnet")


def _suggest_xgboost(trial: optuna.Trial) -> dict:
    return {
        "objective": "count:poisson",
        "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "subsample": trial.suggest_float("subsample", 0.6, 0.95),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.95),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 5),
        "gamma": trial.suggest_float("gamma", 0.0, 1.0),
    }


def _suggest_lightgbm(trial: optuna.Trial) -> dict:
    return {
        "objective": "poisson",
        "n_estimators": trial.suggest_int("n_estimators", 200, 800, step=20),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.12, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 16, 64),
        "subsample": trial.suggest_float("subsample", 0.6, 0.95),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.95),
    }


def _suggest_randomforest(trial: optuna.Trial) -> dict:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 200, 600, step=50),
        "max_depth": trial.suggest_int("max_depth", 5, 15),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 5),
        "max_features": trial.suggest_float("max_features", 0.4, 0.95),
    }


def _suggest_ridge(trial: optuna.Trial) -> dict:
    return {
        "alpha": trial.suggest_float("alpha", 0.001, 50.0, log=True),
    }


def _suggest_elasticnet(trial: optuna.Trial) -> dict:
    return {
        "alpha": trial.suggest_float("alpha", 0.001, 50.0, log=True),
        "l1_ratio": trial.suggest_float("l1_ratio", 0.05, 0.95),
        "max_iter": 20000,
    }


SUGGEST_FN = {
    "xgboost": _suggest_xgboost,
    "lightgbm": _suggest_lightgbm,
    "randomforest": _suggest_randomforest,
    "ridge": _suggest_ridge,
    "elasticnet": _suggest_elasticnet,
}


# ---------------------------------------------------------------------------
# Data preparation (mirrors mvp_pipeline feature engineering)
# ---------------------------------------------------------------------------


def _prepare_data(config: PipelineConfig) -> tuple[pd.DataFrame, pd.Series]:
    """Load data and apply feature engineering, return train slice + weights."""
    data = load_historical_dataset(config.data.raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)

    for window in config.features.rolling_windows:
        data = _add_rolling_stats(data, window, season_col="season")
        if config.features.rolling_use_std:
            data = _add_rolling_std_features(data, window, season_col="season")
        if config.features.rolling_use_ema:
            data = _add_rolling_ema_features(data, window, season_col="season")
        data = add_matchup_features(data, window=window)
        data = _add_total_corners_features(data, window=window)
        data = _add_total_goals_features(data, window=window)

    data = add_h2h_features(data, h2h_window=config.features.h2h_window)
    data["home_advantage"] = 1.0

    if config.features.drop_redundant:
        data = drop_redundant_features(data, config.features.rolling_windows)

    train_mask, _ = _build_temporal_split(data["season"], config.model.random_state)
    data = data.loc[train_mask].copy()

    feature_cols = _select_feature_columns(data, exclude=("home_corners", "away_corners"))
    if not feature_cols:
        raise RuntimeError("No feature columns after filtering.")

    x = data[feature_cols]
    y_home = data["home_corners"]
    y_away = data["away_corners"]
    mask = _valid_training_mask(x, y_home, y_away)
    data = data.loc[mask]

    return data, feature_cols


# ---------------------------------------------------------------------------
# Objective
# ---------------------------------------------------------------------------


def _poisson_deviance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Poisson deviance — lower is better."""
    y_pred = np.clip(y_pred, 1e-6, None)
    return float(np.mean(2 * (y_true * np.log(y_true / y_pred + 1e-12) - (y_true - y_pred))))


def _make_objective(
    algorithm: str,
    data: pd.DataFrame,
    feature_cols: list[str],
    home_target: str,
    away_target: str,
    n_folds: int,
    random_state: int,
):
    """Create an Optuna objective function for the given algorithm."""

    x = data[feature_cols].values
    y_home = data[home_target].values
    y_away = data[away_target].values
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)

    def objective(trial: optuna.Trial) -> float:
        params = SUGGEST_FN[algorithm](trial)
        deviances = []

        for train_idx, val_idx in kf.split(x):
            x_train, x_val = x[train_idx], x[val_idx]
            y_h_train, y_h_val = y_home[train_idx], y_home[val_idx]
            y_a_train, y_a_val = y_away[train_idx], y_away[val_idx]

            model_h = _build_regressor(algorithm, random_state, params)
            model_a = _build_regressor(algorithm, random_state, params)
            model_h.fit(x_train, y_h_train)
            model_a.fit(x_train, y_a_train)

            pred_h = np.clip(model_h.predict(x_val), 1e-6, None)
            pred_a = np.clip(model_a.predict(x_val), 1e-6, None)

            deviances.append(_poisson_deviance(y_h_val, pred_h))
            deviances.append(_poisson_deviance(y_a_val, pred_a))

        return float(np.mean(deviances))

    return objective


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_hyperopt(
    config: PipelineConfig,
    algorithms: list[str],
    n_trials: int,
    n_folds: int,
) -> dict:
    """Run Optuna hyperparameter search and return best params per algorithm."""
    print(f"[HyperOpt] Preparing data...")
    data, feature_cols = _prepare_data(config)
    print(f"[HyperOpt] Training data: {len(data)} rows, {len(feature_cols)} features")

    results = {}
    for algo in algorithms:
        print(f"\n[HyperOpt] Optimizing {algo} ({n_trials} trials, {n_folds}-fold CV)...")
        sampler = optuna.samplers.TPESampler(seed=config.model.random_state)
        study = optuna.create_study(direction="minimize", sampler=sampler)

        objective = _make_objective(
            algorithm=algo,
            data=data,
            feature_cols=feature_cols,
            home_target="home_corners",
            away_target="away_corners",
            n_folds=n_folds,
            random_state=config.model.random_state,
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        best = study.best_trial
        results[algo] = {
            "best_params": best.params,
            "best_value": best.value,
            "n_trials": n_trials,
            "n_folds": n_folds,
        }
        print(f"[HyperOpt] {algo} best Poisson deviance: {best.value:.6f}")
        print(f"[HyperOpt] {algo} best params: {json.dumps(best.params, indent=2)}")

    return results


def _save_results(results: dict, output_dir: Path) -> None:
    """Save hyperopt results to JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for algo, data in results.items():
        path = output_dir / f"{algo}_best_params.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[HyperOpt] Saved: {path}")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "algorithms": list(results.keys()),
        "results": results,
    }
    summary_path = output_dir / "study_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[HyperOpt] Summary saved: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P1.C1 Hyperparameter Optimization")
    parser.add_argument("--config", default="config.yml", help="Pipeline config path")
    parser.add_argument(
        "--algorithm",
        default="all",
        help="Algorithm to optimize (xgboost, lightgbm, randomforest, ridge, elasticnet, all)",
    )
    parser.add_argument("--n-trials", type=int, default=50, help="Number of Optuna trials per algorithm")
    parser.add_argument("--n-folds", type=int, default=5, help="CV folds")
    parser.add_argument("--output-dir", default="artifacts/hyperopt", help="Output directory")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    import yaml
    with open(args.config) as f:
        raw = yaml.safe_load(f)

    config = PipelineConfig(
        data=DataConfig(
            raw_path=Path(raw["data"]["raw_path"]),
            processed_path=Path(raw["data"]["processed_path"]),
            date_column=raw["data"].get("date_column", "date"),
        ),
        features=FeatureConfig(**raw["features"]),
        model=ModelConfig(**raw["model"]),
        odds=OddsConfig(**raw["odds"]),
        value=ValueConfig(**raw["value"]),
    )

    if args.algorithm == "all":
        algorithms = list(ALGORITHMS)
    else:
        algo = args.algorithm.strip().lower()
        if algo not in ALGORITHMS:
            print(f"Error: unknown algorithm '{algo}'. Choose from: {ALGORITHMS}")
            sys.exit(1)
        algorithms = [algo]

    results = run_hyperopt(config, algorithms, args.n_trials, args.n_folds)
    _save_results(results, Path(args.output_dir))


if __name__ == "__main__":
    main()
