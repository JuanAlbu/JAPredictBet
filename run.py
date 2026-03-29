"""Main entrypoint to run the MVP pipeline."""

import argparse
import pickle
import yaml
from pathlib import Path
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
    model_cfg = ModelConfig(**config_dict["model"])
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


if __name__ == "__main__":
    args = parse_args()
    config_path = args.config
    print(f"Running JAPredictBet MVP Pipeline...")
    print(f"Loading configuration from: {config_path}")

    try:
        config = load_config(config_path)
        ensemble_models = load_model_artifacts(args.model_artifact)

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
            print(results_df[["match", "consensus_threshold", "vote_distribution", "status_message"]])

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
