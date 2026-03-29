"""Configuration models for the MVP pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataConfig:
    """Input/output paths for datasets."""

    raw_path: Path
    processed_path: Path
    date_column: str = "date"


@dataclass(frozen=True)
class FeatureConfig:
    """Feature engineering settings."""

    rolling_window: int = 10


@dataclass(frozen=True)
class ModelConfig:
    """Model training settings."""

    objective: str = "count:poisson"
    random_state: int = 42
    ensemble_size: int = 30
    algorithms: tuple[str, ...] = ("xgboost", "lightgbm", "randomforest")
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


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration."""

    data: DataConfig
    features: FeatureConfig
    model: ModelConfig
    odds: OddsConfig
    value: ValueConfig
