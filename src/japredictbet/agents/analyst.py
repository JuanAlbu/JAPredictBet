"""Analyst agent — LLM-based evaluation of non-corner markets.

Evaluates 1x2 (match result), BTTS (both teams to score), and other
complementary markets using purely qualitative context analysis.  The
30-model Poisson consensus is **exclusive to corners** — this agent
provides coverage for all remaining Superbet markets.

Safety: this module is strictly observational.  It never places real
bets — output is written to a shadow log only.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from japredictbet.agents.base import AgentContext, BaseAgent
from japredictbet.agents.gatekeeper import classify_odd
from japredictbet.config import GatekeeperConfig

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "docs" / "PROMPT_ANALYST.md"

_STATUS_APPROVED = "APPROVED"
_STATUS_NO_BET = "NO BET"
_STATUS_ERROR = "ERROR"
_STATUS_FILTERED = "FILTERED"

_DEFAULT_MODEL = "gpt-4o-mini"


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class MarketEvaluation:
    """Evaluation result for a single market."""

    market: str  # e.g. "1x2 HOME", "BTTS SIM", "Over 2.5 Gols"
    status: str  # APPROVED | NO BET
    stake: Optional[float] = None  # 0.5, 1.0, 2.0
    odd: Optional[float] = None
    edge: Optional[str] = None  # Alto | Médio | Baixo
    classification: Optional[str] = None  # Pricing zone tag
    justification: Optional[str] = None
    red_flags: List[str] = field(default_factory=list)


@dataclass
class AnalystResult:
    """Structured output from the Analyst agent."""

    status: str  # APPROVED | NO BET | FILTERED | ERROR
    markets: List[MarketEvaluation] = field(default_factory=list)
    best_pick: Optional[MarketEvaluation] = None
    raw_llm_response: Optional[str] = None


# ── Analyst Agent ────────────────────────────────────────────────────


class AnalystAgent(BaseAgent):
    """LLM-driven analyst for non-corner markets.

    Flow
    ----
    1. Python hard-filter: reject when no non-corner odds meet ``min_odd``.
    2. Build LLM prompt with match context JSON (no ensemble output).
    3. Call OpenAI chat completion (system = Prompt Analyst V1).
    4. Parse structured JSON response → ``AnalystResult``.
    """

    name: str = "analyst"

    def __init__(
        self,
        gatekeeper_cfg: GatekeeperConfig,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._cfg = gatekeeper_cfg
        self._model = model or _DEFAULT_MODEL
        resolved_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "LLM API key not provided.  "
                "Set LLM_API_KEY (or OPENAI_API_KEY) environment variable or pass api_key=."
            )
        resolved_base_url = base_url or os.environ.get("LLM_BASE_URL") or None
        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
        self._system_prompt = self._load_system_prompt()

    # ── BaseAgent contract ───────────────────────────────────────────

    def run(self, context: AgentContext) -> Dict[str, Any]:
        """Evaluate non-corner markets from *context.payload*.

        Expected payload keys
        ---------------------
        match_context_json : str
            Serialised ``MatchContext`` (from ``MatchContext.to_json()``).
        """
        result = self.evaluate_match(
            match_context_json=context.payload.get("match_context_json", "{}"),
        )
        return {
            "status": result.status,
            "markets": [
                {
                    "market": m.market,
                    "status": m.status,
                    "stake": m.stake,
                    "odd": m.odd,
                    "edge": m.edge,
                    "classification": m.classification,
                    "justification": m.justification,
                    "red_flags": m.red_flags,
                }
                for m in result.markets
            ],
            "best_pick": (
                {
                    "market": result.best_pick.market,
                    "status": result.best_pick.status,
                    "stake": result.best_pick.stake,
                    "odd": result.best_pick.odd,
                    "edge": result.best_pick.edge,
                    "classification": result.best_pick.classification,
                    "justification": result.best_pick.justification,
                    "red_flags": result.best_pick.red_flags,
                }
                if result.best_pick
                else None
            ),
        }

    # ── Public evaluation method ─────────────────────────────────────

    def evaluate_match(
        self,
        match_context_json: str,
    ) -> AnalystResult:
        """Evaluate non-corner markets and return structured results.

        Parameters
        ----------
        match_context_json:
            JSON string produced by ``MatchContext.to_json()``.
        """

        # ── Step 1: hard pre-filter (min_odd on non-corner markets) ──
        filtered = self._apply_pre_filter(match_context_json)
        if filtered is not None:
            return filtered

        # ── Step 2: build user prompt ────────────────────────────────
        user_prompt = self._build_user_prompt(match_context_json)

        # ── Step 3: call LLM ─────────────────────────────────────────
        raw_response = self._call_llm(user_prompt)
        if raw_response is None:
            return AnalystResult(
                status=_STATUS_ERROR,
                raw_llm_response=None,
            )

        # ── Step 4: parse response ───────────────────────────────────
        return self._parse_response(raw_response)

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _load_system_prompt() -> str:
        """Load Prompt Analyst V1 from docs/PROMPT_ANALYST.md."""
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning(
            "PROMPT_ANALYST.md not found at %s — using fallback.", _PROMPT_PATH
        )
        return (
            "Você é um Analista de Mercados Complementares. "
            "Avalie mercados 1x2, BTTS, e outros (exceto escanteios). "
            "Responda em JSON com os campos: markets (lista), best_pick."
        )

    def _apply_pre_filter(
        self, match_context_json: str
    ) -> Optional[AnalystResult]:
        """Return a FILTERED result if no non-corner odds meet min_odd."""
        try:
            ctx = json.loads(match_context_json)
        except (json.JSONDecodeError, TypeError):
            return AnalystResult(
                status=_STATUS_ERROR,
                raw_llm_response="Invalid match context JSON.",
            )

        odds = ctx.get("odds", {})
        non_corner_odds = [
            v
            for v in [
                odds.get("home_odds"),
                odds.get("draw_odds"),
                odds.get("away_odds"),
                odds.get("btts_yes"),
                odds.get("btts_no"),
            ]
            if v is not None
        ]

        if not non_corner_odds:
            home = ctx.get("home_team", "?")
            away = ctx.get("away_team", "?")
            logger.info(
                "Analyst pre-filter: %s vs %s — no non-corner odds available → FILTERED",
                home,
                away,
            )
            return AnalystResult(
                status=_STATUS_FILTERED,
            )

        best_odd = max(non_corner_odds)
        if best_odd < self._cfg.min_odd:
            home = ctx.get("home_team", "?")
            away = ctx.get("away_team", "?")
            logger.info(
                "Analyst pre-filter: %s vs %s — best non-corner odd %.2f < min %.2f → FILTERED",
                home,
                away,
                best_odd,
                self._cfg.min_odd,
            )
            return AnalystResult(
                status=_STATUS_FILTERED,
            )
        return None

    @staticmethod
    def _build_user_prompt(match_context_json: str) -> str:
        """Compose the user message sent to the LLM."""
        parts = [
            "Avalie os mercados complementares (NÃO escanteios) deste jogo. "
            "Responda **exclusivamente** com um JSON válido contendo:\n"
            "  markets (lista de objetos com: market, status, stake, odd, edge, "
            "classification, justification, red_flags),\n"
            "  best_pick (o melhor mercado ou null).\n"
            "\n"
            "REGRAS DE ZONA (classification):\n"
            "- Odd < 1.25 → REJEITAR (ZONA MORTA)\n"
            "- Odd 1.25–1.59 → classification=\"PERNA DE COMPOSIÇÃO\" "
            "(proibido como aposta simples)\n"
            "- Odd 1.60–2.20 → classification=\"APOSTA SIMPLES\"\n"
            "- Odd > 2.20 → classification=\"APOSTA SIMPLES — VARIÂNCIA\" "
            "(stake máx 0.5u)\n",
            "Mercados a avaliar: **1x2 (Resultado Final)**, **BTTS (Ambas Marcam)**, "
            "**Over/Under Gols** e quaisquer outros disponíveis nas odds.\n",
            "Ignore completamente o mercado de **escanteios** — ele é coberto por um "
            "sistema de consenso estatístico separado.\n"
            "Ignore completamente o mercado de **Handicap** — não faz parte do "
            "perfil operacional.\n",
            "=== CONTEXTO DO JOGO ===",
            match_context_json,
            "\nSe não houver cenário favorável em nenhum mercado, retorne "
            '{"markets": [], "best_pick": null}.',
        ]
        return "\n".join(parts)

    def _call_llm(self, user_prompt: str) -> Optional[str]:
        """Send prompt to OpenAI and return raw content string."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1536,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            logger.debug("Analyst LLM raw response: %s", content)
            return content
        except Exception:
            logger.exception("Analyst LLM call failed")
            return None

    @staticmethod
    def _parse_response(raw: str) -> AnalystResult:
        """Parse the LLM JSON response into an ``AnalystResult``."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return AnalystResult(
                status=_STATUS_ERROR,
                raw_llm_response=raw,
            )

        markets_raw = data.get("markets", [])
        markets: List[MarketEvaluation] = []

        for m in markets_raw:
            if not isinstance(m, dict):
                continue

            status = m.get("status", _STATUS_NO_BET).upper().strip()
            if status not in (_STATUS_APPROVED, _STATUS_NO_BET):
                status = _STATUS_NO_BET

            stake_raw = m.get("stake")
            stake: Optional[float] = None
            if stake_raw is not None:
                try:
                    stake = float(stake_raw)
                    if stake not in (0.5, 1.0, 2.0):
                        stake = min(max(stake, 0.5), 2.0)
                except (ValueError, TypeError):
                    stake = None

            markets.append(
                MarketEvaluation(
                    market=m.get("market", "unknown"),
                    status=status,
                    stake=stake,
                    odd=m.get("odd"),
                    edge=m.get("edge"),
                    classification=m.get("classification") or classify_odd(
                        float(m["odd"]) if m.get("odd") is not None else None
                    ),
                    justification=m.get("justification"),
                    red_flags=m.get("red_flags", []),
                )
            )

        # Parse best_pick
        best_pick_raw = data.get("best_pick")
        best_pick: Optional[MarketEvaluation] = None
        if best_pick_raw and isinstance(best_pick_raw, dict):
            bp_status = best_pick_raw.get("status", _STATUS_NO_BET).upper().strip()
            if bp_status not in (_STATUS_APPROVED, _STATUS_NO_BET):
                bp_status = _STATUS_NO_BET

            bp_stake_raw = best_pick_raw.get("stake")
            bp_stake: Optional[float] = None
            if bp_stake_raw is not None:
                try:
                    bp_stake = float(bp_stake_raw)
                    if bp_stake not in (0.5, 1.0, 2.0):
                        bp_stake = min(max(bp_stake, 0.5), 2.0)
                except (ValueError, TypeError):
                    bp_stake = None

            best_pick = MarketEvaluation(
                market=best_pick_raw.get("market", "unknown"),
                status=bp_status,
                stake=bp_stake,
                odd=best_pick_raw.get("odd"),
                edge=best_pick_raw.get("edge"),
                classification=best_pick_raw.get("classification") or classify_odd(
                    float(best_pick_raw["odd"]) if best_pick_raw.get("odd") is not None else None
                ),
                justification=best_pick_raw.get("justification"),
                red_flags=best_pick_raw.get("red_flags", []),
            )

        # Overall status: APPROVED if any market approved
        has_approved = any(m.status == _STATUS_APPROVED for m in markets)
        overall_status = _STATUS_APPROVED if has_approved else _STATUS_NO_BET

        return AnalystResult(
            status=overall_status,
            markets=markets,
            best_pick=best_pick,
            raw_llm_response=raw,
        )
