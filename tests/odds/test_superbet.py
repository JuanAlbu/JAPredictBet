"""Tests for the Superbet SSE client (odds/superbet_client.py).

Covers:
- SSE multi-event parsing
- Malformed JSON tolerance
- Team name parsing (middle dot separator)
- Market detection (corners, match odds, BTTS)
- Odds extraction from selections
- Non-football event filtering
- Dataclass construction
"""

from __future__ import annotations

import json

import pytest

from japredictbet.config import SuperbetShadowConfig
from japredictbet.odds.superbet_client import (
    SuperbetCollector,
    SuperbetOdds,
    SuperbetSnapshot,
    _extract_odds_from_selections,
    _is_btts_market,
    _is_corner_market,
    _is_match_odds_market,
    _iter_sse_events,
    _parse_team_names,
)


@pytest.fixture
def default_cfg() -> SuperbetShadowConfig:
    return SuperbetShadowConfig()


# ── SSE Parsing ──────────────────────────────────────────────────────


class TestIterSseEvents:
    """Test _iter_sse_events line-by-line SSE parser."""

    def _wrap(self, inner: dict) -> str:
        """Wrap an inner event dict in the real Superbet SSE envelope."""
        outer = {"resourceId": "event:1", "timestamp": 0, "data": inner}
        return f"data:{json.dumps(outer)}\n"

    def test_single_data_line(self):
        payload = {"id": 1, "sportId": 5, "matchName": "Time A\u00b7Time B"}
        raw_text = self._wrap(payload)
        events = list(_iter_sse_events(raw_text))
        assert len(events) == 1
        assert events[0]["id"] == 1

    def test_multiple_events(self):
        payloads = [
            {"id": i, "sportId": 5, "matchName": f"Home{i}\u00b7Away{i}"}
            for i in range(3)
        ]
        raw_text = "\n".join(
            f"data:{json.dumps({'resourceId': 'event:' + str(p['id']), 'timestamp': 0, 'data': p})}"
            for p in payloads
        ) + "\n"
        events = list(_iter_sse_events(raw_text))
        assert len(events) == 3

    def test_malformed_json_skipped(self):
        valid_outer = json.dumps({"resourceId": "e:1", "timestamp": 0, "data": {"id": 1, "sportId": 5}})
        raw_text = f'data:{{invalid json}}\ndata:{valid_outer}\n'
        events = list(_iter_sse_events(raw_text))
        assert len(events) == 1
        assert events[0]["id"] == 1

    def test_retry_and_empty_lines_ignored(self):
        outer = json.dumps({"resourceId": "e:1", "timestamp": 0, "data": {"id": 1}})
        raw_text = f'retry:1000\n\ndata:{outer}\n\n'
        events = list(_iter_sse_events(raw_text))
        assert len(events) == 1

    def test_empty_input(self):
        events = list(_iter_sse_events(""))
        assert events == []


# ── Team Name Parsing ────────────────────────────────────────────────


class TestParseTeamNames:
    """Test _parse_team_names with middle-dot separator."""

    def test_standard_separator(self):
        home, away = _parse_team_names("Flamengo\u00b7Palmeiras")
        assert home == "Flamengo"
        assert away == "Palmeiras"

    def test_no_separator_raises(self):
        with pytest.raises(ValueError, match="Cannot split"):
            _parse_team_names("SingleTeamName")

    def test_whitespace_stripped(self):
        home, away = _parse_team_names(" Flamengo \u00b7 Palmeiras ")
        assert home == "Flamengo"
        assert away == "Palmeiras"

    def test_three_parts_raises(self):
        with pytest.raises(ValueError, match="Cannot split"):
            _parse_team_names("A\u00b7B\u00b7C")


# ── Market Detection ─────────────────────────────────────────────────


class TestMarketDetection:
    """Test _is_corner_market, _is_match_odds_market, _is_btts_market."""

    def test_corner_market(self, default_cfg: SuperbetShadowConfig):
        assert _is_corner_market("Total de Escanteios", default_cfg) is True
        assert _is_corner_market("Total de Gols", default_cfg) is False

    def test_match_odds_market(self):
        assert _is_match_odds_market("Resultado Final") is True
        assert _is_match_odds_market("1x2") is True
        assert _is_match_odds_market("Ambas Marcam") is False

    def test_btts_market(self):
        assert _is_btts_market("Ambas Marcam") is True
        assert _is_btts_market("BTTS") is True
        assert _is_btts_market("Total de Gols") is False


# ── Odds Extraction ─────────────────────────────────────────────────


class TestOddsExtraction:
    """Test _extract_odds_from_selections."""

    def test_over_under(self):
        sels = [
            {"code": "over", "name": "Over", "price": 1.85},
            {"code": "under", "name": "Under", "price": 1.95},
        ]
        result = _extract_odds_from_selections(sels)
        assert result["over"] == 1.85
        assert result["under"] == 1.95

    def test_home_draw_away(self):
        sels = [
            {"code": "1", "name": "Home", "price": 2.10},
            {"code": "x", "name": "Draw", "price": 3.20},
            {"code": "2", "name": "Away", "price": 3.50},
        ]
        result = _extract_odds_from_selections(sels)
        assert result["home"] == 2.10
        assert result["draw"] == 3.20
        assert result["away"] == 3.50

    def test_yes_no(self):
        sels = [
            {"code": "yes", "name": "Sim", "price": 1.70},
            {"code": "no", "name": "Não", "price": 2.10},
        ]
        result = _extract_odds_from_selections(sels)
        assert result["yes"] == 1.70
        assert result["no"] == 2.10

    def test_invalid_price_becomes_none(self):
        sels = [{"code": "over", "name": "Over", "price": "invalid"}]
        result = _extract_odds_from_selections(sels)
        assert result["over"] is None

    def test_empty_selections(self):
        result = _extract_odds_from_selections([])
        assert result == {}


# ── Non-Football Filtering ───────────────────────────────────────────


class TestSportFiltering:
    """Ensure non-football events (sportId != 5) are present in SSE parse."""

    def test_basketball_event_parsed(self):
        inner = {"id": 99, "sportId": 2, "matchName": "Lakers\u00b7Celtics"}
        outer = {"resourceId": "event:99", "timestamp": 0, "data": inner}
        raw_text = f"data:{json.dumps(outer)}\n"
        events = list(_iter_sse_events(raw_text))
        assert len(events) == 1
        assert events[0]["sportId"] == 2


# ── Dataclass Construction ───────────────────────────────────────────


class TestDataclasses:
    """Test SuperbetOdds and SuperbetSnapshot dataclass creation."""

    def test_superbet_odds_creation(self):
        odds = SuperbetOdds(
            event_id="123",
            home_team="Flamengo",
            away_team="Palmeiras",
            market_name="Total de Escanteios",
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
        assert odds.event_id == "123"
        assert odds.over_odds == 1.85

    def test_superbet_snapshot_creation(self):
        snap = SuperbetSnapshot(
            event_id="456",
            home_team="Corinthians",
            away_team="São Paulo",
        )
        assert snap.event_id == "456"
        assert snap.corners == []

    def test_collector_construction(self, default_cfg: SuperbetShadowConfig):
        collector = SuperbetCollector(default_cfg)
        assert collector._cfg == default_cfg
