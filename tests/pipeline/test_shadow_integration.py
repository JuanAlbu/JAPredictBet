"""Integration tests for the Shadow pipeline (P2-SH19).

Covers:
- ContextCollector: Superbet-only mode, REST enrichment, kickoff extraction
- FeatureStore: build/load roundtrip, H2H exclusion, fuzzy matching
- load_pre_match_contexts: odds extraction from mock snapshots
- GatekeeperLivePipeline: from_config factory, pre-match run, dry-run,
  Gatekeeper LLM call (single motor — V26 multi-market)
- ApiFootballClient: fixture queries by date

Post-refactoring (May-2026): The Shadow pipeline uses a SINGLE LLM motor
(GatekeeperAgent evaluating ALL markets). The 30-model ensemble and
AnalystAgent are exclusive to Mode 1 (Backtest).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from japredictbet.config import (
    ApiFootballConfig,
    ApiKeysConfig,
    DataConfig,
    FeatureConfig,
    GatekeeperConfig,
    ModelConfig,
    OddsConfig,
    PipelineConfig,
    SuperbetShadowConfig,
    ValueConfig,
)
from japredictbet.data.context_collector import (
    ApiFootballClient,
    ContextCollector,
    MatchContext,
    OddsContext,
    StandingsEntry,
    TeamLineup,
    _find_standing,
    _merge_injuries,
)
from japredictbet.data.feature_store import (
    FeatureStore,
    _extract_latest_per_team,
    _fuzzy_match,
    _prefix_row,
)
from japredictbet.odds.pre_match_odds import load_pre_match_contexts
from japredictbet.odds.superbet_client import SuperbetOdds, SuperbetSnapshot
from japredictbet.pipeline.gatekeeper_live_pipeline import GatekeeperLivePipeline

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def sample_snapshots() -> dict[str, SuperbetSnapshot]:
    """Build a dict of SuperbetSnapshots simulating SSE output."""
    now = datetime.now(UTC)
    kickoff_ts = int((now + timedelta(minutes=30)).timestamp() * 1000)

    return {
        "12345": SuperbetSnapshot(
            event_id="12345",
            home_team="Team A",
            away_team="Team B",
            match_name="Team A vs Team B",
            corners=[
                SuperbetOdds(
                    market_line=9.5,
                    over_odds=1.85,
                    under_odds=1.95,
                )
            ],
            match_odds=[
                SuperbetOdds(
                    home_odds=2.10,
                    draw_odds=3.40,
                    away_odds=3.80,
                )
            ],
            btts=[
                SuperbetOdds(
                    yes_odds=1.80,
                    no_odds=2.00,
                )
            ],
            raw_event={
                "id": 12345,
                "sportId": 5,
                "matchName": "Team A\u00b7Team B",
                "unixDateMillis": kickoff_ts,
            },
        ),
        "67890": SuperbetSnapshot(
            event_id="67890",
            home_team="Team C",
            away_team="Team D",
            match_name="Team C vs Team D",
            corners=[
                SuperbetOdds(
                    market_line=10.5,
                    over_odds=1.90,
                    under_odds=1.90,
                )
            ],
            match_odds=[],
            btts=[],
            raw_event={
                "id": 67890,
                "sportId": 5,
                "matchName": "Team C\u00b7Team D",
                "unixDateMillis": kickoff_ts,
            },
        ),
    }


@pytest.fixture
def sample_feature_dataframe() -> pd.DataFrame:
    """Simulate a feature store DataFrame with rolling + H2H columns."""
    return pd.DataFrame(
        {
            "home_team": ["Team A", "Team A", "Team B", "Team B"],
            "away_team": ["Team C", "Team D", "Team C", "Team D"],
            "date": pd.to_datetime(["2026-04-01", "2026-04-08", "2026-04-01", "2026-04-08"]),
            "season": [2026, 2026, 2026, 2026],
            "total_corners_avg_last10": [5.2, 5.5, 4.8, 5.0],
            "total_corners_std_last10": [1.2, 1.3, 1.1, 1.0],
            "total_corners_ema_last10": [5.1, 5.4, 4.7, 5.1],
            "total_corners_h2h_last3": [8.0, 9.0, 8.0, 9.0],
            "total_goals_h2h_last3": [2.5, 3.0, 2.5, 3.0],
            "total_shots_h2h_last3": [12.0, 13.0, 12.0, 13.0],
            "win_rate_last10": [0.6, 0.7, 0.5, 0.5],
            "points_per_game_last10": [1.8, 2.1, 1.5, 1.5],
        }
    )


@pytest.fixture
def mock_pre_match_snapshot(tmp_path: Path) -> Path:
    """Create a mock daily pre-match JSON file."""
    dir_path = tmp_path / "pre_match"
    dir_path.mkdir(parents=True)
    file_path = dir_path / "2026-05-10.json"

    data = [
        {
            "event_id": "ev001",
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "date": "2026-05-10",
            "kickoff": "16:00",
            "league": "Campeonato Brasileiro Série A",
            "markets": {
                "corners": {"line": 9.5, "over": 1.85, "under": 1.95},
                "1x2": {"home": 2.10, "draw": 3.30, "away": 3.50},
                "btts": {"yes": 1.80, "no": 2.00},
            },
        },
        {
            "event_id": "ev002",
            "home_team": "Corinthians",
            "away_team": "São Paulo",
            "date": "2026-05-10",
            "kickoff": "18:30",
            "league": "Campeonato Brasileiro Série A",
            "markets": {"corners": {"line": 10.5, "over": 1.90, "under": 1.90}},
        },
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return dir_path


# Helper to build a minimal PipelineConfig for gatekeeper tests
def _minimal_gk_pipeline_config(
    llm_api_key: str = "",
    api_football_key: str = "",
) -> PipelineConfig:
    return PipelineConfig(
        data=DataConfig(
            raw_path=Path("data/raw"),
            processed_path=Path("data/processed"),
        ),
        features=FeatureConfig(rolling_windows=[10]),
        model=ModelConfig(),
        odds=OddsConfig(),
        value=ValueConfig(
            tight_margin_threshold=0.5,
            tight_margin_consensus=0.8,
        ),
        gatekeeper=GatekeeperConfig(
            cron_trigger_minutes_before=60,
            min_odd=1.5,
            max_entries_per_day=5,
            shadow_log_path="logs/test_shadow.log",
        ),
        api_keys=ApiKeysConfig(
            llm_api_key=llm_api_key,
            api_football_key=api_football_key,
        ),
    )


# =========================================================================
# ContextCollector — Superbet-only mode
# =========================================================================


class TestContextCollectorSuperbetOnly:
    """Tests for ContextCollector in Superbet-only mode (no API key)."""

    def test_no_api_creates_no_client(self):
        """Without API key, _api is None."""
        collector = ContextCollector.from_configs(
            superbet_cfg=SuperbetShadowConfig(),
            api_football_cfg=ApiFootballConfig(),
            gatekeeper_cfg=GatekeeperConfig(),
            api_football_key="",
        )
        assert collector._api is None

    @patch("japredictbet.data.context_collector.SuperbetCollector")
    def test_enrich_pre_match_is_noop_without_api(
        self,
        mock_superbet_cls: MagicMock,
    ):
        """enrich_pre_match_contexts is a no-op when _api is None."""
        collector = ContextCollector.from_configs(
            superbet_cfg=SuperbetShadowConfig(),
            api_football_cfg=ApiFootballConfig(),
            gatekeeper_cfg=GatekeeperConfig(),
            api_football_key="",
        )
        ctx = MatchContext(event_id="1", home_team="A", away_team="B")
        result = collector.enrich_pre_match_contexts([ctx], date="2026-05-10")
        assert result == [ctx]
        assert ctx.home_lineup is None


# =========================================================================
# ContextCollector — REST enrichment
# =========================================================================


class TestContextCollectorRestEnrichment:
    """Tests for REST enrichment flag and plumbing."""

    def test_use_rest_enrichment_default_false(self):
        """use_rest_enrichment defaults to False."""
        collector = ContextCollector.from_configs(
            superbet_cfg=SuperbetShadowConfig(),
            api_football_cfg=ApiFootballConfig(),
            gatekeeper_cfg=GatekeeperConfig(),
            api_football_key="",
        )
        assert collector._use_rest_enrichment is False

    def test_use_rest_enrichment_true(self):
        """use_rest_enrichment can be set to True."""
        collector = ContextCollector.from_configs(
            superbet_cfg=SuperbetShadowConfig(),
            api_football_cfg=ApiFootballConfig(),
            gatekeeper_cfg=GatekeeperConfig(),
            api_football_key="",
            use_rest_enrichment=True,
        )
        assert collector._use_rest_enrichment is True


# =========================================================================
# _extract_kickoff_from_snapshot
# =========================================================================


class TestExtractKickoffFromSnapshot:
    """Tests for static kickoff extraction from raw Superbet event data."""

    def test_unix_date_millis(self):
        """unixDateMillis is parsed correctly."""
        now = datetime.now(UTC)
        ts_ms = int(now.timestamp() * 1000)
        snap = SuperbetSnapshot(
            event_id="1",
            home_team="A",
            away_team="B",
            raw_event={"unixDateMillis": ts_ms},
        )
        result = ContextCollector._extract_kickoff_from_snapshot(snap)
        assert result is not None
        assert abs((result - now).total_seconds()) < 1

    def test_iso_date_field(self):
        """matchDate ISO string is parsed."""
        snap = SuperbetSnapshot(
            event_id="1",
            home_team="A",
            away_team="B",
            raw_event={"matchDate": "2026-05-10T16:00:00Z"},
        )
        result = ContextCollector._extract_kickoff_from_snapshot(snap)
        assert result is not None
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 10
        assert result.hour == 16

    def test_no_raw_event_returns_none(self):
        """Snapshot with no raw_event returns None."""
        snap = SuperbetSnapshot(event_id="1", home_team="A", away_team="B")
        assert ContextCollector._extract_kickoff_from_snapshot(snap) is None

    def test_empty_event_returns_none(self):
        """Empty raw_event dict returns None."""
        snap = SuperbetSnapshot(
            event_id="1",
            home_team="A",
            away_team="B",
            raw_event={},
        )
        assert ContextCollector._extract_kickoff_from_snapshot(snap) is None

    def test_numeric_string_as_epoch(self):
        """Numeric string in ISO date field is treated as epoch."""
        snap = SuperbetSnapshot(
            event_id="1",
            home_team="A",
            away_team="B",
            raw_event={"startDate": "1715356800000"},
        )
        result = ContextCollector._extract_kickoff_from_snapshot(snap)
        assert result is not None


# =========================================================================
# _merge_injuries / _find_standing
# =========================================================================


class TestMergeInjuries:
    """Tests for _merge_injuries helper."""

    def test_injury_merged_into_lineup(self):
        """Matching team injury is appended to lineup.missing_players."""
        lineup = TeamLineup(formation="4-3-3", starting_xi=[])
        injuries = [
            {
                "player": "Player X",
                "team": "Team A",
                "type": "Injury",
                "reason": "Hamstring",
            },
            {
                "player": "Player Y",
                "team": "Team B",
                "type": "Suspension",
                "reason": "Red card",
            },
        ]
        _merge_injuries(injuries, "Team A", lineup)
        assert len(lineup.missing_players) == 1
        assert lineup.missing_players[0]["player"] == "Player X"

    def test_no_lineup_skipped(self):
        """No-op when lineup is None."""
        injuries = [
            {
                "player": "X",
                "team": "Team A",
                "type": "Injury",
                "reason": "Knee",
            }
        ]
        _merge_injuries(injuries, "Team A", None)  # Should not raise

    def test_wrong_team_not_merged(self):
        """Injury for different team is ignored."""
        lineup = TeamLineup(formation="4-4-2", starting_xi=[])
        injuries = [
            {
                "player": "Player Z",
                "team": "Team Other",
                "type": "Injury",
                "reason": "Ankle",
            }
        ]
        _merge_injuries(injuries, "Team A", lineup)
        assert lineup.missing_players == []


class TestFindStanding:
    """Tests for _find_standing helper."""

    def test_exact_match(self):
        standings = [
            StandingsEntry(rank=1, team="Team A", points=30, played=10, goal_diff=15),
            StandingsEntry(rank=2, team="Team B", points=25, played=10, goal_diff=10),
        ]
        result = _find_standing(standings, "Team A")
        assert result is not None
        assert result.rank == 1

    def test_partial_match(self):
        standings = [
            StandingsEntry(rank=3, team="Flamengo RJ", points=20, played=10, goal_diff=5),
        ]
        result = _find_standing(standings, "Flamengo")
        assert result is not None
        assert result.rank == 3

    def test_no_match_returns_none(self):
        standings = [
            StandingsEntry(rank=1, team="Team A", points=30, played=10, goal_diff=15),
        ]
        result = _find_standing(standings, "Team Z")
        assert result is None


# =========================================================================
# FeatureStore — H2H exclusion & helpers
# =========================================================================


class TestFeatureStoreH2HExclusion:
    """H2H columns must be excluded from _extract_latest_per_team."""

    def test_h2h_columns_excluded(self, sample_feature_dataframe):
        """_extract_latest_per_team excludes H2H columns."""
        result = _extract_latest_per_team(sample_feature_dataframe)
        for col in result.columns:
            assert not col.startswith("total_corners_h2h_last"), f"Column '{col}' should have been excluded"
            assert not col.startswith("total_goals_h2h_last")
            assert not col.startswith("total_shots_h2h_last")

    def test_non_h2h_columns_retained(self, sample_feature_dataframe):
        """Regular feature columns are retained."""
        result = _extract_latest_per_team(sample_feature_dataframe)
        assert "total_corners_avg_last10" in result.columns
        assert "total_corners_std_last10" in result.columns
        assert "win_rate_last10" in result.columns

    def test_latest_row_per_team(self, sample_feature_dataframe):
        """Only the most recent row per team is kept."""
        result = _extract_latest_per_team(sample_feature_dataframe)
        # Index is the team name (lowercased)
        assert len(result) == 4  # Team A, B, C, D — two from home_view, two from away_view
        assert "team a" in result.index
        team_a = result.loc["team a"]
        assert team_a["total_corners_avg_last10"] == 5.5

    def test_prefix_row_creates_side_prefixed_dict(self):
        """_prefix_row keeps columns as-is, only filters opposite side."""
        series = pd.Series({"total_corners_avg_last10": 5.2, "win_rate_last10": 0.6})
        result = _prefix_row(series, "home")
        # Columns without prefix are kept as-is (no prefix added)
        assert result["total_corners_avg_last10"] == 5.2
        assert result["win_rate_last10"] == 0.6

    def test_fuzzy_match_same_string(self):
        """Exact match returns confidence 1.0."""
        matched_name, confidence = _fuzzy_match("Flamengo", ["Flamengo"])
        assert confidence == 1.0
        assert matched_name == "Flamengo"

    def test_fuzzy_match_similar(self):
        """Similar strings return high confidence."""
        named_name, confidence = _fuzzy_match("Flamengo RJ", ["Flamengo"])
        assert confidence > 0.5


class TestFeatureStoreBuildLoad:
    """FeatureStore build/load roundtrip."""

    def test_build_and_save_load(self, sample_feature_dataframe, tmp_path: Path):
        """Build from DataFrame, save, and load back."""
        # Use _extract_latest_per_team to build the table, then construct
        table = _extract_latest_per_team(sample_feature_dataframe)
        store = FeatureStore(table=table, built_at="2026-05-10T12:00:00")
        save_path = tmp_path / "test_fs.pkl"
        store.save(str(save_path))

        loaded = FeatureStore.load(str(save_path))
        assert loaded.table is not None
        features = loaded.get_match_features("Team A", "Team B")
        assert features is not None
        # _prefix_row keeps columns as-is (no home_ prefix added)
        assert "total_corners_avg_last10" in features.columns

    def test_get_match_features_missing_team(self, sample_feature_dataframe):
        """get_match_features returns None when a team is not found."""
        table = _extract_latest_per_team(sample_feature_dataframe)
        store = FeatureStore(table=table, built_at="2026-05-10T12:00:00")
        features = store.get_match_features("Unknown Team", "Team B")
        assert features is None

    def test_get_match_features_returns_dataframe(self, sample_feature_dataframe):
        """get_match_features returns a single-row DataFrame."""
        table = _extract_latest_per_team(sample_feature_dataframe)
        store = FeatureStore(table=table, built_at="2026-05-10T12:00:00")
        features = store.get_match_features("Team A", "Team B")
        assert isinstance(features, pd.DataFrame)
        assert len(features) == 1
        # _prefix_row keeps columns as-is (no home_/away_ prefix added)
        assert "total_corners_avg_last10" in features.columns
        assert "total_corners_std_last10" in features.columns


# =========================================================================
# load_pre_match_contexts
# =========================================================================


class TestLoadPreMatchContexts:
    """Tests for load_pre_match_contexts using mock JSON snapshots."""

    def test_loads_correct_number_of_matches(self, mock_pre_match_snapshot: Path):
        """Two events in snapshot → two MatchContexts."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        assert len(contexts) == 2

    def test_odds_context_populated(self, mock_pre_match_snapshot: Path):
        """Corner, match_odds, and BTTS are extracted."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        ctx = contexts[0]
        assert ctx.odds.corner_line == 9.5
        assert ctx.odds.corner_over_odds == 1.85
        assert ctx.odds.corner_under_odds == 1.95
        assert ctx.odds.home_odds == 2.10
        assert ctx.odds.draw_odds == 3.30
        assert ctx.odds.away_odds == 3.50
        assert ctx.odds.btts_yes == 1.80
        assert ctx.odds.btts_no == 2.00

    def test_kickoff_utc_built(self, mock_pre_match_snapshot: Path):
        """Kickoff is built from date + kickoff fields."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        assert contexts[0].kickoff_utc == "2026-05-10T16:00:00"

    def test_team_names_populated(self, mock_pre_match_snapshot: Path):
        """Home and away teams are set."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        assert contexts[0].home_team == "Flamengo"
        assert contexts[0].away_team == "Palmeiras"

    def test_league_populated(self, mock_pre_match_snapshot: Path):
        """League name is set from snapshot."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        assert contexts[0].league == "Campeonato Brasileiro Série A"

    def test_no_lineup_by_default(self, mock_pre_match_snapshot: Path):
        """Pre-match contexts start without lineup enrichment."""
        contexts = load_pre_match_contexts(date="2026-05-10", directory=mock_pre_match_snapshot)
        assert contexts[0].home_lineup is None
        assert contexts[0].away_lineup is None


