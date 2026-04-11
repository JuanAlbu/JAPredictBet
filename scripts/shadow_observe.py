#!/usr/bin/env python
"""Shadow-mode observation script for the Gatekeeper Live Pipeline.

Usage
-----
    # Default: loads config.yml, models from artifacts/models/
    python scripts/shadow_observe.py

    # Custom config + models dir
    python scripts/shadow_observe.py --config config.yml --models-dir artifacts/models

    # Dry-run (collect + log, skip LLM calls)
    python scripts/shadow_observe.py --dry-run

Safety: This script is strictly observational.
        It never places real bets.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the src package is importable when running as a script.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

from japredictbet.config import PipelineConfig  # noqa: E402
from japredictbet.pipeline.gatekeeper_live_pipeline import (  # noqa: E402
    GatekeeperLivePipeline,
)

logger = logging.getLogger("shadow_observe")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gatekeeper Shadow-mode observation — collects odds, "
        "runs consensus, and evaluates via LLM (no real bets).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="Path to the pipeline config YAML (default: config.yml).",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("artifacts/models"),
        help="Directory containing trained .pkl model artifacts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect context and run consensus only — skip LLM calls.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Logging ──────────────────────────────────────────────────────
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Load .env for API keys ───────────────────────────────────────
    env_path = _ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded environment from %s", env_path)
    else:
        logger.info("No .env file found — using system environment variables.")

    # ── Config ───────────────────────────────────────────────────────
    config_path = args.config
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config = PipelineConfig.from_yaml(str(config_path))
    logger.info("Config loaded from %s", config_path)

    # ── Build pipeline ───────────────────────────────────────────────
    try:
        pipeline = GatekeeperLivePipeline.from_config(
            config=config,
            models_dir=args.models_dir,
        )
    except ValueError as exc:
        logger.error("Pipeline setup failed: %s", exc)
        sys.exit(1)

    # ── Run ──────────────────────────────────────────────────────────
    logger.info(
        "Starting shadow observation (dry_run=%s, models_dir=%s)...",
        args.dry_run,
        args.models_dir,
    )

    result = pipeline.run()

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SHADOW OBSERVATION SUMMARY")
    print("=" * 60)
    print(f"  Run at:            {result.run_at}")
    print(f"  Matches collected: {result.matches_collected}")
    print(f"  Matches evaluated: {result.matches_evaluated}")
    print(f"  Entries approved:  {result.entries_approved}")
    print("-" * 60)

    for entry in result.entries:
        status_icon = {
            "APPROVED": "✅",
            "NO BET": "❌",
            "FILTERED": "⛔",
            "CAPPED": "🔒",
            "ERROR": "⚠️",
        }.get(entry.gatekeeper_status or "", "❓")

        print(
            f"  {status_icon} {entry.home_team} vs {entry.away_team}"
            f"  | {entry.gatekeeper_status}"
            f"  | stake={entry.gatekeeper_stake}"
            f"  | consensus={entry.consensus_pct:.0%}"
            if entry.consensus_pct is not None
            else f"  {status_icon} {entry.home_team} vs {entry.away_team}"
            f"  | {entry.gatekeeper_status}"
            f"  | stake={entry.gatekeeper_stake}"
        )
        if entry.gatekeeper_justification:
            print(f"        → {entry.gatekeeper_justification}")

    if not result.entries:
        print("  (nenhum jogo coletado dentro da janela T-60)")

    print("=" * 60)
    shadow_path = (
        config.gatekeeper.shadow_log_path
        if config.gatekeeper
        else "logs/shadow_bets.log"
    )
    print(f"  Shadow log: {shadow_path}")
    print()


if __name__ == "__main__":
    main()
