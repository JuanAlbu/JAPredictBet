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


@dataclass(frozen=True)
class OddsConfig:
    """Odds ingestion settings."""

    provider_name: str = "mock"


@dataclass(frozen=True)
class ValueConfig:
    """Value-bet detection settings."""

    threshold: float = 0.05


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration."""

    data: DataConfig
    features: FeatureConfig
    model: ModelConfig
    odds: OddsConfig
    value: ValueConfig