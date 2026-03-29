"""Dataset ingestion utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


REQUIRED_COLUMNS: Iterable[str] = (
    "date",
    "home_team",
    "away_team",
    "home_corners",
    "away_corners",
)

STANDARD_COLUMN_MAP = {
    # Common football-data.co.uk style columns
    "date": "date",
    "hometeam": "home_team",
    "awayteam": "away_team",
    "fthg": "home_goals",
    "ftag": "away_goals",
    "hc": "home_corners",
    "ac": "away_corners",
    # Alternate naming seen in other feeds
    "home": "home_team",
    "away": "away_team",
    "home_corners": "home_corners",
    "away_corners": "away_corners",
    # Match statistics (where available)
    "attendance": "attendance",
    "referee": "referee",
    "hs": "home_shots",
    "as": "away_shots",
    "hst": "home_shots_on_target",
    "ast": "away_shots_on_target",
    "hhw": "home_hit_woodwork",
    "ahw": "away_hit_woodwork",
    "hf": "home_fouls",
    "af": "away_fouls",
    "hfkc": "home_free_kicks_conceded",
    "afkc": "away_free_kicks_conceded",
    "ho": "home_offsides",
    "ao": "away_offsides",
    "hy": "home_yellow_cards",
    "ay": "away_yellow_cards",
    "hr": "home_red_cards",
    "ar": "away_red_cards",
    "hbp": "home_booking_points",
    "abp": "away_booking_points",
}

STAT_COLUMNS = {
    "attendance",
    "referee",
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_hit_woodwork",
    "away_hit_woodwork",
    "home_fouls",
    "away_fouls",
    "home_free_kicks_conceded",
    "away_free_kicks_conceded",
    "home_offsides",
    "away_offsides",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",
    "home_booking_points",
    "away_booking_points",
    "home_corners",
    "away_corners",
}

COMMON_STAT_COLUMNS = {
    "referee",
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_fouls",
    "away_fouls",
    "home_corners",
    "away_corners",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",
}


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to the project's required schema."""

    normalized = {col: col.strip().lower() for col in df.columns}
    renamed = {}
    for original, lowered in normalized.items():
        if lowered in STANDARD_COLUMN_MAP:
            renamed[original] = STANDARD_COLUMN_MAP[lowered]
    if renamed:
        df = df.rename(columns=renamed)
    drop_stats = [
        col
        for col in df.columns
        if col in STAT_COLUMNS and col not in COMMON_STAT_COLUMNS
    ]
    if drop_stats:
        df = df.drop(columns=drop_stats)
    return df


def load_historical_dataset(path: Path, date_column: str = "date") -> pd.DataFrame:
    """Load and validate the historical dataset.

    Args:
        path: Path to the dataset file (CSV or parquet).
        date_column: Column name containing the match date.

    Returns:
        Cleaned DataFrame sorted by date.
    """

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        raise ValueError("Unsupported dataset format. Use CSV or Parquet.")

    df = _standardize_columns(df)
    normalized_date_column = STANDARD_COLUMN_MAP.get(
        date_column.strip().lower(), date_column
    )

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df[normalized_date_column] = pd.to_datetime(
        df[normalized_date_column],
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )
    required_non_null_columns = sorted(set(REQUIRED_COLUMNS) | {normalized_date_column})
    df = df.dropna(subset=required_non_null_columns)
    df = df.sort_values(normalized_date_column).reset_index(drop=True)
    return df
