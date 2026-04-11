"""Tests for the Gatekeeper agent (agents/gatekeeper.py).

Covers:
- Pre-filter (min_odd) logic
- LLM prompt construction
- Response parsing (valid/invalid JSON, edge cases)
- BaseAgent contract (run method)
- Error handling (LLM failures, malformed context)

All tests mock the OpenAI client — no real API calls are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from japredictbet.agents.base import AgentContext
from japredictbet.config import GatekeeperConfig


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def gk_cfg() -> GatekeeperConfig:
    return GatekeeperConfig(min_odd=1.60, max_entries_per_day=5)


@pytest.fixture
def mock_openai():
    """Patch OpenAI client globally so GatekeeperAgent can be instantiated."""
    with patch("japredictbet.agents.gatekeeper.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def agent(gk_cfg, mock_openai):
    from japredictbet.agents.gatekeeper import GatekeeperAgent

    return GatekeeperAgent(gatekeeper_cfg=gk_cfg, api_key="sk-test-key")


def _make_match_context(
    home: str = "Flamengo",
    away: str = "Palmeiras",
    corner_over_odds: float = 1.85,
    corner_under_odds: float = 1.95,
    corner_line: float = 9.5,
    home_odds: float = 2.10,
    draw_odds: float = 3.20,
    away_odds: float = 3.50,
) -> str:
    """Build a minimal MatchContext JSON string for testing."""
    return json.dumps(
        {
            "event_id": "12345",
            "home_team": home,
            "away_team": away,
            "kickoff_utc": "2026-04-11T20:00:00Z",
            "league": "Brasileirão",
            "odds": {
                "corner_line": corner_line,
                "corner_over_odds": corner_over_odds,
                "corner_under_odds": corner_under_odds,
                "home_odds": home_odds,
                "draw_odds": draw_odds,
                "away_odds": away_odds,
                "btts_yes": None,
                "btts_no": None,
            },
        }
    )


def _mock_llm_response(mock_client: MagicMock, content: str) -> None:
    """Configure the mock OpenAI client to return *content*."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response


# ── Pre-filter tests ─────────────────────────────────────────────────


class TestPreFilter:
    """Test the Python hard-filter before LLM call."""

    def test_all_odds_below_min_returns_filtered(self, agent):
        ctx = _make_match_context(
            corner_over_odds=1.40,
            corner_under_odds=1.50,
            home_odds=1.10,
            draw_odds=1.20,
            away_odds=1.30,
        )
        result = agent.evaluate_match(ctx)
        assert result.status == "FILTERED"
        assert "1.60" in result.justification

    def test_one_odd_above_min_passes_filter(self, agent, mock_openai):
        _mock_llm_response(
            mock_openai,
            json.dumps({"status": "NO BET", "justification": "Sem cenário"}),
        )
        ctx = _make_match_context(
            corner_over_odds=1.85,  # above 1.60
            corner_under_odds=1.40,
            home_odds=1.10,
            draw_odds=1.20,
            away_odds=1.30,
        )
        result = agent.evaluate_match(ctx)
        assert result.status != "FILTERED"

    def test_invalid_json_context_returns_error(self, agent):
        result = agent.evaluate_match("not valid json {{")
        assert result.status == "ERROR"

    def test_empty_odds_returns_filtered(self, agent):
        ctx = json.dumps(
            {"event_id": "1", "home_team": "A", "away_team": "B", "odds": {}}
        )
        result = agent.evaluate_match(ctx)
        assert result.status == "FILTERED"


# ── LLM response parsing ────────────────────────────────────────────


class TestResponseParsing:
    """Test _parse_response with various LLM outputs."""

    def test_approved_response(self, agent, mock_openai):
        llm_output = json.dumps(
            {
                "status": "APPROVED",
                "stake": 1.0,
                "market": "Total de Escanteios Over 9.5",
                "odd": 1.85,
                "edge": "Médio",
                "justification": "Cenário estável com padrão sustentável.",
                "red_flags": [],
            }
        )
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "APPROVED"
        assert result.stake == 1.0
        assert result.market == "Total de Escanteios Over 9.5"
        assert result.odd == 1.85
        assert result.edge == "Médio"
        assert result.red_flags == []

    def test_no_bet_response(self, agent, mock_openai):
        llm_output = json.dumps(
            {
                "status": "NO BET",
                "justification": "Escalação incerta, 2 red flags.",
                "red_flags": ["escalação incerta", "linha esticada"],
            }
        )
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "NO BET"
        assert result.stake is None
        assert len(result.red_flags) == 2

    def test_malformed_llm_json_returns_error(self, agent, mock_openai):
        _mock_llm_response(mock_openai, "this is not json at all")
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "ERROR"
        assert "parse" in (result.justification or "").lower()

    def test_unexpected_status_defaults_to_no_bet(self, agent, mock_openai):
        llm_output = json.dumps({"status": "MAYBE", "justification": "Hmm"})
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "NO BET"

    def test_stake_clamped_to_valid_range(self, agent, mock_openai):
        llm_output = json.dumps(
            {"status": "APPROVED", "stake": 5.0, "justification": "Strong"}
        )
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.stake == 2.0  # clamped to max

    def test_stake_below_minimum(self, agent, mock_openai):
        llm_output = json.dumps(
            {"status": "APPROVED", "stake": 0.1, "justification": "Weak"}
        )
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.stake == 0.5  # clamped to min


# ── LLM call failure ────────────────────────────────────────────────


class TestLLMFailure:
    """Test graceful handling when LLM call raises an exception."""

    def test_llm_exception_returns_error(self, agent, mock_openai):
        mock_openai.chat.completions.create.side_effect = RuntimeError(
            "API down"
        )
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "ERROR"
        assert "failed" in (result.justification or "").lower()


# ── BaseAgent contract ───────────────────────────────────────────────


class TestBaseAgentContract:
    """Test that GatekeeperAgent fulfils the BaseAgent contract."""

    def test_name_attribute(self, agent):
        assert agent.name == "gatekeeper"

    def test_run_method(self, agent, mock_openai):
        llm_output = json.dumps(
            {"status": "NO BET", "justification": "Test via run()"}
        )
        _mock_llm_response(mock_openai, llm_output)
        context = AgentContext(
            payload={"match_context_json": _make_match_context()}
        )
        result = agent.run(context)
        assert isinstance(result, dict)
        assert result["status"] == "NO BET"


# ── Constructor validation ───────────────────────────────────────────


class TestConstructor:
    """Test GatekeeperAgent constructor validation."""

    def test_missing_api_key_raises(self, gk_cfg):
        with patch("japredictbet.agents.gatekeeper.OpenAI"):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="API key"):
                    from japredictbet.agents.gatekeeper import GatekeeperAgent

                    GatekeeperAgent(gatekeeper_cfg=gk_cfg, api_key="")
