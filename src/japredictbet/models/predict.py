"""Model inference helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .train import TrainedModels


def predict_expected_corners(
    models: TrainedModels,
    features: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Predict expected home and away corners.

    Uses the feature columns captured during training to align inputs.
    """

    if not models.feature_columns:
        raise ValueError("Trained models are missing feature columns metadata.")

    missing = [col for col in models.feature_columns if col not in features.columns]
    if missing:
        raise ValueError(f"Missing feature columns for prediction: {missing}")

    x = features[list(models.feature_columns)].copy()
    if models.feature_fill_values:
        x = x.fillna(models.feature_fill_values)
        home_pred = models.home_model.predict(x)  # type: ignore[attr-defined]
        away_pred = models.away_model.predict(x)  # type: ignore[attr-defined]

    home_series = pd.Series(
        np.clip(home_pred, 0, None),
        index=features.index,
        name="expected_home_corners",
    )
    away_series = pd.Series(
        np.clip(away_pred, 0, None),
        index=features.index,
        name="expected_away_corners",
    )

    return home_series, away_series
