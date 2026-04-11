"""Feature Store — daily pre-computation of rolling team features.

This module implements Option C of the live inference strategy:
instead of calling APIs at T-60 to build features, a daily cron job
loads all historical CSVs from ``data/raw/leagues/``, computes the
same rolling features used during training, and saves a lookup table
(Parquet) keyed by team name.

At T-60, ``GatekeeperLivePipeline._get_match_features()`` reads this
table to build a single-row feature DataFrame for each match — zero
live API calls required.

Folder convention
-----------------
``data/raw/leagues/<league_slug>/*.csv``

Each CSV follows the standard football-data.co.uk column names
(HC, AC, HS, AS, HF, AF, HY, AY, HR, AR, FTHG, FTAG, …).
Multi-season files can be named freely (e.g. ``2024-25.csv``).

Usage
-----
    store = FeatureStore.build(leagues_dir="data/raw/leagues")
    store.save("artifacts/feature_store.parquet")

    # Later, at T-60:
    store = FeatureStore.load("artifacts/feature_store.parquet")
    features = store.get_match_features("Arsenal", "Chelsea")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.rolling import (
    add_rolling_ema,
    add_rolling_std,
    add_result_rolling,
    add_stat_rolling,
    drop_redundant_features,
)
from japredictbet.features.matchup import add_h2h_features

logger = logging.getLogger(__name__)

# Rolling windows — must match what was used for training
_DEFAULT_WINDOWS: tuple[int, ...] = (10, 5)
_STAT_PAIRS: list[tuple[str, str, str]] = [
    ("home_corners", "away_corners", "corners"),
    ("home_shots", "away_shots", "shots"),
    ("home_fouls", "away_fouls", "fouls"),
    ("home_yellow_cards", "away_yellow_cards", "yellow_cards"),
    ("home_goals", "away_goals", "goals"),
]


# ── Feature Store ────────────────────────────────────────────────────


class FeatureStore:
    """Pre-computed rolling feature lookup table keyed by team name.

    The table holds the *most recent* feature snapshot for each team,
    ready for single-match inference.

    Attributes
    ----------
    table:
        DataFrame with one row per team. Index = team name (normalised).
        Columns = all rolling features computed during build.
    built_at:
        ISO timestamp when the store was last built.
    """

    def __init__(self, table: pd.DataFrame, built_at: str) -> None:
        self.table = table
        self.built_at = built_at

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        leagues_dir: str | Path = "data/raw/leagues",
        rolling_windows: Sequence[int] = _DEFAULT_WINDOWS,
        h2h_window: int = 3,
        use_std: bool = True,
        use_ema: bool = True,
        drop_redundant: bool = True,
    ) -> "FeatureStore":
        """Build the feature store from all league CSVs under *leagues_dir*.

        Parameters
        ----------
        leagues_dir:
            Root folder containing one sub-folder per league.
            Each sub-folder may contain multiple per-season CSVs.
        rolling_windows:
            Rolling window sizes to compute (must match training config).
        h2h_window:
            Number of past meetings to use for H2H features.
        use_std:
            Whether to compute rolling standard deviation features.
        use_ema:
            Whether to compute rolling EMA features.
        drop_redundant:
            Whether to drop correlated redundant features.
        """
        from datetime import datetime, timezone

        leagues_dir = Path(leagues_dir)
        dfs: list[pd.DataFrame] = []

        for league_dir in sorted(leagues_dir.iterdir()):
            if not league_dir.is_dir():
                continue
            csvs = sorted(league_dir.glob("*.csv"))
            if not csvs:
                logger.debug("No CSVs found in %s — skipping.", league_dir)
                continue
            league_slug = league_dir.name
            for csv_path in csvs:
                try:
                    df = load_historical_dataset(csv_path)
                    # Assign league tag without fragmentation warning
                    df = pd.concat(
                        [df, pd.Series([league_slug] * len(df), name="_league", index=df.index)],
                        axis=1,
                    )
                    dfs.append(df)
                    logger.debug(
                        "Loaded %d rows from %s", len(df), csv_path.relative_to(leagues_dir.parent)
                    )
                except Exception:
                    logger.warning(
                        "Failed to load %s — skipping.", csv_path, exc_info=True
                    )

        if not dfs:
            raise RuntimeError(
                f"No CSV data found under '{leagues_dir}'. "
                "Place football-data.org CSVs in data/raw/leagues/<league_slug>/*.csv"
            )

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.sort_values("date").reset_index(drop=True)
        logger.info(
            "Combined dataset: %d rows across %d league(s).",
            len(combined),
            len(dfs),
        )

        # Ensure season column exists
        if "season" not in combined.columns:
            combined = combined.copy()
            combined["season"] = combined["date"].dt.year

        # Feature engineering (same as mvp_pipeline.py)
        combined = _add_all_features(
            combined,
            rolling_windows=list(rolling_windows),
            h2h_window=h2h_window,
            use_std=use_std,
            use_ema=use_ema,
            drop_redundant=drop_redundant,
        )

        # Extract the most recent row per team
        table = _extract_latest_per_team(combined)
        built_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "FeatureStore built: %d teams | %d feature columns | at %s",
            len(table),
            len(table.columns),
            built_at,
        )
        return cls(table=table, built_at=built_at)

    # ── Persistence ───────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Persist the feature store to a Parquet file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only keep numeric columns — odds/string columns from raw CSV are
        # not model features and cause pyarrow type errors.
        numeric_table = self.table.select_dtypes(include="number")
        numeric_table.to_parquet(path, index=True)
        logger.info("FeatureStore saved → %s  (%d teams, %d numeric cols)",
                    path, len(numeric_table), len(numeric_table.columns))

    @classmethod
    def load(cls, path: str | Path) -> "FeatureStore":
        """Load a previously saved feature store from Parquet."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Feature store not found at '{path}'. "
                "Run 'python scripts/refresh_features.py' to build it."
            )
        table = pd.read_parquet(path)
        built_at = str(table.attrs.get("built_at", "unknown"))
        logger.info(
            "FeatureStore loaded from %s  (%d teams, built_at=%s)",
            path,
            len(table),
            built_at,
        )
        return cls(table=table, built_at=built_at)

    # ── Query API ────────────────────────────────────────────────────

    def get_match_features(
        self,
        home_team: str,
        away_team: str,
        fuzzy: bool = True,
    ) -> Optional[pd.DataFrame]:
        """Build a single-row feature DataFrame for inference.

        Combines the most recent home-team row (home_* features) with
        the most recent away-team row (away_* features).

        Parameters
        ----------
        home_team:
            Home team name as it appears in the Superbet feed.
        away_team:
            Away team name as it appears in the Superbet feed.
        fuzzy:
            If True, attempts fuzzy name matching when exact lookup
            fails (handles slight spelling differences between data
            sources).

        Returns
        -------
        Single-row DataFrame ready for ``predict_expected_corners``,
        or ``None`` if either team is not found.
        """
        home_row = self._lookup(home_team, fuzzy=fuzzy)
        away_row = self._lookup(away_team, fuzzy=fuzzy)

        if home_row is None:
            logger.warning("FeatureStore: team not found — '%s'", home_team)
            return None
        if away_row is None:
            logger.warning("FeatureStore: team not found — '%s'", away_team)
            return None

        # Rename columns: home_* keeps prefix; away_* columns that lack it
        # get it added. Columns that already have the right prefix are kept.
        home_features = _prefix_row(home_row, "home")
        away_features = _prefix_row(away_row, "away")

        combined = {**home_features, **away_features}
        combined["home_advantage"] = 1.0
        return pd.DataFrame([combined])

    def known_teams(self) -> List[str]:
        """Return the list of all team names in the store."""
        return list(self.table.index)

    # ── Internal helpers ─────────────────────────────────────────────

    def _lookup(self, team_name: str, fuzzy: bool) -> Optional[pd.Series]:
        """Return the feature row for *team_name*, or None."""
        key = _normalise_name(team_name)
        if key in self.table.index:
            return self.table.loc[key]

        if fuzzy:
            best_match, score = _fuzzy_match(key, list(self.table.index))
            if score >= 0.82:
                logger.debug(
                    "Fuzzy match: '%s' → '%s' (score=%.2f)", key, best_match, score
                )
                return self.table.loc[best_match]

        return None


