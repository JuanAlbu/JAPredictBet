"""Tests for the ContextCollector and data models (AUDIT.1 + AUDIT.2).

Covers:
- MatchContext.news_context field and serialization (AUDIT.1)
- _is_target_zone() — Target Zone gating
- _collect_news_context() — DuckDuckGo search (mocked)
- _enrich_news_contexts() — batch enrichment with safety
- collect_upcoming() — Superbet-only and Full mode (mocked)
- enrich_pre_match_contexts() — pre-match with news (mocked)
- Edge cases: empty response, timeout, JSON inválido, HTTP 429/500,
  fixture sem lineups, standings vazias, injuries vazias
- DuckDuckGo unavailable graceful degradation

All network calls are mocked — no real HTTP or DuckDuckGo requests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from japredictbet.config import (
    ApiFootballConfig,
    GatekeeperConfig,
    SuperbetShadowConfig,
)
from japredictbet.data.context_collector import (
    ApiFootballClient,
    ContextCollector,
    MatchContext,
    OddsContext,
    _find_standing,
    _merge_injuries,
)
from japredictbet.odds.superbet_client import (
    SuperbetCollector,
    SuperbetOdds,
    SuperbetSnapshot,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def odds_target_zone() -> OddsContext:
    """OddsContext with at least one market in the Target Zone (1.60–2.20)."""
    return OddsContext(
        corner_line=9.5,
        corner_over_odds=1.85,
        corner_under_odds=1.95,
        home_odds=1.70,
        draw_odds=3.50,
        away_odds=5.00,
    )


@pytest.fixture
def odds_dead_zone() -> OddsContext:
    """OddsContext with all markets below 1.25 (Zona Morta) — no target."""
    return OddsContext(
        corner_over_odds=1.10,
        corner_under_odds=1.05,
    )


@pytest.fixture
def odds_variance_zone() -> OddsContext:
    """OddsContext with all markets above 2.20 or below 1.60 (no target zone)."""
    return OddsContext(
        btts_yes=2.50,
        btts_no=3.00,
        goals_over_1_5=1.15,
        goals_under_1_5=5.00,
    )


@pytest.fixture
def sample_context(odds_target_zone: OddsContext) -> MatchContext:
    """Minimal MatchContext with target-zone odds."""
    return MatchContext(
        event_id="12345",
        home_team="Flamengo",
        away_team="Palmeiras",
        league="Brasileirão Série A",
        odds=odds_target_zone,
    )


@pytest.fixture
def sample_context_no_target(odds_variance_zone: OddsContext) -> MatchContext:
    """MatchContext without any target-zone odds."""
    return MatchContext(
        event_id="67890",
        home_team="Cuiabá",
        away_team="Goiás",
        league="Brasileirão Série A",
        odds=odds_variance_zone,
    )


# ── Shared test data builders ─────────────────────────────────────────


def _make_snapshot(event_id: str, home: str, away: str) -> SuperbetSnapshot:
    """Build a minimal SuperbetSnapshot with corner odds (kickoff ~30min from now)."""
    corner_odds = SuperbetOdds(
        event_id=event_id,
        home_team=home,
        away_team=away,
        market_name="Cantos - Total de Cantos",
        market_line=9.5,
        over_odds=1.85,
        under_odds=1.95,
        home_odds=None,
        draw_odds=None,
        away_odds=None,
        yes_odds=None,
        no_odds=None,
        raw_event={},
    )
    # Kickoff ~30 minutes from now (guarantees it falls within any realistic window)
    kickoff_ms = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp() * 1000)
    return SuperbetSnapshot(
        event_id=event_id,
        home_team=home,
        away_team=away,
        corners=[corner_odds],
        raw_event={"unixDateMillis": kickoff_ms, "matchName": f"{home}·{away}"},
    )


def _make_api_football_fixture(
    fixture_id: int,
    home: str,
    away: str,
    league_name: str = "Brasileirão Série A",
    league_id: int = 71,
    kickoff: str | None = None,
) -> dict:
    """Build a minimal API-Football fixture dict (kickoff ~30min from now if not set)."""
    if kickoff is None:
        kickoff = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    return {
        "fixture": {"id": fixture_id, "date": kickoff},
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "league": {"id": league_id, "name": league_name, "season": 2024},
    }


def _make_api_lineups_response() -> dict:
    """Minimal API-Football lineups response."""
    return {
        "get": "fixtures/lineups",
        "response": [
            {
                "formation": "4-4-2",
                "startXI": [
                    {"player": {"name": "Player H1", "number": 1, "pos": "G"}},
                    {"player": {"name": "Player H2", "number": 9, "pos": "F"}},
                ],
            },
            {
                "formation": "4-3-3",
                "startXI": [
                    {"player": {"name": "Player A1", "number": 1, "pos": "G"}},
                ],
            },
        ],
    }


def _make_api_injuries_response() -> dict:
    """Minimal API-Football injuries response."""
    return {
        "get": "injuries",
        "response": [
            {
                "player": {"name": "Lesionado H", "type": "Injury", "reason": "Muscle"},
                "team": {"name": "Flamengo"},
            }
        ],
    }


# Raw standings rows passed directly to _make_mock_api_client
_STANDINGS_ROWS: list[dict] = [
    {
        "rank": 1,
        "team": {"name": "Flamengo"},
        "points": 30,
        "all": {"played": 10},
        "goalsDiff": 15,
        "form": "WWWDL",
    },
    {
        "rank": 5,
        "team": {"name": "Palmeiras"},
        "points": 20,
        "all": {"played": 10},
        "goalsDiff": 5,
        "form": "LWDWW",
    },
]


# ── AUDIT.1: MatchContext.news_context ────────────────────────────────


class TestMatchContextNewsContext:
    """Verify news_context field is present and serialized correctly."""

    def test_news_context_default_none(self):
        """Default value is None."""
        ctx = MatchContext(event_id="1", home_team="A", away_team="B")
        assert ctx.news_context is None

    def test_news_context_assignment(self):
        """Can be set explicitly."""
        ctx = MatchContext(
            event_id="1",
            home_team="A",
            away_team="B",
            news_context="Derby importante",
        )
        assert ctx.news_context == "Derby importante"

    def test_to_json_includes_news_context(self):
        """to_json serializes news_context."""
        ctx = MatchContext(
            event_id="1",
            home_team="A",
            away_team="B",
            news_context="Crise financeira no clube.",
        )
        data = json.loads(ctx.to_json())
        assert data["news_context"] == "Crise financeira no clube."

    def test_to_json_news_context_null(self):
        """to_json with news_context=None includes it as null."""
        ctx = MatchContext(event_id="1", home_team="A", away_team="B")
        data = json.loads(ctx.to_json())
        assert data["news_context"] is None

    def test_to_llm_context_includes_news_when_present(self):
        """to_llm_context includes 'news_context' key when populated."""
        ctx = MatchContext(
            event_id="1",
            home_team="A",
            away_team="B",
            news_context="Derby histórico.",
        )
        payload = json.loads(ctx.to_llm_context())
        assert "news_context" in payload
        assert payload["news_context"] == "Derby histórico."

    def test_to_llm_context_omits_news_when_none(self):
        """to_llm_context omits 'news_context' key when None."""
        ctx = MatchContext(event_id="1", home_team="A", away_team="B")
        payload = json.loads(ctx.to_llm_context())
        assert "news_context" not in payload


# ── _is_target_zone ───────────────────────────────────────────────────


class TestIsTargetZone:
    """Verify target-zone gating logic."""

    def test_corner_over_in_zone(self, odds_target_zone: OddsContext):
        assert ContextCollector._is_target_zone(odds_target_zone)

    def test_btts_in_zone(self):
        odds = OddsContext(btts_yes=1.80)
        assert ContextCollector._is_target_zone(odds)

    def test_all_outside_zone(self, odds_dead_zone: OddsContext):
        assert not ContextCollector._is_target_zone(odds_dead_zone)

    def test_all_none(self):
        odds = OddsContext()
        assert not ContextCollector._is_target_zone(odds)

    def test_boundary_min(self):
        """Exactly 1.60 is in target zone."""
        odds = OddsContext(corner_over_odds=1.60)
        assert ContextCollector._is_target_zone(odds)

    def test_boundary_max(self):
        """Exactly 2.20 is in target zone."""
        odds = OddsContext(corner_over_odds=2.20)
        assert ContextCollector._is_target_zone(odds)

    def test_just_below_boundary(self):
        odds = OddsContext(corner_over_odds=1.59)
        assert not ContextCollector._is_target_zone(odds)

    def test_just_above_boundary(self):
        odds = OddsContext(corner_over_odds=2.21)
        assert not ContextCollector._is_target_zone(odds)

    def test_mixed_odds(self):
        """One in zone, rest outside — should be True."""
        odds = OddsContext(
            corner_over_odds=1.10,
            corner_under_odds=1.05,
            btts_yes=1.90,
            btts_no=1.85,
        )
        assert ContextCollector._is_target_zone(odds)


# ── _collect_news_context (mocked DuckDuckGo) ─────────────────────────


class TestCollectNewsContext:
    """Verify DuckDuckGo search integration (mocked)."""

    def test_successful_search_returns_summary(self):
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch("japredictbet.data.context_collector.DDGS") as mock_ddgs_cls,
        ):
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = [
                {"title": "Notícia 1", "body": "Flamengo terá desfalques importantes."},
                {"title": "Notícia 2", "body": "Palmeiras vem de sequência positiva."},
            ]
            mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

            result = ContextCollector._collect_news_context("Flamengo", "Palmeiras", "Brasileirão Série A")

            assert result is not None
            assert "Flamengo" in result
            assert "Palmeiras" in result
            assert "desfalques" in result

    def test_empty_results_returns_none(self):
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch("japredictbet.data.context_collector.DDGS") as mock_ddgs_cls,
        ):
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = []
            mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

            result = ContextCollector._collect_news_context("A", "B")
            assert result is None

    def test_search_exception_returns_none(self):
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch("japredictbet.data.context_collector.DDGS") as mock_ddgs_cls,
        ):
            mock_ddgs_cls.side_effect = RuntimeError("Network error")

            result = ContextCollector._collect_news_context("A", "B")
            assert result is None

    def test_duckduckgo_unavailable_returns_none(self):
        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            result = ContextCollector._collect_news_context("A", "B")
            assert result is None

    def test_results_with_empty_body_skipped(self):
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch("japredictbet.data.context_collector.DDGS") as mock_ddgs_cls,
        ):
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = [
                {"title": "X", "body": ""},
                {"title": "Notícia válida", "body": "Conteúdo relevante sobre o jogo."},
            ]
            mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

            result = ContextCollector._collect_news_context("A", "B")
            assert result is not None
            assert "Conteúdo relevante" in result
            # Empty body entry should be skipped
            assert "X:" not in result

    def test_summary_truncated_at_max_chars(self):
        """Long results are truncated to ~500 chars."""
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch("japredictbet.data.context_collector.DDGS") as mock_ddgs_cls,
        ):
            mock_ddgs = MagicMock()
            long_body = "A" * 300
            mock_ddgs.text.return_value = [{"title": f"T{i}", "body": long_body} for i in range(10)]
            mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

            result = ContextCollector._collect_news_context("A", "B")
            assert result is not None
            assert len(result) <= 520  # 500 + small tolerance


# ── _enrich_news_contexts ─────────────────────────────────────────────


class TestEnrichNewsContexts:
    """Verify batch news enrichment with safety."""

    def test_enriches_target_zone_only(
        self,
        sample_context: MatchContext,
        sample_context_no_target: MatchContext,
    ):
        contexts = [sample_context, sample_context_no_target]
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch(
                "japredictbet.data.context_collector.ContextCollector._collect_news_context",
                return_value="Notícia sobre Flamengo vs Palmeiras.",
            ) as mock_collect,
        ):
            collector = _make_minimal_collector()
            collector._enrich_news_contexts(contexts)

            # Only target-zone match should trigger search
            # (sample_context_no_target has odds all outside 1.60–2.20)
            assert mock_collect.call_count == 1
            assert sample_context.news_context is not None
            assert sample_context_no_target.news_context is None

    def test_skips_already_populated(self, sample_context: MatchContext):
        sample_context.news_context = "Já populado."
        contexts = [sample_context]
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch(
                "japredictbet.data.context_collector.ContextCollector._collect_news_context",
            ) as mock_collect,
        ):
            collector = _make_minimal_collector()
            collector._enrich_news_contexts(contexts)

            mock_collect.assert_not_called()

    def test_handles_search_failure_gracefully(self, sample_context: MatchContext):
        contexts = [sample_context]
        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch(
                "japredictbet.data.context_collector.ContextCollector._collect_news_context",
                return_value=None,
            ),
        ):
            collector = _make_minimal_collector()
            collector._enrich_news_contexts(contexts)

            # Should not crash; news_context remains None
            assert sample_context.news_context is None

    def test_duckduckgo_unavailable_noop(self, sample_context: MatchContext):
        contexts = [sample_context]
        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = _make_minimal_collector()
            collector._enrich_news_contexts(contexts)

            assert sample_context.news_context is None


# ── collect_upcoming ── Superbet-only mode (mocked) ───────────────────


class TestCollectUpcomingSuperbetOnly:
    """Verify collect_upcoming() in Superbet-only mode."""

    def test_superbet_only_with_news_enrichment(self):
        snapshot = _make_snapshot("evt1", "Flamengo", "Palmeiras")
        mock_superbet = _make_mock_superbet(fetch_return={"evt1": snapshot})
        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = ContextCollector(
                superbet=mock_superbet,
                api_football=None,
                gatekeeper_cfg=GatekeeperConfig(),
            )
            contexts = collector.collect_upcoming(minutes_before=120)

            assert len(contexts) >= 1
            ctx = contexts[0]
            assert ctx.home_team == "Flamengo"
            assert ctx.away_team == "Palmeiras"

    def test_superbet_only_empty_feed(self):
        mock_superbet = _make_mock_superbet(fetch_return={})
        collector = ContextCollector(
            superbet=mock_superbet,
            api_football=None,
            gatekeeper_cfg=GatekeeperConfig(),
        )
        contexts = collector.collect_upcoming()
        assert contexts == []


# ── collect_upcoming ── Full mode (mocked) ────────────────────────────


class TestCollectUpcomingFullMode:
    """Verify collect_upcoming() with API-Football + Superbet."""

    def test_full_mode_basic(self):
        fixture = _make_api_football_fixture(100, "Flamengo", "Palmeiras")
        snapshot = _make_snapshot("evt1", "Flamengo", "Palmeiras")
        mock_superbet = _make_mock_superbet(fetch_return={"evt1": snapshot})
        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups=_make_api_lineups_response(),
            injuries=_make_api_injuries_response(),
            standings=_STANDINGS_ROWS,
        )

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = ContextCollector(
                superbet=mock_superbet,
                api_football=api_client,
                gatekeeper_cfg=GatekeeperConfig(),
            )
            contexts = collector.collect_upcoming(minutes_before=120)

        assert len(contexts) >= 1
        ctx = contexts[0]
        assert ctx.home_team == "Flamengo"
        assert ctx.away_team == "Palmeiras"
        assert ctx.home_lineup is not None
        assert ctx.away_lineup is not None
        assert ctx.home_lineup.formation == "4-4-2"  # type: ignore[union-attr]
        assert ctx.home_standing is not None
        assert ctx.home_standing.rank == 1  # type: ignore[union-attr]

    def test_full_mode_lineups_fail_safe(self):
        """Pipeline survives when lineups API fails."""
        fixture = _make_api_football_fixture(100, "Flamengo", "Palmeiras")
        snapshot = _make_snapshot("evt1", "Flamengo", "Palmeiras")
        mock_superbet = _make_mock_superbet(fetch_return={"evt1": snapshot})

        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups_side_effect=RuntimeError("Timeout"),
        )

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = ContextCollector(
                superbet=mock_superbet,
                api_football=api_client,
                gatekeeper_cfg=GatekeeperConfig(),
            )
            contexts = collector.collect_upcoming(minutes_before=120)

        assert len(contexts) >= 1
        ctx = contexts[0]
        # Lineups should be None (fail-safe)
        assert ctx.home_lineup is None

    def test_full_mode_standings_2025_returns_none(self):
        """Standings > 2024 are None — free-tier API cap."""
        kickoff_future = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        fixture = _make_api_football_fixture(
            100,
            "Flamengo",
            "Palmeiras",
            league_id=71,
            kickoff=kickoff_future,
        )
        fixture["league"]["season"] = 2025  # type: ignore[index]
        snapshot = _make_snapshot("evt1", "Flamengo", "Palmeiras")
        mock_superbet = _make_mock_superbet(fetch_return={"evt1": snapshot})

        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups=_make_api_lineups_response(),
            injuries=_make_api_injuries_response(),
            standings=[],  # empty standings
        )

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = ContextCollector(
                superbet=mock_superbet,
                api_football=api_client,
                gatekeeper_cfg=GatekeeperConfig(),
            )
            contexts = collector.collect_upcoming(minutes_before=120)

        assert len(contexts) >= 1
        ctx = contexts[0]
        assert ctx.home_standing is None

    def test_full_mode_empty_fixtures(self):
        mock_superbet = _make_mock_superbet(fetch_return={})
        api_client = _make_mock_api_client(fixtures=[])

        collector = ContextCollector(
            superbet=mock_superbet,
            api_football=api_client,
            gatekeeper_cfg=GatekeeperConfig(),
        )
        contexts = collector.collect_upcoming()
        assert contexts == []

    def test_full_mode_injuries_merged(self):
        """Injuries are merged into lineup.missing_players."""
        fixture = _make_api_football_fixture(100, "Flamengo", "Palmeiras")
        snapshot = _make_snapshot("evt1", "Flamengo", "Palmeiras")
        mock_superbet = _make_mock_superbet(fetch_return={"evt1": snapshot})

        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups=_make_api_lineups_response(),
            injuries=_make_api_injuries_response(),
            standings=_STANDINGS_ROWS,
        )

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = ContextCollector(
                superbet=mock_superbet,
                api_football=api_client,
                gatekeeper_cfg=GatekeeperConfig(),
            )
            contexts = collector.collect_upcoming(minutes_before=120)

        assert len(contexts) >= 1
        ctx = contexts[0]
        assert ctx.home_lineup is not None
        assert len(ctx.home_lineup.missing_players) == 1  # type: ignore[union-attr]
        assert ctx.home_lineup.missing_players[0]["player"] == "Lesionado H"  # type: ignore[union-attr]


# ── enrich_pre_match_contexts (mocked) ────────────────────────────────


class TestEnrichPreMatchContexts:
    """Verify pre-match enrichment with API-Football data."""

    def test_no_api_client_returns_unchanged(self, sample_context: MatchContext):
        collector = _make_minimal_collector(api_football_client=None)
        result = collector.enrich_pre_match_contexts([sample_context], "2026-05-08")
        assert result is not None
        assert len(result) == 1
        assert result[0] is sample_context

    def test_enriches_with_lineups_and_standings(self, sample_context: MatchContext):
        fixture = _make_api_football_fixture(
            100,
            "Flamengo",
            "Palmeiras",
            kickoff="2026-05-08T20:00:00+00:00",
        )
        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups=_make_api_lineups_response(),
            injuries=_make_api_injuries_response(),
            standings=_STANDINGS_ROWS,
        )

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = _make_minimal_collector(api_football_client=api_client)
            result = collector.enrich_pre_match_contexts([sample_context], "2026-05-08")

        assert len(result) == 1
        ctx = result[0]
        assert ctx.home_lineup is not None
        assert ctx.home_standing is not None
        assert ctx.home_standing.rank == 1  # type: ignore[union-attr]

    def test_no_matching_fixture(self, sample_context: MatchContext):
        """No fixture matched — context unchanged."""
        fixture = _make_api_football_fixture(100, "Santos", "Corinthians")
        api_client = _make_mock_api_client(fixtures=[fixture])

        with patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", False):
            collector = _make_minimal_collector(api_football_client=api_client)
            result = collector.enrich_pre_match_contexts([sample_context], "2026-05-08")

        assert result[0].home_lineup is None

    def test_enrich_news_integration(self, sample_context: MatchContext):
        """News enrichment fires after pre-match enrichment."""
        fixture = _make_api_football_fixture(100, "Flamengo", "Palmeiras")
        api_client = _make_mock_api_client(
            fixtures=[fixture],
            lineups=_make_api_lineups_response(),
            injuries=_make_api_injuries_response(),
            standings=_STANDINGS_ROWS,
        )

        with (
            patch("japredictbet.data.context_collector._DUCKDUCKGO_AVAILABLE", True),
            patch(
                "japredictbet.data.context_collector.ContextCollector._collect_news_context",
                return_value="Notícia de derby.",
            ),
        ):
            collector = _make_minimal_collector(api_football_client=api_client)
            result = collector.enrich_pre_match_contexts([sample_context], "2026-05-08")

        ctx = result[0]
        assert ctx.news_context == "Notícia de derby."


# ── API-Football Client Edge Cases ────────────────────────────────────


class TestApiFootballClientEdgeCases:
    """Edge cases for ApiFootballClient HTTP handling."""

    def test_http_500_raises(self):
        client = _make_api_client_with_response(status_code=500, text="Server Error")
        with pytest.raises(httpx.HTTPStatusError):
            client.get_fixtures_today()

    def test_http_429_raises(self):
        client = _make_api_client_with_response(status_code=429, text="Rate Limited")
        with pytest.raises(httpx.HTTPStatusError):
            client.get_fixtures_today()

    def test_invalid_json_raises(self):
        client = _make_api_client_with_response(status_code=200, text="Not JSON at all")
        with pytest.raises(json.JSONDecodeError):
            client.get_fixtures_today()

    def test_api_errors_in_response(self):
        """API-Football returns errors key — still returns the dict."""
        client = _make_api_client_with_response(
            status_code=200,
            json_body={"errors": {"rate": "Limit reached"}, "response": []},
        )
        result = client.get_fixtures_today()
        assert result == []

    def test_get_lineups_empty(self):
        client = _make_api_client_with_response(
            status_code=200,
            json_body={"response": []},
        )
        result = client.get_lineups(123)
        assert result == {}

    def test_get_injuries_empty(self):
        client = _make_api_client_with_response(
            status_code=200,
            json_body={"response": []},
        )
        result = client.get_injuries(123)
        assert result == []

    def test_get_standings_empty(self):
        client = _make_api_client_with_response(
            status_code=200,
            json_body={"response": []},
        )
        result = client.get_standings(71, 2024)
        assert result == []

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="API-Football key is empty"):
            ApiFootballClient("", ApiFootballConfig())


# ── Helper functions ──────────────────────────────────────────────────


class TestModuleHelpers:
    """Tests for module-level helper functions."""

    def test_merge_injuries_matching_team(self):
        from japredictbet.data.context_collector import TeamLineup

        lineup = TeamLineup()
        injuries = [
            {"player": "P1", "team": "Flamengo", "type": "Injury", "reason": "Knee"},
        ]
        _merge_injuries(injuries, "Flamengo", lineup)
        assert len(lineup.missing_players) == 1
        assert lineup.missing_players[0]["player"] == "P1"

    def test_merge_injuries_non_matching_team(self):
        from japredictbet.data.context_collector import TeamLineup

        lineup = TeamLineup()
        injuries = [
            {"player": "P1", "team": "Palmeiras", "type": "Injury", "reason": "Knee"},
        ]
        _merge_injuries(injuries, "Flamengo", lineup)
        assert len(lineup.missing_players) == 0

    def test_merge_injuries_none_lineup(self):
        _merge_injuries([{"player": "P", "team": "X"}], "X", None)
        # Should not raise

    def test_find_standing_match(self):
        from japredictbet.data.context_collector import StandingsEntry

        standings = [
            StandingsEntry(rank=1, team="Flamengo", points=30, played=10, goal_diff=15),
        ]
        result = _find_standing(standings, "Flamengo")
        assert result is not None
        assert result.rank == 1

    def test_find_standing_none(self):
        result = _find_standing([], "AnyTeam")
        assert result is None


# ── ContextCollector.from_configs ─────────────────────────────────────


class TestContextCollectorFromConfigs:
    """Verify factory method behavior."""

    def test_superbet_only_when_no_api_key(self):
        with patch.object(SuperbetCollector, "fetch_today_odds", return_value={}):
            collector = ContextCollector.from_configs(
                superbet_cfg=SuperbetShadowConfig(),
                api_football_cfg=ApiFootballConfig(),
                gatekeeper_cfg=GatekeeperConfig(),
                api_football_key="",
            )
            # Should not raise; API client should be None internally
            assert collector._api is None  # type: ignore[union-attr]

    def test_with_api_key_creates_client(self):
        with patch.object(SuperbetCollector, "fetch_today_odds", return_value={}):
            collector = ContextCollector.from_configs(
                superbet_cfg=SuperbetShadowConfig(),
                api_football_cfg=ApiFootballConfig(),
                gatekeeper_cfg=GatekeeperConfig(),
                api_football_key="fake-key-123",
            )
            assert collector._api is not None  # type: ignore[union-attr]


# ── Helpers ───────────────────────────────────────────────────────────


def _make_minimal_collector(
    api_football_client: ApiFootballClient | None = None,
) -> ContextCollector:
    """Build a ContextCollector with a fully mocked SuperbetCollector.

    The mock superbet has fetch_today_odds returning an empty dict by
    default — individual tests should create their own ContextCollector
    with a custom mock when they need specific snapshot data.
    """
    mock_superbet = _make_mock_superbet()
    return ContextCollector(
        superbet=mock_superbet,
        api_football=api_football_client,
        gatekeeper_cfg=GatekeeperConfig(),
    )


def _make_mock_superbet(
    fetch_return: dict[str, SuperbetSnapshot] | None = None,
) -> SuperbetCollector:
    """Create a SuperbetCollector mock whose fetch_today_odds returns controlled data."""
    mock = MagicMock(spec=SuperbetCollector)
    mock.fetch_today_odds.return_value = fetch_return or {}
    # enrich_snapshots_with_rest is identity by default
    mock.enrich_snapshots_with_rest.side_effect = lambda snapshots: snapshots
    return mock


def _make_mock_api_client(
    fixtures: list[dict] | None = None,
    lineups: dict | None = None,
    injuries: dict | None = None,
    standings: list | None = None,
    lineups_side_effect: Exception | None = None,
) -> ApiFootballClient:
    """Create an ApiFootballClient with mocked _get method.

    Standings should be a plain list of rows (e.g., _STANDINGS_ROWS).
    The mock wraps them in the API-Football envelope automatically.
    """
    client = ApiFootballClient(api_key="test-key", cfg=ApiFootballConfig())

    def _mock_get(endpoint: str, params: dict):
        if lineups_side_effect and "lineups" in endpoint and "headtohead" not in endpoint:
            raise lineups_side_effect
        if "lineups" in endpoint and "headtohead" not in endpoint:
            return lineups or {"response": []}
        if "injuries" in endpoint:
            return injuries or {"response": []}
        if "standings" in endpoint:
            resp = standings or []
            return {"response": [{"league": {"standings": [resp]}}]} if resp else {"response": []}
        if "fixtures" in endpoint:
            return {"response": fixtures or []}
        return {"response": []}

    client._get = _mock_get  # type: ignore[method-assign]
    return client


def _make_api_client_with_response(
    status_code: int = 200,
    text: str = "",
    json_body: dict | None = None,
) -> ApiFootballClient:
    """Create an ApiFootballClient with mocked httpx.Client."""
    client = ApiFootballClient(api_key="test-key", cfg=ApiFootballConfig())

    mock_response = MagicMock()
    mock_response.status_code = status_code

    if json_body is not None:
        mock_response.json.return_value = json_body
        mock_response.raise_for_status.return_value = None
    elif status_code >= 400:
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.text = text
    else:
        mock_response.json.side_effect = json.JSONDecodeError("bad json", text, 0)
        mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_response
    mock_client.__enter__.return_value.post.return_value = mock_response

    def _mock_get(endpoint: str, params: dict):
        with mock_client as c:
            resp = c.get("http://fake", params=params)
            resp.raise_for_status()
            return resp.json()

    client._get = _mock_get  # type: ignore[method-assign]
    return client
