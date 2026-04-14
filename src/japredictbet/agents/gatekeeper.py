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

from openai import OpenAI, RateLimitError

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


# ── Pricing Zones ────────────────────────────────────────────────────

_ZONE_DEAD = "ZONA MORTA"           # < 1.25
_ZONE_BUILDER = "PERNA DE COMPOSIÇÃO"  # 1.25–1.59
_ZONE_SINGLE = "APOSTA SIMPLES"       # 1.60–2.20
_ZONE_VARIANCE = "APOSTA SIMPLES — VARIÂNCIA"  # > 2.20


def classify_odd(odd: Optional[float]) -> Optional[str]:
    """Return the pricing-zone tag for a given odd value."""
    if odd is None:
        return None
    if odd < 1.25:
        return _ZONE_DEAD
    if odd < 1.60:
        return _ZONE_BUILDER
    if odd <= 2.20:
        return _ZONE_SINGLE
    return _ZONE_VARIANCE


@dataclass
class GatekeeperResult:
    """Structured output from the Gatekeeper evaluation."""

    status: str  # APPROVED | NO BET | FILTERED | ERROR
    stake: Optional[float] = None  # in units (0.5, 1.0, 2.0)
    market: Optional[str] = None
    odd: Optional[float] = None
    edge: Optional[str] = None  # Alto | Médio | Baixo
    classification: Optional[str] = None  # Pricing zone tag
    justification: Optional[str] = None
    red_flags: List[str] = field(default_factory=list)
    raw_llm_response: Optional[str] = None


# ── Gatekeeper Agent ─────────────────────────────────────────────────