# =========================================================================
# GatekeeperLivePipeline — factory & dry-run
# =========================================================================


class TestGatekeeperLivePipelineFactory:
    """Tests for GatekeeperLivePipeline.from_config()."""

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.ContextCollector.from_configs")
    def test_from_config_minimal(
        self,
        mock_collector_cls: MagicMock,
    ):
        """from_config creates a pipeline with single Gatekeeper LLM motor."""
        mock_collector_cls.return_value = MagicMock(spec=ContextCollector)

        config = _minimal_gk_pipeline_config(llm_api_key="test-key")

        pipeline = GatekeeperLivePipeline.from_config(
            config,
        )
        assert pipeline._config is not None
        assert pipeline._collector is not None
        assert pipeline._gatekeeper is not None  # Gatekeeper created with API key

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.ContextCollector.from_configs")
    def test_dry_run_skips_gatekeeper_llm(
        self,
        mock_collector_cls: MagicMock,
    ):
        """In dry-run, Gatekeeper agent is None (LLM calls skipped)."""
        mock_collector_cls.return_value = MagicMock(spec=ContextCollector)

        config = _minimal_gk_pipeline_config(llm_api_key="")

        pipeline = GatekeeperLivePipeline.from_config(config, dry_run=True)
        assert pipeline._gatekeeper is None


