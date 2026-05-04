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
from collections.abc import Generator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from japredictbet.config import SuperbetShadowConfig

logger = logging.getLogger(__name__)

_MIDDLE_DOT = "\u00b7"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# REST API endpoint for full event data (700+ markets vs SSE's ~3)
_REST_EVENT_URL = "https://production-superbet-offer-br.freetls.fastly.net/v2/pt-BR/events/{event_id}"


# ── Data models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SuperbetOdds:
    """A single market extracted from the Superbet feed."""

    event_id: str
    home_team: str
    away_team: str
    market_name: str
    market_line: float | None
    over_odds: float | None
    under_odds: float | None
    home_odds: float | None
    draw_odds: float | None
    away_odds: float | None
    yes_odds: float | None
    no_odds: float | None
    raw_event: dict  # Keep the raw dict for debugging


@dataclass
class SuperbetSnapshot:
    """Aggregated odds snapshot for a single match."""

    event_id: str
    home_team: str
    away_team: str
    match_name: str = ""
    corners: list[SuperbetOdds] = field(default_factory=list)
    match_odds: list[SuperbetOdds] = field(default_factory=list)
    btts: list[SuperbetOdds] = field(default_factory=list)
    other: list[SuperbetOdds] = field(default_factory=list)
    raw_event: dict = field(default_factory=dict)


# ── SSE line parser ──────────────────────────────────────────────────


