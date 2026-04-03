"""SHAP-based model quality weights for ensemble consensus (P1.C2).

Computes SHAP importance per ensemble member and derives quality-based
weights for weighted consensus voting.

Usage:
    weights = compute_model_weights(ensemble_models, X_sample)
    # Pass weights to ConsensusEngine.evaluate_with_consensus(model_weights=weights)
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

try:
    import shap
except ImportError:  # pragma: no cover
    shap = None

from .train import TrainedModels

logger = logging.getLogger(__name__)


def compute_shap_importance(
    model: object,
    x_sample: pd.DataFrame,
) -> np.ndarray:
    """Compute mean |SHAP values| for a single model.

    Args:
        model: Trained model (XGBoost, LightGBM, RF, Ridge, ElasticNet).
        x_sample: Feature matrix (sample of training data).

    Returns:
        Array of mean absolute SHAP values per feature, shape (n_features,).
    """
    if shap is None:
        raise ImportError("shap is required for SHAP-based weights. pip install shap")

    model_type = type(model).__name__

    if hasattr(model, "get_booster"):
        # XGBoost — use TreeExplainer
        explainer = shap.TreeExplainer(model)
    elif model_type == "LGBMRegressor":
        explainer = shap.TreeExplainer(model)
    elif hasattr(model, "estimators_"):
        # RandomForest
        explainer = shap.TreeExplainer(model)
    elif hasattr(model, "coef_"):
        # Linear models (Ridge, ElasticNet)
        explainer = shap.LinearExplainer(model, x_sample)
    else:
        raise TypeError(f"Unsupported model type: {model_type}")

    shap_values = explainer.shap_values(x_sample)
    return np.abs(shap_values).mean(axis=0)


def compute_model_weights(
    ensemble_models: Sequence[TrainedModels],
    x_sample: pd.DataFrame,
    normalize: bool = True,
) -> list[float]:
    """Compute quality-based weights for each ensemble member using SHAP.

    Each model's weight is proportional to its mean total SHAP importance,
    reflecting how effectively it uses features.

    Args:
        ensemble_models: List of TrainedModels in ensemble order.
        x_sample: Feature matrix sample for SHAP computation.
        normalize: If True, normalize weights to sum to 1.

    Returns:
        List of weights (one per ensemble member), same order as input.
    """
    weights = []

    for idx, models in enumerate(ensemble_models):
        # Use features available for this specific model
        model_features = [c for c in models.feature_columns if c in x_sample.columns]
        x_model = x_sample[model_features]

        try:
            home_shap = compute_shap_importance(models.home_model, x_model)
            away_shap = compute_shap_importance(models.away_model, x_model)
            # Model quality = average total SHAP importance
            quality = float((home_shap.sum() + away_shap.sum()) / 2.0)
        except Exception as e:
            logger.warning("SHAP computation failed for model %d: %s. Using weight=1.0", idx, e)
            quality = 1.0

        weights.append(quality)

    if normalize and weights:
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

    return weights


def compute_ensemble_feature_importance(
    ensemble_models: Sequence[TrainedModels],
    x_sample: pd.DataFrame,
) -> pd.DataFrame:
    """Compute aggregated SHAP feature importance across the ensemble.

    Returns a DataFrame with columns: feature, mean_shap, std_shap, n_models.
    Useful for populating FEATURE_IMPORTANCE_GUIDE.md.
    """
    all_importances: dict[str, list[float]] = {}

    for models in ensemble_models:
        model_features = [c for c in models.feature_columns if c in x_sample.columns]
        x_model = x_sample[model_features]

        try:
            home_shap = compute_shap_importance(models.home_model, x_model)
            away_shap = compute_shap_importance(models.away_model, x_model)
            combined = (home_shap + away_shap) / 2.0

            for feat, val in zip(model_features, combined):
                all_importances.setdefault(feat, []).append(float(val))
        except Exception:
            continue

    rows = []
    for feat, values in all_importances.items():
        rows.append({
            "feature": feat,
            "mean_shap": float(np.mean(values)),
            "std_shap": float(np.std(values)),
            "n_models": len(values),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("mean_shap", ascending=False).reset_index(drop=True)
    return df
