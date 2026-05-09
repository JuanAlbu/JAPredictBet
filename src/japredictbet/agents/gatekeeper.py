"""Gatekeeper agent — LLM-based match evaluation for Shadow Mode.

Uses the Prompt Mestre V26 system prompt to evaluate whether a match
context warrants a bet entry across **all available markets** (corners,
1x2, BTTS, Over/Under Gols, 1º Tempo).  The agent applies a **hard Python
pre-filter** (min_odd) before calling the LLM, and parses the
structured JSON response (markets array + best_pick) into typed results.

Safety: this module is strictly observational.  It never places real
bets — output is written to a shadow log only.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


# ── Pricing Zones ────────────────────────────────────────────────────

_ZONE_DEAD = "ZONA MORTA"  # < 1.25
_ZONE_BUILDER = "PERNA DE COMPOSIÇÃO"  # 1.25–1.59
_ZONE_SINGLE = "APOSTA SIMPLES"  # 1.60–2.20
_ZONE_VARIANCE = "APOSTA SIMPLES — VARIÂNCIA"  # > 2.20


def classify_odd(odd: float | None) -> str | None:
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


def _coerce_float(value: Any) -> float | None:
    """Return *value* as float, or None when it is not numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_stake(value: object) -> float | None:
    """Normalize a stake value to the supported unit ladder."""
    stake = _coerce_float(value)
    if stake is None:
        return None
    if stake not in (0.5, 1.0, 2.0):
        return min(max(stake, 0.5), 2.0)
    return stake


def _with_red_flag(red_flags: list[str], flag: str) -> list[str]:
    """Return red flags with *flag* added once."""
    if flag not in red_flags:
        red_flags.append(flag)
    return red_flags


def _normalize_pricing_rules(market: MarketEvaluation) -> MarketEvaluation:
    """Enforce the hard pricing matrix after the LLM response is parsed."""
    odd = _coerce_float(market.odd)
    classification = classify_odd(odd) if odd is not None else market.classification
    status = market.status
    stake = market.stake
    edge = market.edge
    red_flags = list(market.red_flags)
    justification = market.justification

    if odd is None:
        if status == _STATUS_NO_BET:
            stake = None
            edge = None
        return MarketEvaluation(
            market=market.market,
            status=status,
            stake=stake,
            odd=None,
            edge=edge,
            classification=classification,
            justification=justification,
            red_flags=red_flags,
        )

    if classification == _ZONE_DEAD:
        status = _STATUS_NO_BET
        stake = None
        edge = None
        red_flags = _with_red_flag(red_flags, "zona morta")
        if not justification:
            justification = "Odd abaixo de 1.25: rejeicao obrigatoria pela matriz de precificacao."
    elif classification == _ZONE_BUILDER:
        stake = None
    elif classification == _ZONE_VARIANCE and stake is not None:
        stake = min(stake, 0.5)

    if status == _STATUS_NO_BET:
        stake = None
        edge = None

    return MarketEvaluation(
        market=market.market,
        status=status,
        stake=stake,
        odd=odd,
        edge=edge,
        classification=classification,
        justification=justification,
        red_flags=red_flags,
    )


def _is_actionable_single(market: MarketEvaluation | None) -> bool:
    """Return True when a market can become the day's single bet entry."""
    return (
        market is not None
        and market.status == _STATUS_APPROVED
        and market.classification in (_ZONE_SINGLE, _ZONE_VARIANCE)
    )


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class MarketEvaluation:
    """Evaluation result for a single market within a match.

    Mirrors the per-market object in the LLM JSON response.

    Attributes
    ----------
    market:
        Human-readable label (e.g. ``"Escanteios Over 9.5"``,
        ``"1x2 HOME"``, ``"BTTS SIM"``).
    status:
        ``"APPROVED"`` or ``"NO BET"``.
    stake:
        Recommended stake in units (0.5 / 1.0 / 2.0), or ``None``.
    odd:
        Odd value for this selection, or ``None``.
    edge:
        Perceived edge: ``"Alto"``, ``"Médio"``, ``"Baixo"``, or ``None``.
    classification:
        Pricing-zone tag from the 4-zone matrix, or ``None``.
    justification:
        Brief technical rationale.
    red_flags:
        List of risk factors flagged for this market.
    """

    market: str
    status: str  # APPROVED | NO BET
    stake: float | None = None
    odd: float | None = None
    edge: str | None = None  # Alto | Médio | Baixo
    classification: str | None = None  # Pricing zone tag
    justification: str | None = None
    red_flags: list[str] = field(default_factory=list)


