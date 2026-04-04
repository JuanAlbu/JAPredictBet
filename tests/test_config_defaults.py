"""Configuration defaults regression tests."""

from japredictbet.config import ModelConfig


def test_model_config_default_algorithms_include_hybrid_linear_members() -> None:
    model_cfg = ModelConfig()
    assert model_cfg.algorithms == (
        "xgboost",
        "lightgbm",
        "randomforest",
        "ridge",
        "elasticnet",
    )
