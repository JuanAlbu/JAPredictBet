"""Tests for lambda validation in betting engine (P1.A3)."""

import math
import pytest

from src.japredictbet.betting.engine import (
    _validate_lambda,
    _extract_lambda_total,
    report_consensus,
)
from src.japredictbet.betting.engine import ConsensusEngine


class TestLambdaValidation:
    """Test the _validate_lambda validation function."""

    def test_validate_lambda_valid_positive(self):
        """Valid positive lambda should not raise."""
        _validate_lambda(5.5, context="test")
        _validate_lambda(10.0, context="test")
        _validate_lambda(0.1, context="test")

    def test_validate_lambda_zero_logs_warning(self, caplog):
        """Lambda == 0 should log warning but not raise."""
        _validate_lambda(0.0, context="zero_test")
        assert "Lambda is 0" in caplog.text

    def test_validate_lambda_nan_raises(self):
        """Lambda NaN should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            _validate_lambda(float("nan"), context="nan_test")

    def test_validate_lambda_inf_raises(self):
        """Lambda Inf should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            _validate_lambda(float("inf"), context="inf_test")

    def test_validate_lambda_negative_inf_raises(self):
        """Lambda -Inf should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            _validate_lambda(float("-inf"), context="ninf_test")

    def test_validate_lambda_negative_raises(self):
        """Lambda < 0 should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _validate_lambda(-5.5, context="negative_test")


class TestExtractLambdaTotal:
    """Test lambda extraction with validation."""

    def test_extract_lambda_total_from_total_field(self):
        """Extract valid lambda_total."""
        result = _extract_lambda_total({"lambda_total": 9.5})
        assert result == 9.5

    def test_extract_lambda_total_from_parts(self):
        """Extract lambda_total from lambda_home + lambda_away."""
        result = _extract_lambda_total({"lambda_home": 4.5, "lambda_away": 5.0})
        assert result == 9.5

    def test_extract_lambda_total_missing_fields_raises(self):
        """Missing lambda fields should raise ValueError."""
        with pytest.raises(ValueError, match="must contain either"):
            _extract_lambda_total({"some_field": 10.0})

    def test_extract_lambda_total_nan_raises(self):
        """NaN lambda_total should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            _extract_lambda_total({"lambda_total": float("nan")})

    def test_extract_lambda_total_negative_raises(self):
        """Negative lambda_total should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _extract_lambda_total({"lambda_total": -5.5})

    def test_extract_lambda_total_sum_nan_raises(self):
        """Sum of lambda_home + lambda_away being NaN should raise."""
        # This is a bit tricky - in practice, adding two numbers won't give NaN
        # unless one is already NaN
        with pytest.raises(ValueError, match="not finite"):
            _extract_lambda_total(
                {"lambda_home": float("nan"), "lambda_away": 5.0}
            )


class TestReportConsensusValidation:
    """Test report_consensus with lambda validation."""

    def test_report_consensus_valid_lambdas(self):
        """Valid lambdas should work."""
        result = report_consensus(
            lambdas=[9.0, 9.5, 10.0, 9.2],
            odds=2.0,
            line=9.5,
            threshold_edge=0.05,
            consensus_threshold=0.5,
        )
        assert result["mean_lambda"] == pytest.approx(9.425, abs=0.01)

    def test_report_consensus_single_lambda(self):
        """Single lambda should work."""
        result = report_consensus(
            lambdas=[9.5],
            odds=2.0,
            line=9.5,
            threshold_edge=0.05,
            consensus_threshold=0.5,
        )
        assert result["mean_lambda"] == 9.5
        assert result["votes"] >= 0

    def test_report_consensus_empty_lambdas_raises(self):
        """Empty lambdas list should raise ValueError."""
        with pytest.raises(ValueError, match="at least one value"):
            report_consensus(
                lambdas=[],
                odds=2.0,
                line=9.5,
                threshold_edge=0.05,
                consensus_threshold=0.5,
            )

    def test_report_consensus_invalid_odds_raises(self):
        """Invalid odds should raise ValueError."""
        with pytest.raises(ValueError, match="odds must be positive"):
            report_consensus(
                lambdas=[9.5],
                odds=0.0,
                line=9.5,
                threshold_edge=0.05,
                consensus_threshold=0.5,
            )

    def test_report_consensus_nan_lambda_raises(self):
        """NaN in lambdas list should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            report_consensus(
                lambdas=[9.0, float("nan"), 10.0],
                odds=2.0,
                line=9.5,
                threshold_edge=0.05,
                consensus_threshold=0.5,
            )

    def test_report_consensus_inf_lambda_raises(self):
        """Inf in lambdas list should raise ValueError."""
        with pytest.raises(ValueError, match="not finite"):
            report_consensus(
                lambdas=[9.0, float("inf"), 10.0],
                odds=2.0,
                line=9.5,
                threshold_edge=0.05,
                consensus_threshold=0.5,
            )

    def test_report_consensus_negative_lambda_raises(self):
        """Negative lambda in list should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            report_consensus(
                lambdas=[9.0, -5.0, 10.0],
                odds=2.0,
                line=9.5,
                threshold_edge=0.05,
                consensus_threshold=0.5,
            )


