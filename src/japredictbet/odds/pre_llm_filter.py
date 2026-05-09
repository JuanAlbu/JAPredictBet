"""The Bouncer V2 — pré-filtro determinístico de odds antes da LLM.

Três camadas de defesa (ODDS.1):

1. ``scraper_filter``: remove mercados não rastreados, remove odds < 1.25,
   reduz linhas redundantes antes de salvar o snapshot.

2. ``llm_candidate_builder``: monta payload compacto, marca ``zone``,
   ``stake_allowed``, ``best_pick_allowed``, e decide se o jogo merece
   chamada LLM.

3. ``gatekeeper_post_guard``: mantém a trava rígida pós-LLM já implementada
   em ``gatekeeper.py::_normalize_pricing_rules``, corrige respostas
   inválidas e impede ``best_pick`` fora da faixa permitida.

Uso:
    from japredictbet.odds.pre_llm_filter import (
        build_llm_candidates,
        PreLlmCandidate,
        PreLlmFilterResult,
        WHITELIST_MARKETS,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constantes de zona (mesmas do gatekeeper.py) ─────────────────────

_ZONE_DEAD = "ZONA MORTA"  # < 1.25
_ZONE_BUILDER = "PERNA DE COMPOSIÇÃO"  # 1.25–1.59
_ZONE_SINGLE = "APOSTA SIMPLES"  # 1.60–2.20
_ZONE_VARIANCE = "APOSTA SIMPLES — VARIÂNCIA"  # > 2.20

_MIN_ODD = 1.25
_COMPOSITION_MAX = 1.59
_SINGLE_MAX = 2.20

# ── Whitelist de mercados permitidos antes da LLM ────────────────────

WHITELIST_MARKETS = {
    "resultado final",
    "1x2",
    "match result",
    "ambas as equipes marcam",
    "btts",
    "both teams",
    "total de gols",
    "over/under gols",
    "total de escanteios",
    "escanteios",
    "1º tempo - resultado final",
    "first half - match result",
    "1º tempo - ambas as equipes marcam",
    "first half - both teams",
    "1º tempo - total de gols",
    "first half - total goals",
    "1º tempo - total de escanteios",
    "first half - corners",
}


# ── Data classes ──────────────────────────────────────────────────────


@dataclass
class PreLlmCandidate:
    """Uma seleção de mercado candidata (após filtragem)."""

    market_name: str
    selection_label: str  # ex: "Escanteios Over 9.5", "1x2 HOME"
    odd: float
    line: float | None = None
    zone: str | None = None
    stake_allowed: bool = False
    best_pick_allowed: bool = False
    max_stake: float | None = None  # Apenas para VARIANCE


@dataclass
class PreLlmFilterResult:
    """Resultado da filtragem pré-LLM para um jogo."""

    event_id: str
    home_team: str
    away_team: str
    candidates: list[PreLlmCandidate] = field(default_factory=list)
    has_single_or_variance: bool = False
    has_composition: bool = False
    composition_count: int = 0
    total_removed: int = 0
    reasons: list[str] = field(default_factory=list)
    should_call_llm: bool = False

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


# ── Helpers de zona ──────────────────────────────────────────────────


def classify_odd(odd: float) -> str:
    """Classifica uma odd na zona de precificação correspondente."""
    if odd < _MIN_ODD:
        return _ZONE_DEAD
    if odd <= _COMPOSITION_MAX:
        return _ZONE_BUILDER
    if odd <= _SINGLE_MAX:
        return _ZONE_SINGLE
    return _ZONE_VARIANCE


def _is_market_whitelisted(market_name: str) -> bool:
    """Verifica se o mercado está na whitelist permitida para LLM.

    Usa correspondência parcial (case-insensitive) para capturar
    variações como "Total de Escanteios Over/Under" etc.
    """
    lower = market_name.lower()
    for allowed in WHITELIST_MARKETS:
        if allowed in lower:
            return True
    return False


def _is_player_market(market_name: str) -> bool:
    """Detecta mercados de jogador (props) que devem ser excluídos."""
    player_kw = (
        "jogador", "player", "chutes no gol",
        "finalizações", "faltas cometidas",
    )
    lower = market_name.lower()
    return any(kw in lower for kw in player_kw)


def _is_handicap_market(market_name: str) -> bool:
    """Detecta mercados de handicap."""
    lower = market_name.lower()
    return "handicap" in lower


# ── Função principal de filtragem ─────────────────────────────────────


def build_llm_candidates(
    match_ctx_json: str,
    *,
    min_odd: float = _MIN_ODD,
    composition_enabled: bool = False,
    max_lines_per_direction: int = 2,
) -> PreLlmFilterResult:
    """Filtra as seleções de um MatchContext e retorna apenas candidatos válidos.

    Opera por **seleção** (não apenas por evento), removendo:
    - Odds abaixo de ``min_odd`` (ZONA MORTA)
    - Mercados fora da whitelist (handicap, props, placar correto)
    - Linhas redundantes por direção (max 1-2 linhas)

    Args:
        match_ctx_json: JSON string do ``MatchContext.to_llm_context()``.
        min_odd: Odd mínima operacional (default: 1.25).
        composition_enabled: Se True, permite candidatos COMPOSITION_ONLY.
        max_lines_per_direction: Máx. de linhas por direção (over/under/home/away).

    Returns:
        ``PreLlmFilterResult`` com candidatos filtrados.
    """
    import json

    try:
        ctx = json.loads(match_ctx_json)
    except (json.JSONDecodeError, TypeError):
        return PreLlmFilterResult(
            event_id="",
            home_team="?",
            away_team="?",
            candidates=[],
            should_call_llm=False,
            reasons=["JSON inválido no MatchContext"],
        )

    event_id = ctx.get("event_id", "")
    home_team = ctx.get("home_team", "?")
    away_team = ctx.get("away_team", "?")
    odds = ctx.get("odds", {})

    result = PreLlmFilterResult(
        event_id=event_id,
        home_team=home_team,
        away_team=away_team,
    )

    candidates: list[PreLlmCandidate] = []
    removed = 0
    reasons: list[str] = []

    # Mapeia as odds do MatchContext para seleções candidatas
    # Estrutura: {market_name: [(selection_label, odd, line), ...]}
    selections = _extract_selections(odds)

    for market_name, sel_list in selections.items():
        # ── Filtro 1: whitelist de mercados ──────────────────────────
        if not _is_market_whitelisted(market_name):
            removed += len(sel_list)
            reasons.append(f"Mercado '{market_name}' fora da whitelist ({len(sel_list)} seleções removidas)")
            continue

        # ── Filtro 2: handicap e props ───────────────────────────────
        if _is_handicap_market(market_name):
            removed += len(sel_list)
            reasons.append(f"Handicap ignorado: {market_name}")
            continue

        if _is_player_market(market_name):
            removed += len(sel_list)
            reasons.append(f"Mercado de jogador ignorado: {market_name}")
            continue

        # ── Filtro 3: por odd (zona morta) ───────────────────────────
        for label, odd, line in sel_list:
            zone = classify_odd(odd)

            if zone == _ZONE_DEAD:
                removed += 1
                reasons.append(f"{label}: odd {odd:.2f} < {min_odd} → ZONA MORTA")
                continue

            # PERNA DE COMPOSIÇÃO → sempre composition_only
            # (sem stake, sem best_pick) independente de composition_enabled.
            # composition_enabled só afeta a decisão de chamar LLM.
            if zone == _ZONE_BUILDER:
                candidates.append(PreLlmCandidate(
                    market_name=market_name,
                    selection_label=label,
                    odd=odd,
                    line=line,
                    zone=zone,
                    stake_allowed=False,
                    best_pick_allowed=False,
                ))
                continue

            # SINGLE ou VARIANCE — candidato válido
            stake_allowed = True
            best_pick_allowed = True
            max_stake: float | None = None

            if zone == _ZONE_VARIANCE:
                max_stake = 0.5

            candidates.append(PreLlmCandidate(
                market_name=market_name,
                selection_label=label,
                odd=odd,
                line=line,
                zone=zone,
                stake_allowed=stake_allowed,
                best_pick_allowed=best_pick_allowed,
                max_stake=max_stake,
            ))

    # ── Filtro 4: reduzir linhas redundantes por direção ─────────────
    candidates = _deduplicate_lines(candidates, max_lines_per_direction)

    # ── Estatísticas finais ──────────────────────────────────────────
    result.candidates = candidates
    result.total_removed = removed

    singles_or_variances = [c for c in candidates if c.stake_allowed]
    compositions = [c for c in candidates if not c.stake_allowed]

    result.has_single_or_variance = len(singles_or_variances) > 0
    result.has_composition = len(compositions) > 0
    result.composition_count = len(compositions)

    # ── Decisão: chamar LLM ou não? ──────────────────────────────────
    if not candidates:
        result.should_call_llm = False
        result.reasons = reasons + ["Nenhum candidato restante após filtragem"]
        logger.info(
            "Pre-LLM: %s vs %s — 0 candidatos, LLM não chamada (%d removidos).",
            home_team, away_team, removed,
        )
        return result

    # Chama LLM quando:
    # a) Pelo menos 1 SINGLE/VARIANCE_SINGLE, OU
    # b) Pelo menos 2 COMPOSITION_ONLY com composition_enabled
    if result.has_single_or_variance:
        result.should_call_llm = True
    elif composition_enabled and result.composition_count >= 2:
        result.should_call_llm = True

    if not result.should_call_llm:
        result.reasons = reasons + [
            f"Apenas {len(compositions)} composition(s), mínimo 2 exigido"
            if composition_enabled else
            "Nenhum candidato SINGLE/VARIANCE — composition desabilitado"
        ]

    logger.info(
        "Pre-LLM: %s vs %s — %d candidatos (%d singles, %d comp), "
        "call_llm=%s, %d removidos.",
        home_team, away_team,
        len(candidates),
        len(singles_or_variances),
        len(compositions),
        result.should_call_llm,
        removed,
    )

    result.reasons = reasons
    return result


# ── Extractor de seleções ─────────────────────────────────────────────


def _extract_selections(
    odds: dict[str, Any],
) -> dict[str, list[tuple[str, float, float | None]]]:
    """Extrai seleções candidatas do dicionário de odds do MatchContext.

    Retorna: {market_name: [(selection_label, odd, line), ...]}
    """
    selections: dict[str, list[tuple[str, float, float | None]]] = {}

    # Escanteios
    if odds.get("corner_over_odds") is not None:
        line = odds.get("corner_line")
        selections.setdefault("Total de Escanteios", []).append((
            f"Escanteios Over {line}" if line else "Escanteios Over",
            float(odds["corner_over_odds"]),
            line,
        ))
    if odds.get("corner_under_odds") is not None:
        line = odds.get("corner_line")
        selections.setdefault("Total de Escanteios", []).append((
            f"Escanteios Under {line}" if line else "Escanteios Under",
            float(odds["corner_under_odds"]),
            line,
        ))

    # 1x2
    if odds.get("home_odds") is not None:
        selections.setdefault("Resultado Final", []).append((
            "1x2 HOME",
            float(odds["home_odds"]),
            None,
        ))
    if odds.get("draw_odds") is not None:
        selections.setdefault("Resultado Final", []).append((
            "1x2 DRAW",
            float(odds["draw_odds"]),
            None,
        ))
    if odds.get("away_odds") is not None:
        selections.setdefault("Resultado Final", []).append((
            "1x2 AWAY",
            float(odds["away_odds"]),
            None,
        ))

    # BTTS
    if odds.get("btts_yes") is not None:
        selections.setdefault("Ambas as Equipes Marcam", []).append((
            "BTTS SIM",
            float(odds["btts_yes"]),
            None,
        ))
    if odds.get("btts_no") is not None:
        selections.setdefault("Ambas as Equipes Marcam", []).append((
            "BTTS NAO",
            float(odds["btts_no"]),
            None,
        ))

    # Over/Under Gols (1.5, 2.5, 3.5)
    goal_lines = [
        (1.5, "goals_over_1_5", "goals_under_1_5"),
        (2.5, "goals_over_2_5", "goals_under_2_5"),
    ]
    for goal_line, over_key, under_key in goal_lines:
        if odds.get(over_key) is not None:
            selections.setdefault("Total de Gols", []).append((
                f"Gols Over {goal_line}",
                float(odds[over_key]),
                goal_line,
            ))
        if odds.get(under_key) is not None:
            selections.setdefault("Total de Gols", []).append((
                f"Gols Under {goal_line}",
                float(odds[under_key]),
                goal_line,
            ))

    return selections


# ── Deduplicação de linhas redundantes ────────────────────────────────


def _deduplicate_lines(
    candidates: list[PreLlmCandidate],
    max_per_direction: int = 2,
) -> list[PreLlmCandidate]:
    """Remove linhas redundantes por direção de mercado.

    Para cada mercado, mantém no máximo ``max_per_direction`` linhas,
    priorizando as que têm odd mais próxima da Zona Alvo (1.60-2.20).
    """
    from collections import defaultdict

    # Agrupa por market_name
    by_market: dict[str, list[PreLlmCandidate]] = defaultdict(list)
    for c in candidates:
        by_market[c.market_name].append(c)

    result: list[PreLlmCandidate] = []
    for market_name, cands in by_market.items():
        # Ordena: SINGLE primeiro, depois VARIANCE, depois COMPOSITION
        def _sort_key(c: PreLlmCandidate) -> tuple:
            zone_priority = {
                _ZONE_SINGLE: 0,
                _ZONE_VARIANCE: 1,
                _ZONE_BUILDER: 2,
            }
            return (zone_priority.get(c.zone, 99), abs(c.odd - 1.9))

        cands_sorted = sorted(cands, key=_sort_key)
        result.extend(cands_sorted[:max_per_direction])

        removed_count = len(cands) - min(len(cands), max_per_direction)
        if removed_count > 0:
            logger.debug(
                "Dedup: %s — %d linhas redundantes removidas (max=%d)",
                market_name, removed_count, max_per_direction,
            )

    return result


# ── Filtro para snapshots do scraper (camada 1) ───────────────────────


def apply_scraper_market_filter(
    markets: dict[str, Any],
    *,
    min_odd: float = _MIN_ODD,
) -> dict[str, Any]:
    """Filtra mercados de um evento do scraper antes de salvar o snapshot.

    Remove:
    - Mercados não rastreados (fora da whitelist)
    - Seleções com odd < min_odd
    - Handicaps e props

    Args:
        markets: Dicionário de mercados do evento (``_extract_markets``).
        min_odd: Odd mínima operacional.

    Returns:
        Dicionário de mercados filtrado (pode ser vazio).
    """
    filtered: dict[str, Any] = {}

    for market_name, mdata in markets.items():
        # Filtro whitelist
        if not _is_market_whitelisted(market_name):
            continue
        if _is_handicap_market(market_name):
            continue
        if _is_player_market(market_name):
            continue

        # Filtra seleções individuais por odd mínima
        selections = mdata.get("selections", [])
        kept_selections = [
            s for s in selections
            if s.get("price") is None or float(s["price"]) >= min_odd
        ]

        if not kept_selections:
            continue

        # Reconstrói o market data com seleções filtradas
        filtered_market = dict(mdata)
        filtered_market["selections"] = kept_selections

        # Recalcula atalhos (home/draw/away/yes/no)
        for key in ("home", "draw", "away", "yes", "no"):
            if key in filtered_market:
                matching = [
                    s for s in kept_selections
                    if s.get("code", "").lower() == key
                    or s.get("name", "").lower() == key
                ]
                if matching:
                    filtered_market[key] = matching[0]["price"]
                else:
                    del filtered_market[key]

        filtered[market_name] = filtered_market

    return filtered
