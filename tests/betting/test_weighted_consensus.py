"""Tests for SHAP-based model weights and weighted consensus (P1.C2)."""

from __future__ import annotations

import numpy as np
import pytest

from japredictbet.betting.engine import ConsensusEngine


class TestWeightedConsensus:
    """Tests for weighted voting in ConsensusEngine."""

    def _make_predictions(self, lambdas: list[float]) -> list[dict]:
        """Helper: create prediction dicts from lambda totals."""
        return [{"lambda_total": l} for l in lambdas]

    def _make_odds(self, line: float = 9.5, odds: float = 1.85) -> dict:
        return {"line": line, "odds": odds, "type": "over"}

    def test_equal_weights_same_as_unweighted(self):
        """Equal weights should produce same result as no weights."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=False)
        preds = self._make_predictions([11.0, 11.5, 10.0, 9.0, 12.0])
        odds = self._make_odds()

        result_no_weights = engine.evaluate_with_consensus(preds, odds, threshold=0.5)
        result_equal = engine.evaluate_with_consensus(
            preds, odds, threshold=0.5, model_weights=[1.0, 1.0, 1.0, 1.0, 1.0]
        )

        assert result_no_weights["bet"] == result_equal["bet"]
        assert result_no_weights["agreement"] == pytest.approx(result_equal["agreement"])

    def test_weighted_votes_shift_decision(self):
        """High weight on dissenting model can flip the decision."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=False)
        # 3 models vote yes (high lambda), 2 vote no (low lambda)
        preds = self._make_predictions([12.0, 12.0, 12.0, 5.0, 5.0])
        odds = self._make_odds(line=9.5, odds=1.85)

        # Without weights: 3/5 = 60% → bet if threshold=0.5
        result_unweighted = engine.evaluate_with_consensus(
            preds, odds, threshold=0.5
        )
        assert result_unweighted["bet"] is True

        # With heavy weight on "no" models → weighted agreement should drop
        result_weighted = engine.evaluate_with_consensus(
            preds, odds, threshold=0.5,
            model_weights=[1.0, 1.0, 1.0, 10.0, 10.0]
        )
        # Weighted: (1+1+1+0+0) / (1+1+1+10+10) = 3/23 ≈ 13% → no bet
        assert result_weighted["bet"] is False

    def test_weights_none_uses_equal(self):
        """model_weights=None falls back to equal weighting."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=False)
        preds = self._make_predictions([11.0, 11.0, 11.0])
        odds = self._make_odds()

        result = engine.evaluate_with_consensus(preds, odds, threshold=0.5, model_weights=None)
        assert "agreement" in result

    def test_mismatched_weights_length_ignored(self):
        """If weights length doesn't match models, falls back to equal."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=False)
        preds = self._make_predictions([11.0, 11.0, 11.0])
        odds = self._make_odds()

        # 2 weights for 3 models → ignored, uses equal
        result = engine.evaluate_with_consensus(
            preds, odds, threshold=0.5, model_weights=[1.0, 1.0]
        )
        assert result["total_models"] == 3

    def test_weighted_agreement_value(self):
        """Verify weighted agreement computation."""
        engine = ConsensusEngine(edge_threshold=0.0, use_dynamic_margin=False)
        # All models predict high → all vote yes
        preds = self._make_predictions([15.0, 15.0, 15.0])
        odds = self._make_odds(line=9.5, odds=1.85)

        result = engine.evaluate_with_consensus(
            preds, odds, threshold=0.5,
            model_weights=[2.0, 3.0, 5.0]
        )
        # All vote yes: weighted = (2+3+5)/(2+3+5) = 1.0
        assert result["agreement"] == pytest.approx(1.0)

    def test_evaluate_match_with_consensus_passes_weights(self):
        """Alias method should forward model_weights."""
        engine = ConsensusEngine(edge_threshold=0.05, use_dynamic_margin=False)
        preds = self._make_predictions([12.0, 12.0, 5.0, 5.0])
        odds = self._make_odds()

        result = engine.evaluate_match_with_consensus(
            preds, odds, threshold=0.5,
            model_weights=[1.0, 1.0, 10.0, 10.0]
        )
        # Weighted: (1+1+0+0) / (1+1+10+10) = 2/22 ≈ 9% → no bet
        assert result["bet"] is False
