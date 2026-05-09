"""Discover new tournament IDs from the Superbet SSE feed.

Captures ALL football events without tournament filtering, then shows
unique tournament IDs with sample team names for identification.

Usage:
    python scripts/discover_tournaments.py                        # broad scan (90s)
    python scripts/discover_tournaments.py --target-date 2026-05-08  # specific date
    python scripts/discover_tournaments.py --duration 60          # shorter scan
    python scripts/discover_tournaments.py --rest                 # also fetch REST details
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
MAPPING_DIR = ROOT / "data" / "mapping"
LEAGUE_IDS_PATH = MAPPING_DIR / "league_tournament_ids.json"
OUTPUT_PATH = ROOT / "data" / "_discovered_tournaments.json"

SSE_ENDPOINT_PREMATCH = "https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/prematch"
SSE_ENDPOINT_ALL = "https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/all"
REST_EVENT_URL = "https://production-superbet-offer-br.freetls.fastly.net/v2/pt-BR/events/{event_id}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
MIDDLE_DOT = "\u00b7"
SPORT_ID_FOOTBALL = 5

logger = logging.getLogger(__name__)


def load_known_ids() -> dict[str, int | list[int]]:
    """Load currently known league -> tournament ID(s).

    Some leagues (e.g. Copa Sul-Americana) have multiple TIDs per group stage;
    those are stored as ``list[int]``. This function retains the raw types.
    """
    if not LEAGUE_IDS_PATH.exists():
        return {}
    with open(LEAGUE_IDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def stream_sse(
    endpoint: str,
    duration_s: float = 90.0,
) -> list[dict[str, Any]]:
    """Stream SSE feed and collect ALL events (no filter)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/event-stream"}
    timeout = httpx.Timeout(connect=10.0, read=duration_s + 10.0, write=10.0, pool=10.0)

    events: dict[str, dict[str, Any]] = {}
    deadline = time.monotonic() + duration_s
    lines_read = 0

    print(f"  Conectando ao SSE {endpoint.rsplit('/', maxsplit=1)[-1]} por {duration_s:.0f}s...")

    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("GET", endpoint, headers=headers) as resp:
                resp.raise_for_status()
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

                    eid = str(inner.get("eventId", ""))
                    if eid:
                        events[eid] = inner

                    if time.monotonic() >= deadline:
                        break
    except Exception as exc:
        print(f"  [AVISO] Erro SSE: {exc}")

    print(f"  Linhas lidas: {lines_read}, Eventos unicos: {len(events)}")
    return list(events.values())


def extract_event_date(event: dict) -> str | None:
    """Try to extract match date (YYYY-MM-DD) from event data."""
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
            if val_str.isdigit() and len(val_str) >= 10:
                try:
                    ts = int(val_str)
                    if ts > 1e12:
                        ts = ts / 1000
                    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    pass
            try:
                dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
            if len(val_str) >= 10:
                try:
                    datetime.strptime(val_str[:10], "%Y-%m-%d")
                    return val_str[:10]
                except ValueError:
                    pass
    return None


def fetch_rest_event(event_id: str) -> dict[str, Any] | None:
    """Fetch full event details from REST API."""
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
                return None
            events = data.get("data", [])
            if events:
                return events[0]
    except Exception:
        return None
    return None


