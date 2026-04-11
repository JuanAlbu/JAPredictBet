"""Live context collector (T-60) for the Gatekeeper pipeline.

Aggregates data from two sources exactly ``cron_trigger_minutes_before``
minutes before kick-off:

1. **Superbet** — live odds via :mod:`japredictbet.odds.superbet_client`.
2. **API-Football** — confirmed lineups, injuries, referee history and
   league standings via ``api-sports.io`` (v3).

The combined payload is serialised as a typed :class:`MatchContext` ready
to be consumed by the Gatekeeper LLM agent.

Security note
─────────────
API keys are **never** hardcoded.  They are resolved from environment
variables at runtime via :meth:`ApiKeysConfig.resolve`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from japredictbet.config import (
    ApiFootballConfig,
    ApiKeysConfig,
    GatekeeperConfig,
    SuperbetShadowConfig,
)
from japredictbet.odds.superbet_client import SuperbetCollector, SuperbetSnapshot

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────


@dataclass
class PlayerInfo:
    """Minimal lineup entry."""

    name: str
    number: Optional[int] = None
    position: Optional[str] = None


@dataclass
class TeamLineup:
    """Confirmed / projected lineup for one side."""

    formation: Optional[str] = None
    starting_xi: List[PlayerInfo] = field(default_factory=list)
    missing_players: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class RefereeInfo:
    """Referee profile with relevant stats."""

    name: str
    avg_fouls_per_match: Optional[float] = None
    avg_cards_per_match: Optional[float] = None
    avg_corners_per_match: Optional[float] = None


@dataclass
class StandingsEntry:
    """Simplified league table row."""

    rank: int
    team: str
    points: int
    played: int
    goal_diff: int
    form: Optional[str] = None  # e.g. "WWDLW"


@dataclass
class OddsContext:
    """Odds snapshot carried into the LLM context."""

    corner_line: Optional[float] = None
    corner_over_odds: Optional[float] = None
    corner_under_odds: Optional[float] = None
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    btts_yes: Optional[float] = None
    btts_no: Optional[float] = None


@dataclass
class MatchContext:
    """Full context for a single match — input for the Gatekeeper agent."""

    event_id: str
    home_team: str
    away_team: str
    kickoff_utc: Optional[str] = None
    league: Optional[str] = None
    odds: OddsContext = field(default_factory=OddsContext)
    home_lineup: Optional[TeamLineup] = None
    away_lineup: Optional[TeamLineup] = None
    referee: Optional[RefereeInfo] = None
    home_standing: Optional[StandingsEntry] = None
    away_standing: Optional[StandingsEntry] = None
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        """Serialise to a JSON string (for LLM injection)."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


# ── API-Football client ──────────────────────────────────────────────