# =========================================================================
# GatekeeperLivePipeline — pre-match run
# =========================================================================


class TestGatekeeperLivePipelinePreMatch:
    """Tests for GatekeeperLivePipeline.run() in pre-match mode."""

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.load_pre_match_contexts")
    def test_run_pre_match_collects_matches(
        self,
        mock_load_ctx: MagicMock,
    ):
        """run() with pre_match_date calls load_pre_match_contexts."""
        mock_ctx_1 = MatchContext(
            event_id="ev001",
            home_team="Team A",
            away_team="Team B",
            kickoff_utc="2026-05-10T16:00:00",
            odds=OddsContext(
                corner_line=9.5,
                corner_over_odds=1.85,
                corner_under_odds=1.95,
            ),
        )
        mock_ctx_2 = MatchContext(
            event_id="ev002",
            home_team="Team C",
            away_team="Team D",
            kickoff_utc="2026-05-10T18:30:00",
        )
        mock_load_ctx.return_value = [mock_ctx_1, mock_ctx_2]

        config = _minimal_gk_pipeline_config()

        mock_collector = MagicMock(spec=ContextCollector)
        mock_collector.enrich_pre_match_contexts.return_value = [
            mock_ctx_1,
            mock_ctx_2,
        ]

        pipeline = GatekeeperLivePipeline(
            config=config,
            context_collector=mock_collector,
            gatekeeper=None,
        )

        result = pipeline.run(pre_match_date="2026-05-10", dry_run=True)

        assert result.matches_collected == 2
        assert result.matches_evaluated == 2
        mock_collector.enrich_pre_match_contexts.assert_called_once_with([mock_ctx_1, mock_ctx_2], date="2026-05-10")

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.load_pre_match_contexts")
    def test_run_pre_match_empty_returns_early(
        self,
        mock_load_ctx: MagicMock,
    ):
        """run() returns early when no matches are collected."""
        mock_load_ctx.return_value = []

        config = _minimal_gk_pipeline_config()

        mock_collector = MagicMock(spec=ContextCollector)
        mock_collector.enrich_pre_match_contexts.return_value = []

        pipeline = GatekeeperLivePipeline(
            config=config,
            context_collector=mock_collector,
            gatekeeper=None,
        )

        result = pipeline.run(pre_match_date="2026-05-10", dry_run=True)
        assert result.matches_collected == 0
        assert result.matches_evaluated == 0