# ── Feature engineering helpers ──────────────────────────────────────


def _add_all_features(
    df: pd.DataFrame,
    rolling_windows: list[int],
    h2h_window: int,
    use_std: bool,
    use_ema: bool,
    drop_redundant: bool,
) -> pd.DataFrame:
    """Apply the same feature pipeline as mvp_pipeline.py."""
    for window in rolling_windows:
        # Corners rolling mean
        df = add_stat_rolling(
            df, "home_team", "home_corners", "away_corners",
            window, "home", "corners",
        )
        df = add_stat_rolling(
            df, "away_team", "away_corners", "home_corners",
            window, "away", "corners",
        )

        # Other stats (shots, fouls, goals, cards) — only if column exists
        for home_col, away_col, stat_name in _STAT_PAIRS[1:]:  # skip corners, already done
            if home_col in df.columns and away_col in df.columns:
                df = add_stat_rolling(
                    df, "home_team", home_col, away_col,
                    window, "home", stat_name,
                )
                df = add_stat_rolling(
                    df, "away_team", away_col, home_col,
                    window, "away", stat_name,
                )

        # Results (wins, draws, losses, points)
        if "home_goals" in df.columns and "away_goals" in df.columns:
            df = add_result_rolling(
                df, "home_team", "home_goals", "away_goals",
                window, "home",
            )
            df = add_result_rolling(
                df, "away_team", "away_goals", "home_goals",
                window, "away",
            )

        # Rolling STD
        if use_std:
            df = add_rolling_std(
                df, "home_team", "home_corners", "away_corners",
                window, "home", "corners",
            )
            df = add_rolling_std(
                df, "away_team", "away_corners", "home_corners",
                window, "away", "corners",
            )

        # Rolling EMA
        if use_ema:
            df = add_rolling_ema(
                df, "home_team", "home_corners", "away_corners",
                window, "home", "corners",
            )
            df = add_rolling_ema(
                df, "away_team", "away_corners", "home_corners",
                window, "away", "corners",
            )

    # H2H features
    df = add_h2h_features(df, h2h_window=h2h_window)

    if drop_redundant:
        df = drop_redundant_features(df, rolling_windows)

    return df


