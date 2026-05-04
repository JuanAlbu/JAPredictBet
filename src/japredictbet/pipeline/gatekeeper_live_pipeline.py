"""Gatekeeper Live Pipeline — shadow-mode orchestration.

Supports two modes:

1. **Pre-match mode** (primary): loads odds from daily JSON snapshots
   created by ``scripts/superbet_scraper.py``.  Runs the Gatekeeper
   LLM agent on all matches for the day, evaluating ALL markets
   (corners, 1x2, BTTS, Over/Under Gols) in a single LLM call.

2. **Live mode** (T-60): connects to Superbet SSE feed + API-Football
   to monitor odds movements during matches.

All outputs are written to a shadow log — **no real bets are ever placed**.

Typical invocation::

    # Pre-match (from scraper snapshot)
    pipeline = GatekeeperLivePipeline.from_config(config)
    results  = pipeline.run(pre_match_date="2026-04-11")

    # Live T-60
    results  = pipeline.run()
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from japredictbet.agents.base import AgentContext
from japredictbet.agents.gatekeeper import (
    GatekeeperAgent,
    GatekeeperResult,
    MarketEvaluation,
    _STATUS_APPROVED,
)
from japredictbet.config import PipelineConfig
from japredictbet.data.context_collector import ContextCollector, MatchContext
from japredictbet.data.feature_store import get_active_tournament_ids
from japredictbet.odds.pre_match_odds import load_pre_match_contexts

logger = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class ShadowEntry:
    """Single entry in the shadow log for one match evaluation."""

    timestamp: str
    event_id: str
    home_team: str
    away_team: str
    kickoff_utc: Optional[str]
    # Odds
    corner_line: Optional[float] = None
    corner_over_odds: Optional[float] = None
    corner_under_odds: Optional[float] = None
    # Gatekeeper LLM decision (all markets)
    gatekeeper_status: Optional[str] = None
    gatekeeper_stake: Optional[float] = None
    gatekeeper_market: Optional[str] = None
    gatekeeper_odd: Optional[float] = None
    gatekeeper_edge: Optional[str] = None
    gatekeeper_classification: Optional[str] = None
    gatekeeper_justification: Optional[str] = None
    gatekeeper_red_flags: List[str] = field(default_factory=list)
    gatekeeper_markets: List[Dict[str, Any]] = field(default_factory=list)
    gatekeeper_markets_evaluated: int = 0
    gatekeeper_markets_approved: int = 0


@dataclass
class PipelineRunResult:
    """Summary of a full pipeline run."""

    run_at: str
    matches_collected: int
    matches_evaluated: int
    entries_approved: int
    entries: List[ShadowEntry]


# ── Pipeline ─────────────────────────────────────────────────────────


class GatekeeperLivePipeline:
    """Orchestrate shadow-mode evaluation with a single LLM motor.

    Flow
    ----
    1. Collect upcoming matches via ``ContextCollector`` (Superbet + API-Football).
    2. For each match with valid odds:
       a. **Gatekeeper LLM**: evaluate ALL markets (corners, 1x2, BTTS,
          Over/Under Gols) via context only (no ML / ensemble data).
    3. Cap approved entries at ``max_entries_per_day``.
    4. Write all evaluations to the shadow log.

    The Gatekeeper is the **only evaluation engine** in this pipeline.
    The 30-model ensemble is exclusive to Mode 1 (Backtest / consensus
    accuracy report).
    """

    def __init__(
        self,
        config: PipelineConfig,
        context_collector: ContextCollector,
        gatekeeper: Optional[GatekeeperAgent],
    ) -> None:
        self._config = config
        self._collector = context_collector
        self._gatekeeper = gatekeeper
        self._shadow_log_path = Path(
            config.gatekeeper.shadow_log_path
            if config.gatekeeper
            else "logs/shadow_bets.log"
        )

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config: PipelineConfig,
        dry_run: bool = False,
    ) -> GatekeeperLivePipeline:
        """Build a ready-to-run pipeline from a ``PipelineConfig``.

        Parameters
        ----------
        config:
            Fully-loaded ``PipelineConfig`` (including gatekeeper block).
        dry_run:
            If True, skip LLM agent creation.
            The pipeline will still collect matches but won't evaluate.
        """
        gk_cfg = config.gatekeeper
        if gk_cfg is None:
            raise ValueError(
                "PipelineConfig.gatekeeper is None — "
                "add a 'gatekeeper' block to config.yml."
            )

        # Resolve API keys
        api_keys = config.api_keys.resolve() if config.api_keys else None
        if api_keys is None and not dry_run:
            raise ValueError(
                "PipelineConfig.api_keys is None — "
                "add an 'api_keys' block to config.yml."
            )

        # Derive tournament whitelist from league folders that actually have
        # historical CSV data.
        active_tournament_ids = get_active_tournament_ids()
        superbet_cfg = replace(
            config.superbet_shadow,
            tournament_ids=active_tournament_ids,
        )

        # Context collector
        collector = ContextCollector.from_configs(
            superbet_cfg=superbet_cfg,
            api_football_cfg=config.api_football,
            api_football_key=api_keys.api_football_key if api_keys else None,
            gatekeeper_cfg=gk_cfg,
        )

        # Gatekeeper agent (all markets via single LLM call)
        gatekeeper: Optional[GatekeeperAgent] = None

        if dry_run:
            logger.info("Dry-run mode: Gatekeeper LLM will be skipped.")
        else:
            llm_base_url = api_keys.llm_base_url if api_keys else None
            llm_model = api_keys.llm_model if api_keys else None
            gatekeeper = GatekeeperAgent(
                gatekeeper_cfg=gk_cfg,
                api_key=api_keys.llm_api_key if api_keys else None,
                base_url=llm_base_url or None,
                model=llm_model or "gpt-4o-mini",
            )

        return cls(
            config=config,
            context_collector=collector,
            gatekeeper=gatekeeper,
        )

    # ── Main entry point ─────────────────────────────────────────────

    def run(
        self,
        pre_match_date: Optional[str] = None,
        dry_run: bool = False,
    ) -> PipelineRunResult:
        """Execute the pipeline and return results.

        Parameters
        ----------
        pre_match_date:
            If provided, loads pre-match odds from the scraper snapshot
            for the given date (YYYY-MM-DD).  This is the **primary**
            mode of operation — run the scraper first, then the pipeline.
            If ``None``, falls back to live T-60 collection.
        dry_run:
            If True, skip LLM calls.  Useful for validating data flow
            without API keys.
        """

        now = datetime.now(timezone.utc)
        logger.info("=== Gatekeeper Live Pipeline — %s ===", now.isoformat())

        # ── 1. Collect matches ───────────────────────────────────────
        if pre_match_date:
            logger.info(
                "Pre-match mode: loading snapshot for %s", pre_match_date
            )
            matches = load_pre_match_contexts(date=pre_match_date)

            # Enrich with API-Football data (lineups, standings, injuries)
            matches = self._collector.enrich_pre_match_contexts(
                matches, date=pre_match_date,
            )
        else:
            matches = self._collect_matches()
        logger.info("Collected %d matches with context.", len(matches))

        if not matches:
            result = PipelineRunResult(
                run_at=now.isoformat(),
                matches_collected=0,
                matches_evaluated=0,
                entries_approved=0,
                entries=[],
            )
            self._write_shadow_log(result)
            return result

        # ── 2. Evaluate each match ───────────────────────────────────
        entries: List[ShadowEntry] = []
        max_entries = (
            self._config.gatekeeper.max_entries_per_day
            if self._config.gatekeeper
            else 5
        )
        approved_count = 0

        for match_ctx in matches:
            entry = self._evaluate_single_match(match_ctx, dry_run=dry_run)
            if entry is None:
                continue

            # Cap approved entries
            if entry.gatekeeper_status == _STATUS_APPROVED:
                if approved_count >= max_entries:
                    entry.gatekeeper_status = "CAPPED"
                    entry.gatekeeper_justification = (
                        f"Limite diário de {max_entries} entradas atingido."
                    )
                else:
                    approved_count += 1

            entries.append(entry)

        result = PipelineRunResult(
            run_at=now.isoformat(),
            matches_collected=len(matches),
            matches_evaluated=len(entries),
            entries_approved=approved_count,
            entries=entries,
        )

        # ── 3. Persist shadow log ────────────────────────────────────
        self._write_shadow_log(result)
        logger.info(
            "Pipeline complete: %d collected, %d evaluated, %d approved.",
            result.matches_collected,
            result.matches_evaluated,
            result.entries_approved,
        )
        return result

    # ── Internal methods ─────────────────────────────────────────────

    def _collect_matches(self) -> List[MatchContext]:
        """Collect upcoming matches via the ContextCollector."""
        try:
            return self._collector.collect_upcoming()
        except Exception:
            logger.exception("Failed to collect upcoming matches.")
            return []

    def _evaluate_single_match(
        self, match_ctx: MatchContext, *, dry_run: bool = False,
    ) -> Optional[ShadowEntry]:
        """Run Gatekeeper LLM evaluation for a single match.

        Forwards the match context (odds, lineups, standings,
        qualitative factors) to the Gatekeeper agent, which evaluates
        ALL available markets in a single LLM call.
        """
        home = match_ctx.home_team
        away = match_ctx.away_team
        event_id = match_ctx.event_id

        logger.info("Evaluating: %s vs %s (event=%s)", home, away, event_id)

        # ── Gatekeeper LLM (all markets, context-only) ───────────────
        if dry_run or self._gatekeeper is None:
            logger.info(
                "Dry-run: skipping Gatekeeper LLM for %s vs %s.", home, away
            )
            gk_result = GatekeeperResult(
                status="DRY_RUN",
                justification="Dry-run mode — LLM evaluation skipped.",
            )
        else:
            gk_result = self._call_gatekeeper(match_ctx)

        # ── Serialize markets for shadow log ─────────────────────────
        serialized_markets = [
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
            for m in gk_result.markets
        ]

        # ── Build shadow entry ───────────────────────────────────────
        odds = match_ctx.odds
        return ShadowEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id=event_id,
            home_team=home,
            away_team=away,
            kickoff_utc=match_ctx.kickoff_utc,
            corner_line=odds.corner_line,
            corner_over_odds=odds.corner_over_odds,
            corner_under_odds=odds.corner_under_odds,
            gatekeeper_status=gk_result.status,
            gatekeeper_stake=gk_result.stake,
            gatekeeper_market=gk_result.market,
            gatekeeper_odd=gk_result.odd,
            gatekeeper_edge=gk_result.edge,
            gatekeeper_classification=gk_result.classification,
            gatekeeper_justification=gk_result.justification,
            gatekeeper_red_flags=gk_result.red_flags,
            gatekeeper_markets=serialized_markets,
            gatekeeper_markets_evaluated=gk_result.markets_evaluated,
            gatekeeper_markets_approved=gk_result.markets_approved,
        )

    def _call_gatekeeper(
        self,
        match_ctx: MatchContext,
    ) -> GatekeeperResult:
        """Call the Gatekeeper LLM agent (context-only, no ML data).

        The Gatekeeper evaluates ALL markets (corners, 1x2, BTTS,
        Over/Under Gols) in a single call using Prompt Mestre V26.
        """
        try:
            context = AgentContext(
                payload={
                    "match_context_json": match_ctx.to_llm_context(),
                }
            )
            raw = self._gatekeeper.run(context)
            markets_data = raw.get("markets", [])
            markets = [
                MarketEvaluation(
                    market=m.get("market", ""),
                    status=m.get("status", "NO BET"),
                    stake=m.get("stake"),
                    odd=m.get("odd"),
                    edge=m.get("edge"),
                    classification=m.get("classification"),
                    justification=m.get("justification"),
                    red_flags=m.get("red_flags", []),
                )
                for m in markets_data
                if isinstance(m, dict)
            ]

            best_data = raw.get("best_pick")
            best_pick = None
            if best_data and isinstance(best_data, dict):
                best_pick = MarketEvaluation(
                    market=best_data.get("market", ""),
                    status=best_data.get("status", "NO BET"),
                    stake=best_data.get("stake"),
                    odd=best_data.get("odd"),
                    edge=best_data.get("edge"),
                    classification=best_data.get("classification"),
                    justification=best_data.get("justification"),
                    red_flags=best_data.get("red_flags", []),
                )

            has_approved = any(
                m.status == _STATUS_APPROVED for m in markets
            )
            overall_status = (
                _STATUS_APPROVED if has_approved else raw.get("status", "NO BET")
            )

            return GatekeeperResult(
                status=overall_status,
                stake=best_pick.stake if best_pick else raw.get("stake"),
                market=best_pick.market if best_pick else raw.get("market"),
                odd=best_pick.odd if best_pick else raw.get("odd"),
                edge=best_pick.edge if best_pick else raw.get("edge"),
                classification=(
                    best_pick.classification
                    if best_pick
                    else raw.get("classification")
                ),
                justification=(
                    best_pick.justification
                    if best_pick
                    else raw.get("justification")
                ),
                red_flags=best_pick.red_flags if best_pick else raw.get("red_flags", []),
                markets=markets,
                best_pick=best_pick,
            )
        except Exception:
            logger.exception(
                "Gatekeeper call failed for %s vs %s.",
                match_ctx.home_team,
                match_ctx.away_team,
            )
            return GatekeeperResult(
                status="ERROR",
                justification="Gatekeeper call failed — see logs.",
            )

    def _write_shadow_log(self, result: PipelineRunResult) -> None:
        """Append the pipeline result to the shadow log (JSONL format)."""
        try:
            self._shadow_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._shadow_log_path, "a", encoding="utf-8") as f:
                for entry in result.entries:
                    line = json.dumps(asdict(entry), ensure_ascii=False)
                    f.write(line + "\n")
            logger.info("Shadow log written to %s", self._shadow_log_path)
        except Exception:
            logger.exception("Failed to write shadow log.")