# =========================================================================
# GatekeeperLivePipeline — Gatekeeper LLM call (single motor, V26)
# =========================================================================


class TestGatekeeperLivePipelineLLM:
    """Tests for the single Gatekeeper LLM call (all markets)."""

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.GatekeeperAgent")
    def test_call_gatekeeper_returns_result(
        self,
        mock_gk_cls: MagicMock,
    ):
        """_call_gatekeeper returns a GatekeeperResult with V26 multi-market fields."""
        from japredictbet.agents.gatekeeper import GatekeeperResult

        mock_gk_instance = MagicMock()
        # V26 response: markets array + best_pick
        mock_gk_instance.run.return_value = {
            "status": "APPROVED",
            "markets": [
                {
                    "market": "Escanteios Over 9.5",
                    "status": "APPROVED",
                    "stake": 1.0,
                    "odd": 1.85,
                    "edge": "Médio",
                    "classification": "APOSTA SIMPLES",
                    "justification": "Team A dominates corners at home.",
                    "red_flags": [],
                },
                {
                    "market": "1x2 HOME",
                    "status": "NO BET",
                    "stake": None,
                    "odd": 2.10,
                    "edge": None,
                    "classification": None,
                    "justification": "Inconsistent.",
                    "red_flags": ["escalação incerta"],
                },
            ],
            "best_pick": {
                "market": "Escanteios Over 9.5",
                "status": "APPROVED",
                "stake": 1.0,
                "odd": 1.85,
                "edge": "Médio",
                "classification": "APOSTA SIMPLES",
                "justification": "Melhor entrada",
                "red_flags": [],
            },
        }
        mock_gk_cls.return_value = mock_gk_instance

        config = _minimal_gk_pipeline_config()

        pipeline = GatekeeperLivePipeline(
            config=config,
            context_collector=MagicMock(spec=ContextCollector),
            gatekeeper=mock_gk_instance,
        )

        ctx = MatchContext(
            event_id="ev001",
            home_team="Team A",
            away_team="Team B",
            odds=OddsContext(corner_line=9.5, corner_over_odds=1.85),
        )

        result = pipeline._call_gatekeeper(ctx)
        assert isinstance(result, GatekeeperResult)
        assert result.status == "APPROVED"
        assert result.stake == 1.0
        assert result.market == "Escanteios Over 9.5"
        assert result.markets_evaluated == 2
        assert result.markets_approved == 1
        assert result.best_pick is not None
        assert result.best_pick.market == "Escanteios Over 9.5"

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.GatekeeperAgent")
    def test_call_gatekeeper_all_no_bet(
        self,
        mock_gk_cls: MagicMock,
    ):
        """_call_gatekeeper returns NO BET when all markets are NO BET."""
        from japredictbet.agents.gatekeeper import GatekeeperResult

        mock_gk_instance = MagicMock()
        mock_gk_instance.run.return_value = {
            "status": "NO BET",
            "markets": [
                {
                    "market": "Escanteios Over 9.5",
                    "status": "NO BET",
                    "stake": None,
                    "odd": 1.85,
                    "edge": None,
                    "justification": "No pressure.",
                    "red_flags": ["linha esticada"],
                }
            ],
            "best_pick": None,
        }
        mock_gk_cls.return_value = mock_gk_instance

        config = _minimal_gk_pipeline_config()

        pipeline = GatekeeperLivePipeline(
            config=config,
            context_collector=MagicMock(spec=ContextCollector),
            gatekeeper=mock_gk_instance,
        )

        ctx = MatchContext(
            event_id="ev001",
            home_team="Team A",
            away_team="Team B",
            odds=OddsContext(corner_line=9.5, corner_over_odds=1.85),
        )

        result = pipeline._call_gatekeeper(ctx)
        assert isinstance(result, GatekeeperResult)
        assert result.status == "NO BET"
        assert result.markets_approved == 0
        assert result.best_pick is None

    @patch("japredictbet.pipeline.gatekeeper_live_pipeline.GatekeeperAgent")
    def test_call_gatekeeper_handles_exception(
        self,
        mock_gk_cls: MagicMock,
    ):
        """_call_gatekeeper returns ERROR GatekeeperResult on exception."""
        from japredictbet.agents.gatekeeper import GatekeeperResult

        mock_gk_instance = MagicMock()
        mock_gk_instance.run.side_effect = RuntimeError("LLM timeout")
        mock_gk_cls.return_value = mock_gk_instance

        config = _minimal_gk_pipeline_config()

        pipeline = GatekeeperLivePipeline(
            config=config,
            context_collector=MagicMock(spec=ContextCollector),
            gatekeeper=mock_gk_instance,
        )

        ctx = MatchContext(
            event_id="ev001",
            home_team="Team A",
            away_team="Team B",
            odds=OddsContext(corner_line=9.5, corner_over_odds=1.85),
        )

        result = pipeline._call_gatekeeper(ctx)
        assert isinstance(result, GatekeeperResult)
        assert result.status == "ERROR"


