"""Tests for model training and ensemble scheduling."""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

from japredictbet.models.train import (
    _build_ensemble_schedule,
    _build_hybrid_ensemble_schedule,
    build_variation_params,
    _build_model_filename,
    save_ensemble_models,
    TrainedModels,
    EnsembleModelSpec,
)


class TestHybridEnsembleSchedule:
    """Test hybrid 70/30 ensemble scheduling."""

    def test_hybrid_schedule_size_30(self) -> None:
        """Test that size=30 yields 21 boosters + 9 linear."""
        schedule = _build_hybrid_ensemble_schedule(30)
        
        assert len(schedule) == 30, f"Expected 30 models, got {len(schedule)}"
        
        boosters = [algo for algo in schedule if algo in ("xgboost", "lightgbm")]
        linear = [algo for algo in schedule if algo in ("ridge", "elasticnet")]
        
        assert len(boosters) == 21, f"Expected 21 boosters, got {len(boosters)}"
        assert len(linear) == 9, f"Expected 9 linear, got {len(linear)}"

    def test_hybrid_alternates_boosters(self) -> None:
        """Test that boosters alternate between xgboost and lightgbm."""
        schedule = _build_hybrid_ensemble_schedule(30)
        boosters = schedule[:21]  # First 21 are boosters
        
        # Should alternate: xgb, lgb, xgb, lgb, ...
        for i, algo in enumerate(boosters):
            if i % 2 == 0:
                assert algo == "xgboost", f"Position {i}: expected xgboost, got {algo}"
            else:
                assert algo == "lightgbm", f"Position {i}: expected lightgbm, got {algo}"

    def test_hybrid_alternates_linear(self) -> None:
        """Test that linear models alternate between ridge and elasticnet."""
        schedule = _build_hybrid_ensemble_schedule(30)
        linear = schedule[21:]  # Last 9 are linear
        
        # Should alternate: ridge, elastic, ridge, elastic, ...
        for i, algo in enumerate(linear):
            if i % 2 == 0:
                assert algo == "ridge", f"Position {i}: expected ridge, got {algo}"
            else:
                assert algo == "elasticnet", f"Position {i}: expected elasticnet, got {algo}"

    def test_build_ensemble_schedule_triggers_hybrid(self) -> None:
        """Test that size 25-35 triggers hybrid mode."""
        for size in [25, 28, 30, 32, 35]:
            schedule = _build_ensemble_schedule(size, ("xgboost", "lightgbm", "randomforest"))
            
            has_ridge = "ridge" in schedule
            has_elastic = "elasticnet" in schedule
            
            assert has_ridge or has_elastic, (
                f"Size {size} should trigger hybrid (have ridge or elasticnet)"
            )


class TestVariationParams:
    """Test hyperparameter generation."""

    def test_ridge_params_valid(self) -> None:
        """Test that ridge generates valid params."""
        for var_idx in range(10):
            params = build_variation_params("ridge", var_idx)
            
            assert "alpha" in params, "Ridge params must have alpha"
            assert params["alpha"] > 0, "Alpha must be positive"
            assert "max_iter" in params, "Ridge params must have max_iter"

    def test_elasticnet_params_valid(self) -> None:
        """Test that elasticnet generates valid params."""
        for var_idx in range(10):
            params = build_variation_params("elasticnet", var_idx)
            
            assert "alpha" in params, "ElasticNet params must have alpha"
            assert params["alpha"] > 0, "Alpha must be positive"
            assert "l1_ratio" in params, "ElasticNet params must have l1_ratio"
            assert 0 <= params["l1_ratio"] <= 1, "l1_ratio must be in [0,1]"
            assert "max_iter" in params, "ElasticNet params must have max_iter"

    def test_xgboost_params(self) -> None:
        """Test xgboost params still work."""
        params = build_variation_params("xgboost", 0)
        
        assert "objective" in params
        assert params["objective"] == "count:poisson"
        assert "n_estimators" in params
        assert "learning_rate" in params

    def test_lightgbm_params(self) -> None:
        """Test lightgbm params still work."""
        params = build_variation_params("lightgbm", 0)
        
        assert "objective" in params
        assert params["objective"] == "poisson"
        assert "n_estimators" in params
        assert "learning_rate" in params

    def test_randomforest_params(self) -> None:
        """Test randomforest params still work."""
        params = build_variation_params("randomforest", 0)
        
        assert "n_estimators" in params
        assert "max_depth" in params


