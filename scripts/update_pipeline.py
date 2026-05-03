"""
update_pipeline.py
Orquestrador de MLOps para atualizar dados e retreinar o Ensemble de 30 Modelos.

Bugs corrigidos (P2.B3):
  - Bug 1: PipelineConfig(**config_dict) → crash. CORRIGIDO via P2.B6 (from_yaml).
  - Bug 2: Feature engineering ausente — portado pipeline completo (rolling, STD, EMA, ELO,
    matchup, H2H, drop redundant, team encoding).
  - Bug 3: algorithms hardcoded sem Ridge/ElasticNet — corrigido (usa config + fallback completo).
"""
import logging
import shutil
from pathlib import Path
from typing import Sequence

import pandas as pd

from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_h2h_features, add_matchup_features
from japredictbet.features.rolling import (
    add_result_rolling,
    add_stat_rolling,
    add_rolling_std,
    add_rolling_ema,
    drop_redundant_features,
)
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.train import train_and_save_ensemble

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("MLOps_Pipeline")


def _ensure_season_column(data: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Ensure the dataset has a season column for temporal splits."""
    if "season" in data.columns:
        return data
    date_col = date_column if date_column in data.columns else "date"
    df = data.copy()
    df["season"] = df[date_col].dt.year
    return df


def _build_temporal_split_simple(seasons: pd.Series, seed: int = 42) -> pd.Series:
    """Build train mask: use all but the most recent season as training."""
    most_recent = seasons.max()
    return seasons < most_recent


def _build_recency_weights(seasons: pd.Series) -> pd.Series:
    """Linearly scale weights from oldest to most recent season."""
    unique = sorted(seasons.unique())
    season_rank = {season: idx for idx, season in enumerate(unique)}
    max_rank = max(season_rank.values()) if season_rank else 1
    return seasons.map(
        lambda season: 1.0 + (season_rank[season] / max_rank if max_rank else 0.0)
    )


def _engineer_features(data: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    """Apply the complete feature engineering pipeline (port of mvp_pipeline.py)."""
    df = data.copy()

    for window in config.features.rolling_windows:
        # Rolling stats (mean)
        df = add_result_rolling(df, window, season_col="season")
        df = add_stat_rolling(df, window, season_col="season")

        # Rolling STD (P1.B2)
        if config.features.rolling_use_std:
            df = _add_rolling_std_features(df, window, season_col="season")

        # Rolling EMA (P1.B2)
        if config.features.rolling_use_ema:
            df = _add_rolling_ema_features(df, window, season_col="season")

        # Matchup features
        df = add_matchup_features(df, window=window)

    # H2H features (P1.B5)
    df = add_h2h_features(df, h2h_window=config.features.h2h_window)
    df["home_advantage"] = 1.0

    # Drop redundant features
    if config.features.drop_redundant:
        df = drop_redundant_features(df, config.features.rolling_windows)

    # Team target encoding
    train_mask = _build_temporal_split_simple(
        df["season"], config.model.random_state
    )
    df = add_elo_ratings(
        df,
        home_team_col="home_team",
        away_team_col="away_team",
        home_score_col="home_goals",
        away_score_col="away_goals",
        season_col="season",
        config=EloConfig(),
    )
    df = add_team_target_encoding(
        df,
        team_col="home_team",
        target_col="home_corners",
        train_mask=train_mask,
        feature_name="home_team_team_enc",
    )
    df = add_team_target_encoding(
        df,
        team_col="away_team",
        target_col="away_corners",
        train_mask=train_mask,
        feature_name="away_team_team_enc",
    )

    # Drop rows with missing critical data
    before = len(df)
    df = df.dropna(subset=["home_corners", "away_corners"])
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with missing corner data", dropped)

    return df


def _add_rolling_std_features(
    data: pd.DataFrame, window: int, season_col: str | None = None
) -> pd.DataFrame:
    """Add rolling standard deviation features for key stats."""
    df = data.copy()
    group_cols = ["home_team", "away_team"]
    if season_col and season_col in df.columns:
        group_cols = [season_col, "home_team", "away_team"]

    stat_pairs = [
        ("home_corners", "away_corners"),
        ("home_goals", "away_goals"),
        ("home_shots", "away_shots"),
        ("home_shots_on_target", "away_shots_on_target"),
    ]

    for home_stat, away_stat in stat_pairs:
        for prefix, stat in [("home", home_stat), ("away", away_stat)]:
            if stat not in df.columns:
                continue
            col = f"{stat}_rolling_std_{window}"
            if col not in df.columns:  # Avoid redundant computation
                df[col] = (
                    df.groupby(group_cols)[stat]
                    .transform(lambda s: s.shift(1).rolling(window, min_periods=1).std())
                )
    return df


def _add_rolling_ema_features(
    data: pd.DataFrame, window: int, season_col: str | None = None
) -> pd.DataFrame:
    """Add EMA features for key stats."""
    df = data.copy()
    group_cols = ["home_team", "away_team"]
    if season_col and season_col in df.columns:
        group_cols = [season_col, "home_team", "away_team"]

    span = max(2, window)
    stat_list = [
        "home_corners", "away_corners",
        "home_goals", "away_goals",
        "home_shots", "away_shots",
        "home_shots_on_target", "away_shots_on_target",
    ]

    for stat in stat_list:
        if stat not in df.columns:
            continue
        col = f"{stat}_ema_{window}"
        if col not in df.columns:
            df[col] = (
                df.groupby(group_cols)[stat]
                .transform(lambda s: s.shift(1).ewm(span=span, adjust=False).mean())
            )
    return df


def backup_artifacts(models_dir: Path) -> None:
    """Back up old models before retraining."""
    backup_dir = Path("artifacts/backup_models")
    if models_dir.exists():
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(models_dir, backup_dir)
        logger.info("Backup dos modelos antigos salvo em: %s", backup_dir)


def main(new_dataset_path: str) -> None:
    """Run the full update pipeline: backup → engineer features → retrain."""
    logger.info("=== INICIANDO PIPELINE DE ATUALIZAÇÃO (CONTINUOUS TRAINING) ===")

    # 1. Load config
    config = PipelineConfig.from_yaml("config.yml")
    raw_path = Path(config.data.raw_path)
    models_dir = Path("artifacts/models")

    # 2. Copy new dataset
    new_data_file = Path(new_dataset_path)
    if not new_data_file.exists():
        logger.error("Nova planilha não encontrada em %s", new_data_file)
        return

    logger.info("Substituindo dataset antigo pelo novo...")
    shutil.copy(new_data_file, raw_path)

    # 3. Load and validate
    logger.info("Carregando e validando o novo dataset...")
    data = load_historical_dataset(raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)
    logger.info("Dataset carregado: %d linhas, %d colunas", len(data), len(data.columns))

    # 4. Engineer features (Bug 2 CORRIGIDO — pipeline completo)
    logger.info("Aplicando engenharia de features (rolling, ELO, matchup, H2H)...")
    data_features = _engineer_features(data, config)
    logger.info(
        "Features geradas: %d linhas, %d colunas",
        len(data_features),
        len(data_features.columns),
    )

    # 5. Backup old models
    backup_artifacts(models_dir)

    # 6. Retrain with full algorithm set (Bug 3 CORRIGIDO — inclui Ridge/ElasticNet)
    logger.info("Iniciando treinamento dos 30 modelos (21 boosters + 9 lineares)...")
    weights = _build_recency_weights(data_features["season"])

    # Use config algorithms; fall back to full set if not specified
    algorithms: tuple[str, ...] = (
        tuple(a.lower() for a in config.model.algorithms)
        if config.model.algorithms
        else ("xgboost", "lightgbm", "ridge", "elasticnet")
    )

    models, specs, paths = train_and_save_ensemble(
        features=data_features,
        home_target="home_corners",
        away_target="away_corners",
        output_dir=models_dir,
        algorithms=algorithms,
        ensemble_size=max(1, int(config.model.ensemble_size)),
        sample_weight=weights,
        random_state=config.model.random_state,
    )

    logger.info(
        "✅ Sucesso! %d novos modelos salvos em %s.",
        len(paths),
        models_dir,
    )
    logger.info("=== PIPELINE DE ATUALIZAÇÃO CONCLUÍDO ===")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print(
            "Uso: python update_pipeline.py caminho/para/planilha_baixada_hoje.csv\n"
            "Exemplo: python update_pipeline.py downloads/novo_ds.csv"
        )