def _iter_sse_events(raw_lines: str) -> Generator[dict, None, None]:
    """Yield the inner event dicts from an SSE text chunk.

    The Superbet feed wraps each event as::

        data:{"resourceId": "...", "timestamp": ..., "data": { <event> }}

    We unwrap the outer envelope and yield the ``data`` sub-object so the
    rest of the code can access ``sportId``, ``matchName``, etc. directly.
    Heartbeat lines (no ``data`` key or empty payload) are skipped.
    Malformed lines are logged and skipped.
    """
    for raw_line in raw_lines.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:]  # strip "data:" prefix
        try:
            outer = json.loads(payload)
            inner = outer.get("data")
            if inner and isinstance(inner, dict):
                yield inner
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
) -> dict[str, float | None]:
    """Map selection codes/names to a flat dict of odds values."""
    result: dict[str, float | None] = {}
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
        elif code in ("0", "x", "draw", "empate"):
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
        team_mapping: dict[str, str] | None = None,
    ) -> dict[str, SuperbetSnapshot]:
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
        last_exc: Exception | None = None

        for attempt in range(1, self._cfg.max_retries + 1):
            try:
                return self._do_request()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                wait = self._cfg.backoff_base_s**attempt
                logger.warning(
                    "Superbet request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    self._cfg.max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise ConnectionError(f"Superbet SSE unreachable after {self._cfg.max_retries} attempts") from last_exc

    def _do_request(self) -> str:
        """Stream the SSE endpoint for ``stream_duration_s`` seconds and
        return the accumulated lines as a single string.

        Using ``client.stream()`` instead of ``client.get()`` avoids blocking
        forever on a never-closing SSE connection.
        """
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/event-stream",
        }
        # Per-read chunk timeout — short so we can break on the deadline
        stream_timeout = httpx.Timeout(
            connect=self._cfg.connect_timeout_s,
            read=5.0,
            write=10.0,
            pool=10.0,
        )
        deadline = time.monotonic() + self._cfg.stream_duration_s
        lines: list[str] = []

        with httpx.Client(timeout=stream_timeout) as client:
            with client.stream("GET", self._cfg.sse_endpoint, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        lines.append(line)
                    if time.monotonic() >= deadline:
                        break

        logger.debug(
            "SSE stream collected %d lines over %.0fs.",
            len(lines),
            self._cfg.stream_duration_s,
        )
        return "\n".join(lines)

    # ── Event parsing ────────────────────────────────────────────────

    def _parse_events(
        self,
        raw_sse: str,
        team_mapping: dict[str, str] | None,
    ) -> dict[str, SuperbetSnapshot]:
        """Parse raw SSE text into :class:`SuperbetSnapshot` objects."""
        snapshots: dict[str, SuperbetSnapshot] = {}

        for event in _iter_sse_events(raw_sse):
            try:
                self._process_single_event(event, snapshots, team_mapping)
            except Exception:
                logger.debug("Skipping malformed event: %.200s", event, exc_info=True)

        logger.info("Superbet feed parsed: %d football matches extracted.", len(snapshots))
        return snapshots

    def _process_single_event(
        self,
        event: dict,
        snapshots: dict[str, SuperbetSnapshot],
        team_mapping: dict[str, str] | None,
    ) -> None:
        """Process one SSE JSON payload into the snapshots dict."""
        sport_id = event.get("sportId")
        if sport_id != self._cfg.sport_id:
            return  # Not football

        # Tournament whitelist filter (empty = no filter)
        tournament_id = event.get("tournamentId")
        if self._cfg.tournament_ids and tournament_id not in self._cfg.tournament_ids:
            return

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
        if team_mapping is not None and home not in team_mapping and away not in team_mapping:
            logger.warning("Unmapped teams skipped: %s vs %s (event %s)", home, away, event_id)
            return

        if event_id not in snapshots:
            snapshots[event_id] = SuperbetSnapshot(event_id=event_id, home_team=home, away_team=away)
        snap = snapshots[event_id]

        # The Superbet feed sends a FLAT list of individual selection objects
        # under event["odds"], each with an embedded "marketName" and "code".
        # We group them by marketName first, then extract odds per group.
        from collections import defaultdict

        markets_raw: dict = defaultdict(list)
        for sel in event.get("odds", []):
            mn = sel.get("marketName", "")
            if mn:
                markets_raw[mn].append(sel)

        for market_name, selections in markets_raw.items():
            sel_odds = _extract_odds_from_selections(selections)

            # Try to get the line value from showSpecialBetValue / specialBetValue
            raw_line: float | None = None
            for sel in selections:
                line_str = sel.get("showSpecialBetValue") or sel.get("specialBetValue")
                if line_str and str(line_str) not in ("0", ""):
                    try:
                        raw_line = float(line_str)
                        break
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

    # ── REST API enrichment (full markets, not just SSE ~3) ──────────

    def fetch_full_event(self, event_id: str) -> dict[str, Any] | None:
        """Fetch full event data (all 700+ markets) from the REST API.

        Uses: GET /v2/pt-BR/events/{eventId}

        Returns the first event dict with full odds, or ``None`` on error.
        This is a clean extraction of the logic from ``scripts/superbet_scraper.py``
        so the live pipeline can access complete market data (P2-SH13).
        """
        url = _REST_EVENT_URL.format(event_id=event_id)
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Origin": "https://superbet.bet.br",
            "Referer": "https://superbet.bet.br/",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, headers=headers)
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    logger.warning("REST API error for event %s: %s", event_id, data)
                    return None
                events = data.get("data", [])
                if events:
                    return events[0]
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            logger.warning("Failed to fetch event %s: %s", event_id, exc)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Malformed response for event %s: %s", event_id, exc)
        return None

    def enrich_snapshots_with_rest(
        self,
        snapshots: dict[str, SuperbetSnapshot],
    ) -> dict[str, SuperbetSnapshot]:
        """Enrich SSE snapshots with full market data from the REST API.

        For each snapshot, fetches the REST ``/v2/pt-BR/events/{eventId}`` endpoint
        and rebuilds all market groups (corners, match_odds, btts, other) from the
        complete REST response.  SSE data is replaced where REST is available.

        Args:
            snapshots: Dict of ``event_id`` → :class:`SuperbetSnapshot` from SSE.

        Returns:
            The same dict with enriched snapshots (SSE fallback where REST fails).
        """
        from collections import defaultdict

        enriched_count = 0
        for event_id, snap in snapshots.items():
            full_event = self.fetch_full_event(event_id)
            if full_event is None:
                continue  # Keep SSE data as fallback

            # Parse REST odds grouped by marketName
            markets_raw: dict[str, list] = defaultdict(list)
            for sel in full_event.get("odds") or []:
                mn = sel.get("marketName", "")
                if mn:
                    markets_raw[mn].append(sel)

            # Clear SSE data — will rebuild from REST
            snap.corners.clear()
            snap.match_odds.clear()
            snap.btts.clear()
            snap.other.clear()
            snap.raw_event = full_event  # Preserve full REST payload

            for market_name, selections in markets_raw.items():
                sel_odds = _extract_odds_from_selections(selections)

                # REST API uses centesimal pricing (e.g. 150 → 1.50)
                for key in ("over", "under", "home", "draw", "away", "yes", "no"):
                    val = sel_odds.get(key)
                    if val is not None and val >= 100:
                        sel_odds[key] = val / 100.0

                # Try to get the line value
                raw_line: float | None = None
                for sel in selections:
                    line_str = sel.get("showSpecialBetValue") or sel.get("specialBetValue")
                    if line_str and str(line_str) not in ("0", ""):
                        try:
                            raw_line = float(line_str)
                            break
                        except (TypeError, ValueError):
                            pass

                odds_obj = SuperbetOdds(
                    event_id=event_id,
                    home_team=snap.home_team,
                    away_team=snap.away_team,
                    market_name=market_name,
                    market_line=raw_line,
                    over_odds=sel_odds.get("over"),
                    under_odds=sel_odds.get("under"),
                    home_odds=sel_odds.get("home"),
                    draw_odds=sel_odds.get("draw"),
                    away_odds=sel_odds.get("away"),
                    yes_odds=sel_odds.get("yes"),
                    no_odds=sel_odds.get("no"),
                    raw_event=full_event,
                )

                if _is_corner_market(market_name, self._cfg):
                    snap.corners.append(odds_obj)
                elif _is_match_odds_market(market_name):
                    snap.match_odds.append(odds_obj)
                elif _is_btts_market(market_name):
                    snap.btts.append(odds_obj)
                else:
                    snap.other.append(odds_obj)

            enriched_count += 1

        logger.info(
            "REST enrichment: %d/%d snapshots enriched with full market data.",
            enriched_count,
            len(snapshots),
        )
        return snapshots
