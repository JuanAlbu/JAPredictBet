"""Configuration models for the MVP pipeline."""

from __future__ import annotations

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
    tight_margin_threshold: float = 0.5  # Dynamic margin rule: trigger when |lambda - line| < this
    tight_margin_consensus: float = 0.50  # Consensus required when margin is tight (e.g., 50%)


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration."""

    data: DataConfig
    features: FeatureConfig
    model: ModelConfig
    odds: OddsConfig
    value: ValueConfig