class TestModelFilenames:
    """Test model artifact naming."""

    def test_filename_xgboost(self) -> None:
        """Test xgboost filename format."""
        name = _build_model_filename("xgboost", 0)
        assert name.startswith("xgb_model_"), f"Expected xgb prefix, got {name}"
        assert name.endswith(".pkl"), f"Expected .pkl suffix, got {name}"

    def test_filename_ridge(self) -> None:
        """Test ridge filename format."""
        name = _build_model_filename("ridge", 0)
        assert name.startswith("ridge_model_"), f"Expected ridge prefix, got {name}"
        assert name.endswith(".pkl"), f"Expected .pkl suffix, got {name}"

    def test_filename_elasticnet(self) -> None:
        """Test elasticnet filename format."""
        name = _build_model_filename("elasticnet", 0)
        assert name.startswith("elastic_model_"), f"Expected elastic prefix, got {name}"
        assert name.endswith(".pkl"), f"Expected .pkl suffix, got {name}"

    def test_filename_increments_variation(self) -> None:
        """Test that filenames increment with variation index."""
        name_0 = _build_model_filename("ridge", 0)
        name_1 = _build_model_filename("ridge", 1)
        
        assert "ridge_model_1" in name_0
        assert "ridge_model_2" in name_1


class TestHyperparameterPersistence:
    """Tests for P1.C3: JSON metadata saved alongside .pkl files."""

    def _make_dummy_model(self, features=("feat_a", "feat_b")):
        """Create a minimal TrainedModels for testing."""
        return TrainedModels(
            home_model="dummy_home",
            away_model="dummy_away",
            feature_columns=tuple(features),
        )

    def _make_spec(self, algorithm="xgboost", variation=0, seed=42):
        """Create a minimal EnsembleModelSpec for testing."""
        params = build_variation_params(algorithm, variation)
        name = _build_model_filename(algorithm, variation)
        return EnsembleModelSpec(
            algorithm=algorithm,
            variation_index=variation,
            random_state=seed,
            model_name=name,
            params=params,
        )

    def test_json_metadata_created(self):
        """save_ensemble_models should create .json alongside .pkl."""
        model = self._make_dummy_model()
        spec = self._make_spec("ridge", 0, 42)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_ensemble_models([model], [spec], tmpdir)
            pkl_path = Path(tmpdir) / spec.model_name
            json_path = pkl_path.with_suffix(".json")

            assert pkl_path.exists(), "PKL file should exist"
            assert json_path.exists(), "JSON metadata file should exist"

    def test_json_contains_required_fields(self):
        """JSON metadata should contain algorithm, params, features."""
        model = self._make_dummy_model(("corner_for_last10", "elo_rating"))
        spec = self._make_spec("elasticnet", 2, 100)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_ensemble_models([model], [spec], tmpdir)
            json_path = (Path(tmpdir) / spec.model_name).with_suffix(".json")

            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            assert meta["algorithm"] == "elasticnet"
            assert meta["variation_index"] == 2
            assert meta["random_state"] == 100
            assert "params" in meta
            assert "alpha" in meta["params"]
            assert "l1_ratio" in meta["params"]
            assert meta["feature_columns"] == ["corner_for_last10", "elo_rating"]
            assert meta["n_features"] == 2

    def test_json_for_all_ensemble_members(self):
        """All 3 models should get JSON metadata."""
        models = [self._make_dummy_model() for _ in range(3)]
        specs = [
            self._make_spec("xgboost", 0, 42),
            self._make_spec("lightgbm", 0, 43),
            self._make_spec("ridge", 0, 44),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            save_ensemble_models(models, specs, tmpdir)
            json_files = list(Path(tmpdir).glob("*.json"))
            assert len(json_files) == 3

    def test_json_is_valid_json(self):
        """JSON file should be parseable."""
        model = self._make_dummy_model()
        spec = self._make_spec("xgboost", 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_ensemble_models([model], [spec], tmpdir)
            json_path = (Path(tmpdir) / spec.model_name).with_suffix(".json")

            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)  # Should not raise

            assert isinstance(meta, dict)
