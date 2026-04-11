"""Pre-match odds loader — reads daily snapshots from the Superbet scraper.

The ``superbet_scraper.py`` script collects odds **before** matches start
and saves them as JSON files in ``data/odds/pre_match/YYYY-MM-DD.json``.

This module loads those snapshots and converts them into structured data
that the pipeline can consume directly as ``MatchContext`` objects or as
raw dicts for further processing.

Architecture
────────────
  superbet_scraper.py  →  data/odds/pre_match/YYYY-MM-DD.json  (pré-jogo)
  superbet_client.py   →  live SSE stream                       (in-play)
  pre_match_odds.py    →  reads the JSON → pipeline / agents
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from japredictbet.data.context_collector import MatchContext, OddsContext

logger = logging.getLogger(__name__)

# Default directory for daily pre-match snapshots
_DEFAULT_DIR = Path("data/odds/pre_match")


def _is_corner_market(name: str) -> bool:
    lower = name.lower()
    return "escanteio" in lower or "corners" in lower


def _is_match_odds_market(name: str) -> bool:
    lower = name.lower()
    return lower in ("resultado final", "1x2", "match result")


def _is_btts_market(name: str) -> bool:
    lower = name.lower()
    return "ambas" in lower or "btts" in lower or "both teams" in lower


def _extract_odds_context(markets: Dict[str, Dict[str, Any]]) -> OddsContext:
    """Convert a scraper markets dict into an OddsContext."""
    odds = OddsContext()

    for mname, m in markets.items():
        if _is_corner_market(mname):
            if odds.corner_line is None:
                odds.corner_line = m.get("line")
                odds.corner_over_odds = m.get("over")
                odds.corner_under_odds = m.get("under")
        elif _is_match_odds_market(mname):
            if odds.home_odds is None:
                odds.home_odds = m.get("home")
                odds.draw_odds = m.get("draw")
                odds.away_odds = m.get("away")
        elif _is_btts_market(mname):
            if odds.btts_yes is None:
                odds.btts_yes = m.get("yes")
                odds.btts_no = m.get("no")

    return odds


def load_pre_match_snapshot(
    date: Optional[str] = None,
    directory: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Load raw pre-match data for a given date.

    Parameters
    ----------
    date:
        ISO date string (YYYY-MM-DD).  Defaults to today.
    directory:
        Directory containing daily JSON files.
        Defaults to ``data/odds/pre_match/``.

    Returns
    -------
    List of event dicts as saved by the scraper.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    base_dir = directory or _DEFAULT_DIR
    path = base_dir / f"{target_date}.json"

    if not path.exists():
        logger.warning(
            "Pre-match snapshot not found: %s.  "
            "Run 'python scripts/superbet_scraper.py hoje' first.",
            path,
        )
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(
        "Loaded %d events from pre-match snapshot: %s", len(data), path
    )
    return data


def load_pre_match_contexts(
    date: Optional[str] = None,
    directory: Optional[Path] = None,
) -> List[MatchContext]:
    """Load pre-match data and convert to MatchContext objects.

    This is the main entry point for the pipeline — it reads the
    scraper's daily JSON and returns typed contexts ready for
    Gatekeeper + Analyst evaluation.

    Parameters
    ----------
    date:
        ISO date string (YYYY-MM-DD).  Defaults to today.
    directory:
        Directory containing daily JSON files.

    Returns
    -------
    List of ``MatchContext`` objects with odds populated.
    """
    raw = load_pre_match_snapshot(date=date, directory=directory)
    contexts: List[MatchContext] = []

    for event in raw:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        if not home or not away:
            continue

        markets = event.get("markets", {})
        odds_ctx = _extract_odds_context(markets)

        # Build kickoff UTC from date + time
        kickoff_utc = None
        ev_date = event.get("date")
        ev_time = event.get("kickoff")
        if ev_date and ev_time:
            try:
                kickoff_utc = f"{ev_date}T{ev_time}:00"
            except Exception:
                pass

        ctx = MatchContext(
            event_id=event.get("event_id", ""),
            home_team=home,
            away_team=away,
            kickoff_utc=kickoff_utc,
            league=event.get("league"),
            odds=odds_ctx,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
        contexts.append(ctx)

    logger.info(
        "Converted %d pre-match events to MatchContext objects.", len(contexts)
    )
    return contexts


def get_available_dates(directory: Optional[Path] = None) -> List[str]:
    """List all available pre-match snapshot dates."""
    base_dir = directory or _DEFAULT_DIR
    if not base_dir.exists():
        return []
    return sorted(
        p.stem for p in base_dir.glob("*.json") if p.stem[0].isdigit()
    )