class GatekeeperAgent(BaseAgent):
    """LLM-driven gatekeeper that decides GO / NO-GO per match.

    Flow
    ----
    1. Python hard-filter: reject when best Superbet odd < min_odd.
    2. Build LLM prompt with match context JSON (context-only, no ML data).
    3. Call OpenAI chat completion (system = Prompt Mestre V25).
    4. Parse structured JSON response → ``GatekeeperResult``.

    Note: The Gatekeeper is strictly a **context engine**.  It receives
    desfalques, table standings, odds and qualitative factors.  It does
    NOT receive ensemble/ML output — that is produced independently by
    the ML Value Engine and surfaced as a separate suggestion list.
    """

    name: str = "gatekeeper"

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

        # Optional fallback provider (activated on HTTP 429 from primary)
        fallback_key = os.environ.get("LLM_FALLBACK_API_KEY") or ""
        if fallback_key:
            fallback_base_url = os.environ.get("LLM_FALLBACK_BASE_URL") or None
            self._fallback_client: Optional[OpenAI] = OpenAI(
                api_key=fallback_key, base_url=fallback_base_url
            )
            self._fallback_model: Optional[str] = (
                os.environ.get("LLM_FALLBACK_MODEL") or _DEFAULT_MODEL
            )
            logger.info(
                "Gatekeeper: fallback LLM provider configured (model=%s).",
                self._fallback_model,
            )
        else:
            self._fallback_client = None
            self._fallback_model = None

        self._system_prompt = self._load_system_prompt()

    # ── BaseAgent contract ───────────────────────────────────────────

    def run(self, context: AgentContext) -> Dict[str, Any]:
        """Evaluate a single match from *context.payload*.

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
            "stake": result.stake,
            "market": result.market,
            "odd": result.odd,
            "edge": result.edge,
            "classification": result.classification,
            "justification": result.justification,
            "red_flags": result.red_flags,
        }

    # ── Public evaluation method ─────────────────────────────────────

    def evaluate_match(
        self,
        match_context_json: str,
    ) -> GatekeeperResult:
        """Evaluate a match and return a structured decision.

        Parameters
        ----------
        match_context_json:
            JSON string produced by ``MatchContext.to_json()``.
        """

        # ── Step 1: hard pre-filter (min_odd) ────────────────────────
        filtered = self._apply_pre_filter(match_context_json)
        if filtered is not None:
            return filtered

        # ── Step 2: build user prompt ────────────────────────────────
        user_prompt = self._build_user_prompt(match_context_json)

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
    ) -> str:
        """Compose the user message sent to the LLM (context-only, no ML)."""
        parts = [
            "Avalie o jogo abaixo e responda **exclusivamente** com um "
            "JSON válido contendo os campos:\n"
            '  status ("APPROVED" ou "NO BET"),\n'
            "  stake (0.5 / 1.0 / 2.0 ou null),\n"
            "  market (string ou null),\n"
            "  odd (number ou null),\n"
            '  edge ("Alto" / "Médio" / "Baixo" ou null),\n'
            '  classification ("PERNA DE COMPOSIÇÃO" / "APOSTA SIMPLES" / '
            '"APOSTA SIMPLES — VARIÂNCIA" ou null — '
            "conforme MATRIZ DE PRECIFICAÇÃO),\n"
            "  justification (string — breve),\n"
            "  red_flags (lista de strings).\n"
            "\n"
            "REGRAS DE ZONA:\n"
            "- Odd < 1.25 → REJEITAR (ZONA MORTA)\n"
            "- Odd 1.25–1.59 → classification=\"PERNA DE COMPOSIÇÃO\" "
            "(proibido como aposta simples)\n"
            "- Odd 1.60–2.20 → classification=\"APOSTA SIMPLES\"\n"
            "- Odd > 2.20 → classification=\"APOSTA SIMPLES — VARIÂNCIA\" "
            "(stake máx 0.5u)\n"
            "\n"
            "Se o mesmo jogo tiver linhas em zonas diferentes, liste cada "
            "uma separadamente como objeto no array 'entries'.\n"
            "\n"
            "IMPORTANTE: Ignore completamente o mercado de Handicap. "
            "Handicap NÃO faz parte do perfil operacional.\n",
            "=== CONTEXTO DO JOGO ===",
            match_context_json,
        ]

        parts.append(
            "\nSe não houver cenário favorável, retorne "
            '{"status": "NO BET", "justification": "motivo"}.'
        )
        return "\n".join(parts)

    def _call_llm(self, user_prompt: str) -> Optional[str]:
        """Send prompt to primary LLM; on HTTP 429 retry with fallback provider."""
        try:
            return self._call_provider(
                self._client, self._model, user_prompt, max_tokens=1024
            )
        except RateLimitError as exc:
            logger.warning(
                "Gatekeeper: rate limit / cota esgotada no provedor principal — %s", exc
            )
            if self._fallback_client is None:
                logger.error(
                    "Gatekeeper: nenhum fallback configurado. "
                    "Defina LLM_FALLBACK_API_KEY no .env para ativar Groq → Gemini."
                )
                return None
            logger.info(
                "Gatekeeper: alternando para fallback (model=%s).", self._fallback_model
            )
            try:
                return self._call_provider(
                    self._fallback_client,
                    self._fallback_model,
                    user_prompt,
                    max_tokens=1024,
                )
            except Exception:
                logger.exception("Gatekeeper: fallback LLM call also failed")
                return None
        except Exception:
            logger.exception("Gatekeeper: LLM call failed")
            return None

    def _call_provider(
        self,
        client: OpenAI,
        model: Optional[str],
        user_prompt: str,
        *,
        max_tokens: int,
    ) -> Optional[str]:
        """Execute a single chat completion request and return the content string."""
        response = client.chat.completions.create(
            model=model or _DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        logger.debug("LLM raw response: %s", content)
        return content

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

        odd_val = data.get("odd")
        # Use LLM-provided classification, or derive from odd value
        classification = data.get("classification") or classify_odd(
            float(odd_val) if odd_val is not None else None
        )

        return GatekeeperResult(
            status=status,
            stake=stake,
            market=data.get("market"),
            odd=odd_val,
            edge=data.get("edge"),
            classification=classification,
            justification=data.get("justification"),
            red_flags=data.get("red_flags", []),
            raw_llm_response=raw,
        )