def _extract_latest_per_team(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per team: the most recent feature snapshot.

    Uses vectorized pandas operations (no iterrows) for performance.
    """
    feature_cols = [
        c for c in df.columns
        if c not in ("date", "home_team", "away_team", "_league", "season",
                     "home_goals", "away_goals", "home_corners", "away_corners",
                     "home_shots", "away_shots", "home_fouls", "away_fouls",
                     "home_yellow_cards", "away_yellow_cards",
                     "home_red_cards", "away_red_cards",
                     "home_shots_on_target", "away_shots_on_target")
    ]

    # Build two views: one keyed by home_team, one by away_team,
    # both including the date for sorting. Then union and keep latest.
    home_view = df[["date", "home_team"] + feature_cols].copy()
    home_view = home_view.rename(columns={"home_team": "_team"})

    away_view = df[["date", "away_team"] + feature_cols].copy()
    away_view = away_view.rename(columns={"away_team": "_team"})

    combined = pd.concat([home_view, away_view], ignore_index=True)
    combined["_team_key"] = combined["_team"].str.strip().str.lower()

    # Keep only the most recent row per team (df is already sorted by date)
    latest = combined.sort_values("date").groupby("_team_key", sort=False).last()
    latest = latest.drop(columns=["date", "_team"], errors="ignore")
    latest.index.name = "team"
    return latest


def _prefix_row(row: pd.Series, side: str) -> Dict[str, float]:
    """Extract features for *side* from a combined-row Series.

    Columns starting with the correct side prefix are kept as-is.
    Columns with the opposite prefix are skipped.
    Columns with no prefix (e.g. h2h features) are included as-is.
    """
    opposite = "away" if side == "home" else "home"
    result: Dict[str, float] = {}
    for col, val in row.items():
        if isinstance(col, str):
            if col.startswith(opposite + "_"):
                continue
            result[col] = float(val) if pd.notna(val) else np.nan
    return result


def _normalise_name(name: str) -> str:
    """Return a lower-cased, stripped team name for stable key lookup."""
    return name.strip().lower()


def _fuzzy_match(
    query: str,
    candidates: list[str],
) -> tuple[str, float]:
    """Return the best fuzzy match and its similarity score (0–1)."""
    from difflib import SequenceMatcher

    best_name = ""
    best_score = 0.0
    for candidate in candidates:
        score = SequenceMatcher(None, query, candidate).ratio()
        if score > best_score:
            best_score = score
            best_name = candidate
    return best_name, best_score


# ── Tournament ID whitelist helper ───────────────────────────────────


def get_active_tournament_ids(
    leagues_dir: str | Path = "data/raw/leagues",
    mapping_path: str | Path = "data/mapping/league_tournament_ids.json",
) -> tuple[int, ...]:
    """Return Superbet tournamentIds for leagues that have historical CSV data.

    Scans *leagues_dir* for sub-folders that contain at least one ``.csv``
    file, looks each folder name up in *mapping_path*, and returns the
    matching tournament IDs.

    Folders without a mapping entry emit a DEBUG log and are skipped
    (e.g. ``premier_league`` while its Superbet ID is still unconfirmed).
    Folders with no CSVs are silently skipped.

    Parameters
    ----------
    leagues_dir:
        Root folder containing one sub-folder per league.
    mapping_path:
        JSON file mapping ``{folder_name: tournament_id}``.
        See ``data/mapping/league_tournament_ids.json``.

    Returns
    -------
    Tuple of integer tournamentIds — empty tuple means no filter (all
    leagues pass through, same as an unset whitelist).
    """
    leagues_dir = Path(leagues_dir)
    mapping_path = Path(mapping_path)

    if not mapping_path.exists():
        logger.warning(
            "League→tournamentId mapping not found at '%s'. "
            "Superbet tournament filter will be disabled.",
            mapping_path,
        )
        return ()

    with open(mapping_path, encoding="utf-8") as f:
        raw = json.load(f)
    # Strip comment keys (keys starting with "_")
    mapping: dict[str, int] = {
        k.strip().lower(): v for k, v in raw.items() if not k.startswith("_")
    }

    active_ids: list[int] = []
    folders_with_data: list[str] = []
    folders_no_mapping: list[str] = []

    if leagues_dir.exists():
        for folder in sorted(leagues_dir.iterdir()):
            if not folder.is_dir():
                continue
            has_csvs = any(folder.glob("*.csv"))
            if not has_csvs:
                continue
            slug = folder.name
            slug_key = slug.strip().lower()
            folders_with_data.append(slug)
            if slug_key in mapping:
                active_ids.append(mapping[slug_key])
            else:
                folders_no_mapping.append(slug)

    if folders_no_mapping:
        logger.debug(
            "League folders with CSVs but no Superbet tournamentId mapping: %s. "
            "Add entries to '%s' when IDs are confirmed via the SSE feed.",
            folders_no_mapping,
            mapping_path,
        )

    logger.info(
        "Active tournament filter: %d IDs from %d league folder(s) "
        "(%d folder(s) have no mapping yet: %s).",
        len(active_ids),
        len(folders_with_data),
        len(folders_no_mapping),
        folders_no_mapping or "none",
    )
    return tuple(active_ids)

