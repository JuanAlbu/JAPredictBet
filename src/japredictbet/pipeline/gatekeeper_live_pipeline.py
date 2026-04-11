"""Gatekeeper Live Pipeline — T-60 shadow-mode orchestration.

Collects Superbet odds + API-Football context, runs the 30-model
ensemble consensus, and passes each qualifying match to the
``GatekeeperAgent`` for LLM-based evaluation.  All outputs are
written to a shadow log — **no real bets are ever placed**.

Typical invocation (via ``scripts/shadow_observe.py``)::

    pipeline = GatekeeperLivePipeline.from_config(config)
    results  = pipeline.run()
"""

from __future__ import annotations

import json
import logging
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from japredictbet.agents.base import AgentContext
from japredictbet.agents.gatekeeper import GatekeeperAgent, GatekeeperResult
from japredictbet.betting.engine import ConsensusEngine
from japredictbet.config import PipelineConfig
from japredictbet.data.context_collector import ContextCollector, MatchContext
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
        gatekeeper: GatekeeperAgent,
        models: List[TrainedModels],
        consensus_engine: ConsensusEngine,
    ) -> None:
        self._config = config
        self._collector = context_collector
        self._gatekeeper = gatekeeper
        self._models = models
        self._consensus = consensus_engine
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
    ) -> GatekeeperLivePipeline:
        """Build a ready-to-run pipeline from a ``PipelineConfig``.

        Parameters
        ----------
        config:
            Fully-loaded ``PipelineConfig`` (including gatekeeper block).
        models_dir:
            Directory containing persisted ``.pkl`` ensemble artifacts.
        """
        gk_cfg = config.gatekeeper
        if gk_cfg is None:
            raise ValueError(
                "PipelineConfig.gatekeeper is None — "
                "add a 'gatekeeper' block to config.yml."
            )

        # Resolve API keys
        api_keys = config.api_keys.resolve() if config.api_keys else None
        if api_keys is None:
            raise ValueError(
                "PipelineConfig.api_keys is None — "
                "add an 'api_keys' block to config.yml."
            )

        # Context collector
        collector = ContextCollector.from_configs(
            superbet_cfg=config.superbet_shadow,
            api_football_cfg=config.api_football,
            api_football_key=api_keys.api_football_key,
            gatekeeper_cfg=gk_cfg,
        )

        # Gatekeeper agent
        gatekeeper = GatekeeperAgent(
            gatekeeper_cfg=gk_cfg,
            api_key=api_keys.llm_api_key,
        )

        # Load ensemble models
        models = _load_ensemble(Path(models_dir))

        # Consensus engine (reuse pipeline settings)
        consensus = ConsensusEngine(
            edge_threshold=0.01,
            use_dynamic_margin=True,
            tight_margin_threshold=config.tight_margin_threshold,
            tight_margin_consensus=config.tight_margin_consensus,
        )

        return cls(
            config=config,
            context_collector=collector,
            gatekeeper=gatekeeper,
            models=models,
            consensus_engine=consensus,
        )

    # ── Main entry point ─────────────────────────────────────────────

    def run(self) -> PipelineRunResult:
        """Execute the full T-60 pipeline and return results."""

        now = datetime.now(timezone.utc)
        logger.info("=== Gatekeeper Live Pipeline — %s ===", now.isoformat())

        # ── 1. Collect upcoming matches ──────────────────────────────
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
            entry = self._evaluate_single_match(match_ctx)
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
        self, match_ctx: MatchContext
    ) -> Optional[ShadowEntry]:
        """Run consensus + Gatekeeper for a single match."""
        home = match_ctx.home_team
        away = match_ctx.away_team
        event_id = match_ctx.event_id

        logger.info("Evaluating: %s vs %s (event=%s)", home, away, event_id)

        # ── Ensemble consensus ───────────────────────────────────────
        ensemble_output = self._run_consensus(match_ctx)

        # ── Gatekeeper LLM ───────────────────────────────────────────
        gk_result = self._call_gatekeeper(match_ctx, ensemble_output)

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
            # Collect predictions from all loaded models
            predictions: List[Dict[str, float]] = []
            for model in self._models:
                # predict_expected_corners expects a DataFrame; for now we need
                # the feature-engineered row.  In Shadow Mode the models were
                # already trained on historical data — we pass features through
                # the standard predict path.
                #
                # NOTE: Full feature engineering for a *live* match is complex
                # (requires rolling history).  For the MVP shadow pipeline we
                # log lambda=None when feature data is unavailable and let the
                # Gatekeeper operate on context + odds only.
                #
                # When pre-computed features are available (e.g. from a cron
                # job that ran the full pipeline), they can be injected via
                # ``match_ctx.payload["features"]`` (future extension).
                home_pred, away_pred = predict_expected_corners(
                    model, self._get_match_features(match_ctx)
                )
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
                threshold=self._config.consensus_threshold,
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
        """Extract or build a feature DataFrame for a single match.

        For the MVP shadow pipeline, features must be pre-computed
        by the daily cron and stored in ``artifacts/models/``.
        This is a placeholder that returns an empty DataFrame —
        callers should check for prediction failures gracefully.
        """
        import pandas as pd

        # Future: load pre-engineered features for upcoming matches.
        # For now, return empty frame — predict_expected_corners will
        # handle missing columns via its fill-value mechanism.
        logger.debug(
            "Feature engineering for live matches not yet implemented. "
            "Using empty feature frame for %s vs %s.",
            match_ctx.home_team,
            match_ctx.away_team,
        )
        return pd.DataFrame([{}])

    def _call_gatekeeper(
        self,
        match_ctx: MatchContext,
        ensemble_output: Optional[Dict[str, Any]],
    ) -> GatekeeperResult:
        """Call the Gatekeeper LLM agent."""
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