class ApiFootballClient:
    """Thin wrapper around api-sports.io v3 endpoints.

    All methods are **read-only** and safe to call in any context.
    """

    def __init__(
        self,
        api_key: str,
        cfg: ApiFootballConfig,
    ) -> None:
        if not api_key:
            raise ValueError(
                "API-Football key is empty. "
                "Set the API_FOOTBALL_KEY environment variable."
            )
        self._api_key = api_key
        self._cfg = cfg
        self._timeout = httpx.Timeout(
            connect=cfg.connect_timeout_s,
            read=cfg.read_timeout_s,
            write=10.0,
            pool=10.0,
        )

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GET request with authentication and error handling."""
        headers = {
            "x-apisports-key": self._api_key,
        }
        url = f"{self._cfg.base_url}/{endpoint.lstrip('/')}"

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        errors = data.get("errors")
        if errors:
            logger.warning("API-Football returned errors: %s", errors)

        return data

    # ── fixtures (today's matches) ───────────────────────────────────

    def get_fixtures_today(
        self, league_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return today's fixtures, optionally filtered by league."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        params: Dict[str, Any] = {"date": today}
        if league_id is not None:
            params["league"] = league_id
        data = self._get("fixtures", params)
        return data.get("response", [])

    # ── lineups ──────────────────────────────────────────────────────

    def get_lineups(self, fixture_id: int) -> Dict[str, TeamLineup]:
        """Fetch confirmed lineups for a fixture.

        Returns a dict ``{"home": TeamLineup, "away": TeamLineup}``.
        If lineups are not yet confirmed, fields are empty.
        """
        data = self._get("fixtures/lineups", {"fixture": fixture_id})
        result: Dict[str, TeamLineup] = {}

        for idx, team_data in enumerate(data.get("response", [])):
            side = "home" if idx == 0 else "away"
            formation = team_data.get("formation")
            xi = [
                PlayerInfo(
                    name=p["player"]["name"],
                    number=p["player"].get("number"),
                    position=p["player"].get("pos"),
                )
                for p in team_data.get("startXI", [])
            ]
            result[side] = TeamLineup(formation=formation, starting_xi=xi)

        return result

    # ── injuries / suspensions ───────────────────────────────────────

    def get_injuries(self, fixture_id: int) -> List[Dict[str, str]]:
        """Return list of injured / suspended players for a fixture."""
        data = self._get("injuries", {"fixture": fixture_id})
        injuries: List[Dict[str, str]] = []
        for entry in data.get("response", []):
            player = entry.get("player", {})
            team = entry.get("team", {})
            injuries.append(
                {
                    "player": player.get("name", ""),
                    "team": team.get("name", ""),
                    "type": player.get("type", ""),
                    "reason": player.get("reason", ""),
                }
            )
        return injuries

    # ── standings ────────────────────────────────────────────────────

    def get_standings(
        self, league_id: int, season: int
    ) -> List[StandingsEntry]:
        """Fetch league standings for a given season."""
        data = self._get(
            "standings", {"league": league_id, "season": season}
        )
        entries: List[StandingsEntry] = []
        for league_resp in data.get("response", []):
            for group in league_resp.get("league", {}).get("standings", []):
                for row in group:
                    entries.append(
                        StandingsEntry(
                            rank=row.get("rank", 0),
                            team=row.get("team", {}).get("name", ""),
                            points=row.get("points", 0),
                            played=row.get("all", {}).get("played", 0),
                            goal_diff=row.get("goalsDiff", 0),
                            form=row.get("form"),
                        )
                    )
        return entries


# ── Context aggregator ───────────────────────────────────────────────


class ContextCollector:
    """Orchestrates data collection from Superbet + API-Football.

    Usage::

        collector = ContextCollector.from_configs(cfg, api_keys)
        contexts = collector.collect_upcoming(minutes_before=60)
    """

    def __init__(
        self,
        superbet: SuperbetCollector,
        api_football: ApiFootballClient,
        gatekeeper_cfg: GatekeeperConfig,
        team_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        self._superbet = superbet
        self._api = api_football
        self._gk_cfg = gatekeeper_cfg
        self._team_mapping = team_mapping

    @classmethod
    def from_configs(
        cls,
        superbet_cfg: SuperbetShadowConfig,
        api_football_cfg: ApiFootballConfig,
        api_keys: ApiKeysConfig,
        gatekeeper_cfg: GatekeeperConfig,
    ) -> ContextCollector:
        """Factory that resolves API keys and loads team mapping."""
        resolved = api_keys.resolve()

        superbet = SuperbetCollector(superbet_cfg)
        api_client = ApiFootballClient(resolved.api_football_key, api_football_cfg)

        team_mapping = _load_team_mapping(superbet_cfg.team_mapping_path)

        return cls(
            superbet=superbet,
            api_football=api_client,
            gatekeeper_cfg=gatekeeper_cfg,
            team_mapping=team_mapping,
        )

    # ── public ───────────────────────────────────────────────────────

    def collect_upcoming(
        self,
        minutes_before: Optional[int] = None,
    ) -> List[MatchContext]:
        """Collect context for matches kicking off within the next ``minutes_before`` minutes.

        1. Fetch today's Superbet odds snapshot.
        2. For each football match with a known kick-off time within the
           window, fetch lineups + injuries + standings from API-Football.
        3. Combine into :class:`MatchContext` objects.
        """
        window = minutes_before or self._gk_cfg.cron_trigger_minutes_before

        # ── Superbet odds ────────────────────────────────────────────
        logger.info("Fetching Superbet odds feed…")
        sb_snapshots = self._superbet.fetch_today_odds(self._team_mapping)

        # ── API-Football fixtures ────────────────────────────────────
        logger.info("Fetching today's fixtures from API-Football…")
        fixtures = self._api.get_fixtures_today()

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(minutes=window)

        contexts: List[MatchContext] = []

        for fix in fixtures:
            fixture_info = fix.get("fixture", {})
            fixture_id: int = fixture_info.get("id", 0)
            kickoff_str: str = fixture_info.get("date", "")

            try:
                kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            # Only matches within the T-{window} window
            if not (now <= kickoff <= cutoff):
                continue

            teams = fix.get("teams", {})
            home_name: str = teams.get("home", {}).get("name", "")
            away_name: str = teams.get("away", {}).get("name", "")
            league_info = fix.get("league", {})

            # ── Build odds context from Superbet snapshot ────────────
            odds_ctx = self._match_superbet_odds(
                home_name, away_name, sb_snapshots
            )

            # ── Lineups ─────────────────────────────────────────────
            lineups = self._safe_call(
                self._api.get_lineups, fixture_id, label="lineups"
            ) or {}

            home_lineup = lineups.get("home")
            away_lineup = lineups.get("away")

            # ── Injuries → merge into lineup.missing_players ────────
            injuries = self._safe_call(
                self._api.get_injuries, fixture_id, label="injuries"
            ) or []
            if injuries:
                _merge_injuries(injuries, home_name, home_lineup)
                _merge_injuries(injuries, away_name, away_lineup)

            # ── Standings ───────────────────────────────────────────
            league_id: int = league_info.get("id", 0)
            season: int = league_info.get("season", now.year)
            standings = self._safe_call(
                self._api.get_standings,
                league_id,
                season,
                label="standings",
            ) or []

            home_standing = _find_standing(standings, home_name)
            away_standing = _find_standing(standings, away_name)

            ctx = MatchContext(
                event_id=str(fixture_id),
                home_team=home_name,
                away_team=away_name,
                kickoff_utc=kickoff.isoformat(),
                league=league_info.get("name"),
                odds=odds_ctx,
                home_lineup=home_lineup,
                away_lineup=away_lineup,
                home_standing=home_standing,
                away_standing=away_standing,
            )
            contexts.append(ctx)

        logger.info(
            "ContextCollector: %d matches within T-%d window.", len(contexts), window
        )
        return contexts

    # ── private helpers ──────────────────────────────────────────────

    def _match_superbet_odds(
        self,
        home: str,
        away: str,
        snapshots: Dict[str, SuperbetSnapshot],
    ) -> OddsContext:
        """Best-effort fuzzy match between API-Football teams and Superbet events."""
        odds = OddsContext()
        home_l, away_l = home.lower(), away.lower()

        for snap in snapshots.values():
            sb_home_l = snap.home_team.lower()
            sb_away_l = snap.away_team.lower()

            if home_l in sb_home_l or sb_home_l in home_l:
                if away_l in sb_away_l or sb_away_l in away_l:
                    # Corner market — pick the first available line
                    if snap.corners:
                        c = snap.corners[0]
                        odds.corner_line = c.market_line
                        odds.corner_over_odds = c.over_odds
                        odds.corner_under_odds = c.under_odds
                    # Match odds
                    if snap.match_odds:
                        m = snap.match_odds[0]
                        odds.home_odds = m.home_odds
                        odds.draw_odds = m.draw_odds
                        odds.away_odds = m.away_odds
                    # BTTS
                    if snap.btts:
                        b = snap.btts[0]
                        odds.btts_yes = b.yes_odds
                        odds.btts_no = b.no_odds
                    break

        return odds

    @staticmethod
    def _safe_call(func, *args, label: str = "call", **kwargs):  # type: ignore[no-untyped-def]
        """Wrap an API call so failures don't crash the whole pipeline."""
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.warning("Failed to fetch %s — continuing without it.", label, exc_info=True)
            return None


# ── module-level helpers ─────────────────────────────────────────────


def _load_team_mapping(path: str) -> Optional[Dict[str, str]]:
    """Load the Superbet → internal team name mapping.

    Returns ``None`` (skip filtering) if the file doesn't exist.
    """
    p = Path(path)
    if not p.exists():
        logger.info("Team mapping file not found at %s — skipping filter.", path)
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _merge_injuries(
    injuries: List[Dict[str, str]],
    team_name: str,
    lineup: Optional[TeamLineup],
) -> None:
    """Add injury records into the lineup's ``missing_players`` list."""
    if lineup is None:
        return
    for inj in injuries:
        if inj.get("team", "").lower() == team_name.lower():
            lineup.missing_players.append(inj)


def _find_standing(
    standings: List[StandingsEntry], team_name: str
) -> Optional[StandingsEntry]:
    """Find a team's standing row by case-insensitive partial match."""
    lower = team_name.lower()
    for entry in standings:
        if lower in entry.team.lower() or entry.team.lower() in lower:
            return entry
    return None
