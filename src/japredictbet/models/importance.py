"""Feature importance utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .train import TrainedModels


def _extract_scores(model: object, feature_columns: tuple[str, ...]) -> dict[str, float]:
    """Extract feature importance scores from any supported model type.

    Dispatch order:
    1. XGBoost  → gain from booster
    2. LightGBM → feature_importances_ (gain)
    3. Tree-based (RandomForest) → feature_importances_
    4. Linear (Ridge, ElasticNet) → abs(coef_)
    """
    model_type = type(model).__name__

    # XGBoost
    if hasattr(model, "get_booster"):
        raw = model.get_booster().get_score(importance_type="gain")
        return {k: float(v) for k, v in raw.items()}

    # LightGBM or tree-based ensemble
    if hasattr(model, "feature_importances_"):
        importances = np.asarray(model.feature_importances_, dtype=float)
        return dict(zip(feature_columns, importances))

    # Linear models (Ridge, ElasticNet, Lasso…)
    if hasattr(model, "coef_"):
        coefs = np.asarray(model.coef_, dtype=float)
        if coefs.ndim > 1:
            coefs = coefs.mean(axis=0)
        return dict(zip(feature_columns, np.abs(coefs)))

    raise TypeError(
        f"Model type '{model_type}' does not expose get_booster(), "
        "feature_importances_, or coef_. Cannot compute importance."
    )


def compute_feature_importance(models: TrainedModels) -> pd.DataFrame:
    """Compute feature importance for home and away models.

    Supports XGBoost, LightGBM, RandomForest, Ridge, and ElasticNet.
    """

    home_scores = _extract_scores(models.home_model, models.feature_columns)
    away_scores = _extract_scores(models.away_model, models.feature_columns)

    features = sorted(set(home_scores) | set(away_scores))
    rows = []
    for feature in features:
        rows.append(
            {
                "feature": feature,
                "home_gain": float(home_scores.get(feature, 0.0)),
                "away_gain": float(away_scores.get(feature, 0.0)),
            }
        )

    df = pd.DataFrame(rows)
    df["mean_gain"] = df[["home_gain", "away_gain"]].mean(axis=1)
    return df.sort_values("mean_gain", ascending=False).reset_index(drop=True)


def select_top_features(
    importance: pd.DataFrame,
    top_n: int | None = None,
    min_gain: float | None = None,
) -> list[str]:
    """Select features by top-N and/or minimum gain threshold."""

    df = importance.copy()
    if min_gain is not None:
        df = df[df["mean_gain"] >= min_gain]
    if top_n is not None:
        df = df.head(top_n)
    return df["feature"].tolist()
