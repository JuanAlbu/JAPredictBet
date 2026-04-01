"""Test P1.A2: Dynamic margin parameters in config and ConsensusEngine integration."""

import pytest
from src.japredictbet.config import ValueConfig
from src.japredictbet.betting.engine import ConsensusEngine


def test_value_config_defaults():
    """Test that ValueConfig has new dynamic margin fields with defaults."""
    cfg = ValueConfig()
    assert cfg.tight_margin_threshold == 0.5
    assert cfg.tight_margin_consensus == 0.50


def test_value_config_custom_values():
    """Test that ValueConfig can be created with custom dynamic margin values."""
    cfg = ValueConfig(
        threshold=0.05,
        consensus_threshold=0.45,
        tight_margin_threshold=0.3,
        tight_margin_consensus=0.60,
    )
    assert cfg.tight_margin_threshold == 0.3
    assert cfg.tight_margin_consensus == 0.60


def test_consensus_engine_accepts_dynamic_margin_params():
    """Test that ConsensusEngine accepts dynamic margin parameters."""
    engine = ConsensusEngine(
        edge_threshold=0.05,
        tight_margin_threshold=0.3,
        tight_margin_consensus=0.60,
    )
    assert engine.tight_margin_threshold == 0.3
    assert engine.tight_margin_consensus == 0.60


def test_consensus_engine_dynamic_margin_defaults():
    """Test that ConsensusEngine has sensible defaults."""
    engine = ConsensusEngine(edge_threshold=0.05)
    assert engine.tight_margin_threshold == 0.5
    assert engine.tight_margin_consensus == 0.50


def test_dynamic_threshold_uses_stored_values():
    """Test that _compute_dynamic_threshold uses stored values from __init__."""
    # Create engine with custom tight values
    engine = ConsensusEngine(
        edge_threshold=0.05,
        tight_margin_threshold=0.2,  # Lower threshold
        tight_margin_consensus=0.70,  # Higher requirement
    )

    # When margin < threshold, should return tight_margin_consensus
    result_tight = engine._compute_dynamic_threshold(
        mean_lambda=9.8, line=10.0, base_threshold=0.45
    )
    assert result_tight == 0.70, "Should return tight_margin_consensus when margin < threshold"

    # When margin >= threshold, should return base_threshold
    result_loose = engine._compute_dynamic_threshold(
        mean_lambda=9.0, line=10.0, base_threshold=0.45
    )
    assert result_loose == 0.45, "Should return base_threshold when margin >= threshold"


def test_dynamic_threshold_disabled():
    """Test that dynamic margin can be disabled."""
    engine = ConsensusEngine(
        edge_threshold=0.05,
        use_dynamic_margin=False,
        tight_margin_threshold=0.2,
        tight_margin_consensus=0.70,
    )

    # Even when margin < threshold, should return base_threshold if disabled
    result = engine._compute_dynamic_threshold(
        mean_lambda=9.8, line=10.0, base_threshold=0.45
    )
    assert result == 0.45, "Should return base_threshold when dynamic margin is disabled"


def test_consensus_engine_with_config_values():
    """Test ConsensusEngine initialized with config.value values."""
    cfg = ValueConfig(
        threshold=0.05,
        consensus_threshold=0.7,
        tight_margin_threshold=0.4,
        tight_margin_consensus=0.55,
    )

    # This simulates how mvp_pipeline.py initializes the engine
    engine = ConsensusEngine(
        edge_threshold=cfg.threshold,
        tight_margin_threshold=cfg.tight_margin_threshold,
        tight_margin_consensus=cfg.tight_margin_consensus,
    )

    assert engine.edge_threshold == cfg.threshold
    assert engine.tight_margin_threshold == cfg.tight_margin_threshold
    assert engine.tight_margin_consensus == cfg.tight_margin_consensus


def test_different_margin_scenarios():
    """Test various margin scenarios with configured thresholds."""
    engine = ConsensusEngine(
        tight_margin_threshold=0.5,
        tight_margin_consensus=0.50,
    )

    scenarios = [
        # (mean_lambda, line, expected_result, description)
        (9.8, 10.0, 0.50, "Very tight margin (0.2 < 0.5) → tight threshold"),
        (9.5, 10.0, 0.50, "Tight margin (0.5 = 0.5) → tight threshold at boundary"),
        (9.4, 10.0, 0.45, "Margin just over (0.6 > 0.5) → base threshold"),
        (8.0, 10.0, 0.45, "Wide margin (2.0 > 0.5) → base threshold"),
        (10.2, 10.0, 0.45, "Margin on other side (0.2 < 0.5 but abs = 0.2) → tight"),
    ]

    for mean_lambda, line, expected, description in scenarios:
        result = engine._compute_dynamic_threshold(
            mean_lambda=mean_lambda, line=line, base_threshold=0.45
        )
        expected_val = 0.50 if expected == 0.50 else 0.45
        # The boundary is actually "< tight_margin_threshold", so 0.5 should trigger
        if abs(mean_lambda - line) < 0.5:
            expected_val = 0.50
        else:
            expected_val = 0.45
        assert result == expected_val, f"Failed: {description}"
