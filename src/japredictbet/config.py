"""Configuration models for the MVP pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class DataConfig:
    """Input/output paths for datasets."""

    raw_path: Path
    processed_path: Path
    date_column: str = "date"


@dataclass(frozen=True)
class FeatureConfig:
    """Feature engineering settings."""

    rolling_windows: List[int] = field(default_factory=lambda: [10, 5])
    rolling_use_std: bool = True  # Include rolling standard deviation (P1.B2)
    rolling_use_ema: bool = True  # Include rolling EMA for current form (P1.B2)
    drop_redundant: bool = True  # Drop highly correlated redundant features
    h2h_window: int = 3  # Head-to-head last N meetings (P1.B5)

    def __post_init__(self) -> None:
        if not isinstance(self.rolling_windows, (list, tuple)) or not self.rolling_windows:
            raise ValueError(
                "FeatureConfig.rolling_windows must be a non-empty list of integers. "
                f"Got: {self.rolling_windows!r}. "
                "Check your config YAML — the key must be 'rolling_windows' (plural)."
            )


@dataclass(frozen=True)
class ModelConfig:
    """Model training settings."""

    objective: str = "count:poisson"
    random_state: int = 42
    ensemble_size: int = 30
    algorithms: tuple[str, ...] = (
        "xgboost",
        "lightgbm",
        "randomforest",
        "ridge",
        "elasticnet",
    )
    ensemble_seed_stride: int = 1


@dataclass(frozen=True)
class OddsConfig:
    """Odds ingestion settings."""

    provider_name: str = "mock"
    match_similarity_threshold: float = 95.0
    ambiguity_margin: float = 1.0


@dataclass(frozen=True)
class ValueConfig:
    """Value-bet detection settings."""

    threshold: float = 0.05
    consensus_threshold: float = 0.7
    run_consensus_sweep: bool = True
    consensus_start: float = 0.35
    consensus_end: float = 1.0
    consensus_step: float = 0.05
    tight_margin_threshold: float = 0.5  # Dynamic margin rule: trigger when |lambda - line| < this
    tight_margin_consensus: float = 0.50  # Consensus required when margin is tight (e.g., 50%)


# ── Gatekeeper Live Pipeline configs ─────────────────────────────────


@dataclass(frozen=True)
class GatekeeperConfig:
    """Gatekeeper agent operational parameters."""

    cron_trigger_minutes_before: int = 60
    min_odd: float = 1.60
    max_entries_per_day: int = 5
    shadow_log_path: str = "logs/shadow_bets.log"
    feature_store_path: str = "artifacts/feature_store.parquet"


@dataclass(frozen=True)
class ApiKeysConfig:
    """External API keys — resolved from environment variables at runtime."""

    api_football_key: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""   # Empty = OpenAI default. Set to Groq/Gemini endpoint for free tiers.
    llm_model: str = ""      # Empty = use agent default (gpt-4o-mini). Override e.g. llama-3.3-70b-versatile.
    # Fallback provider — used automatically when primary returns HTTP 429.
    llm_fallback_api_key: str = ""
    llm_fallback_base_url: str = ""
    llm_fallback_model: str = ""

    def resolve(self) -> ApiKeysConfig:
        """Return a new instance with env-var placeholders expanded."""
        return ApiKeysConfig(
            api_football_key=_resolve_env(self.api_football_key),
            llm_api_key=_resolve_env(self.llm_api_key),
            llm_base_url=_resolve_env(self.llm_base_url),
            llm_model=_resolve_env(self.llm_model),
            llm_fallback_api_key=_resolve_env(self.llm_fallback_api_key),
            llm_fallback_base_url=_resolve_env(self.llm_fallback_base_url),
            llm_fallback_model=_resolve_env(self.llm_fallback_model),
        )


@dataclass(frozen=True)
class SuperbetShadowConfig:
    """Superbet SSE feed configuration."""

    sse_endpoint: str = (
        "https://production-superbet-offer-br.freetls.fastly.net"
        "/subscription/v2/pt-BR/events/all"
    )
    sport_id: int = 5
    corner_market_name: str = "Total de Escanteios"
    team_mapping_path: str = "data/mapping/superbet_teams.json"
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 30.0
    stream_duration_s: float = 30.0  # Seconds to listen to the SSE stream per collection cycle
    max_retries: int = 3
    backoff_base_s: float = 2.0
    # Whitelist of Superbet tournamentId values to process.
    # Empty tuple = no filter (all football events pass through).
    # Populate with IDs for leagues available on football-data.org.
    tournament_ids: tuple = ()


@dataclass(frozen=True)
class ApiFootballConfig:
    """API-Football (api-sports.io) settings."""

    base_url: str = "https://v3.football.api-sports.io"
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 15.0


# ── Top-level container ──────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration."""

    data: DataConfig
    features: FeatureConfig
    model: ModelConfig
    odds: OddsConfig
    value: ValueConfig
    gatekeeper: GatekeeperConfig = field(default_factory=GatekeeperConfig)
    api_keys: ApiKeysConfig = field(default_factory=ApiKeysConfig)
    superbet_shadow: SuperbetShadowConfig = field(default_factory=SuperbetShadowConfig)
    api_football: ApiFootballConfig = field(default_factory=ApiFootballConfig)

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> PipelineConfig:
        """Load and parse a YAML config file into a PipelineConfig.

        Centralised loader — all scripts should use this instead of
        duplicating YAML-to-dataclass logic.
        """
        import yaml

        path = Path(config_path)
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        data_cfg = DataConfig(
            raw_path=Path(raw["data"]["raw_path"]),
            processed_path=Path(raw["data"]["processed_path"]),
            date_column=raw["data"].get("date_column", "date"),
        )
        features_cfg = FeatureConfig(**raw["features"])

        model_dict = raw["model"].copy()
        if "algorithms" in model_dict and isinstance(model_dict["algorithms"], list):
            model_dict["algorithms"] = tuple(model_dict["algorithms"])
        model_cfg = ModelConfig(**model_dict)

        odds_cfg = OddsConfig(**raw["odds"])
        value_cfg = ValueConfig(**raw["value"])

        gatekeeper_cfg = (
            GatekeeperConfig(**raw["gatekeeper"]) if "gatekeeper" in raw else GatekeeperConfig()
        )
        api_keys_cfg = (
            ApiKeysConfig(**raw["api_keys"]) if "api_keys" in raw else ApiKeysConfig()
        )
        superbet_cfg = (
            SuperbetShadowConfig(
                **{
                    **raw["superbet_shadow"],
                    "tournament_ids": tuple(
                        raw["superbet_shadow"].get("tournament_ids", [])
                    ),
                }
            )
            if "superbet_shadow" in raw
            else SuperbetShadowConfig()
        )
        api_football_cfg = (
            ApiFootballConfig(**raw["api_football"])
            if "api_football" in raw
            else ApiFootballConfig()
        )

        return cls(
            data=data_cfg,
            features=features_cfg,
            model=model_cfg,
            odds=odds_cfg,
            value=value_cfg,
            gatekeeper=gatekeeper_cfg,
            api_keys=api_keys_cfg,
            superbet_shadow=superbet_cfg,
            api_football=api_football_cfg,
        )


# ── helpers ──────────────────────────────────────────────────────────


def _resolve_env(value: str) -> str:
    """Expand ``${VAR}`` references from environment variables."""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value
