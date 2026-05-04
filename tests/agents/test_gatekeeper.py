"""Tests for the Gatekeeper agent (agents/gatekeeper.py).

Covers:
- Pre-filter (min_odd) logic for ALL markets (corners + non-corners)
- LLM prompt construction (Prompt Mestre V26)
- Response parsing – legacy single-market + V26 multi-market
- Markdown-fence stripping in JSON parsing
- GatekeeperResult properties (markets_evaluated, markets_approved)
- BaseAgent contract (run method)
- Error handling (LLM failures, malformed context)

All tests mock the OpenAI client — no real API calls are made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from japredictbet.agents.base import AgentContext
from japredictbet.agents.gatekeeper import MarketEvaluation
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
    btts_yes: float | None = None,
    btts_no: float | None = None,
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


class TestPreFilter:
    """Test the Python hard-filter before LLM call."""

    def test_all_odds_below_min_returns_filtered(self, agent):
        ctx = _make_match_context(
            corner_over_odds=1.40,
            corner_under_odds=1.50,
            home_odds=1.10,
            draw_odds=1.20,
            away_odds=1.30,
            btts_yes=1.40,
            btts_no=1.20,
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

    def test_one_non_corner_odd_above_min_passes_filter(self, agent, mock_openai):
        """Pre-filter checks ALL odds (corners + non-corners)."""
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        ctx = _make_match_context(
            corner_over_odds=1.40,
            corner_under_odds=1.50,
            home_odds=1.65,  # above 1.60 — non-corner
            draw_odds=1.20,
            away_odds=1.30,
        )
        result = agent.evaluate_match(ctx)
        assert result.status != "FILTERED"

    def test_invalid_json_context_returns_error(self, agent):
        result = agent.evaluate_match("not valid json {{")
        assert result.status == "ERROR"

    def test_empty_odds_returns_filtered(self, agent):
        ctx = json.dumps({"event_id": "1", "home_team": "A", "away_team": "B", "odds": {}})
        result = agent.evaluate_match(ctx)
        assert result.status == "FILTERED"


# ── LLM response parsing (legacy single-market) ──────────────────────


class TestResponseParsing:
    """Test _parse_response with legacy single-market LLM outputs."""

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
        llm_output = json.dumps({"status": "APPROVED", "stake": 5.0, "justification": "Strong"})
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.stake == 2.0  # clamped to max

    def test_stake_below_minimum(self, agent, mock_openai):
        llm_output = json.dumps({"status": "APPROVED", "stake": 0.1, "justification": "Weak"})
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.stake == 0.5  # clamped to min


# ── V26 Multi-market response parsing ────────────────────────────────


class TestMultiMarketParsing:
    """Test _parse_response with V26 multi-market format (markets array + best_pick)."""

    def test_multi_market_approved_with_best_pick(self, agent, mock_openai):
        """Parse V26 response with multiple markets and a best_pick."""
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "Escanteios Over 9.5",
                        "status": "APPROVED",
                        "stake": 1.0,
                        "odd": 2.10,
                        "edge": "Médio",
                        "classification": "APOSTA SIMPLES",
                        "justification": "Pressão alta dos dois lados",
                        "red_flags": [],
                    },
                    {
                        "market": "1x2 HOME",
                        "status": "NO BET",
                        "stake": None,
                        "odd": 1.85,
                        "edge": None,
                        "classification": None,
                        "justification": "Escalação incerta",
                        "red_flags": ["escalação incerta"],
                    },
                    {
                        "market": "BTTS SIM",
                        "status": "APPROVED",
                        "stake": 0.5,
                        "odd": 1.80,
                        "edge": "Baixo",
                        "classification": "PERNA DE COMPOSIÇÃO",
                        "justification": "Ambos marcam com frequência",
                        "red_flags": [],
                    },
                ],
                "best_pick": {
                    "market": "Escanteios Over 9.5",
                    "status": "APPROVED",
                    "stake": 1.0,
                    "odd": 2.10,
                    "edge": "Médio",
                    "classification": "APOSTA SIMPLES",
                    "justification": "Melhor valor global",
                    "red_flags": [],
                },
            }
        )
        _mock_llm_response(mock_openai, response)
        result = agent.evaluate_match(_make_match_context())

        assert result.status == "APPROVED"
        assert result.stake == 1.0
        assert result.market == "Escanteios Over 9.5"
        assert result.odd == 2.10
        assert result.edge == "Médio"
        assert result.classification == "APOSTA SIMPLES"

        # Markets array intact
        assert len(result.markets) == 3
        assert result.markets_evaluated == 3
        assert result.markets_approved == 2

        assert isinstance(result.markets[0], MarketEvaluation)
        assert result.markets[0].market == "Escanteios Over 9.5"
        assert result.markets[0].status == "APPROVED"
        assert result.markets[0].stake == 1.0
        assert result.markets[0].classification == "APOSTA SIMPLES"

        assert result.markets[1].market == "1x2 HOME"
        assert result.markets[1].status == "NO BET"
        assert len(result.markets[1].red_flags) == 1

        assert result.markets[2].market == "BTTS SIM"
        assert result.markets[2].status == "APPROVED"
        assert result.markets[2].stake == 0.5

        # Best pick populated
        assert result.best_pick is not None
        assert result.best_pick.market == "Escanteios Over 9.5"
        assert result.best_pick.status == "APPROVED"

    def test_multi_market_all_no_bet(self, agent, mock_openai):
        """All markets NO BET → overall NO BET, best_pick None."""
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "Escanteios Over 9.5",
                        "status": "NO BET",
                        "stake": None,
                        "odd": 1.85,
                        "edge": None,
                        "justification": "Sem pressão sustentável",
                        "red_flags": ["linha esticada"],
                    },
                    {
                        "market": "1x2 HOME",
                        "status": "NO BET",
                        "stake": None,
                        "odd": 2.10,
                        "edge": None,
                        "justification": "Risco alto",
                        "red_flags": ["desfalque"],
                    },
                    {
                        "market": "BTTS SIM",
                        "status": "NO BET",
                        "stake": None,
                        "odd": 1.80,
                        "edge": None,
                        "justification": "Defesas sólidas",
                        "red_flags": [],
                    },
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        result = agent.evaluate_match(_make_match_context())

        assert result.status == "NO BET"
        assert result.markets_evaluated == 3
        assert result.markets_approved == 0
        assert result.best_pick is None
        assert result.stake is None

    def test_multi_market_empty_markets(self, agent, mock_openai):
        """Empty markets array → NO BET."""
        _mock_llm_response(
            mock_openai,
            json.dumps({"markets": [], "best_pick": None}),
        )
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "NO BET"
        assert result.markets_evaluated == 0
        assert result.markets_approved == 0

    def test_multi_market_legacy_fallback(self, agent, mock_openai):
        """Legacy single-market response still works (backward compat)."""
        # Legacy format: plain status/stake/market/odd (no markets array)
        llm_output = json.dumps(
            {
                "status": "APPROVED",
                "stake": 1.0,
                "market": "Total de Escanteios Over 9.5",
                "odd": 2.10,
                "edge": "Alto",
                "justification": "Cenário forte",
                "red_flags": [],
            }
        )
        _mock_llm_response(mock_openai, llm_output)
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "APPROVED"
        assert result.market == "Total de Escanteios Over 9.5"
        assert result.markets_evaluated == 0  # No markets array in legacy
        assert result.best_pick is None

    def test_multi_market_stake_clamped_in_market(self, agent, mock_openai):
        """Stake in individual market entry is clamped."""
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "Over 2.5 Gols",
                        "status": "APPROVED",
                        "stake": 3.5,
                        "odd": 2.20,
                    }
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        result = agent.evaluate_match(_make_match_context())
        assert result.markets[0].stake == 2.0  # clamped to max

    def test_multi_market_invalid_status_defaults_to_no_bet(self, agent, mock_openai):
        """Market with unexpected status defaults to NO BET."""
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "1x2 EMPATE",
                        "status": "TALVEZ",
                        "stake": 1.0,
                        "odd": 3.20,
                    }
                ],
                "best_pick": None,
            }
        )
        _mock_llm_response(mock_openai, response)
        result = agent.evaluate_match(_make_match_context())
        assert result.markets[0].status == "NO BET"


# ── Markdown-fence stripping ─────────────────────────────────────────


class TestMarkdownStripping:
    """Test _strip_markdown_fences and _safe_json_parse robustness."""

    def test_strip_markdown_fences_with_json_tag(self, agent):
        """```json ... ``` is stripped correctly."""
        raw = '```json\n{"status": "NO BET", "justification": "test"}\n```'
        result = agent._parse_response(raw)
        assert result.status == "NO BET"
        assert result.justification == "test"

    def test_strip_markdown_fences_without_tag(self, agent):
        """``` ... ``` (no json tag) is stripped correctly."""
        raw = '```\n{"status": "NO BET", "justification": "test"}\n```'
        result = agent._parse_response(raw)
        assert result.status == "NO BET"
        assert result.justification == "test"

    def test_strip_markdown_fences_v26_multi_market(self, agent):
        """Markdown-fenced V26 multi-market response is parsed correctly."""
        response_dict = {
            "markets": [
                {
                    "market": "Escanteios Over 9.5",
                    "status": "APPROVED",
                    "stake": 1.0,
                    "odd": 2.10,
                    "edge": "Médio",
                    "justification": "Pressão alta",
                    "red_flags": [],
                }
            ],
            "best_pick": {
                "market": "Escanteios Over 9.5",
                "status": "APPROVED",
                "stake": 1.0,
                "odd": 2.10,
                "edge": "Médio",
                "justification": "Melhor entrada",
                "red_flags": [],
            },
        }
        raw = "```json\n" + json.dumps(response_dict) + "\n```"
        result = agent._parse_response(raw)
        assert result.status == "APPROVED"
        assert result.markets_evaluated == 1
        assert result.best_pick is not None
        assert result.best_pick.market == "Escanteios Over 9.5"

    def test_no_fences_passes_through(self, agent):
        """Plain JSON without fences parses normally."""
        raw = json.dumps({"status": "NO BET", "justification": "plain"})
        result = agent._parse_response(raw)
        assert result.status == "NO BET"
        assert result.justification == "plain"

    def test_strip_only_leading_trailing(self, agent):
        """Only leading/trailing fences are stripped; inline is preserved."""
        # The word "json" inside a justification should NOT be stripped
        raw = '```json\n{"status": "NO BET", "justification": "using json format"}\n```'
        result = agent._parse_response(raw)
        assert result.status == "NO BET"
        assert "json" in result.justification.lower()


# ── LLM call failure ────────────────────────────────────────────────


class TestLLMFailure:
    """Test graceful handling when LLM call raises an exception."""

    def test_llm_exception_returns_error(self, agent, mock_openai):
        mock_openai.chat.completions.create.side_effect = RuntimeError("API down")
        result = agent.evaluate_match(_make_match_context())
        assert result.status == "ERROR"
        assert "failed" in (result.justification or "").lower()


# ── BaseAgent contract ───────────────────────────────────────────────


class TestBaseAgentContract:
    """Test that GatekeeperAgent fulfils the BaseAgent contract."""

    def test_name_attribute(self, agent):
        assert agent.name == "gatekeeper"

    def test_run_method_legacy(self, agent, mock_openai):
        llm_output = json.dumps({"status": "NO BET", "justification": "Test via run()"})
        _mock_llm_response(mock_openai, llm_output)
        context = AgentContext(payload={"match_context_json": _make_match_context()})
        result = agent.run(context)
        assert isinstance(result, dict)
        assert result["status"] == "NO BET"

    def test_run_method_v26(self, agent, mock_openai):
        """run() returns serialized markets array for V26."""
        response = json.dumps(
            {
                "markets": [
                    {
                        "market": "BTTS SIM",
                        "status": "APPROVED",
                        "stake": 0.5,
                        "odd": 1.85,
                        "edge": "Baixo",
                        "justification": "Ofensivos",
                        "red_flags": [],
                    }
                ],
                "best_pick": {
                    "market": "BTTS SIM",
                    "status": "APPROVED",
                    "stake": 0.5,
                    "odd": 1.85,
                    "edge": "Baixo",
                    "justification": "Melhor entrada",
                    "red_flags": [],
                },
            }
        )
        _mock_llm_response(mock_openai, response)
        context = AgentContext(payload={"match_context_json": _make_match_context()})
        result = agent.run(context)
        assert isinstance(result, dict)
        assert "status" in result
        assert "markets" in result
        assert "best_pick" in result
        assert isinstance(result["markets"], list)


# ── Constructor validation ───────────────────────────────────────────


class TestConstructor:
    """Test GatekeeperAgent constructor validation."""

    def test_missing_api_key_raises(self, gk_cfg):
        with patch("japredictbet.agents.gatekeeper.OpenAI"):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="API key"):
                    from japredictbet.agents.gatekeeper import GatekeeperAgent

                    GatekeeperAgent(gatekeeper_cfg=gk_cfg, api_key="")
