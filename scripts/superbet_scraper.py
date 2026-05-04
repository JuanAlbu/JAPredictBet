"""Superbet odds scraper — fetch pre-match odds by day from the SSE feed.

This is the **primary** odds collector for the JAPredictBet pipeline.
It runs BEFORE match day (or early on match day) to capture baseline odds
for all markets (corners, 1x2, BTTS, etc.).

The live SSE client (``superbet_client.py``) is used separately to
**monitor odds movements** during matches.

Architecture:
    superbet_scraper.py  →  pre-match snapshot (JSON)  →  pipeline reads it
    superbet_client.py   →  live SSE stream (in-play)  →  movement alerts

Maps the Superbet website URL pattern to SSE feed filtering:
    https://superbet.bet.br/apostas/futebol/domingo  →  Sunday's matches

Usage:
    python scripts/superbet_scraper.py domingo
    python scripts/superbet_scraper.py hoje
    python scripts/superbet_scraper.py amanha
    python scripts/superbet_scraper.py 2026-04-13
    python scripts/superbet_scraper.py domingo --leagues brasileirao serie_a
    python scripts/superbet_scraper.py domingo --stream-seconds 60
    python scripts/superbet_scraper.py domingo --json output.json
    python scripts/superbet_scraper.py domingo --debug

Output:
    By default, saves a daily JSON snapshot to:
        data/odds/pre_match/YYYY-MM-DD.json

This is **strictly an analytics tool** — no bets are placed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

# ── Paths ────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
MAPPING_DIR = ROOT / "data" / "mapping"
LEAGUE_IDS_PATH = MAPPING_DIR / "league_tournament_ids.json"
TEAM_MAPPING_PATH = MAPPING_DIR / "superbet_teams.json"
PRE_MATCH_DIR = ROOT / "data" / "odds" / "pre_match"

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

SSE_ENDPOINT = "https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/all"
SSE_ENDPOINT_PREMATCH = "https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/prematch"
REST_EVENT_URL = "https://production-superbet-offer-br.freetls.fastly.net/v2/pt-BR/events/{event_id}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
MIDDLE_DOT = "\u00b7"
SPORT_ID_FOOTBALL = 5

# ── Day name → date mapping ─────────────────────────────────────────

DAY_NAMES_PT = {
    "domingo": 6,  # Sunday
    "segunda": 0,  # Monday
    "terca": 1,
    "terça": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "sábado": 5,
}

ALIASES = {
    "hoje": "today",
    "amanha": "tomorrow",
    "amanhã": "tomorrow",
    "today": "today",
    "tomorrow": "tomorrow",
    "todos": "all",
    "all": "all",
}


def _resolve_target_date(day_str: str) -> str | None:
    """Convert a day name or alias to ISO date string (YYYY-MM-DD).

    Returns None for 'all' (no date filter).
    """
    day_lower = day_str.lower().strip()

    if day_lower in ALIASES:
        alias = ALIASES[day_lower]
        if alias == "today":
            return datetime.now().strftime("%Y-%m-%d")
        elif alias == "tomorrow":
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif alias == "all":
            return None

    if day_lower in DAY_NAMES_PT:
        target_weekday = DAY_NAMES_PT[day_lower]
        today = datetime.now()
        days_ahead = target_weekday - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        # If days_ahead == 0, the target day is today — show today's matches
        target = today + timedelta(days=days_ahead)
        return target.strftime("%Y-%m-%d")

    # Try parsing as ISO date directly
    try:
        datetime.strptime(day_lower, "%Y-%m-%d")
        return day_lower
    except ValueError:
        pass

    raise ValueError(
        f"Dia não reconhecido: '{day_str}'. Use: hoje, amanha, domingo, segunda, ..., sabado, todos, ou YYYY-MM-DD"
    )


# ── Load mappings ────────────────────────────────────────────────────


def _load_league_ids() -> dict[str, int]:
    """Load league folder name → tournament ID mapping."""
    if not LEAGUE_IDS_PATH.exists():
        logger.warning("League IDs file not found: %s", LEAGUE_IDS_PATH)
        return {}
    with open(LEAGUE_IDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # Filter out comments/metadata keys
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _load_team_mapping() -> dict[str, str]:
    """Load Superbet team name → canonical name mapping (flat)."""
    if not TEAM_MAPPING_PATH.exists():
        logger.warning("Team mapping file not found: %s", TEAM_MAPPING_PATH)
        return {}
    with open(TEAM_MAPPING_PATH, encoding="utf-8") as f:
        data = json.load(f)
    flat: dict[str, str] = {}
    for league_key, teams in data.items():
        if league_key.startswith("_"):
            continue
        if isinstance(teams, dict):
            flat.update(teams)
    return flat


# ── SSE streaming ────────────────────────────────────────────────────


def _stream_sse(
    duration_s: float = 45.0,
    tournament_ids: set | None = None,
    use_prematch: bool = False,
) -> list[dict[str, Any]]:
    """Stream SSE feed and collect football events.

    Args:
        use_prematch: If True, uses the prematch endpoint (future events).
                      If False, uses the all/live endpoint.

    Returns list of raw event dicts that pass sport + tournament filters.

    Hardening (P2-SH13.B):
    - Tracks HTTP response status vs zero-events to aid diagnostics.
    - Returns ``None`` when the connection fails entirely (transport error
      before any data), vs. an empty list when 200 OK but no events arrived.
    """
    endpoint = SSE_ENDPOINT_PREMATCH if use_prematch else SSE_ENDPOINT
    headers = {"User-Agent": USER_AGENT, "Accept": "text/event-stream"}
    timeout = httpx.Timeout(connect=10.0, read=12.0, write=10.0, pool=10.0)

    events: dict[str, dict[str, Any]] = {}
    deadline = time.monotonic() + duration_s
    lines_read = 0
    connection_succeeded = False

    logger.info(
        "Conectando ao feed SSE Superbet %s (%.0fs)...",
        "PREMATCH" if use_prematch else "LIVE/ALL",
        duration_s,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("GET", endpoint, headers=headers) as resp:
                resp.raise_for_status()
                connection_succeeded = True
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    lines_read += 1
                    try:
                        outer = json.loads(line[5:])
                        inner = outer.get("data")
                        if not inner or not isinstance(inner, dict):
                            continue
                    except json.JSONDecodeError:
                        continue

                    if inner.get("sportId") != SPORT_ID_FOOTBALL:
                        continue

                    tid = inner.get("tournamentId")
                    if tournament_ids and tid not in tournament_ids:
                        continue

                    eid = str(inner.get("eventId", ""))
                    if eid:
                        events[eid] = inner

                    if time.monotonic() >= deadline:
                        break
    except (httpx.HTTPStatusError, httpx.TransportError) as exc:
        if events:
            logger.warning(
                "SSE interrompido (%s), preservando %d eventos coletados.",
                exc,
                len(events),
            )
        else:
            logger.warning("Erro na conexão SSE: %s", exc)

    if connection_succeeded and lines_read == 0:
        logger.warning(
            "SSE conectou (200 OK) mas nenhuma linha recebida em %.0fs. "
            "O feed pode estar vazio ou o timeout muito curto.",
            duration_s,
        )
    elif connection_succeeded and events:
        logger.info(
            "SSE: %d linhas lidas, %d eventos de futebol coletados.",
            lines_read,
            len(events),
        )

    # Signal "connection failed entirely" vs "empty response"
    if not connection_succeeded and not events:
        return None  # Transport error — distinct from empty but connected
    return list(events.values())


def _collect_raw_events_with_fallback(
    target_date: str | None,
    tournament_filter: set[int],
    stream_seconds: float,
) -> list[dict[str, Any]]:
    """Collect SSE events with broader fallback strategies when needed.

    Hardening (P2-SH13.B):
    - ``_stream_sse`` now returns ``None`` on transport error vs ``[]`` on empty.
    - Falls back to a long-duration SSE stream (2× duration) when all
      standard attempts return empty.
    - Checks for existing ``data/odds/pre_match/{target_date}.json`` as
      a last-resort cache fallback.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    use_prematch = target_date is not None and target_date > today_str

    if target_date is None:
        logger.info("Coletando eventos LIVE + PREMATCH...")
        raw_live = _stream_sse(
            duration_s=stream_seconds,
            tournament_ids=tournament_filter,
            use_prematch=False,
        )
        raw_pre = _stream_sse(
            duration_s=stream_seconds,
            tournament_ids=tournament_filter,
            use_prematch=True,
        )
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for ev in (raw_live or []) + (raw_pre or []):
            eid = str(ev.get("eventId", ""))
            if eid and eid not in seen:
                seen.add(eid)
                merged.append(ev)
        return merged

    attempts: list[tuple[str, bool, set[int] | None]] = [
        ("endpoint principal + filtro de torneios", use_prematch, tournament_filter),
    ]

    if use_prematch:
        attempts.extend(
            [
                ("endpoint ALL + filtro de torneios", False, tournament_filter),
                ("endpoint PREMATCH sem filtro de torneios", True, None),
                ("endpoint ALL sem filtro de torneios", False, None),
            ]
        )
    else:
        attempts.append(("endpoint atual sem filtro de torneios", use_prematch, None))

    all_failed = True  # Track if ALL attempts were transport errors
    for label, prematch_flag, tournament_ids in attempts:
        logger.info("Tentativa SSE fallback: %s", label)
        raw_events = _stream_sse(
            duration_s=stream_seconds,
            tournament_ids=tournament_ids,
            use_prematch=prematch_flag,
        )

        # None = transport error (connection never established)
        if raw_events is None:
            logger.warning("Falha de conexão na tentativa: %s", label)
            continue

        # Empty list = 200 OK but 0 events — keep trying
        if not raw_events:
            logger.info("Tentativa sem eventos: %s", label)
            continue

        all_failed = False

        if target_date is not None:
            matching_events = [ev for ev in raw_events if _extract_event_date(ev) == target_date]
            undated_events = [ev for ev in raw_events if _extract_event_date(ev) is None]
            if not matching_events and not undated_events:
                dates_found = sorted({ev_date for ev_date in (_extract_event_date(ev) for ev in raw_events) if ev_date})
                logger.info(
                    "Tentativa sem eventos da data alvo (%s). Datas vistas: %s",
                    target_date,
                    ", ".join(dates_found) if dates_found else "nenhuma",
                )
                continue

        logger.info(
            "Tentativa bem-sucedida: %s (%d eventos brutos).",
            label,
            len(raw_events),
        )
        return raw_events

    # ── Final long-duration last resort ──────────────────────────────
    if all_failed:
        logger.warning(
            "Todas as tentativas SSE falharam por erro de conexão. Tentando stream longo (%.0fs) como último recurso…",
            stream_seconds * 2,
        )
        final_events = _stream_sse(
            duration_s=stream_seconds * 2,
            tournament_ids=tournament_filter,
            use_prematch=use_prematch,
        )
        if final_events:
            logger.info("Stream longo recuperou %d eventos.", len(final_events))
            return final_events

    # ── Cache fallback ───────────────────────────────────────────────
    if target_date is not None:
        cache_path = PRE_MATCH_DIR / f"{target_date}.json"
        if cache_path.exists():
            logger.warning(
                "SSE não retornou eventos. Usando cache existente: %s",
                cache_path,
            )
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cached = json.load(f)
                if cached:
                    logger.info(
                        "Cache fallback: %d eventos carregados de %s.",
                        len(cached),
                        cache_path,
                    )
                    return cached
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Cache corrompido ou ilegível: %s", exc)

    return []


