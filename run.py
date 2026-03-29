"""Main entrypoint to run the MVP pipeline."""

import argparse
import pickle
import yaml
from pathlib import Path
import math
import pandas as pd

from japredictbet.config import (
    DataConfig,
    FeatureConfig,
    ModelConfig,
    OddsConfig,
    PipelineConfig,
    ValueConfig,
)
from japredictbet.models.train import TrainedModels
from japredictbet.pipeline.mvp_pipeline import run_mvp_pipeline


def load_config(config_path: Path) -> PipelineConfig:
    """Load and parse the YAML config file into a PipelineConfig object."""
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)

    # Convert path strings to Path objects before creating dataclasses
    data_conf_dict = config_dict["data"]
    data_conf_dict["raw_path"] = Path(data_conf_dict["raw_path"])
    data_conf_dict["processed_path"] = Path(data_conf_dict["processed_path"])

    # Recursively build the nested dataclasses
    data_cfg = DataConfig(**data_conf_dict)
    features_cfg = FeatureConfig(**config_dict["features"])
    model_conf_dict = config_dict["model"].copy()
    if "algorithms" in model_conf_dict and isinstance(model_conf_dict["algorithms"], list):
        model_conf_dict["algorithms"] = tuple(model_conf_dict["algorithms"])
    model_cfg = ModelConfig(**model_conf_dict)
    odds_cfg = OddsConfig(**config_dict["odds"])
    value_cfg = ValueConfig(**config_dict["value"])

    return PipelineConfig(
        data=data_cfg,
        features=features_cfg,
        model=model_cfg,
        odds=odds_cfg,
        value=value_cfg,
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args for pipeline execution."""

    parser = argparse.ArgumentParser(description="Run JAPredictBet MVP pipeline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="Path to pipeline config file.",
    )
    parser.add_argument(
        "--model-artifact",
        action="append",
        default=[],
        type=Path,
        help="Optional pickled TrainedModels artifact path. Can be repeated.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("artifacts/models"),
        help="Directory containing standard ensemble artifacts (xgb_model_1.pkl etc.).",
    )
    parser.add_argument(
        "--skip-model-dir",
        action="store_true",
        help="Disable auto-loading artifacts from --models-dir.",
    )
    return parser.parse_args()


def load_model_artifacts(artifact_paths: list[Path]) -> list[TrainedModels]:
    """Load a list of pickled TrainedModels artifacts."""

    loaded_models: list[TrainedModels] = []
    for artifact in artifact_paths:
        with open(artifact, "rb") as handle:
            model = pickle.load(handle)
        if not isinstance(model, TrainedModels):
            raise TypeError(
                f"Artifact '{artifact}' did not contain a TrainedModels instance."
            )
        loaded_models.append(model)
    return loaded_models


def discover_model_artifacts(models_dir: Path) -> list[Path]:
    """Discover standardized ensemble artifact files in a directory."""

    if not models_dir.exists() or not models_dir.is_dir():
        return []
    patterns = ("xgb_model_*.pkl", "lgbm_model_*.pkl", "rf_model_*.pkl")
    discovered: list[Path] = []
    for pattern in patterns:
        discovered.extend(sorted(models_dir.glob(pattern)))
    return discovered


if __name__ == "__main__":
    args = parse_args()
    config_path = args.config
    print(f"Running JAPredictBet MVP Pipeline...")
    print(f"Loading configuration from: {config_path}")

    try:
        config = load_config(config_path)
        artifact_paths = list(args.model_artifact)
        if not args.skip_model_dir and not artifact_paths:
            artifact_paths = discover_model_artifacts(args.models_dir)
            if artifact_paths:
                print(
                    f"Discovered {len(artifact_paths)} model artifacts in {args.models_dir}"
                )
        ensemble_models = load_model_artifacts(artifact_paths)
        if ensemble_models and len(ensemble_models) != config.model.ensemble_size:
            raise ValueError(
                "Loaded artifact count does not match configured ensemble_size "
                f"({len(ensemble_models)} != {config.model.ensemble_size})."
            )

        print("\nPipeline configured. Starting execution...")
        if ensemble_models:
            print(f"Loaded {len(ensemble_models)} model artifacts for consensus.")
        results_df = run_mvp_pipeline(
            config,
            ensemble_models=ensemble_models if ensemble_models else None,
        )

        print("\nPipeline execution finished successfully!")
        print("Consensus betting decisions:")
        print("-" * 40)

        if results_df.empty:
            print("No markets available for evaluation.")
        else:
            # Display settings for pandas
            pd.set_option("display.max_rows", 500)
            pd.set_option("display.max_columns", 50)
            pd.set_option("display.width", 120)
            print(
                results_df[
                    [
                        "match",
                        "consensus_threshold",
                        "consensus_label",
                        "status_message",
                    ]
                ]
            )

            threshold_summary = (
                results_df[
                    [
                        "consensus_threshold",
                        "bets_placed",
                        "profit_total",
                        "yield",
                        "roi",
                        "hit_rate",
                    ]
                ]
                .drop_duplicates(subset=["consensus_threshold"])
                .sort_values(by="consensus_threshold")
            )
            threshold_summary["balance_score"] = threshold_summary.apply(
                lambda row: float(row["roi"]) * math.log1p(float(row["bets_placed"])),
                axis=1,
            )
            print("\nThreshold performance (ROI/Yield):")
            print(threshold_summary)

            best_row = threshold_summary.sort_values(
                by=["balance_score", "roi", "bets_placed"],
                ascending=False,
            ).iloc[0]
            print("\nBest threshold balance (ROI x volume):")
            print(
                f"Threshold={best_row['consensus_threshold']:.2f} | "
                f"ROI={best_row['roi']:.3f} | Yield={best_row['yield']:.3f} | "
                f"HitRate={best_row['hit_rate']:.3f} | Bets={int(best_row['bets_placed'])}"
            )

            confirmed = results_df[results_df["is_value"]].copy()
            if confirmed.empty:
                print("\nNo confirmed bets after consensus filtering.")
            else:
                print("\nConfirmed bets:")
                print(
                    confirmed[
                        [
                            "match",
                            "consensus_threshold",
                            "agreement",
                            "vote_distribution",
                            "edge_mean",
                            "status_message",
                        ]
                    ]
                )

        print("-" * 40)

    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at '{config_path}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Optionally, re-raise for more detailed traceback
        # raise e
