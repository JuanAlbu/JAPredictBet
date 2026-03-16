"""Team identity feature generation."""

from __future__ import annotations

import pandas as pd


def add_team_target_encoding(
    df: pd.DataFrame,
    team_col: str,
    target_col: str,
    train_mask: pd.Series,
    feature_name: str,
) -> pd.DataFrame:
    """Add target-encoded team feature using training data only."""

    df = df.copy()
    train_data = df.loc[train_mask]
    global_mean = train_data[target_col].mean()
    team_means = train_data.groupby(team_col)[target_col].mean()
    df[feature_name] = df[team_col].map(team_means).fillna(global_mean)
    return df