# ── REST API per-event (full markets) ────────────────────────────────

# Markets we want to display (lowercase substrings for matching)
MARKETS_OF_INTEREST = [
    "resultado final",
    "total de gols",
    "dupla chance",
    "ambas as equipes marcam",
    "total de gols",
    "1º tempo - total de gols",
    "total de gols da equipe",
    "total de escanteios",
    "total de escanteios da equipe",
    "total de cartões",
    "total de finalizações",
    "total de finalizações da equipe",
    "total de chutes no gol",
    "total de faltas",
    "handicap",
]

# Player-level markets (keywords)
PLAYER_MARKET_KEYWORDS = [
    "chutes no gol",
    "finalizações",
    "faltas cometidas",
    "impedimentos",
]


def _is_market_of_interest(market_name: str) -> bool:
    """Check if a market name matches our interest list (SH12 — word boundary).

    Uses regex with word boundaries (\\b) to prevent player-level combos
    (e.g. "Total de Gols do Jogador") from matching team/match markets
    (e.g. "Total de Gols").
    """
    lower = market_name.lower()
    for keyword in MARKETS_OF_INTEREST:
        # Build word-boundary pattern: /\b{keyword}\b/
        escaped = re.escape(keyword)
        pattern = re.compile(r"\b" + escaped + r"\b")
        if pattern.search(lower):
            return True
    return False