@dataclass
class GatekeeperResult:
    """Structured output from the Gatekeeper evaluation.

    Contains the overall match evaluation, a list of all individual
    market assessments, and the single best recommendation (if any).
    """

    status: str  # APPROVED | NO BET | FILTERED | ERROR
    stake: float | None = None  # in units (0.5, 1.0, 2.0) — from best_pick
    market: str | None = None  # from best_pick
    odd: float | None = None  # from best_pick
    edge: str | None = None  # Alto | Médio | Baixo — from best_pick
    classification: str | None = None  # Pricing zone tag — from best_pick
    justification: str | None = None  # from best_pick
    red_flags: list[str] = field(default_factory=list)

    # ── Multi-market fields (V26) ────────────────────────────────────
    markets: list[MarketEvaluation] = field(default_factory=list)
    """All individual market evaluations returned by the LLM."""

    best_pick: MarketEvaluation | None = None
    """The single best approved market, or None if nothing is valid."""

    raw_llm_response: str | None = None

    @property
    def markets_evaluated(self) -> int:
        """Count of markets assessed by the LLM."""
        return len(self.markets)

    @property
    def markets_approved(self) -> int:
        """Count of markets with status == APPROVED."""
        return sum(1 for m in self.markets if m.status == _STATUS_APPROVED)


# ── Gatekeeper Agent ─────────────────────────────────────────────────


