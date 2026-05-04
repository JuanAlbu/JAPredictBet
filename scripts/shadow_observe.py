#!/usr/bin/env python
"""Shadow-mode observation script for the Gatekeeper Live Pipeline.

Supports two modes:
  1. Pre-match (primary): reads odds from scraper snapshot JSON
  2. Live T-60: connects to SSE feed for real-time monitoring

Usage
-----
    # Pre-match mode (recommended — run scraper first)
    python scripts/superbet_scraper.py hoje
    python scripts/shadow_observe.py --pre-match hoje

    # Pre-match with specific date
    python scripts/shadow_observe.py --pre-match 2026-04-12

    # Live T-60 mode (fallback)
    python scripts/shadow_observe.py

    # Custom config
    python scripts/shadow_observe.py --config config.yml

Safety: This script is strictly observational.
        It never places real bets.
"""

from __future__ import annotations

import argparse
import logging
import os
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
        "evaluates via LLM across all markets (no real bets).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="Path to the pipeline config YAML (default: config.yml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect context only — skip LLM calls.",
    )
    parser.add_argument(
        "--pre-match",
        type=str,
        default=None,
        metavar="DATE",
        help=(
            "Pre-match mode: load odds from scraper snapshot. "
            "Accepts: 'hoje', 'amanha', or YYYY-MM-DD. "
            "Run 'python scripts/superbet_scraper.py <dia>' first."
        ),
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
    _log_dir = _ROOT / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_file = _log_dir / "shadow_observe.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(_log_file, encoding="utf-8"),
        ],
    )

    # ── Load .env for API keys ───────────────────────────────────────
    env_path = _ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded environment from %s", env_path)
    else:
        logger.info("No .env file found — using system environment variables.")

    # ── Pre-flight checks ────────────────────────────────────────────
    has_llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not has_llm_key and not args.dry_run:
        logger.error(
            "LLM API key is not set.\n"
            "  1. Copy .env.example  →  .env\n"
            "  2. Set LLM_API_KEY (Groq/Gemini) ou OPENAI_API_KEY\n"
            "  3. Re-run this script.\n"
            "  (or use --dry-run to skip LLM calls)"
        )
        sys.exit(1)

    if not os.getenv("API_FOOTBALL_KEY"):
        logger.warning(
            "API_FOOTBALL_KEY not set — running in Superbet-only mode. "
            "Lineups, injuries and standings will not be fetched."
        )

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
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        logger.error("Pipeline setup failed: %s", exc)
        sys.exit(1)

    # ── Resolve pre-match date ─────────────────────────────────────
    pre_match_date = None
    if args.pre_match:
        from datetime import datetime, timedelta

        alias = args.pre_match.lower().strip()
        if alias in ("hoje", "today"):
            pre_match_date = datetime.now().strftime("%Y-%m-%d")
        elif alias in ("amanha", "amanhã", "tomorrow"):
            pre_match_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            pre_match_date = alias  # Assume YYYY-MM-DD

        logger.info("Pre-match mode: date=%s", pre_match_date)

    # ── Run ──────────────────────────────────────────────────────────
    mode = "pre-match" if pre_match_date else "live T-60"
    logger.info(
        "Starting shadow observation (mode=%s, dry_run=%s)...",
        mode,
        args.dry_run,
    )

    result = pipeline.run(pre_match_date=pre_match_date, dry_run=args.dry_run)

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SHADOW OBSERVATION SUMMARY")
    print("=" * 60)
    print(f"  Mode:              {mode}")
    print(f"  Run at:            {result.run_at}")
    print(f"  Matches collected: {result.matches_collected}")
    print(f"  Matches evaluated: {result.matches_evaluated}")
    print(f"  Entries approved:  {result.entries_approved}")
    print("-" * 60)

    for entry in result.entries:
        status_icon = {
            "APPROVED": "[OK]",
            "NO BET": "[NO]",
            "FILTERED": "[SKIP]",
            "CAPPED": "[CAP]",
            "ERROR": "[ERR]",
            "DRY_RUN": "[DRY]",
        }.get(entry.gatekeeper_status or "", "[?]")

        print(
            f"  {status_icon} {entry.home_team} vs {entry.away_team}"
            f"  | {entry.gatekeeper_status}"
            f"  | stake={entry.gatekeeper_stake}"
        )
        if entry.gatekeeper_justification:
            print(f"        -> {entry.gatekeeper_justification}")

        # Gatekeeper multi-market results
        if entry.gatekeeper_markets:
            print(
                f"        Mercados: {entry.gatekeeper_markets_approved}/"
                f"{entry.gatekeeper_markets_evaluated} aprovados"
            )
            for m in entry.gatekeeper_markets:
                if m.get("status") == "APPROVED":
                    print(
                        f"          [OK] {m.get('market')}"
                        f"  @ {m.get('odd')}"
                        f"  | stake={m.get('stake')}"
                        f"  | {m.get('classification', '')}"
                    )
                    if m.get("justification"):
                        print(f"               -> {m.get('justification')}")

    if not result.entries:
        print("  (nenhum jogo coletado dentro da janela)")

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
