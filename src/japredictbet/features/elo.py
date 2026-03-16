"""ELO-style team strength features."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EloConfig:
    """Configuration for Elo ratings."""

    base_rating: float = 1500.0
    k_factor: float = 20.0
    home_advantage: float = 50.0


def add_elo_ratings(
    df: pd.DataFrame,
    home_team_col: str,
    away_team_col: str,
    home_score_col: str,
    away_score_col: str,
    season_col: str,
    config: EloConfig | None = None,
) -> pd.DataFrame:
    """Add pre-match Elo ratings for home/away teams."""

    cfg = config or EloConfig()
    data = df.copy()
    data["home_elo_rating"] = pd.NA
    data["away_elo_rating"] = pd.NA
    data["elo_diff"] = pd.NA

    for season, group in data.groupby(season_col, sort=False):
        ratings: dict[str, float] = {}
        for idx, row in group.iterrows():
            home = row[home_team_col]
            away = row[away_team_col]
            home_rating = ratings.get(home, cfg.base_rating)
            away_rating = ratings.get(away, cfg.base_rating)

            data.at[idx, "home_elo_rating"] = home_rating
            data.at[idx, "away_elo_rating"] = away_rating
            data.at[idx, "elo_diff"] = home_rating - away_rating

            home_score = row[home_score_col]
            away_score = row[away_score_col]
            if pd.isna(home_score) or pd.isna(away_score):
                continue

            result = _result_from_score(float(home_score), float(away_score))
            expected_home = _expected_score(
                home_rating + cfg.home_advantage, away_rating
            )
            expected_away = 1.0 - expected_home

            ratings[home] = home_rating + cfg.k_factor * (result - expected_home)
            ratings[away] = away_rating + cfg.k_factor * ((1.0 - result) - expected_away)

    return data


def _expected_score(home_rating: float, away_rating: float) -> float:
    return 1.0 / (1.0 + 10 ** ((away_rating - home_rating) / 400.0))


def _result_from_score(home_score: float, away_score: float) -> float:
    if home_score > away_score:
        return 1.0
    if home_score < away_score:
        return 0.0
    return 0.5