class GatekeeperAgent(BaseAgent):
    """LLM-driven gatekeeper that evaluates ALL markets for a match.

    Flow
    ----
    1. Python hard-filter: reject when *no* Superbet odd >= min_odd.
    2. Build LLM prompt with match context JSON (context-only, no ML data).
    3. Call OpenAI chat completion (system = Prompt Mestre V26).
    4. Parse structured JSON response → ``GatekeeperResult``
       (markets array + best_pick).

    The Gatekeeper is strictly a **context engine**.  It receives
    desfalques, table standings, odds and qualitative factors.  It does
    NOT receive ensemble/ML output — the ensemble is exclusive to
    Mode 1 (Backtest / consensus accuracy report).
    """

    name: str = "gatekeeper"

    def __init__(
        self,
        gatekeeper_cfg: GatekeeperConfig,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._cfg = gatekeeper_cfg
        self._model = model or _DEFAULT_MODEL
        resolved_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "LLM API key not provided.  Set LLM_API_KEY (or OPENAI_API_KEY) environment variable or pass api_key=."
            )
        resolved_base_url = base_url or os.environ.get("LLM_BASE_URL") or None
        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)

        # Optional fallback provider (activated on HTTP 429 from primary)
        fallback_key = os.environ.get("LLM_FALLBACK_API_KEY") or ""
        if fallback_key:
            fallback_base_url = os.environ.get("LLM_FALLBACK_BASE_URL") or None
            self._fallback_client: OpenAI | None = OpenAI(api_key=fallback_key, base_url=fallback_base_url)
            self._fallback_model: str | None = os.environ.get("LLM_FALLBACK_MODEL") or _DEFAULT_MODEL
            logger.info(
                "Gatekeeper: fallback LLM provider configured (model=%s).",
                self._fallback_model,
            )
        else:
            self._fallback_client = None
            self._fallback_model = None

        self._system_prompt = self._load_system_prompt()

    # ── BaseAgent contract ───────────────────────────────────────────

    def run(self, context: AgentContext) -> dict[str, Any]:
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
            "markets": [self._serialize_market(m) for m in result.markets],
            "markets_evaluated": result.markets_evaluated,
            "markets_approved": result.markets_approved,
            "best_pick": self._serialize_market(result.best_pick) if result.best_pick else None,
        }

    @staticmethod
    def _serialize_market(m: MarketEvaluation) -> dict[str, Any]:
        """Convert a MarketEvaluation to a plain dict for serialisation."""
        return {
            "market": m.market,
            "status": m.status,
            "stake": m.stake,
            "odd": m.odd,
            "edge": m.edge,
            "classification": m.classification,
            "justification": m.justification,
            "red_flags": m.red_flags,
        }

    # ── Public evaluation method ─────────────────────────────────────

    def evaluate_match(
        self,
        match_context_json: str,
    ) -> GatekeeperResult:
        """Evaluate a match across all available markets and return a
        structured decision.

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
        """Load Prompt Mestre V26 from docs/PROMPT_MESTRE.md."""
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        logger.warning("PROMPT_MESTRE.md not found at %s — using fallback.", _PROMPT_PATH)
        return (
            "Você é um Analista Sênior de Performance e Gestor de Risco. "
            "Avalie o cenário e responda em JSON com os campos: markets, "
            "best_pick, status, stake, market, odd, edge, classification, "
            "justification, red_flags."
        )

    def _apply_pre_filter(self, match_context_json: str) -> GatekeeperResult | None:
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
                    odds.get("over_15_goals"),
                    odds.get("over_25_goals"),
                    odds.get("over_35_goals"),
                    odds.get("under_15_goals"),
                    odds.get("under_25_goals"),
                    odds.get("under_35_goals"),
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
                    f"Melhor odd disponível ({best_odd:.2f}) abaixo do mínimo operacional ({self._cfg.min_odd:.2f})."
                ),
            )
        return None

    @staticmethod
    def _build_user_prompt(
        match_context_json: str,
    ) -> str:
        """Compose the user message sent to the LLM (context-only, no ML data).

        In V26 the agent evaluates ALL available markets (corners, 1x2,
        BTTS, Over/Under Gols) and returns a JSON with a ``markets`` array
        plus a single ``best_pick``.
        """
        parts = [
            "Avalie o jogo abaixo em TODOS os mercados disponíveis "
            "(escanteios, 1x2, BTTS, Over/Under Gols) e responda "
            "**exclusivamente** com um JSON válido no seguinte formato:",
            "",
            "{",
            '  "markets": [',
            "    {",
            '      "market": "<mercado e seleção — ex: Escanteios Over 9.5>",',
            '      "status": "APPROVED" | "NO BET",',
            '      "stake": 0.5 | 1.0 | 2.0 | null,',
            '      "odd": <number ou null>,',
            '      "edge": "Alto" | "Médio" | "Baixo" | null,',
            '      "classification": "PERNA DE COMPOSIÇÃO" | "APOSTA SIMPLES" | "APOSTA SIMPLES — VARIÂNCIA" | null,',
            '      "justification": "<string — breve>",',
            '      "red_flags": ["<string>", ...]',
            "    },",
            "    ...",
            "  ],",
            '  "best_pick": { <melhor mercado aprovado — mesmo formato acima> }',
            "    ou null se nenhum mercado for aprovado",
            "}",
            "",
            "REGRAS DE ZONA:",
            "- Odd < 1.25 → REJEITAR (ZONA MORTA)",
            '- Odd 1.25–1.59 → classification="PERNA DE COMPOSIÇÃO" (proibido como aposta simples)',
            '- Odd 1.60–2.20 → classification="APOSTA SIMPLES"',
            '- Odd > 2.20 → classification="APOSTA SIMPLES — VARIÂNCIA" (stake máx 0.5u)',
            "",
            "Avalie CADA mercado disponível no contexto. "
            "Classifique cada um como APPROVED ou NO BET. "
            "Selecione o melhor (best_pick) entre os aprovados, "
            "ou null se nada for válido.",
            "",
            "IMPORTANTE: Ignore completamente o mercado de Handicap. Handicap NÃO faz parte do perfil operacional.",
            "",
            "=== CONTEXTO DO JOGO ===",
            match_context_json,
        ]

        parts.append(
            '\nSe não houver NENHUM cenário favorável em nenhum mercado, retorne: {"markets": [], "best_pick": null}.'
        )
        return "\n".join(parts)

    def _call_llm(self, user_prompt: str) -> str | None:
        """Send prompt to primary LLM; on HTTP 429 retry with fallback provider."""
        try:
            return self._call_provider(self._client, self._model, user_prompt, max_tokens=2048)
        except RateLimitError as exc:
            logger.warning("Gatekeeper: rate limit / cota esgotada no provedor principal — %s", exc)
            if self._fallback_client is None:
                logger.error(
                    "Gatekeeper: nenhum fallback configurado. Defina LLM_FALLBACK_API_KEY no .env para ativar fallback."
                )
                return None
            logger.info("Gatekeeper: alternando para fallback (model=%s).", self._fallback_model)
            try:
                return self._call_provider(
                    self._fallback_client,
                    self._fallback_model,
                    user_prompt,
                    max_tokens=2048,
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
        model: str | None,
        user_prompt: str,
        *,
        max_tokens: int,
    ) -> str | None:
        """Execute a single chat completion request and return the content string.

        Uses ``response_format={"type": "json_object"}`` to enforce
        structured JSON output from the LLM.
        """
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

    # ── Robust JSON parsing ──────────────────────────────────────────

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences from LLM response, if present.

        Some providers wrap JSON in ```json ... ``` even when
        ``response_format={"type": "json_object"}`` is set.
        This guard strips those fences before parsing.
        """
        text = text.strip()
        # Strip leading ```json or ``` fence
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        return text

    @staticmethod
    def _safe_json_parse(raw: str) -> tuple[dict | None, str | None]:
        """Try to parse raw string as JSON, with markdown-stripping fallbacks.

        Returns
        -------
        (data, None) on success; (None, error_message) on failure.
        """
        candidates = [
            ("raw", raw),
        ]
        stripped = GatekeeperAgent._strip_markdown_fences(raw)
        if stripped != raw:
            candidates.append(("stripped markdown", stripped))

        for label, candidate in candidates:
            try:
                return (json.loads(candidate), None)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.debug("JSON parse attempt (%s) failed: %s", label, exc)

        return (None, "Failed to parse LLM JSON response after all attempts.")

    @staticmethod
    def _parse_response(raw: str) -> GatekeeperResult:
        """Parse the LLM JSON response (V26 format) into a ``GatekeeperResult``.

        Expects the ``markets`` array + optional ``best_pick`` structure
        defined by Prompt Mestre V26.  Falls back gracefully to the
        legacy single-market format for backward compatibility.
        """
        data, err = GatekeeperAgent._safe_json_parse(raw)
        if data is None:
            return GatekeeperResult(
                status=_STATUS_ERROR,
                justification=err or "Failed to parse LLM JSON response.",
                raw_llm_response=raw,
            )

        # ── Parse markets array ────────────────────────────────────
        markets_data: list[dict[str, Any]] = data.get("markets", [])
        markets: list[MarketEvaluation] = []
        for m in markets_data:
            if not isinstance(m, dict):
                continue
            stake = _coerce_stake(m.get("stake"))
            odd_val = _coerce_float(m.get("odd"))
            classification = classify_odd(odd_val) or m.get("classification")

            status = m.get("status", _STATUS_NO_BET).upper().strip()
            if status not in (_STATUS_APPROVED, _STATUS_NO_BET):
                status = _STATUS_NO_BET

            market = MarketEvaluation(
                market=str(m.get("market", "")),
                status=status,
                stake=stake,
                odd=odd_val,
                edge=m.get("edge"),
                classification=classification,
                justification=m.get("justification"),
                red_flags=list(m.get("red_flags", [])),
            )
            markets.append(_normalize_pricing_rules(market))

        # ── Parse best_pick ────────────────────────────────────────
        best_data = data.get("best_pick")
        best_pick: MarketEvaluation | None = None
        if isinstance(best_data, dict):
            bp = best_data
            bp_stake = _coerce_stake(bp.get("stake"))
            bp_odd = _coerce_float(bp.get("odd"))
            bp_classification = classify_odd(bp_odd) or bp.get("classification")
            bp_status = bp.get("status", _STATUS_NO_BET).upper().strip()
            if bp_status not in (_STATUS_APPROVED, _STATUS_NO_BET):
                bp_status = _STATUS_NO_BET

            best_pick = _normalize_pricing_rules(
                MarketEvaluation(
                    market=str(bp.get("market", "")),
                    status=bp_status,
                    stake=bp_stake,
                    odd=bp_odd,
                    edge=bp.get("edge"),
                    classification=bp_classification,
                    justification=bp.get("justification"),
                    red_flags=list(bp.get("red_flags", [])),
                )
            )

        # ── Legacy fallback: single-market format (no markets array) ─
        if not markets and best_pick is None and "status" in data:
            legacy_status = str(data.get("status", _STATUS_NO_BET)).upper().strip()
            if legacy_status not in (_STATUS_APPROVED, _STATUS_NO_BET):
                legacy_status = _STATUS_NO_BET
            legacy_pick = _normalize_pricing_rules(
                MarketEvaluation(
                    market=str(data.get("market", "")),
                    status=legacy_status,
                    stake=_coerce_stake(data.get("stake")),
                    odd=_coerce_float(data.get("odd")),
                    edge=data.get("edge"),
                    classification=data.get("classification"),
                    justification=data.get("justification"),
                    red_flags=list(data.get("red_flags", [])),
                )
            )
            is_actionable = legacy_pick.status == _STATUS_APPROVED and (
                legacy_pick.odd is None or _is_actionable_single(legacy_pick)
            )
            overall_status = legacy_pick.status if is_actionable else _STATUS_NO_BET
            overall_stake = legacy_pick.stake if is_actionable else None
            overall_market = legacy_pick.market if is_actionable else None
            overall_odd = legacy_pick.odd if is_actionable else None
            overall_edge = legacy_pick.edge if is_actionable else None
            overall_classification = legacy_pick.classification if is_actionable else None
            overall_justification = legacy_pick.justification
            overall_red_flags = legacy_pick.red_flags
        # ── Derive overall status from best_pick or markets ────────
        elif _is_actionable_single(best_pick):
            assert best_pick is not None  # type guard — _is_actionable_single garante
            overall_status = _STATUS_APPROVED
            overall_stake = best_pick.stake
            overall_market = best_pick.market
            overall_odd = best_pick.odd
            overall_edge = best_pick.edge
            overall_classification = best_pick.classification
            overall_justification = best_pick.justification
            overall_red_flags = best_pick.red_flags
        elif any(_is_actionable_single(m) for m in markets):
            # BEST_PICK ausente mas há mercados aprovados — usa o primeiro
            first_approved = next(m for m in markets if _is_actionable_single(m))
            overall_status = _STATUS_APPROVED
            overall_stake = first_approved.stake
            overall_market = first_approved.market
            overall_odd = first_approved.odd
            overall_edge = first_approved.edge
            overall_classification = first_approved.classification
            overall_justification = first_approved.justification
            overall_red_flags = first_approved.red_flags
            best_pick = first_approved
        else:
            overall_status = _STATUS_NO_BET
            overall_stake = None
            overall_market = None
            overall_odd = None
            overall_edge = None
            overall_classification = None
            overall_justification = None
            overall_red_flags = []
            best_pick = None

        return GatekeeperResult(
            status=overall_status,
            stake=overall_stake,
            market=overall_market,
            odd=overall_odd,
            edge=overall_edge,
            classification=overall_classification,
            justification=overall_justification,
            red_flags=overall_red_flags,
            markets=markets,
            best_pick=best_pick,
            raw_llm_response=raw,
        )
