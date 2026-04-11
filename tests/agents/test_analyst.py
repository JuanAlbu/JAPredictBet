"""Tests for the Analyst agent (agents/analyst.py).

Covers:
- Pre-filter (min_odd on non-corner markets)
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
    """Patch OpenAI client globally so AnalystAgent can be instantiated."""
    with patch("japredictbet.agents.analyst.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def agent(gk_cfg, mock_openai):
    from japredictbet.agents.analyst import AnalystAgent

    return AnalystAgent(gatekeeper_cfg=gk_cfg, api_key="sk-test-key")


def _make_match_context(
    home: str = "Flamengo",
    away: str = "Palmeiras",
    home_odds: float = 2.10,
    draw_odds: float = 3.20,
    away_odds: float = 3.50,
    btts_yes: float = 1.85,
    btts_no: float = 1.95,
    corner_line: float = 9.5,
    corner_over_odds: float = 1.85,
    corner_under_odds: float = 1.95,
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
                "btts_yes": btts_yes,
                "btts_no": btts_no,
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


class TestAnalystPreFilter:
    """Test the Python hard-filter for non-corner markets."""

    def test_no_non_corner_odds_returns_filtered(self, agent):
        ctx = json.dumps(
            {
                "event_id": "1",
                "home_team": "A",
                "away_team": "B",
                "odds": {
                    "corner_line": 9.5,
                    "corner_over_odds": 1.85,
                    "corner_under_odds": 1.95,
                    "home_odds": None,
                    "draw_odds": None,
                    "away_odds": None,
                    "btts_yes": None,
                    "btts_no": None,
                },
            }
        )
        result = agent.evaluate_match(ctx)
        assert result.status == "FILTERED"

    def test_all_non_corner_below_min_returns_filtered(self, agent):
        ctx = _make_match_context(
            home_odds=1.10,
            draw_odds=1.20,
            away_odds=1.30,
            btts_yes=1.40,
            btts_no=1.50,
        )
        result = agent.evaluate_match(ctx)
        assert result.status == "FILTERED"

    def test_one_non_corner_above_min_passes_filter(self, agent, mock_openai):
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context(
            home_odds=1.50,
            draw_odds=1.50,
            away_odds=1.70,  # Above min
            btts_yes=1.40,
            btts_no=1.50,
        )
        result = agent.evaluate_match(ctx)
        assert result.status != "FILTERED"

    def test_invalid_json_returns_error(self, agent):
        result = agent.evaluate_match("not-valid-json")
        assert result.status == "ERROR"


# ── Prompt construction tests ────────────────────────────────────────


class TestAnalystPrompt:
    """Test that the user prompt is correctly constructed."""

    def test_prompt_excludes_corners_instruction(self, agent, mock_openai):
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context()
        agent.evaluate_match(ctx)

        call_args = mock_openai.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "escanteios" in user_msg.lower()
        assert "1x2" in user_msg or "Resultado Final" in user_msg

    def test_prompt_uses_analyst_system_prompt(self, agent, mock_openai):
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context()
        agent.evaluate_match(ctx)

        call_args = mock_openai.chat.completions.create.call_args
        system_msg = call_args[1]["messages"][0]["content"]
        # System prompt should be loaded (not empty)
        assert len(system_msg) > 50

    def test_no_ensemble_output_in_prompt(self, agent, mock_openai):
        """Analyst should NOT receive ensemble output (corners only)."""
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context()
        agent.evaluate_match(ctx)

        call_args = mock_openai.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "ensemble" not in user_msg.lower()
        assert "consensus" not in user_msg.lower()


# ── Response parsing tests ───────────────────────────────────────────


class TestAnalystParsing:
    """Test LLM response parsing."""

    def test_valid_response_with_approved_market(self, agent, mock_openai):
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "1x2 HOME",
                        "status": "APPROVED",
                        "stake": 1.0,
                        "odd": 2.10,
                        "edge": "Médio",
                        "justification": "Flamengo superior em casa",
                        "red_flags": [],
                    },
                    {
                        "market": "BTTS SIM",
                        "status": "NO BET",
                        "stake": None,
                        "odd": 1.85,
                        "edge": None,
                        "justification": "Palmeiras defensivo fora",
                        "red_flags": ["escalação incerta"],
                    },
                ],
                "best_pick": {
                    "market": "1x2 HOME",
                    "status": "APPROVED",
                    "stake": 1.0,
                    "odd": 2.10,
                    "edge": "Médio",
                    "justification": "Melhor entrada",
                    "red_flags": [],
                },
            }
        )
        _mock_llm_response(mock_openai, response)
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.status == "APPROVED"
        assert len(result.markets) == 2
        assert result.markets[0].market == "1x2 HOME"
        assert result.markets[0].status == "APPROVED"
        assert result.markets[0].stake == 1.0
        assert result.markets[1].market == "BTTS SIM"
        assert result.markets[1].status == "NO BET"
        assert result.best_pick is not None
        assert result.best_pick.market == "1x2 HOME"

    def test_valid_response_no_approved_markets(self, agent, mock_openai):
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "1x2 HOME",
                        "status": "NO BET",
                        "justification": "sem cenário",
                        "red_flags": ["rotação"],
                    }
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.status == "NO BET"
        assert len(result.markets) == 1
        assert result.best_pick is None

    def test_empty_markets_response(self, agent, mock_openai):
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.status == "NO BET"
        assert len(result.markets) == 0
        assert result.best_pick is None

    def test_malformed_json_returns_error(self, agent, mock_openai):
        _mock_llm_response(mock_openai, "not valid json {{{")
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.status == "ERROR"

    def test_stake_clamped_to_valid_range(self, agent, mock_openai):
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "1x2 HOME",
                        "status": "APPROVED",
                        "stake": 5.0,
                        "odd": 2.10,
                    }
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.markets[0].stake == 2.0  # Clamped to max

    def test_invalid_status_defaults_to_no_bet(self, agent, mock_openai):
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "1x2 HOME",
                        "status": "MAYBE",
                        "stake": 1.0,
                        "odd": 2.10,
                    }
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.markets[0].status == "NO BET"


# ── BaseAgent contract ───────────────────────────────────────────────


class TestAnalystBaseAgentContract:
    """Test the ``run()`` method follows BaseAgent contract."""

    def test_run_returns_dict_with_expected_keys(self, agent, mock_openai):
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "BTTS SIM",
                        "status": "APPROVED",
                        "stake": 0.5,
                        "odd": 1.85,
                        "edge": "Baixo",
                        "justification": "Ambos ofensivos",
                        "red_flags": [],
                    }
                ],
                "best_pick": {
                    "market": "BTTS SIM",
                    "status": "APPROVED",
                    "stake": 0.5,
                    "odd": 1.85,
                    "edge": "Baixo",
                    "justification": "Ambos ofensivos",
                    "red_flags": [],
                },
            }
        )
        _mock_llm_response(mock_openai, response)
        ctx = _make_match_context()

        context = AgentContext(payload={"match_context_json": ctx})
        raw = agent.run(context)

        assert "status" in raw
        assert "markets" in raw
        assert "best_pick" in raw
        assert isinstance(raw["markets"], list)

    def test_name_is_analyst(self, agent):
        assert agent.name == "analyst"


# ── LLM failure handling ────────────────────────────────────────────


class TestAnalystLLMFailures:
    """Test error handling when LLM calls fail."""

    def test_llm_exception_returns_error(self, agent, mock_openai):
        mock_openai.chat.completions.create.side_effect = Exception("API down")
        ctx = _make_match_context()

        result = agent.evaluate_match(ctx)
        assert result.status == "ERROR"

    def test_llm_returns_none_content(self, agent, mock_openai):
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai.chat.completions.create.return_value = mock_response

        ctx = _make_match_context()
        result = agent.evaluate_match(ctx)
        assert result.status == "ERROR"
