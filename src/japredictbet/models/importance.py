"""Feature importance utilities."""

from __future__ import annotations

import pandas as pd

from .train import TrainedModels


def compute_feature_importance(models: TrainedModels) -> pd.DataFrame:
    """Compute gain-based feature importance for home and away models."""

    home_scores = models.home_model.get_booster().get_score(importance_type="gain")
    away_scores = models.away_model.get_booster().get_score(importance_type="gain")

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