def get_category_name(category_id: int) -> str:
    """Map category IDs to known competition names based on observed data."""
    category_names = {
        45: "England (Premier League)",
        31: "South America (Libertadores?)",
        194: "Norway",
        248: "Morocco",
        69: "Australia",
        55: "Finland",
        168: "Austria",
        54: "South Africa",
        181: "France (Handball?)",
        236: "Tennis",
        92: "NHL",
        61: "WNBA / NBA",
        90: "OHL (Hockey)",
        202: "MLB",
        1984: "E-Football (Virtual)",
        1697: "E-Basketball (Virtual)",
        1294: "E-Soccer (Virtual)",
        898: "E-Basketball (Virtual)",
        23: "ITF Tennis",
        37: "ITF Doubles",
    }
    return category_names.get(category_id, f"Unknown(cat={category_id})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Discover new tournament IDs from Superbet SSE feed")
    parser.add_argument(
        "--target-date",
        type=str,
        default=None,
        help="Filter events by date (YYYY-MM-DD). Default: all dates.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=90.0,
        help="SSE listening duration in seconds (default: 90)",
    )
    parser.add_argument(
        "--rest",
        action="store_true",
        help="Fetch REST details for unknown TIDs (slower)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all events, not just summary")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    known = load_known_ids()
    # Flatten: handle both int and list[int] values
    known_tids: set[int] = set()
    for v in known.values():
        if isinstance(v, list):
            known_tids.update(v)
        else:
            known_tids.add(v)

    print("=" * 70)
    print("  DISCOVERY DE TORNEIOS - Superbet SSE Feed")
    print("=" * 70)
    print(f"\n  Liga(s) conhecida(s): {len(known_tids)}")
    for name in sorted(known.keys()):
        val = known[name]
        if isinstance(val, list):
            print(f"    {name}: tids={val}")
        else:
            print(f"    {name}: tid={val}")

    # --- Stream PREMATCH (future events) ---
    prematch_events = stream_sse(SSE_ENDPOINT_PREMATCH, args.duration)

    # --- Stream ALL (live + upcoming) ---
    all_events = stream_sse(SSE_ENDPOINT_ALL, args.duration)

    # Merge (deduplicate)
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for ev in prematch_events + all_events:
        eid = str(ev.get("eventId", ""))
        if eid and eid not in seen:
            seen.add(eid)
            merged.append(ev)

    print(f"\n  Total eventos unicos (ambos endpoints): {len(merged)}")

    # --- Analyze by sport ---
    by_sport: dict[int, list[dict]] = defaultdict(list)
    for ev in merged:
        sid = ev.get("sportId")
        if sid:
            by_sport[sid].append(ev)

    print("\n  Esportes encontrados:")
    for sid in sorted(by_sport.keys()):
        sid_events = by_sport[sid]
        sport_label = {
            5: "Futebol",
            11: "Tenis",
            75: "E-Football",
            24: "Ten. Mesa",
            3: "Hoquei",
            4: "Basquete",
            70: "E-Basquete",
            20: "Basebol",
            190: "Fut. Virtual",
            2: "Tenis 2",
        }.get(sid, f"SportId={sid}")
        # Count distinct tournaments
        tids = set()
        for ev in sid_events:
            t = ev.get("tournamentId")
            if t:
                tids.add(t)
        print(f"    SportId={sid} ({sport_label}): {len(sid_events)} events, {len(tids)} torneios")

    # --- Focus on football ---
    football_events = by_sport.get(SPORT_ID_FOOTBALL, [])
    print(f"\n{'=' * 70}")
    print(f"  FUTEBOL (SportId=5): {len(football_events)} eventos")
    print(f"{'=' * 70}")

    if not football_events:
        print("\n  Nenhum evento de futebol encontrado no feed!")
        print("  Pode ser que o feed so retorne eventos ao vivo/proximos.")
        print("  Tente aumentar --duration ou executar mais perto do horario dos jogos.")
        # Save raw data anyway
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_events": len(merged),
            "football_count": 0,
            "sports_found": {str(k): len(v) for k, v in sorted(by_sport.items())},
            "football_events": [],
            "tournament_summary": {},
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n  Dados brutos salvos em: {OUTPUT_PATH}")
        return

    # --- Group football events by tournament ID ---
    by_tid: dict[int, list[dict]] = defaultdict(list)
    for ev in football_events:
        tid = ev.get("tournamentId")
        if tid:
            by_tid[tid].append(ev)

    # --- Filter by date if requested ---
    if args.target_date:
        filtered_football = [ev for ev in football_events if extract_event_date(ev) == args.target_date]
        print(f"\n  Eventos de futebol para {args.target_date}: {len(filtered_football)}")
        football_events = filtered_football
        # Re-group by TID
        by_tid.clear()
        for ev in football_events:
            tid = ev.get("tournamentId")
            if tid:
                by_tid[tid].append(ev)

    # --- Show tournament summary ---
    print("\n  --- Torneios de Futebol Encontrados ---")
    print(f"  {'TID':<8} {'CatID':<6} {'Eventos':<8} {'Conhecido?':<12} {'Exemplos'}")
    print(f"  {'-' * 60}")

    unknown_tids: list[int] = []

    for tid in sorted(by_tid.keys()):
        events = by_tid[tid]
        # Get category from first event
        cat_id = events[0].get("categoryId", "?")
        # Get sample match names (up to 3)
        samples = []
        dates_seen = set()
        for ev in events[:5]:
            mn = ev.get("matchName", "?")
            # Truncate long names
            if len(mn) > 40:
                mn = mn[:37] + "..."
            samples.append(mn)
            d = extract_event_date(ev)
            if d:
                dates_seen.add(d)

        known_status = "CONHECIDO" if tid in known_tids else "DESCONHECIDO"
        if tid not in known_tids:
            unknown_tids.append(tid)

        sample_str = " | ".join(samples[:3])
        dates_str = ", ".join(sorted(dates_seen)) if dates_seen else "?"
        print(f"  {tid:<8} {str(cat_id):<6} {len(events):<8} {known_status:<12} {sample_str}")
        print(f"  {'':8} {'':6} {'':8} {'':12} Datas: {dates_str}")

    # --- Fetch REST details for unknown TIDs ---
    if args.rest and unknown_tids:
        print(f"\n  --- Buscando detalhes REST para {len(unknown_tids)} TIDs desconhecidos ---")
        rest_details: dict[int, dict] = {}
        for tid in unknown_tids:
            # Get one event ID for this TID
            sample_events = by_tid[tid]
            eid = str(sample_events[0].get("eventId", ""))
            if not eid:
                continue
            print(f"  Buscando TID={tid} via event_id={eid}...", end=" ")
            rest_data = fetch_rest_event(eid)
            if rest_data:
                # Extract useful fields
                rest_details[tid] = {
                    "matchName": rest_data.get("matchName", "?"),
                    "tournamentId": rest_data.get("tournamentId"),
                    "categoryId": rest_data.get("categoryId"),
                    "matchDate": rest_data.get("matchDate", rest_data.get("startDate", "?")),
                    "matchStatus": rest_data.get("matchStatus"),
                    "eventId": eid,
                }
                print("OK")
            else:
                print("FALHOU")
            time.sleep(0.3)  # Rate limiting

        # Show REST details
        print("\n  --- Detalhes REST para TIDs desconhecidos ---")
        print(f"  {'TID':<8} {'CatID':<6} {'Match'}")
        print(f"  {'-' * 60}")
        for tid in sorted(rest_details.keys()):
            rd = rest_details[tid]
            mn = rd.get("matchName", "?")
            cat = rd.get("categoryId", "?")
            print(f"  {tid:<8} {str(cat):<6} {mn}")
            print(f"  {'':8} {'':6} Data: {rd.get('matchDate', '?')} | Status: {rd.get('matchStatus', '?')}")

    # --- Also show ALL events (non-football) summary for context ---
    if args.verbose:
        print("\n  --- Todos os Esportes - Resumo de Torneios ---")
        for sid in sorted(by_sport.keys()):
            if sid == SPORT_ID_FOOTBALL:
                continue
            events = by_sport[sid]
            tids_sport = set()
            for ev in events:
                t = ev.get("tournamentId")
                if t:
                    tids_sport.add(t)
            sport_name = {
                11: "Tenis",
                75: "E-Football",
                24: "Ten.Mesa",
                3: "Hoquei",
                4: "Basquete",
                70: "E-Basquete",
                20: "Basebol",
                190: "Fut.Virtual",
                2: "Tenis2",
            }.get(sid, f"Sport{sid}")
            print(f"\n  SportId={sid} ({sport_name}): {len(events)} eventos, {len(tids_sport)} torneios")
            for tid in sorted(tids_sport):
                tid_events = [ev for ev in events if ev.get("tournamentId") == tid]
                cat_id = tid_events[0].get("categoryId", "?")
                samples = [ev.get("matchName", "?")[:50] for ev in tid_events[:3]]
                print(f"    TID={tid:<8} Cat={cat_id:<5} Ex: {' | '.join(samples)}")
    # --- Save results ---
    # Build summary
    tournament_summary = {}
    for tid in sorted(by_tid.keys()):
        events = by_tid[tid]
        cat_id = events[0].get("categoryId", "?")
        samples = [ev.get("matchName", "?") for ev in events[:5]]
        dates = sorted({extract_event_date(ev) for ev in events if extract_event_date(ev)})
        tournament_summary[str(tid)] = {
            "categoryId": cat_id,
            "count": len(events),
            "samples": samples,
            "dates": dates,
            "known": tid in known_tids,
        }

    output = {
        "timestamp": datetime.now().isoformat(),
        "target_date": args.target_date,
        "total_events": len(merged),
        "football_count": len(football_events),
        "known_leagues": {k: v for k, v in sorted(known.items(), key=lambda x: x[1])},
        "tournament_summary": tournament_summary,
        "unknown_tids": unknown_tids,
        "category_guesses": {
            str(cid): name
            for cid, name in {
                45: "England (Premier League)",
                31: "South America - likely Copa Libertadores",
                194: "Norway Eliteserien",
                248: "Morocco Botola",
            }.items()
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  Resultados salvos em: {OUTPUT_PATH}")

    # --- Summary ---
    if unknown_tids:
        print(f"\n  [!] {len(unknown_tids)} TIDs desconhecidos encontrados!")
        print("  Execute com --rest para buscar detalhes via REST API.")
    else:
        print("\n  Todos os TIDs encontrados ja sao conhecidos.")

    print("\n  Concluido!")


if __name__ == "__main__":
    main()
