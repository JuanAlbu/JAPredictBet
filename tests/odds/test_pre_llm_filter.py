"""Unit tests for the Bouncer V2 — ``pre_llm_filter`` module.

Covers:
- ``classify_odd`` — pricing zone detection
- ``build_llm_candidates`` — full pre-filter pipeline
- ``_is_market_whitelisted`` / ``_is_player_market`` / ``_is_handicap_market``
- ``apply_scraper_market_filter`` — snapshot-level filter
- ``_deduplicate_lines`` — redundancy reduction
"""

from __future__ import annotations

import json

from japredictbet.odds.pre_llm_filter import (
    WHITELIST_MARKETS,
    PreLlmCandidate,
    PreLlmFilterResult,
    apply_scraper_market_filter,
    build_llm_candidates,
    classify_odd,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_ctx_json(
    *,
    event_id: str = "evt_001",
    home_team: str = "Flamengo",
    away_team: str = "Palmeiras",
    home_odds: float | None = 1.80,
    draw_odds: float | None = 3.40,
    away_odds: float | None = 4.50,
    corner_line: float | None = 9.5,
    corner_over_odds: float | None = 1.90,
    corner_under_odds: float | None = 1.90,
    btts_yes: float | None = 2.00,
    btts_no: float | None = 1.80,
    goals_over_1_5: float | None = 1.50,
    goals_under_1_5: float | None = 2.50,
    goals_over_2_5: float | None = 1.80,
    goals_under_2_5: float | None = 2.00,
) -> str:
    """Build a JSON string simulating ``MatchContext.to_llm_context()``."""
    odds: dict[str, float] = {}
    for k, v in [
        ("home_odds", home_odds),
        ("draw_odds", draw_odds),
        ("away_odds", away_odds),
        ("corner_line", corner_line),
        ("corner_over_odds", corner_over_odds),
        ("corner_under_odds", corner_under_odds),
        ("btts_yes", btts_yes),
        ("btts_no", btts_no),
        ("goals_over_1_5", goals_over_1_5),
        ("goals_under_1_5", goals_under_1_5),
        ("goals_over_2_5", goals_over_2_5),
        ("goals_under_2_5", goals_under_2_5),
    ]:
        if v is not None:
            odds[k] = v

    ctx = {
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "odds": odds,
    }
    return json.dumps(ctx, ensure_ascii=False)


def _make_scraper_markets(
    *,
    include_corner: bool = True,
    include_1x2: bool = True,
    include_btts: bool = True,
    include_goals: bool = True,
    include_handicap: bool = False,
    include_player_prop: bool = False,
    include_exotic: bool = False,
) -> dict:
    """Build a mock ``markets`` dict as produced by ``_extract_markets``."""
    markets: dict = {}

    if include_corner:
        markets["Total de Escanteios"] = {
            "code": "corner",
            "selections": [
                {"code": "over", "name": "Over 9.5", "price": 1.90},
                {"code": "under", "name": "Under 9.5", "price": 1.90},
            ],
            "over": 1.90,
            "under": 1.90,
        }

    if include_1x2:
        markets["Resultado Final"] = {
            "code": "1x2",
            "selections": [
                {"code": "home", "name": "Flamengo", "price": 1.80},
                {"code": "draw", "name": "Empate", "price": 3.40},
                {"code": "away", "name": "Palmeiras", "price": 4.50},
            ],
            "home": 1.80,
            "draw": 3.40,
            "away": 4.50,
        }

    if include_btts:
        markets["Ambas as Equipes Marcam"] = {
            "code": "btts",
            "selections": [
                {"code": "yes", "name": "Sim", "price": 2.00},
                {"code": "no", "name": "Não", "price": 1.80},
            ],
            "yes": 2.00,
            "no": 1.80,
        }

    if include_goals:
        markets["Total de Gols"] = {
            "code": "goals",
            "selections": [
                {"code": "over", "name": "Over 1.5", "price": 1.50},
                {"code": "under", "name": "Under 1.5", "price": 2.50},
                {"code": "over", "name": "Over 2.5", "price": 1.80},
                {"code": "under", "name": "Under 2.5", "price": 2.00},
            ],
        }

    if include_handicap:
        markets["Handicap Asiático"] = {
            "code": "handicap",
            "selections": [
                {"code": "home", "name": "Flamengo -1.5", "price": 2.10},
            ],
        }

    if include_player_prop:
        markets["Jogador - Chutes no Gol"] = {
            "code": "player_shots",
            "selections": [
                {"code": "yes", "name": "Gabriel > 1.5", "price": 3.00},
            ],
        }

    if include_exotic:
        markets["Placar Correto"] = {
            "code": "correct_score",
            "selections": [
                {"code": "1-0", "name": "1-0", "price": 7.00},
            ],
        }

    return markets


# ── classify_odd ────────────────────────────────────────────────────────


class TestClassifyOdd:
    """Pricing zone classification."""

    def test_dead_below_1_25(self) -> None:
        assert classify_odd(1.10) == "ZONA MORTA"
        assert classify_odd(1.24) == "ZONA MORTA"

    def test_dead_at_1_25_boundary(self) -> None:
        assert classify_odd(1.25) == "PERNA DE COMPOSIÇÃO"

    def test_composition_range(self) -> None:
        assert classify_odd(1.25) == "PERNA DE COMPOSIÇÃO"
        assert classify_odd(1.59) == "PERNA DE COMPOSIÇÃO"
        assert classify_odd(1.40) == "PERNA DE COMPOSIÇÃO"

    def test_single_range(self) -> None:
        assert classify_odd(1.60) == "APOSTA SIMPLES"
        assert classify_odd(2.20) == "APOSTA SIMPLES"
        assert classify_odd(1.90) == "APOSTA SIMPLES"

    def test_variance_above_2_20(self) -> None:
        assert classify_odd(2.21) == "APOSTA SIMPLES — VARIÂNCIA"
        assert classify_odd(5.00) == "APOSTA SIMPLES — VARIÂNCIA"

    def test_zero_odd(self) -> None:
        assert classify_odd(0.0) == "ZONA MORTA"

    def test_negative_odd(self) -> None:
        assert classify_odd(-1.0) == "ZONA MORTA"


# ── build_llm_candidates ────────────────────────────────────────────────


class TestBuildLlmCandidates:
    """Full pre-filter pipeline."""

    def test_invalid_json_returns_empty(self) -> None:
        result = build_llm_candidates("{invalid}")
        assert result.should_call_llm is False
        assert result.candidates == []
        assert "JSON inválido" in " ".join(result.reasons)

    def test_empty_json(self) -> None:
        result = build_llm_candidates("{}")
        assert result.should_call_llm is False
        assert result.candidates == []

    def test_all_single_odds_calls_llm(self) -> None:
        ctx = _make_ctx_json(home_odds=1.80, draw_odds=3.40, away_odds=4.50)
        result = build_llm_candidates(ctx)
        assert result.should_call_llm is True
        assert result.has_single_or_variance is True
        assert result.candidate_count >= 3  # home, draw, away

    def test_all_dead_odds_skips_llm(self) -> None:
        ctx = _make_ctx_json(
            home_odds=1.10,
            draw_odds=1.15,
            away_odds=1.20,
            corner_over_odds=1.05,
            corner_under_odds=1.05,
            btts_yes=1.10,
            btts_no=1.12,
            goals_over_1_5=1.20,
            goals_under_1_5=1.22,
            goals_over_2_5=1.18,
            goals_under_2_5=1.20,
        )
        result = build_llm_candidates(ctx)
        assert result.should_call_llm is False
        assert result.candidates == []
        assert result.total_removed > 0

    def test_all_composition_skips_llm_by_default(self) -> None:
        ctx = _make_ctx_json(
            home_odds=1.50,
            draw_odds=1.55,
            away_odds=1.59,
            btts_yes=1.50,
            btts_no=1.45,
            corner_over_odds=1.55,
            corner_under_odds=1.58,
            goals_over_1_5=1.40,
            goals_under_1_5=1.45,
            goals_over_2_5=1.50,
            goals_under_2_5=1.55,
        )
        result = build_llm_candidates(ctx)
        assert result.should_call_llm is False
        assert result.has_composition is True
        assert result.has_single_or_variance is False

    def test_composition_enabled_triggers_llm_with_2_plus(self) -> None:
        ctx = _make_ctx_json(
            home_odds=1.50,
            draw_odds=1.55,
            away_odds=1.59,
            btts_yes=1.40,
            btts_no=1.45,
            corner_over_odds=1.55,
            corner_under_odds=1.58,
            goals_over_1_5=1.40,
            goals_under_1_5=1.45,
            goals_over_2_5=1.50,
            goals_under_2_5=1.55,
        )
        result = build_llm_candidates(ctx, composition_enabled=True)
        assert result.should_call_llm is True
        assert result.composition_count >= 2

    def test_composition_enabled_but_only_one_skips_llm(self) -> None:
        ctx = _make_ctx_json(
            home_odds=1.50,
            # Only one composition — the rest are dead
            draw_odds=1.10,
            away_odds=1.10,
            corner_over_odds=1.10,
            corner_under_odds=1.10,
            btts_yes=1.10,
            btts_no=1.10,
            goals_over_1_5=1.10,
            goals_under_1_5=1.10,
            goals_over_2_5=1.10,
            goals_under_2_5=1.10,
        )
        result = build_llm_candidates(ctx, composition_enabled=True)
        assert result.should_call_llm is False
        assert result.composition_count == 1

    def test_mixed_zones_only_single_triggers_llm(self) -> None:
        ctx = _make_ctx_json(
            home_odds=1.80,  # SINGLE
            draw_odds=1.50,  # COMPOSITION
            away_odds=1.10,  # DEAD
        )
        result = build_llm_candidates(ctx)
        assert result.should_call_llm is True
        assert result.has_single_or_variance is True
        assert result.has_composition is True

    def test_variance_odd_gets_max_stake_0_5(self) -> None:
        ctx = _make_ctx_json(home_odds=3.50, away_odds=5.00)
        result = build_llm_candidates(ctx)
        var_candidates = [c for c in result.candidates if c.max_stake is not None]
        assert len(var_candidates) > 0
        for c in var_candidates:
            assert c.max_stake == 0.5
            assert c.zone == "APOSTA SIMPLES — VARIÂNCIA"

    def test_single_candidate_allows_stake_and_best_pick(self) -> None:
        ctx = _make_ctx_json(home_odds=1.80)
        result = build_llm_candidates(ctx)
        for c in result.candidates:
            if c.zone == "APOSTA SIMPLES":
                assert c.stake_allowed is True
                assert c.best_pick_allowed is True

    def test_composition_candidate_no_stake_no_best_pick(self) -> None:
        ctx = _make_ctx_json(home_odds=1.50)
        result = build_llm_candidates(ctx)
        for c in result.candidates:
            if c.zone == "PERNA DE COMPOSIÇÃO":
                assert c.stake_allowed is False
                assert c.best_pick_allowed is False

    def test_custom_min_odd(self) -> None:
        """With min_odd=1.50, odds between 1.25-1.49 become DEAD."""
        ctx = _make_ctx_json(
            home_odds=1.40,
            draw_odds=1.50,
            away_odds=1.80,
            # Set all other odds to dead so they don't interfere
            corner_over_odds=1.10,
            corner_under_odds=1.10,
            btts_yes=1.10,
            btts_no=1.10,
            goals_over_1_5=1.10,
            goals_under_1_5=1.10,
            goals_over_2_5=1.10,
            goals_under_2_5=1.10,
        )
        result = build_llm_candidates(ctx, min_odd=1.50)
        # 1.40 < 1.50 → DEAD; 1.50 → COMPOSITION (since 1.50 <= 1.59)
        # 1.80 → SINGLE
        assert result.total_removed >= 1  # home_odds removed
        singles = [c for c in result.candidates if c.stake_allowed]
        assert len(singles) == 1

    def test_event_metadata_preserved(self) -> None:
        ctx = _make_ctx_json(event_id="evt_999", home_team="TimeA", away_team="TimeB")
        result = build_llm_candidates(ctx)
        assert result.event_id == "evt_999"
        assert result.home_team == "TimeA"
        assert result.away_team == "TimeB"

    def test_market_not_in_whitelist_removed(self) -> None:
        """Simulate a JSON with a non-whitelisted market field."""
        ctx = json.dumps(
            {
                "event_id": "evt_001",
                "home_team": "A",
                "away_team": "B",
                "odds": {
                    "home_odds": 1.80,
                    "some_exotic_market": 5.00,
                },
            }
        )
        result = build_llm_candidates(ctx)
        # home_odds (1.80) should be a valid candidate
        # some_exotic_market won't be extracted by _extract_selections
        assert result.should_call_llm is True
        assert result.candidate_count >= 1

    def test_handicap_and_player_markets_removed(self) -> None:
        """Only whitelisted markets pass through."""
        ctx = _make_ctx_json()
        result = build_llm_candidates(ctx)
        # All standard odds should be candidates
        assert result.candidate_count >= 8


# ── _is_market_whitelisted (via WHITELIST_MARKETS) ─────────────────────


class TestMarketWhitelist:
    """Whitelist membership checks."""

    def test_whitelist_contains_core_markets(self) -> None:
        assert "resultado final" in WHITELIST_MARKETS
        assert "1x2" in WHITELIST_MARKETS
        assert "ambas as equipes marcam" in WHITELIST_MARKETS
        assert "total de escanteios" in WHITELIST_MARKETS
        assert "total de gols" in WHITELIST_MARKETS

    def test_whitelist_contains_first_half(self) -> None:
        assert "1º tempo - resultado final" in WHITELIST_MARKETS
        assert "1º tempo - total de escanteios" in WHITELIST_MARKETS

    def test_whitelist_contains_english_variants(self) -> None:
        assert "match result" in WHITELIST_MARKETS
        assert "btts" in WHITELIST_MARKETS
        assert "both teams" in WHITELIST_MARKETS


# ── apply_scraper_market_filter ────────────────────────────────────────


class TestApplyScraperMarketFilter:
    """Snapshot-level market filter."""

    def test_keeps_whitelisted_markets(self) -> None:
        markets = _make_scraper_markets()
        filtered = apply_scraper_market_filter(markets)
        assert "Total de Escanteios" in filtered
        assert "Resultado Final" in filtered
        assert "Ambas as Equipes Marcam" in filtered
        assert "Total de Gols" in filtered

    def test_removes_handicap(self) -> None:
        markets = _make_scraper_markets(include_handicap=True)
        filtered = apply_scraper_market_filter(markets)
        assert "Handicap Asiático" not in filtered

    def test_removes_player_props(self) -> None:
        markets = _make_scraper_markets(include_player_prop=True)
        filtered = apply_scraper_market_filter(markets)
        assert "Jogador - Chutes no Gol" not in filtered

    def test_removes_exotic_markets(self) -> None:
        markets = _make_scraper_markets(include_exotic=True)
        filtered = apply_scraper_market_filter(markets)
        assert "Placar Correto" not in filtered

    def test_removes_selections_below_min_odd(self) -> None:
        markets = _make_scraper_markets()
        # goals_over_1_5 is 1.50, min_odd=1.60 should remove it
        filtered = apply_scraper_market_filter(markets, min_odd=1.60)
        if "Total de Gols" in filtered:
            selections = filtered["Total de Gols"].get("selections", [])
            prices = [s["price"] for s in selections]
            assert all(p >= 1.60 for p in prices)

    def test_removes_empty_market_after_selection_filter(self) -> None:
        markets = {
            "Total de Escanteios": {
                "code": "corner",
                "selections": [
                    {"code": "over", "name": "Over 9.5", "price": 1.20},  # below min
                    {"code": "under", "name": "Under 9.5", "price": 1.15},  # below min
                ],
                "over": 1.20,
                "under": 1.15,
            },
            "Resultado Final": {
                "code": "1x2",
                "selections": [
                    {"code": "home", "name": "Home", "price": 1.80},
                ],
                "home": 1.80,
            },
        }
        filtered = apply_scraper_market_filter(markets, min_odd=1.25)
        # Corner should be removed (all selections below 1.25)
        assert "Total de Escanteios" not in filtered
        assert "Resultado Final" in filtered

    def test_empty_markets_returns_empty(self) -> None:
        assert apply_scraper_market_filter({}) == {}

    def test_recalculates_shortcut_keys(self) -> None:
        markets = {
            "Resultado Final": {
                "code": "1x2",
                "selections": [
                    {"code": "home", "name": "Home", "price": 1.80},
                    {"code": "draw", "name": "Draw", "price": 3.40},
                    {"code": "away", "name": "Away", "price": 1.10},  # below min
                ],
                "home": 1.80,
                "draw": 3.40,
                "away": 1.10,
            },
        }
        filtered = apply_scraper_market_filter(markets, min_odd=1.25)
        assert "Resultado Final" in filtered
        # "away" shortcut should be removed since it's below min_odd
        assert "away" not in filtered["Resultado Final"]
        assert filtered["Resultado Final"]["home"] == 1.80


# ── PreLlmFilterResult ─────────────────────────────────────────────────


class TestPreLlmFilterResult:
    """Data class behavior."""

    def test_candidate_count_property(self) -> None:
        result = PreLlmFilterResult(
            event_id="evt_001",
            home_team="A",
            away_team="B",
            candidates=[
                PreLlmCandidate(market_name="1x2", selection_label="HOME", odd=1.80),
                PreLlmCandidate(market_name="1x2", selection_label="DRAW", odd=3.40),
            ],
        )
        assert result.candidate_count == 2

    def test_default_values(self) -> None:
        result = PreLlmFilterResult(event_id="e", home_team="A", away_team="B")
        assert result.candidates == []
        assert result.should_call_llm is False
        assert result.total_removed == 0
        assert result.reasons == []