def _is_player_market(market_name: str) -> bool:
    """Check if a market is a player-level stat market."""
    lower = market_name.lower()
    return any(kw in lower for kw in PLAYER_MARKET_KEYWORDS)


def _fetch_full_event(event_id: str) -> dict[str, Any] | None:
    """Fetch full event data (all markets) from REST API.

    Uses: GET /v2/pt-BR/events/{eventId}
    Returns the first event dict with full odds, or None on error.
    """
    url = REST_EVENT_URL.format(event_id=event_id)
    headers = {
        "User-Agent": USER_AGENT,
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


def _enrich_events_with_full_odds(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each event, fetch full odds via REST API and replace the SSE odds.

    The SSE feed only returns ~3 selections (Resultado Final).
    The REST API returns all 700+ markets per event.
    """
    enriched = []
    for i, ev in enumerate(events):
        eid = str(ev.get("eventId", ""))
        match_name = ev.get("matchName", "?")
        logger.info(
            "Buscando odds completas [%d/%d]: %s (ID: %s)",
            i + 1,
            len(events),
            match_name,
            eid,
        )
        full = _fetch_full_event(eid)
        if full:
            # Preserve SSE metadata but use REST odds
            enriched.append(full)
        else:
            # Fallback to SSE data
            enriched.append(ev)
    return enriched


def _extract_event_date(event: dict) -> str | None:
    """Try to extract match date (YYYY-MM-DD) from event data.

    Superbet SSE events include: matchDate, utcDate, unixDateMillis.
    """
    # Try unixDateMillis first (most reliable)
    unix_ms = event.get("unixDateMillis")
    if unix_ms:
        try:
            ts = int(unix_ms) / 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass

    for field in ("matchDate", "utcDate", "startDate", "startTime", "matchStartDate"):
        val = event.get(field)
        if val:
            val_str = str(val)
            # Handle epoch milliseconds
            if val_str.isdigit() and len(val_str) >= 10:
                try:
                    ts = int(val_str)
                    if ts > 1e12:
                        ts = ts / 1000
                    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    pass
            # Handle ISO string
            try:
                dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
            # Handle date-only string
            if len(val_str) >= 10:
                try:
                    datetime.strptime(val_str[:10], "%Y-%m-%d")
                    return val_str[:10]
                except ValueError:
                    pass
    return None


def _extract_event_time(event: dict) -> str | None:
    """Try to extract kickoff time (HH:MM) from event data."""
    # Try unixDateMillis first
    unix_ms = event.get("unixDateMillis")
    if unix_ms:
        try:
            ts = int(unix_ms) / 1000
            return datetime.fromtimestamp(ts).strftime("%H:%M")
        except (ValueError, OSError):
            pass

    for field_name in ("matchDate", "utcDate", "startDate", "startTime", "matchStartDate"):
        val = event.get(field_name)
        if val:
            val_str = str(val)
            # Epoch ms
            if val_str.isdigit() and len(val_str) >= 10:
                try:
                    ts = int(val_str)
                    if ts > 1e12:
                        ts = ts / 1000
                    return datetime.fromtimestamp(ts).strftime("%H:%M")
                except (ValueError, OSError):
                    pass
            # ISO string
            try:
                dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
                return dt.strftime("%H:%M")
            except ValueError:
                pass
    return None


def _parse_teams(match_name: str) -> tuple[str, str]:
    """Split matchName by middle-dot into (home, away)."""
    parts = match_name.split(MIDDLE_DOT)
    if len(parts) != 2:
        return match_name, ""
    return parts[0].strip(), parts[1].strip()


def _extract_markets(event: dict) -> dict[str, dict[str, Any]]:
    """Extract odds grouped by market name.

    Returns: {market_name: {name, selections: [{name, code, price, line}], ...}}
    For simple markets (1X2): also has home/draw/away keys.
    For over/under markets: has list of {line, over, under} entries.
    """
    markets_raw: dict[str, list] = defaultdict(list)
    for sel in event.get("odds") or []:
        mn = sel.get("marketName", "")
        if mn:
            markets_raw[mn].append(sel)

    result: dict[str, dict[str, Any]] = {}
    for market_name, selections in markets_raw.items():
        m: dict[str, Any] = {"name": market_name, "selections": []}

        # Parse each selection
        for sel in selections:
            code = str(sel.get("code", "")).lower()
            name = str(sel.get("name", "")).lower()
            raw_name = sel.get("name", "")
            price = sel.get("price")
            if price is None:
                continue
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue

            # Superbet REST API: prices < 100 are decimal, >= 100 centesimal
            if price >= 100:
                price = price / 100.0

            # Try to extract line from selection name (e.g. "Mais de 2.5")
            line_val = None
            line_str = sel.get("showSpecialBetValue") or sel.get("specialBetValue")
            if line_str and str(line_str) not in ("0", ""):
                with contextlib.suppress(TypeError, ValueError):
                    line_val = float(line_str)
            # Parse line from name pattern "Mais de X.Y" / "Menos de X.Y"
            if line_val is None:
                import re as _re

                line_match = _re.search(r"(\d+[.,]\d+)", name)
                if line_match:
                    with contextlib.suppress(ValueError):
                        line_val = float(line_match.group(1).replace(",", "."))

            sel_data = {
                "name": raw_name,
                "code": code,
                "price": price,
                "line": line_val,
            }
            m["selections"].append(sel_data)

            # Convenience keys for simple markets
            if code in ("1", "home"):
                m["home"] = price
            elif code in ("0", "x", "draw", "empate"):
                m["draw"] = price
            elif code in ("2", "away"):
                m["away"] = price
            elif code in ("yes", "sim") or name.strip() == "sim":
                m["yes"] = price
            elif code in ("no", "não", "nao") or name.strip() in ("não", "nao"):
                m["no"] = price

        result[market_name] = m

    return result


# ── Display ──────────────────────────────────────────────────────────


# Reverse lookup: tournamentId → league name
def _build_tid_to_league(league_ids: dict[str, int]) -> dict[int, str]:
    return {v: k for k, v in league_ids.items()}


def _market_is_interesting(name: str) -> bool:
    """Filter for key markets we care about (team/match level)."""
    return _is_market_of_interest(name)


def _display_match(
    event: dict,
    tid_to_league: dict[int, str],
    show_all_markets: bool = False,
) -> list[str]:
    """Format a single match for display. Returns list of lines."""
    match_name = event.get("matchName", "?")
    home, away = _parse_teams(match_name)
    eid = event.get("eventId", "?")
    tid = event.get("tournamentId")
    league = tid_to_league.get(tid, f"tournament:{tid}")
    kickoff = _extract_event_time(event) or "??:??"

    lines: list[str] = []
    lines.append(f"  >> {home} vs {away}")
    lines.append(f"     Liga: {league} | Horário: {kickoff} | ID: {eid}")

    # Build Superbet URL slug
    slug_raw = match_name.replace(MIDDLE_DOT, "-x-").strip()
    # Normalize accented chars for URL
    import unicodedata

    slug_nfkd = unicodedata.normalize("NFKD", slug_raw)
    slug_ascii = slug_nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", slug_ascii).strip("-").lower()
    url = f"https://superbet.bet.br/odds/futebol/{slug}-{eid}"
    lines.append(f"     URL: {url}")

    markets = _extract_markets(event)

    if not markets:
        lines.append("     (sem odds disponíveis no feed)")
        return lines

    # Show key markets
    for mname, m in sorted(markets.items()):
        if not show_all_markets and not _market_is_interesting(mname):
            continue

        sels = m.get("selections", [])

        # Simple 1X2 / Dupla Chance / BTTS markets
        if "home" in m or "yes" in m:
            parts: list[str] = []
            if "home" in m:
                parts.append(f"1={m['home']:.2f}")
            if "draw" in m:
                parts.append(f"X={m['draw']:.2f}")
            if "away" in m:
                parts.append(f"2={m['away']:.2f}")
            if "yes" in m:
                parts.append(f"Sim={m['yes']:.2f}")
            if "no" in m:
                parts.append(f"Nao={m['no']:.2f}")
            if parts:
                lines.append(f"     -> {mname}: {' | '.join(parts)}")
        elif sels:
            # Over/Under or multi-line markets — group by line
            lines.append(f"     -> {mname}:")
            # Pair up over/under by line value
            by_line: dict[float | None, dict[str, float]] = defaultdict(dict)
            unpaired: list[str] = []
            for s in sels:
                sname = s["name"].lower()
                price = s["price"]
                line_v = s.get("line")
                if "mais" in sname or "over" in sname or "+" in s.get("code", ""):
                    by_line[line_v]["over"] = price
                    by_line[line_v]["line"] = line_v
                elif "menos" in sname or "under" in sname or "-" in s.get("code", ""):
                    by_line[line_v]["under"] = price
                    by_line[line_v]["line"] = line_v
                else:
                    unpaired.append(f"{s['name']}: {price:.2f}")

            if by_line:
                for lv in sorted(by_line.keys(), key=lambda x: x or 0):
                    entry = by_line[lv]
                    line_str = f"{lv}" if lv is not None else "?"
                    ov = f"Over={entry['over']:.2f}" if "over" in entry else ""
                    un = f"Under={entry['under']:.2f}" if "under" in entry else ""
                    odds_str = " | ".join(filter(None, [ov, un]))
                    lines.append(f"        Linha {line_str}: {odds_str}")
            for up in unpaired[:6]:
                lines.append(f"        {up}")

    return lines


# ── JSON export ──────────────────────────────────────────────────────


def _event_to_dict(
    event: dict,
    tid_to_league: dict[int, str],
) -> dict[str, Any]:
    """Convert raw event to a clean export dict."""
    match_name = event.get("matchName", "")
    home, away = _parse_teams(match_name)
    tid = event.get("tournamentId")
    return {
        "event_id": str(event.get("eventId", "")),
        "home_team": home,
        "away_team": away,
        "league": tid_to_league.get(tid, f"tournament:{tid}"),
        "tournament_id": tid,
        "date": _extract_event_date(event),
        "kickoff": _extract_event_time(event),
        "markets": _extract_markets(event),
    }


# ── Pre-filter for JSON/snapshot ─────────────────────────────────────


def _apply_snapshot_filter(
    events: list[dict],
    tid_to_league: dict[int, str],
    *,
    min_odd: float = 1.25,
    market_filter: list[str] | None = None,
) -> tuple[list[dict], int, int]:
    """Filter events before saving to JSON/snapshot.

    Parameters
    ----------
    events:
        List of enriched event dicts (with ``markets`` key from
        ``_extract_markets``).
    tid_to_league:
        Tournament ID → league name mapping.
    min_odd:
        Minimum odd threshold.  Events where the best available odd
        across ALL markets is below this value are discarded entirely.
    market_filter:
        Optional list of market name substrings to KEEP.  Markets whose
        ``name`` does not contain ANY of these substrings (case-
        insensitive) are removed from the event's ``markets`` dict.
        If ``None``, all markets are kept.

    Returns
    -------
    (filtered_events, total_before, total_after)
    """
    total_before = len(events)
    filtered: list[dict] = []

    for ev in events:
        markets = ev.get("markets", {})
        if not markets:
            continue

        # ── Market name filtering (optional) ─────────────────────────
        if market_filter:
            filtered_markets = {}
            for mname, mdata in markets.items():
                mname_lower = mname.lower()
                if any(kw in mname_lower for kw in market_filter):
                    filtered_markets[mname] = mdata
            markets = filtered_markets
            if not markets:
                continue

        # ── min_odd check ────────────────────────────────────────────
        best_odd = 0.0
        for mdata in markets.values():
            for sel in mdata.get("selections", []):
                price = sel.get("price")
                if price is not None and price > best_odd:
                    best_odd = price
        if best_odd < min_odd:
            logger.debug(
                "Snapshot filter: %s vs %s descartado — best odd %.2f < min %.2f",
                ev.get("home_team", "?"),
                ev.get("away_team", "?"),
                best_odd,
                min_odd,
            )
            continue

        # ── Rebuild event with filtered markets ──────────────────────
        filtered_ev = dict(ev)
        filtered_ev["markets"] = markets
        filtered.append(filtered_ev)

    total_after = len(filtered)
    if market_filter:
        logger.info(
            "Snapshot filter: %d → %d eventos (filtro mercados=%s, min_odd=%.2f)",
            total_before,
            total_after,
            ", ".join(market_filter),
            min_odd,
        )
    else:
        logger.info(
            "Snapshot filter: %d → %d eventos (min_odd=%.2f)",
            total_before,
            total_after,
            min_odd,
        )
    return filtered, total_before, total_after


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Superbet odds scraper — busca jogos por dia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python scripts/superbet_scraper.py domingo\n"
            "  python scripts/superbet_scraper.py hoje --leagues brasileirao serie_a\n"
            "  python scripts/superbet_scraper.py 2026-04-13 --json odds.json\n"
            "  python scripts/superbet_scraper.py todos --all-markets\n"
        ),
    )
    parser.add_argument(
        "dia",
        help="Dia alvo: hoje, amanha, domingo, segunda, ..., sabado, todos, ou YYYY-MM-DD",
    )
    parser.add_argument(
        "--leagues",
        nargs="*",
        default=None,
        help="Ligas de interesse (nomes do league_tournament_ids.json). Sem flag = todas.",
    )
    parser.add_argument(
        "--stream-seconds",
        type=float,
        default=45.0,
        help="Duração de escuta do SSE em segundos (default: 45)",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Exportar resultados em JSON para o caminho especificado",
    )
    parser.add_argument(
        "--all-markets",
        action="store_true",
        help="Mostrar todos os mercados (default: apenas principais)",
    )
    parser.add_argument(
        "--min-odd",
        type=float,
        default=1.25,
        help="Odd mínima para incluir evento no JSON/snapshot (default: 1.25 — ZONA MORTA). "
        "Eventos sem nenhuma odd >= min_odd são descartados do JSON salvo.",
    )
    parser.add_argument(
        "--markets",
        nargs="*",
        default=[
            "total de escanteios",
            "resultado final",
            "ambas as equipes marcam",
            "total de gols",
        ],
        help="Mercados para incluir no JSON/snapshot (default: corner, 1x2, BTTS, gols). "
        "Use '--markets all' para todos os mercados.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Modo debug: mostra campos brutos do primeiro evento",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log detalhado",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Nao salvar snapshot automatico em data/odds/pre_match/",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Modo rapido: apenas SSE, sem buscar odds completas via REST API",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Resolve target date
    try:
        target_date = _resolve_target_date(args.dia)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if target_date:
        logger.info("Data alvo: %s", target_date)
    else:
        logger.info("Modo: todos os jogos (sem filtro de data)")

    # Load mappings
    league_ids = _load_league_ids()
    tid_to_league = _build_tid_to_league(league_ids)

    # Determine tournament filter
    if args.leagues:
        tournament_filter = set()
        for lg in args.leagues:
            if lg in league_ids:
                tournament_filter.add(league_ids[lg])
            else:
                logger.warning(
                    "Liga '%s' não encontrada em league_tournament_ids.json. Disponíveis: %s",
                    lg,
                    ", ".join(sorted(league_ids.keys())),
                )
        if not tournament_filter:
            logger.error("Nenhuma liga válida especificada.")
            sys.exit(1)
    else:
        tournament_filter = set(league_ids.values())

    logger.info(
        "Filtrando por %d ligas: %s",
        len(tournament_filter),
        ", ".join(tid_to_league.get(t, str(t)) for t in sorted(tournament_filter)),
    )

    raw_events = _collect_raw_events_with_fallback(
        target_date=target_date,
        tournament_filter=tournament_filter,
        stream_seconds=args.stream_seconds,
    )

    if not raw_events:
        print("\n[!] Nenhum evento encontrado no feed SSE para as ligas selecionadas.")
        print("   Possiveis causas:")
        print("   - Nao ha jogos programados para essas ligas")
        print("   - Os tournament_ids podem estar desatualizados")
        print("   - Tente aumentar --stream-seconds")
        sys.exit(0)

    # Debug mode: dump first raw event
    if args.debug:
        print("\n[DEBUG] Campos do primeiro evento bruto:")
        first = raw_events[0]
        for k, v in first.items():
            if k == "odds":
                print(f"  odds: [{len(v)} seleções]")
                if v:
                    print(f"    Exemplo: {json.dumps(v[0], ensure_ascii=False, indent=4)}")
            else:
                print(f"  {k}: {v}")
        print()

    # Filter by date
    if target_date:
        dated = []
        undated = []
        for ev in raw_events:
            ev_date = _extract_event_date(ev)
            if ev_date == target_date:
                dated.append(ev)
            elif ev_date is None:
                undated.append(ev)
        # If most events lack dates, include undated too
        if dated:
            filtered = dated
        elif undated:
            logger.warning(
                "Nenhum evento com data '%s' encontrado. Mostrando %d eventos sem data (podem ser do dia).",
                target_date,
                len(undated),
            )
            filtered = undated
        else:
            print(f"\n[!] Nenhum jogo encontrado para {target_date}.")
            print(f"   Total de eventos coletados: {len(raw_events)}")
            # Show what dates are available
            dates_found = set()
            for ev in raw_events:
                d = _extract_event_date(ev)
                if d:
                    dates_found.add(d)
            if dates_found:
                print(f"   Datas disponíveis: {', '.join(sorted(dates_found))}")
            else:
                print("   Nenhum evento possui campo de data. Use 'todos' para ver tudo.")
            sys.exit(0)
    else:
        filtered = raw_events

    # Enrich with full odds from REST API (unless --quick)
    if not args.quick:
        logger.info(
            "Buscando odds completas para %d jogos via REST API...",
            len(filtered),
        )
        filtered = _enrich_events_with_full_odds(filtered)

    # Group by league
    by_league: dict[str, list[dict]] = defaultdict(list)
    for ev in filtered:
        tid = ev.get("tournamentId")
        league_name = tid_to_league.get(tid, f"tournament:{tid}")
        by_league[league_name].append(ev)

    # Display (all events before snapshot filter)
    total_display = len(filtered)
    date_label = target_date or "todos os dias"
    print(f"\n{'=' * 70}")
    print(f"  SUPERBET — Jogos de Futebol ({date_label})")
    print(f"  {total_display} jogos encontrados em {len(by_league)} ligas")
    print(f"{'=' * 70}")

    for league_name in sorted(by_league.keys()):
        events_in_league = by_league[league_name]
        print(f"\n{'-' * 70}")
        print(f"  [*] {league_name.upper().replace('_', ' ')} ({len(events_in_league)} jogos)")
        print(f"{'-' * 70}")

        for ev in events_in_league:
            match_lines = _display_match(ev, tid_to_league, args.all_markets)
            for ml in match_lines:
                print(ml)
            print()

    # ── Apply snapshot filter (min_odd + market whitelist) ───────────
    # Default: 4 mercados obrigatórios (corner, 1x2, BTTS, gols)
    # --markets all: desabilita o filtro (todos os mercados)
    if args.markets and len(args.markets) == 1 and args.markets[0].lower() == "all":
        market_filter_kw = None
    else:
        market_filter_kw = [kw.lower() for kw in args.markets] if args.markets else None
    snapshot_events, total_before, total_after = _apply_snapshot_filter(
        filtered,
        tid_to_league,
        min_odd=args.min_odd,
        market_filter=market_filter_kw,
    )

    # JSON export (explicit path) — applies snapshot filter
    if args.json:
        export = [_event_to_dict(ev, tid_to_league) for ev in snapshot_events]
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n[OK] {len(export)}/{total_before} jogos exportados para: {out_path}")
        if market_filter_kw:
            print(f"     Filtro mercados: {', '.join(market_filter_kw)} | min_odd: {args.min_odd:.2f}")

    # Auto-save daily snapshot to data/odds/pre_match/YYYY-MM-DD.json
    if not args.no_save:
        export = [_event_to_dict(ev, tid_to_league) for ev in snapshot_events]
        save_date = target_date or datetime.now().strftime("%Y-%m-%d")
        PRE_MATCH_DIR.mkdir(parents=True, exist_ok=True)
        daily_path = PRE_MATCH_DIR / f"{save_date}.json"
        with open(daily_path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n[OK] Snapshot salvo em: {daily_path} ({total_after}/{total_before} eventos)")
        if market_filter_kw:
            print(f"     Filtro mercados: {', '.join(market_filter_kw)} | min_odd: {args.min_odd:.2f}")


if __name__ == "__main__":
    main()
