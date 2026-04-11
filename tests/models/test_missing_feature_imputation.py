"""Regression tests for training/prediction with sparse features."""

from __future__ import annotations

import pandas as pd

from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import train_models


def _build_training_df(n_rows: int = 24) -> pd.DataFrame:
    rows = []
    for i in range(n_rows):
        rows.append(
            {
                "home_corners": float(5 + (i % 4)),
                "away_corners": float(4 + (i % 3)),
                "home_advantage": 1.0,
                "home_corners_for_last10": float(4 + (i % 5)) if i % 6 else None,
                "away_corners_for_last10": float(3 + (i % 4)),
                "home_elo_rating": 1500.0 + i,
                "away_elo_rating": 1490.0 + i,
                # Fully empty column should be dropped automatically.
                "home_shots_last10": None,
            }
        )
    return pd.DataFrame(rows)


def test_train_models_handles_missing_features_with_imputation() -> None:
    df = _build_training_df()
    trained = train_models(
        features=df,
        home_target="home_corners",
        away_target="away_corners",
        algorithm="ridge",
        random_state=42,
    )

    assert trained.feature_columns
    assert "home_shots_last10" not in trained.feature_columns
    assert trained.feature_fill_values is not None
    assert "home_corners_for_last10" in trained.feature_fill_values


def test_predict_expected_corners_uses_training_fill_values() -> None:
    train_df = _build_training_df()
    trained = train_models(
        features=train_df,
        home_target="home_corners",
        away_target="away_corners",
        algorithm="ridge",
        random_state=42,
    )

    predict_df = train_df.copy()
    predict_df.loc[[0, 1, 2], "home_corners_for_last10"] = None

    home_pred, away_pred = predict_expected_corners(trained, predict_df)
    assert len(home_pred) == len(predict_df)
    assert len(away_pred) == len(predict_df)
