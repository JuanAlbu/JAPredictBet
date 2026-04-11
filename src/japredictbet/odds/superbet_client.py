"""Superbet SSE odds collector for Shadow Mode (P2-SHADOW).

Connects to the Superbet Server-Sent Events feed, parses football events
in real-time and extracts corner / match-odds / BTTS markets.

Technical notes
───────────────
* Superbet streams SSE lines: ``data:{json}\\nretry:N\\n``
* ``matchName`` uses middle-dot ``·`` (U+00B7) as team separator.
* ``sportId=5`` → football.  Feed mixes real, virtual and eSports.
* This module is **strictly observational** — no bets are placed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Optional, Sequence

import httpx

from japredictbet.config import SuperbetShadowConfig

logger = logging.getLogger(__name__)

_MIDDLE_DOT = "\u00b7"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ── Data models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SuperbetOdds:
    """A single market extracted from the Superbet feed."""

    event_id: str
    home_team: str
    away_team: str
    market_name: str
    market_line: Optional[float]
    over_odds: Optional[float]
    under_odds: Optional[float]
    home_odds: Optional[float]
    draw_odds: Optional[float]
    away_odds: Optional[float]
    yes_odds: Optional[float]
    no_odds: Optional[float]
    raw_event: Dict  # Keep the raw dict for debugging


@dataclass
class SuperbetSnapshot:
    """Aggregated odds snapshot for a single match."""

    event_id: str
    home_team: str
    away_team: str
    corners: List[SuperbetOdds] = field(default_factory=list)
    match_odds: List[SuperbetOdds] = field(default_factory=list)
    btts: List[SuperbetOdds] = field(default_factory=list)
    other: List[SuperbetOdds] = field(default_factory=list)


# ── SSE line parser ──────────────────────────────────────────────────


def _iter_sse_events(raw_lines: str) -> Generator[dict, None, None]:
    """Yield parsed JSON dicts from an SSE text chunk.

    Tolerant: malformed lines are logged and skipped.
    """
    for line in raw_lines.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:]  # strip "data:" prefix
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Malformed SSE JSON skipped: %.120s…", payload)


def _parse_team_names(match_name: str) -> tuple[str, str]:
    """Split ``matchName`` by middle-dot into (home, away)."""
    parts = match_name.split(_MIDDLE_DOT)
    if len(parts) != 2:
        raise ValueError(f"Cannot split matchName into 2 teams: {match_name!r}")
    return parts[0].strip(), parts[1].strip()


# ── Market extraction helpers ────────────────────────────────────────


def _is_corner_market(market_name: str, cfg: SuperbetShadowConfig) -> bool:
    return cfg.corner_market_name.lower() in market_name.lower()


def _is_match_odds_market(market_name: str) -> bool:
    lower = market_name.lower()
    return lower in ("resultado final", "1x2", "match result")


def _is_btts_market(market_name: str) -> bool:
    lower = market_name.lower()
    return "ambas" in lower or "btts" in lower or "both teams" in lower


def _extract_odds_from_selections(
    selections: Sequence[dict],
) -> Dict[str, Optional[float]]:
    """Map selection codes/names to a flat dict of odds values."""
    result: Dict[str, Optional[float]] = {}
    for sel in selections:
        code = str(sel.get("code", "")).lower()
        name = str(sel.get("name", "")).lower()
        price = sel.get("price")
        if price is not None:
            try:
                price = float(price)
            except (TypeError, ValueError):
                price = None

        if code in ("over", "mais") or "over" in name or "mais" in name:
            result["over"] = price
        elif code in ("under", "menos") or "under" in name or "menos" in name:
            result["under"] = price
        elif code in ("1", "home"):
            result["home"] = price
        elif code in ("x", "draw", "empate"):
            result["draw"] = price
        elif code in ("2", "away"):
            result["away"] = price
        elif code in ("yes", "sim"):
            result["yes"] = price
        elif code in ("no", "não", "nao"):
            result["no"] = price
    return result


# ── Core collector ───────────────────────────────────────────────────


class SuperbetCollector:
    """Connects to the Superbet SSE endpoint and collects football odds.

    Usage::

        cfg = SuperbetShadowConfig()
        collector = SuperbetCollector(cfg)
        snapshots = collector.fetch_today_odds()
    """

    def __init__(self, cfg: SuperbetShadowConfig) -> None:
        self._cfg = cfg
        self._timeout = httpx.Timeout(
            connect=cfg.connect_timeout_s,
            read=cfg.read_timeout_s,
            write=10.0,
            pool=10.0,
        )

    # ── public API ───────────────────────────────────────────────────

    def fetch_today_odds(
        self,
        team_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, SuperbetSnapshot]:
        """Fetch current Superbet feed and return snapshots keyed by event_id.

        Args:
            team_mapping: Optional ``{superbet_name: internal_id}`` dict.
                          Events with unmapped teams emit a WARNING and are skipped.

        Returns:
            Dict mapping ``event_id`` → :class:`SuperbetSnapshot`.
        """
        raw = self._fetch_sse_with_retry()
        return self._parse_events(raw, team_mapping)

    # ── SSE fetch with exponential backoff ───────────────────────────

    def _fetch_sse_with_retry(self) -> str:
        """GET the SSE endpoint with retry + exponential backoff."""
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._cfg.max_retries + 1):
            try:
                return self._do_request()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                wait = self._cfg.backoff_base_s ** attempt
                logger.warning(
                    "Superbet request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    self._cfg.max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise ConnectionError(
            f"Superbet SSE unreachable after {self._cfg.max_retries} attempts"
        ) from last_exc

    def _do_request(self) -> str:
        """Execute a single HTTP GET and return the raw SSE text."""
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/event-stream",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(self._cfg.sse_endpoint, headers=headers)
            resp.raise_for_status()
            return resp.text

    # ── Event parsing ────────────────────────────────────────────────

    def _parse_events(
        self,
        raw_sse: str,
        team_mapping: Optional[Dict[str, str]],
    ) -> Dict[str, SuperbetSnapshot]:
        """Parse raw SSE text into :class:`SuperbetSnapshot` objects."""
        snapshots: Dict[str, SuperbetSnapshot] = {}

        for event in _iter_sse_events(raw_sse):
            try:
                self._process_single_event(event, snapshots, team_mapping)
            except Exception:
                logger.debug("Skipping malformed event: %.200s", event, exc_info=True)

        logger.info(
            "Superbet feed parsed: %d football matches extracted.", len(snapshots)
        )
        return snapshots

    def _process_single_event(
        self,
        event: dict,
        snapshots: Dict[str, SuperbetSnapshot],
        team_mapping: Optional[Dict[str, str]],
    ) -> None:
        """Process one SSE JSON payload into the snapshots dict."""
        sport_id = event.get("sportId")
        if sport_id != self._cfg.sport_id:
            return  # Not football

        match_name: str = event.get("matchName", "")
        event_id: str = str(event.get("eventId", ""))
        if not match_name or not event_id:
            return

        try:
            home, away = _parse_team_names(match_name)
        except ValueError:
            logger.debug("Unparseable matchName: %s", match_name)
            return

        # Team mapping filter
        if team_mapping is not None:
            if home not in team_mapping and away not in team_mapping:
                logger.warning(
                    "Unmapped teams skipped: %s vs %s (event %s)", home, away, event_id
                )
                return

        if event_id not in snapshots:
            snapshots[event_id] = SuperbetSnapshot(
                event_id=event_id, home_team=home, away_team=away
            )
        snap = snapshots[event_id]

        for market in event.get("odds", []):
            market_name: str = market.get("marketName", "")
            if not market_name:
                continue

            selections = market.get("selections", market.get("outcomes", []))
            sel_odds = _extract_odds_from_selections(selections)

            raw_line: Optional[float] = None
            line_str = market.get("line") or market.get("specialBetValue")
            if line_str is not None:
                try:
                    raw_line = float(line_str)
                except (TypeError, ValueError):
                    pass

            odds_obj = SuperbetOdds(
                event_id=event_id,
                home_team=home,
                away_team=away,
                market_name=market_name,
                market_line=raw_line,
                over_odds=sel_odds.get("over"),
                under_odds=sel_odds.get("under"),
                home_odds=sel_odds.get("home"),
                draw_odds=sel_odds.get("draw"),
                away_odds=sel_odds.get("away"),
                yes_odds=sel_odds.get("yes"),
                no_odds=sel_odds.get("no"),
                raw_event=event,
            )

            if _is_corner_market(market_name, self._cfg):
                snap.corners.append(odds_obj)
            elif _is_match_odds_market(market_name):
                snap.match_odds.append(odds_obj)
            elif _is_btts_market(market_name):
                snap.btts.append(odds_obj)
            else:
                snap.other.append(odds_obj)