# =========================================================================
# ApiFootballClient — get_fixtures_by_date
# =========================================================================


class TestApiFootballClientFixtures:
    """Tests for ApiFootballClient fixture queries."""

    @patch("japredictbet.data.context_collector.httpx.Client")
    def test_get_fixtures_by_date_passes_correct_params(self, mock_httpx_client: MagicMock):
        """get_fixtures_by_date sends the date param to the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": []}
        mock_httpx_instance = MagicMock()
        mock_httpx_instance.__enter__.return_value.get.return_value = mock_response
        mock_httpx_client.return_value = mock_httpx_instance

        client = ApiFootballClient(
            api_key="test-key",
            cfg=ApiFootballConfig(),
        )
        result = client.get_fixtures_by_date("2026-05-10")
        assert result == []

        _, kwargs = mock_httpx_instance.__enter__.return_value.get.call_args
        assert kwargs["params"] == {"date": "2026-05-10"}

    @patch("japredictbet.data.context_collector.httpx.Client")
    def test_get_fixtures_today_uses_current_date(self, mock_httpx_client: MagicMock):
        """get_fixtures_today wraps get_fixtures_by_date with today's date."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": [{"fixture": {"id": 1}}]}
        mock_httpx_instance = MagicMock()
        mock_httpx_instance.__enter__.return_value.get.return_value = mock_response
        mock_httpx_client.return_value = mock_httpx_instance

        client = ApiFootballClient(
            api_key="test-key",
            cfg=ApiFootballConfig(),
        )
        result = client.get_fixtures_today()
        assert len(result) == 1
        assert result[0]["fixture"]["id"] == 1

    @patch("japredictbet.data.context_collector.httpx.Client")
    def test_get_fixtures_by_date_with_league_filter(self, mock_httpx_client: MagicMock):
        """get_fixtures_by_date passes league_id when provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": []}
        mock_httpx_instance = MagicMock()
        mock_httpx_instance.__enter__.return_value.get.return_value = mock_response
        mock_httpx_client.return_value = mock_httpx_instance

        client = ApiFootballClient(
            api_key="test-key",
            cfg=ApiFootballConfig(),
        )
        client.get_fixtures_by_date("2026-05-10", league_id=71)

        _, kwargs = mock_httpx_instance.__enter__.return_value.get.call_args
        assert kwargs["params"] == {"date": "2026-05-10", "league": 71}
