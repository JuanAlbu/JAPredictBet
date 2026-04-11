"""Gatekeeper agent — LLM-based match evaluation for Shadow Mode.

Uses the Prompt Mestre V25 system prompt to evaluate whether a match
context warrants a bet entry.  The agent applies a **hard Python
pre-filter** (min_odd) before calling the LLM, and parses the
structured response back into a typed result.

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
from japredictbet.config import GatekeeperConfig

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "docs" / "PROMPT_MESTRE.md"

_STATUS_APPROVED = "APPROVED"
_STATUS_NO_BET = "NO BET"
_STATUS_ERROR = "ERROR"
_STATUS_FILTERED = "FILTERED"

_DEFAULT_MODEL = "gpt-4o-mini"


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class GatekeeperResult:
    """Structured output from the Gatekeeper evaluation."""

    status: str  # APPROVED | NO BET | FILTERED | ERROR
    stake: Optional[float] = None  # in units (0.5, 1.0, 2.0)
    market: Optional[str] = None
    odd: Optional[float] = None
    edge: Optional[str] = None  # Alto | Médio | Baixo
    justification: Optional[str] = None
    red_flags: List[str] = field(default_factory=list)
    raw_llm_response: Optional[str] = None


# ── Gatekeeper Agent ─────────────────────────────────────────────────


class GatekeeperAgent(BaseAgent):
    """LLM-driven gatekeeper that decides GO / NO-GO per match.

    Flow
    ----
    1. Python hard-filter: reject when best Superbet corner odd < min_odd.
    2. Build LLM prompt with match context JSON + ensemble output.
    3. Call OpenAI chat completion (system = Prompt Mestre V25).
    4. Parse structured JSON response → ``GatekeeperResult``.
    """

    name: str = "gatekeeper"

    def __init__(
        self,
        gatekeeper_cfg: GatekeeperConfig,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: Optional[str] = None,
    ) -> None:
        self._cfg = gatekeeper_cfg
        self._model = model
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "OpenAI API key not provided.  "
                "Set the OPENAI_API_KEY environment variable or pass api_key=."
            )
        self._client = OpenAI(api_key=resolved_key)
        self._system_prompt = self._load_system_prompt()

    # ── BaseAgent contract ───────────────────────────────────────────

    def run(self, context: AgentContext) -> Dict[str, Any]:
        """Evaluate a single match from *context.payload*.

        Expected payload keys
        ---------------------
        match_context_json : str
            Serialised ``MatchContext`` (from ``MatchContext.to_json()``).
        ensemble_output : dict, optional
            Keys: ``mean_lambda``, ``consensus_pct``, ``vote_over``,
            ``vote_under``, ``p_over``, ``edge``.
        """
        result = self.evaluate_match(
            match_context_json=context.payload.get("match_context_json", "{}"),
            ensemble_output=context.payload.get("ensemble_output"),
        )
        return {
            "status": result.status,
            "stake": result.stake,
            "market": result.market,
            "odd": result.odd,
            "edge": result.edge,
            "justification": result.justification,
            "red_flags": result.red_flags,
        }

    # ── Public evaluation method ─────────────────────────────────────

    def evaluate_match(
        self,
        match_context_json: str,
        ensemble_output: Optional[Dict[str, Any]] = None,
    ) -> GatekeeperResult:
        """Evaluate a match and return a structured decision.

        Parameters
        ----------
        match_context_json:
            JSON string produced by ``MatchContext.to_json()``.
        ensemble_output:
            Optional dict with consensus engine results
            (mean_lambda, consensus_pct, etc.).
        """

        # ── Step 1: hard pre-filter (min_odd) ────────────────────────
        filtered = self._apply_pre_filter(match_context_json)
        if filtered is not None:
            return filtered

        # ── Step 2: build user prompt ────────────────────────────────
        user_prompt = self._build_user_prompt(
            match_context_json, ensemble_output
        )

        # ── Step 3: call LLM ─────────────────────────────────────────
        raw_response = self._call_llm(user_prompt)
        if raw_response is None:
            return GatekeeperResult(
                status=_STATUS_ERROR,
                justification="LLM call failed — see logs.",
            )

        # ── Step 4: parse response ───────────────────────────────────
        return self._parse_response(raw_response)

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _load_system_prompt() -> str:
        """Load Prompt Mestre V25 from docs/PROMPT_MESTRE.md."""
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning(
            "PROMPT_MESTRE.md not found at %s — using fallback.", _PROMPT_PATH
        )
        return (
            "Você é um Analista Sênior de Performance e Gestor de Risco. "
            "Avalie o cenário e responda em JSON com os campos: "
            "status, stake, market, odd, edge, justification, red_flags."
        )

    def _apply_pre_filter(
        self, match_context_json: str
    ) -> Optional[GatekeeperResult]:
        """Return a FILTERED result if no odds meet min_odd, else None."""
        try:
            ctx = json.loads(match_context_json)
        except (json.JSONDecodeError, TypeError):
            return GatekeeperResult(
                status=_STATUS_ERROR,
                justification="Invalid match context JSON.",
            )

        odds = ctx.get("odds", {})
        best_odd = max(
            filter(
                lambda v: v is not None,
                [
                    odds.get("corner_over_odds"),
                    odds.get("corner_under_odds"),
                    odds.get("home_odds"),
                    odds.get("draw_odds"),
                    odds.get("away_odds"),
                    odds.get("btts_yes"),
                    odds.get("btts_no"),
                ],
            ),
            default=0.0,
        )

        if best_odd < self._cfg.min_odd:
            home = ctx.get("home_team", "?")
            away = ctx.get("away_team", "?")
            logger.info(
                "Pre-filter: %s vs %s — best odd %.2f < min %.2f → FILTERED",
                home,
                away,
                best_odd,
                self._cfg.min_odd,
            )
            return GatekeeperResult(
                status=_STATUS_FILTERED,
                justification=(
                    f"Melhor odd disponível ({best_odd:.2f}) abaixo do "
                    f"mínimo operacional ({self._cfg.min_odd:.2f})."
                ),
            )
        return None

    @staticmethod
    def _build_user_prompt(
        match_context_json: str,
        ensemble_output: Optional[Dict[str, Any]],
    ) -> str:
        """Compose the user message sent to the LLM."""
        parts = [
            "Avalie o jogo abaixo e responda **exclusivamente** com um "
            "JSON válido contendo os campos:\n"
            '  status ("APPROVED" ou "NO BET"),\n'
            "  stake (0.5 / 1.0 / 2.0 ou null),\n"
            "  market (string ou null),\n"
            "  odd (number ou null),\n"
            '  edge ("Alto" / "Médio" / "Baixo" ou null),\n'
            "  justification (string — breve),\n"
            "  red_flags (lista de strings).\n",
            "=== CONTEXTO DO JOGO ===",
            match_context_json,
        ]

        if ensemble_output:
            parts.append("\n=== OUTPUT DO ENSEMBLE (30 modelos) ===")
            parts.append(json.dumps(ensemble_output, ensure_ascii=False, indent=2))

        parts.append(
            "\nSe não houver cenário favorável, retorne "
            '{"status": "NO BET", "justification": "motivo"}.'
        )
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
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            logger.debug("LLM raw response: %s", content)
            return content
        except Exception:
            logger.exception("LLM call failed")
            return None

    @staticmethod
    def _parse_response(raw: str) -> GatekeeperResult:
        """Parse the LLM JSON response into a ``GatekeeperResult``."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return GatekeeperResult(
                status=_STATUS_ERROR,
                justification="Failed to parse LLM JSON response.",
                raw_llm_response=raw,
            )

        status = data.get("status", _STATUS_NO_BET).upper().strip()
        if status not in (_STATUS_APPROVED, _STATUS_NO_BET):
            status = _STATUS_NO_BET

        stake_raw = data.get("stake")
        stake: Optional[float] = None
        if stake_raw is not None:
            try:
                stake = float(stake_raw)
                if stake not in (0.5, 1.0, 2.0):
                    stake = min(max(stake, 0.5), 2.0)
            except (ValueError, TypeError):
                stake = None

        return GatekeeperResult(
            status=status,
            stake=stake,
            market=data.get("market"),
            odd=data.get("odd"),
            edge=data.get("edge"),
            justification=data.get("justification"),
            red_flags=data.get("red_flags", []),
            raw_llm_response=raw,
        )