class TestConsensusEngineValidation:
    """Test ConsensusEngine with invalid lambdas."""

    def test_consensus_engine_valid_predictions(self):
        """Valid predictions should work."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=True)
        predictions = [
            {"lambda_home": 4.5, "lambda_away": 5.0},
            {"lambda_home": 4.0, "lambda_away": 5.5},
        ]
        odds_data = {"line": 9.5, "odds": 2.0, "type": "over"}

        result = engine.evaluate_with_consensus(
            predictions_list=predictions,
            odds_data=odds_data,
            threshold=0.45,
        )
        assert result["bet"] is not None

    def test_consensus_engine_nan_lambda_raises(self):
        """NaN lambda in predictions should raise."""
        engine = ConsensusEngine(edge_threshold=0.05)
        predictions = [
            {"lambda_total": float("nan")},
        ]
        odds_data = {"line": 9.5, "odds": 2.0}

        with pytest.raises(ValueError, match="not finite"):
            engine.evaluate_with_consensus(
                predictions_list=predictions,
                odds_data=odds_data,
                threshold=0.45,
            )

    def test_consensus_engine_negative_lambda_raises(self):
        """Negative lambda in predictions should raise."""
        engine = ConsensusEngine(edge_threshold=0.05)
        predictions = [
            {"lambda_total": -5.0},
        ]
        odds_data = {"line": 9.5, "odds": 2.0}

        with pytest.raises(ValueError, match="non-negative"):
            engine.evaluate_with_consensus(
                predictions_list=predictions,
                odds_data=odds_data,
                threshold=0.45,
            )

    def test_consensus_engine_mixed_valid_invalid_raises(self):
        """If any prediction is invalid, entire evaluation should raise."""
        engine = ConsensusEngine(edge_threshold=0.05)
        predictions = [
            {"lambda_home": 4.5, "lambda_away": 5.0},  # valid
            {"lambda_total": float("inf")},  # invalid
            {"lambda_home": 4.0, "lambda_away": 5.5},  # valid
        ]
        odds_data = {"line": 9.5, "odds": 2.0}

        with pytest.raises(ValueError, match="not finite"):
            engine.evaluate_with_consensus(
                predictions_list=predictions,
                odds_data=odds_data,
                threshold=0.45,
            )


class TestEdgeCases:
    """Test edge cases for lambda validation."""

    def test_very_large_lambda(self):
        """Very large lambda should be valid (Poisson handles it)."""
        _validate_lambda(1e6, context="large_lambda")
        # Should not raise

    def test_very_small_lambda(self):
        """Very small positive lambda should be valid."""
        _validate_lambda(1e-10, context="small_lambda")
        # Should not raise

    def test_extract_multiple_operations(self):
        """Chain operations with validation should work."""
        pred1 = _extract_lambda_total({"lambda_total": 9.5})
        pred2 = _extract_lambda_total({"lambda_home": 4.0, "lambda_away": 5.5})
        lambdas = [pred1, pred2]

        result = report_consensus(
            lambdas=lambdas,
            odds=2.0,
            line=9.5,
            threshold_edge=0.05,
            consensus_threshold=0.5,
        )
        assert result["mean_lambda"] > 0
