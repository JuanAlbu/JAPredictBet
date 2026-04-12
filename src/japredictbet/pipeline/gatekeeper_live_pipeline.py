"""Gatekeeper Live Pipeline — shadow-mode orchestration.

Supports two modes:

1. **Pre-match mode** (primary): loads odds from daily JSON snapshots
   created by ``scripts/superbet_scraper.py``.  Runs consensus (corners)
   + Gatekeeper + Analyst agents on all matches for the day.

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
import pickle
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from japredictbet.agents.analyst import AnalystAgent, AnalystResult
from japredictbet.agents.base import AgentContext
from japredictbet.agents.gatekeeper import GatekeeperAgent, GatekeeperResult
from japredictbet.betting.engine import ConsensusEngine
from japredictbet.config import PipelineConfig
from japredictbet.data.context_collector import ContextCollector, MatchContext
from japredictbet.data.feature_store import FeatureStore, get_active_tournament_ids
from japredictbet.odds.pre_match_odds import load_pre_match_contexts
from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import TrainedModels

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
    # Ensemble output
    ensemble_mean_lambda: Optional[float] = None
    ensemble_std_lambda: Optional[float] = None
    consensus_pct: Optional[float] = None
    votes_positive: Optional[int] = None
    total_models: Optional[int] = None
    p_model_mean: Optional[float] = None
    edge_mean: Optional[float] = None
    consensus_bet: Optional[bool] = None
    # Gatekeeper LLM decision
    gatekeeper_status: Optional[str] = None
    gatekeeper_stake: Optional[float] = None
    gatekeeper_market: Optional[str] = None
    gatekeeper_odd: Optional[float] = None
    gatekeeper_edge: Optional[str] = None
    gatekeeper_justification: Optional[str] = None
    gatekeeper_red_flags: List[str] = field(default_factory=list)
    # Analyst agent (non-corner markets: 1x2, BTTS, etc.)
    analyst_status: Optional[str] = None
    analyst_best_market: Optional[str] = None
    analyst_best_stake: Optional[float] = None
    analyst_best_odd: Optional[float] = None
    analyst_best_edge: Optional[str] = None
    analyst_best_justification: Optional[str] = None
    analyst_markets_evaluated: int = 0
    analyst_markets_approved: int = 0


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
    """Orchestrate T-60 shadow-mode evaluation.

    Flow
    ----
    1. Collect upcoming matches via ``ContextCollector`` (Superbet + API-Football).
    2. Load pre-trained ensemble models from the artifacts directory.
    3. For each match with valid odds:
       a. Run 30-model consensus voting.
       b. Feed ``MatchContext`` + ensemble output to ``GatekeeperAgent``.
    4. Cap approved entries at ``max_entries_per_day``.
    5. Write all evaluations to the shadow log.
    """

    def __init__(
        self,
        config: PipelineConfig,
        context_collector: ContextCollector,
        gatekeeper: Optional[GatekeeperAgent],
        models: List[TrainedModels],
        consensus_engine: ConsensusEngine,
        feature_store: Optional[FeatureStore] = None,
        analyst: Optional[AnalystAgent] = None,
    ) -> None:
        self._config = config
        self._collector = context_collector
        self._gatekeeper = gatekeeper
        self._analyst = analyst
        self._models = models
        self._consensus = consensus_engine
        self._feature_store = feature_store
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
        models_dir: str | Path = "artifacts/models",
        feature_store_path: str | Path | None = None,
        dry_run: bool = False,
    ) -> GatekeeperLivePipeline:
        """Build a ready-to-run pipeline from a ``PipelineConfig``.

        Parameters
        ----------
        config:
            Fully-loaded ``PipelineConfig`` (including gatekeeper block).
        models_dir:
            Directory containing persisted ``.pkl`` ensemble artifacts.
        dry_run:
            If True, skip LLM agent creation (Gatekeeper + Analyst).
            The pipeline will still collect matches and run consensus.
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
        # historical CSV data. This keeps Superbet aligned with the set of
        # leagues for which we can build features.
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

        # Gatekeeper agent (corners — consensus + LLM)
        gatekeeper: Optional[GatekeeperAgent] = None
        analyst: Optional[AnalystAgent] = None

        if dry_run:
            logger.info("Dry-run mode: LLM agents (Gatekeeper + Analyst) will be skipped.")
        else:
            gatekeeper = GatekeeperAgent(
                gatekeeper_cfg=gk_cfg,
                api_key=api_keys.llm_api_key if api_keys else None,
            )
            analyst = AnalystAgent(
                gatekeeper_cfg=gk_cfg,
                api_key=api_keys.llm_api_key if api_keys else None,
            )

        # Load ensemble models
        models = _load_ensemble(Path(models_dir))

        # Load feature store (optional — consensus skipped if missing)
        # Prefer explicit arg → config field → default path
        resolved_fs_path = (
            Path(feature_store_path)
            if feature_store_path is not None
            else Path(gk_cfg.feature_store_path)
        )
        feature_store: Optional[FeatureStore] = None
        try:
            feature_store = FeatureStore.load(resolved_fs_path)
        except FileNotFoundError:
            logger.warning(
                "Feature store not found at '%s'. "
                "Consensus will be skipped. "
                "Run 'python scripts/refresh_features.py' to build it.",
                resolved_fs_path,
            )

        # Consensus engine (reuse pipeline settings)
        consensus = ConsensusEngine(
            edge_threshold=0.01,
            use_dynamic_margin=True,
            tight_margin_threshold=config.value.tight_margin_threshold,
            tight_margin_consensus=config.value.tight_margin_consensus,
        )

        return cls(
            config=config,
            context_collector=collector,
            gatekeeper=gatekeeper,
            models=models,
            consensus_engine=consensus,
            feature_store=feature_store,
            analyst=analyst,
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
            for the given date (YYYY-MM-DD) instead of connecting to
            the live SSE feed.  This is the **primary** mode of
            operation — run the scraper first, then the pipeline.
            If ``None``, falls back to live T-60 collection.
        dry_run:
            If True, skip LLM calls (Gatekeeper + Analyst).  Useful
            for validating data flow without API keys.
        """

        now = datetime.now(timezone.utc)
        logger.info("=== Gatekeeper Live Pipeline — %s ===", now.isoformat())

        # ── 1. Collect matches ───────────────────────────────────────
        if pre_match_date:
            logger.info(
                "Pre-match mode: loading snapshot for %s", pre_match_date
            )
            matches = load_pre_match_contexts(date=pre_match_date)
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
            if entry.gatekeeper_status == "APPROVED":
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
        """Run consensus + Gatekeeper for a single match."""
        home = match_ctx.home_team
        away = match_ctx.away_team
        event_id = match_ctx.event_id

        logger.info("Evaluating: %s vs %s (event=%s)", home, away, event_id)

        # ── Ensemble consensus (corners only) ────────────────────────
        ensemble_output = self._run_consensus(match_ctx)

        # ── Gatekeeper LLM (corners — with ensemble support) ────────
        if dry_run or self._gatekeeper is None:
            logger.info(
                "Dry-run: skipping Gatekeeper LLM for %s vs %s.", home, away
            )
            gk_result = GatekeeperResult(
                status="DRY_RUN",
                justification="Dry-run mode — LLM evaluation skipped.",
            )
        else:
            gk_result = self._call_gatekeeper(match_ctx, ensemble_output)

        # ── Analyst LLM (non-corner markets: 1x2, BTTS, etc.) ───────
        if dry_run or self._analyst is None:
            analyst_result = None
        else:
            analyst_result = self._call_analyst(match_ctx)

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
            ensemble_mean_lambda=(
                ensemble_output.get("ensemble_mean_lambda")
                if ensemble_output
                else None
            ),
            ensemble_std_lambda=(
                ensemble_output.get("ensemble_std_lambda")
                if ensemble_output
                else None
            ),
            consensus_pct=(
                ensemble_output.get("agreement") if ensemble_output else None
            ),
            votes_positive=(
                ensemble_output.get("votes_positive")
                if ensemble_output
                else None
            ),
            total_models=(
                ensemble_output.get("total_models")
                if ensemble_output
                else None
            ),
            p_model_mean=(
                ensemble_output.get("p_model_mean")
                if ensemble_output
                else None
            ),
            edge_mean=(
                ensemble_output.get("edge_mean") if ensemble_output else None
            ),
            consensus_bet=(
                ensemble_output.get("bet") if ensemble_output else None
            ),
            gatekeeper_status=gk_result.status,
            gatekeeper_stake=gk_result.stake,
            gatekeeper_market=gk_result.market,
            gatekeeper_odd=gk_result.odd,
            gatekeeper_edge=gk_result.edge,
            gatekeeper_justification=gk_result.justification,
            gatekeeper_red_flags=gk_result.red_flags,
            analyst_status=analyst_result.status if analyst_result else None,
            analyst_best_market=(
                analyst_result.best_pick.market
                if analyst_result and analyst_result.best_pick
                else None
            ),
            analyst_best_stake=(
                analyst_result.best_pick.stake
                if analyst_result and analyst_result.best_pick
                else None
            ),
            analyst_best_odd=(
                analyst_result.best_pick.odd
                if analyst_result and analyst_result.best_pick
                else None
            ),
            analyst_best_edge=(
                analyst_result.best_pick.edge
                if analyst_result and analyst_result.best_pick
                else None
            ),
            analyst_best_justification=(
                analyst_result.best_pick.justification
                if analyst_result and analyst_result.best_pick
                else None
            ),
            analyst_markets_evaluated=len(analyst_result.markets) if analyst_result else 0,
            analyst_markets_approved=(
                sum(1 for m in analyst_result.markets if m.status == "APPROVED")
                if analyst_result
                else 0
            ),
        )

    def _run_consensus(
        self, match_ctx: MatchContext
    ) -> Optional[Dict[str, Any]]:
        """Run the 30-model consensus vote for a match.

        If no trained models are loaded or the match lacks a corner line,
        returns None (the Gatekeeper still runs with context-only input).
        """
        if not self._models:
            logger.warning("No ensemble models loaded — skipping consensus.")
            return None

        odds = match_ctx.odds
        if odds.corner_line is None or odds.corner_over_odds is None:
            logger.info(
                "%s vs %s — no corner line/odds, skipping consensus.",
                match_ctx.home_team,
                match_ctx.away_team,
            )
            return None

        try:
            features = self._get_match_features(match_ctx)
            if features is None:
                logger.info(
                    "%s vs %s — feature store unavailable, skipping consensus.",
                    match_ctx.home_team,
                    match_ctx.away_team,
                )
                return None

            predictions: List[Dict[str, float]] = []
            for model in self._models:
                home_pred, away_pred = predict_expected_corners(model, features)
                predictions.append(
                    {
                        "lambda_home": float(home_pred.iloc[0]),
                        "lambda_away": float(away_pred.iloc[0]),
                    }
                )

            result = self._consensus.evaluate_with_consensus(
                predictions_list=predictions,
                odds_data={
                    "line": odds.corner_line,
                    "odds": odds.corner_over_odds,
                    "type": "over",
                },
                threshold=self._config.value.consensus_threshold,
            )
            return result

        except Exception:
            logger.exception(
                "Consensus evaluation failed for %s vs %s.",
                match_ctx.home_team,
                match_ctx.away_team,
            )
            return None

    def _get_match_features(self, match_ctx: MatchContext):
        """Build a feature DataFrame for a single live match.

        Reads the pre-computed FeatureStore (built daily by
        ``scripts/refresh_features.py``) to retrieve the most recent
        rolling stats for each team.  Returns None if the store is
        unavailable or either team is not found — the caller
        (_run_consensus) will skip consensus in that case.
        """
        if self._feature_store is None:
            return None

        features = self._feature_store.get_match_features(
            home_team=match_ctx.home_team,
            away_team=match_ctx.away_team,
        )
        if features is None:
            logger.warning(
                "Feature store: no features for '%s' vs '%s' — consensus skipped.",
                match_ctx.home_team,
                match_ctx.away_team,
            )
        return features

    def _call_gatekeeper(
        self,
        match_ctx: MatchContext,
        ensemble_output: Optional[Dict[str, Any]],
    ) -> GatekeeperResult:
        """Call the Gatekeeper LLM agent (corners — with ensemble support)."""
        try:
            context = AgentContext(
                payload={
                    "match_context_json": match_ctx.to_json(),
                    "ensemble_output": ensemble_output,
                }
            )
            raw = self._gatekeeper.run(context)
            return GatekeeperResult(
                status=raw.get("status", "ERROR"),
                stake=raw.get("stake"),
                market=raw.get("market"),
                odd=raw.get("odd"),
                edge=raw.get("edge"),
                justification=raw.get("justification"),
                red_flags=raw.get("red_flags", []),
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

    def _call_analyst(
        self,
        match_ctx: MatchContext,
    ) -> Optional[AnalystResult]:
        """Call the Analyst agent for non-corner markets (1x2, BTTS, etc.).

        Returns None if the analyst agent is not configured.
        """
        if self._analyst is None:
            logger.debug("Analyst agent not configured — skipping.")
            return None

        try:
            context = AgentContext(
                payload={
                    "match_context_json": match_ctx.to_json(),
                }
            )
            raw = self._analyst.run(context)
            markets_raw = raw.get("markets", [])
            from japredictbet.agents.analyst import MarketEvaluation

            markets = [
                MarketEvaluation(
                    market=m.get("market", "unknown"),
                    status=m.get("status", "NO BET"),
                    stake=m.get("stake"),
                    odd=m.get("odd"),
                    edge=m.get("edge"),
                    justification=m.get("justification"),
                    red_flags=m.get("red_flags", []),
                )
                for m in markets_raw
                if isinstance(m, dict)
            ]

            best_raw = raw.get("best_pick")
            best_pick = None
            if best_raw and isinstance(best_raw, dict):
                best_pick = MarketEvaluation(
                    market=best_raw.get("market", "unknown"),
                    status=best_raw.get("status", "NO BET"),
                    stake=best_raw.get("stake"),
                    odd=best_raw.get("odd"),
                    edge=best_raw.get("edge"),
                    justification=best_raw.get("justification"),
                    red_flags=best_raw.get("red_flags", []),
                )

            has_approved = any(m.status == "APPROVED" for m in markets)
            return AnalystResult(
                status=raw.get("status", "APPROVED" if has_approved else "NO BET"),
                markets=markets,
                best_pick=best_pick,
            )
        except Exception:
            logger.exception(
                "Analyst call failed for %s vs %s.",
                match_ctx.home_team,
                match_ctx.away_team,
            )
            return AnalystResult(status="ERROR")

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


# ── Helpers ──────────────────────────────────────────────────────────


def _load_ensemble(models_dir: Path) -> List[TrainedModels]:
    """Load all ``.pkl`` ensemble artifacts from *models_dir*."""
    if not models_dir.exists() or not models_dir.is_dir():
        logger.warning("Models directory not found: %s", models_dir)
        return []

    patterns = (
        "xgb_model_*.pkl",
        "lgbm_model_*.pkl",
        "rf_model_*.pkl",
        "ridge_model_*.pkl",
        "elastic_model_*.pkl",
    )
    paths: List[Path] = []
    for pattern in patterns:
        paths.extend(sorted(models_dir.glob(pattern)))

    if not paths:
        logger.warning("No .pkl artifacts found in %s", models_dir)
        return []

    models: List[TrainedModels] = []
    for p in paths:
        with open(p, "rb") as f:
            obj = pickle.load(f)  # noqa: S301
        if isinstance(obj, TrainedModels):
            models.append(obj)
        else:
            logger.warning("Skipping %s — not a TrainedModels instance.", p)

    logger.info("Loaded %d ensemble models from %s.", len(models), models_dir)
    return models
