"""Main entrypoint to run the MVP pipeline."""

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


if __name__ == "__main__":
    CONFIG_PATH = Path("config.yml")
    print(f"Running JAPredictBet MVP Pipeline...")
    print(f"Loading configuration from: {CONFIG_PATH}")

    try:
        config = load_config(CONFIG_PATH)

        print("\nPipeline configured. Starting execution...")
        results_df = run_mvp_pipeline(config)

        print("\nPipeline execution finished successfully!")
        print("Value Betting Opportunities Found:")
        print("-" * 40)

        if results_df.empty or "is_value" not in results_df.columns:
            print("No value bets found with the current configuration.")
        else:
            value_bets = results_df[results_df["is_value"]].copy()
            if value_bets.empty:
                print("No value bets found with the current configuration.")
                print("-" * 40)
                raise SystemExit(0)
            # Display settings for pandas
            pd.set_option("display.max_rows", 500)
            pd.set_option("display.max_columns", 50)
            pd.set_option("display.width", 120)
            print(value_bets)

        print("-" * 40)

    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at '{CONFIG_PATH}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Optionally, re-raise for more detailed traceback
        # raise e
