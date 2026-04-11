#!/usr/bin/env python
"""Daily feature pre-computation script (Option C).

Loads all historical CSVs from ``data/raw/leagues/``, computes the
same rolling features used during training, and saves a lookup table
at ``artifacts/feature_store.parquet``.

Run once after downloading new CSVs from football-data.org:

    python scripts/refresh_features.py

Or with custom paths:

    python scripts/refresh_features.py \\
        --leagues-dir data/raw/leagues \\
        --output artifacts/feature_store.parquet \\
        --config config.yml

Schedule as a daily cron (after each matchday):

    # Windows Task Scheduler / Linux cron
    0 6 * * * python scripts/refresh_features.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from japredictbet.data.feature_store import FeatureStore  # noqa: E402
from japredictbet.config import PipelineConfig  # noqa: E402

logger = logging.getLogger("refresh_features")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-compute rolling team features from league CSVs.",
    )
    parser.add_argument(
        "--leagues-dir",
        type=Path,
        default=Path("data/raw/leagues"),
        help="Root folder with one sub-folder per league (default: data/raw/leagues).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/feature_store.parquet"),
        help="Output Parquet path (default: artifacts/feature_store.parquet).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="Pipeline config for rolling_windows, h2h_window, etc.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Load feature params from config if available
    rolling_windows = (10, 5)
    h2h_window = 3
    use_std = True
    use_ema = True
    drop_redundant = True

    if args.config.exists():
        try:
            config = PipelineConfig.from_yaml(str(args.config))
            rolling_windows = tuple(config.features.rolling_windows)
            h2h_window = config.features.h2h_window
            use_std = config.features.rolling_use_std
            use_ema = config.features.rolling_use_ema
            drop_redundant = config.features.drop_redundant
            logger.info(
                "Config loaded: windows=%s, h2h=%d, std=%s, ema=%s",
                rolling_windows, h2h_window, use_std, use_ema,
            )
        except Exception:
            logger.warning("Failed to load config — using defaults.", exc_info=True)
    else:
        logger.info("Config not found at '%s' — using defaults.", args.config)

    if not args.leagues_dir.exists():
        logger.error(
            "Leagues directory not found: '%s'\n"
            "Create it and place football-data.org CSVs inside:\n"
            "  data/raw/leagues/serie_a/2024-25.csv\n"
            "  data/raw/leagues/la_liga/2024-25.csv\n"
            "  ...",
            args.leagues_dir,
        )
        sys.exit(1)

    logger.info("Building FeatureStore from '%s' ...", args.leagues_dir)

    try:
        store = FeatureStore.build(
            leagues_dir=args.leagues_dir,
            rolling_windows=rolling_windows,
            h2h_window=h2h_window,
            use_std=use_std,
            use_ema=use_ema,
            drop_redundant=drop_redundant,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    store.save(args.output)

    print()
    print("=" * 60)
    print("FEATURE STORE BUILT")
    print("=" * 60)
    print(f"  Teams indexed : {len(store.known_teams())}")
    print(f"  Feature cols  : {len(store.table.columns)}")
    print(f"  Built at      : {store.built_at}")
    print(f"  Saved to      : {args.output}")
    print()
    print("Sample teams:")
    for t in sorted(store.known_teams())[:10]:
        print(f"  · {t}")
    if len(store.known_teams()) > 10:
        print(f"  ... and {len(store.known_teams()) - 10} more")
    print("=" * 60)


if __name__ == "__main__":
    main()
