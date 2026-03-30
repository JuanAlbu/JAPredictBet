"""Generate per-match ensemble consensus report on the temporal test split.

This script trains an ensemble of corner-prediction models with different
random seeds, then evaluates value-vote consensus for each test match.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import poisson

from japredictbet.config import (
    DataConfig,
    FeatureConfig,
    ModelConfig,
    OddsConfig,
    PipelineConfig,
    ValueConfig,
)
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import EloConfig, add_elo_ratings
from japredictbet.features.matchup import add_matchup_features
from japredictbet.features.rolling import add_result_rolling, add_stat_rolling
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.models.predict import predict_expected_corners
from japredictbet.models.train import _select_feature_columns, train_models
from japredictbet.pipeline.mvp_pipeline import (
    _build_recency_weights,
    _build_temporal_split,
    _ensure_season_column,
)

try:
    import lightgbm  # noqa: F401
    HAS_LIGHTGBM = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_LIGHTGBM = False


def _load_config(config_path: Path) -> PipelineConfig:
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return PipelineConfig(
        data=DataConfig(
            raw_path=Path(raw["data"]["raw_path"]),
            processed_path=Path(raw["data"]["processed_path"]),
            date_column=raw["data"].get("date_column", "date"),
        ),
        features=FeatureConfig(**raw["features"]),
        model=ModelConfig(**raw["model"]),
        odds=OddsConfig(**raw["odds"]),
        value=ValueConfig(**raw["value"]),
    )


def _add_total_corners_features(data: pd.DataFrame, window: int) -> pd.DataFrame:
    df = data.copy()
    suffix = f"_last{window}"
    home_for = f"home_corners_for{suffix}"
    home_against = f"home_corners_against{suffix}"
    away_for = f"away_corners_for{suffix}"
    away_against = f"away_corners_against{suffix}"

    if home_for in df.columns and home_against in df.columns:
        df[f"home_total_corners{suffix}"] = df[home_for] + df[home_against]
    if away_for in df.columns and away_against in df.columns:
        df[f"away_total_corners{suffix}"] = df[away_for] + df[away_against]
    if home_for in df.columns and away_for in df.columns:
        df[f"total_corners_for{suffix}"] = df[home_for] + df[away_for]
    return df


def _add_total_goals_features(data: pd.DataFrame, window: int) -> pd.DataFrame:
    df = data.copy()
    suffix = f"_last{window}"
    home_for = f"home_goals_for{suffix}"
    home_against = f"home_goals_against{suffix}"
    away_for = f"away_goals_for{suffix}"
    away_against = f"away_goals_against{suffix}"

    if home_for in df.columns and home_against in df.columns:
        df[f"home_total_goals{suffix}"] = df[home_for] + df[home_against]
    if away_for in df.columns and away_against in df.columns:
        df[f"away_total_goals{suffix}"] = df[away_for] + df[away_against]
    if home_for in df.columns and away_for in df.columns:
        df[f"total_goals_for{suffix}"] = df[home_for] + df[away_for]
    return df


def _add_rolling_stats(data: pd.DataFrame, window: int) -> pd.DataFrame:
    df = data.copy()
    stats = [
        ("corners", "home_corners", "away_corners"),
        ("goals", "home_goals", "away_goals"),
        ("shots", "home_shots", "away_shots"),
        ("shots_on_target", "home_shots_on_target", "away_shots_on_target"),
        ("fouls", "home_fouls", "away_fouls"),
        ("yellow_cards", "home_yellow_cards", "away_yellow_cards"),
        ("red_cards", "home_red_cards", "away_red_cards"),
    ]
    for stat_name, home_col, away_col in stats:
        if home_col in df.columns and away_col in df.columns:
            df = add_stat_rolling(
                df,
                team_col="home_team",
                for_col=home_col,
                against_col=away_col,
                window=window,
                prefix="home",
                stat_name=stat_name,
                season_col="season",
            )
            df = add_stat_rolling(
                df,
                team_col="away_team",
                for_col=away_col,
                against_col=home_col,
                window=window,
                prefix="away",
                stat_name=stat_name,
                season_col="season",
            )
    if "home_goals" in df.columns and "away_goals" in df.columns:
        df = add_result_rolling(
            df,
            team_col="home_team",
            goals_for_col="home_goals",
            goals_against_col="away_goals",
            window=window,
            prefix="home",
            season_col="season",
        )
        df = add_result_rolling(
            df,
            team_col="away_team",
            goals_for_col="away_goals",
            goals_against_col="home_goals",
            window=window,
            prefix="away",
            season_col="season",
        )
    return df


def _dispersion_label(std_value: float) -> str:
    if std_value <= 0.75:
        return "Baixa Dispersao"
    if std_value <= 1.25:
        return "Media Dispersao"
    return "Alta Dispersao"


def _build_diversified_xgb_params(seed: int) -> dict[str, float | int | str]:
    """Build diversified XGBoost params for ensemble diversity."""

    rng = np.random.default_rng(seed)
    return {
        "n_estimators": 150,
        "learning_rate": float(rng.uniform(0.01, 0.10)),
        "max_depth": int(rng.choice([3, 5, 7, 9])),
        "colsample_bytree": float(rng.uniform(0.4, 0.9)),
        "subsample": float(rng.uniform(0.5, 0.9)),
        "reg_alpha": float(rng.uniform(0.0, 0.5)),
        "reg_lambda": float(rng.uniform(0.0, 1.0)),
        # Keep count-data objective aligned with project assumptions.
        "objective": "count:poisson",
        "n_jobs": 1,
    }


def _build_diversified_lgbm_params(seed: int) -> dict[str, float | int | str]:
    """Build diversified LightGBM params for ensemble diversity."""

    rng = np.random.default_rng(seed + 100_000)
    return {
        "objective": "poisson",
        "n_estimators": 150,
        "learning_rate": float(rng.uniform(0.01, 0.10)),
        "num_leaves": int(rng.choice([15, 31, 63, 127])),
        "colsample_bytree": float(rng.uniform(0.4, 0.9)),
        "subsample": float(rng.uniform(0.5, 0.9)),
        "reg_alpha": float(rng.uniform(0.0, 0.5)),
        "reg_lambda": float(rng.uniform(0.0, 1.0)),
        "n_jobs": 1,
    }


def _build_diversified_rf_params(seed: int) -> dict[str, float | int | str]:
    """Build diversified RandomForest params (limited depth)."""

    rng = np.random.default_rng(seed + 200_000)
    return {
        "criterion": "poisson",
        "n_estimators": int(rng.choice([250, 350, 450])),
        "max_depth": int(rng.choice([3, 4, 5, 6])),
        "min_samples_leaf": int(rng.choice([1, 2, 3, 4])),
        "max_features": float(rng.uniform(0.4, 0.9)),
        "n_jobs": 1,
    }


def _build_diversified_ridge_params(seed: int) -> dict[str, float | int | str]:
    """Build diversified Ridge params with variable alpha."""

    rng = np.random.default_rng(seed + 300_000)
    return {
        "alpha": float(rng.uniform(0.01, 3.0)),
    }


def _build_diversified_elasticnet_params(
    seed: int,
) -> dict[str, float | int | str]:
    """Build diversified ElasticNet params with variable alpha/l1 ratio."""

    rng = np.random.default_rng(seed + 400_000)
    return {
        "alpha": float(rng.uniform(0.01, 1.5)),
        "l1_ratio": float(rng.uniform(0.1, 0.9)),
        "max_iter": 20000,
    }


def _build_model_plan(
    n_models: int,
    seed_start: int,
) -> list[dict[str, object]]:
    """Build a 70/30 algorithm mix plan.

    - 70% boosters (XGBoost + LightGBM when available)
    - 30% linear contrast models (Ridge + ElasticNet)
    """

    n_models = max(1, int(n_models))
    n_boosters = max(1, int(round(n_models * 0.70)))
    n_linear = n_models - n_boosters
    if n_linear == 0 and n_models > 1:
        n_linear = 1
        n_boosters = n_models - 1

    plan: list[dict[str, object]] = []
    seed_values = list(range(seed_start, seed_start + n_models))
    for idx, seed in enumerate(seed_values):
        if idx < n_boosters:
            if HAS_LIGHTGBM and idx % 2 == 1:
                algorithm = "lightgbm"
                params = _build_diversified_lgbm_params(seed)
            else:
                algorithm = "xgboost"
                params = _build_diversified_xgb_params(seed)
        else:
            if idx % 2 == 0:
                algorithm = "ridge"
                params = _build_diversified_ridge_params(seed)
            else:
                algorithm = "elasticnet"
                params = _build_diversified_elasticnet_params(seed)
        plan.append(
            {
                "seed": seed,
                "algorithm": algorithm,
                "params": params,
            }
        )
    return plan


def _select_mirrored_features(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> list[str]:
    """Select train features and enforce an exact mirrored set on test."""

    feature_candidates = _select_feature_columns(
        train_data, exclude=("home_corners", "away_corners")
    )
    train_x = train_data[feature_candidates]
    train_x = train_x.loc[train_x.notna().all(axis=1)]

    corr = train_x.corr(numeric_only=True).abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = [col for col in upper.columns if (upper[col] > 0.90).any()]
    selected_train = [col for col in feature_candidates if col not in to_drop]

    # Apply the same feature filter to test and enforce exact mirror of train selection.
    test_candidates = _select_feature_columns(
        test_data, exclude=("home_corners", "away_corners")
    )
    missing_in_test = [col for col in selected_train if col not in test_candidates]
    if missing_in_test:
        raise ValueError(
            "Test set is missing selected train features: "
            f"{missing_in_test}"
        )

    selected_test = [col for col in test_candidates if col in selected_train]
    if selected_test != selected_train:
        raise ValueError(
            "Test selected features do not mirror train selected features."
        )

    return selected_train


def _build_feature_subset_for_model(
    selected_features: list[str],
    seed: int,
    dropout_rate: float = 0.20,
) -> list[str]:
    """Create a deterministic per-model feature subset (data dropout)."""

    if not selected_features:
        return selected_features

    rate = float(np.clip(dropout_rate, 0.0, 0.95))
    keep_count = max(10, int(round(len(selected_features) * (1.0 - rate))))
    keep_count = min(keep_count, len(selected_features))

    rng = np.random.default_rng(seed + 500_000)
    selected_idx = rng.choice(len(selected_features), size=keep_count, replace=False)
    selected_idx = np.sort(selected_idx)
    return [selected_features[idx] for idx in selected_idx]


def _select_blackout_columns_for_model(
    selected_features: list[str],
    seed: int,
    blackout_count: int = 3,
) -> list[str]:
    """Select deterministic per-seed blackout columns from stats-related features."""

    if not selected_features:
        return []

    stat_tokens = (
        "corners",
        "goals",
        "shots",
        "shots_on_target",
        "fouls",
        "yellow_cards",
        "red_cards",
        "offsides",
        "booking_points",
    )
    candidates = [
        col
        for col in selected_features
        if any(token in col for token in stat_tokens)
    ]
    if not candidates:
        return []

    take = min(max(0, int(blackout_count)), len(candidates))
    if take == 0:
        return []

    rng = np.random.default_rng(seed + 600_000)
    idx = rng.choice(len(candidates), size=take, replace=False)
    idx = np.sort(idx)
    return [candidates[i] for i in idx]


def _to_half_goal_line(value: float) -> float:
    """Convert a numeric expectation to a betting line with .5 only."""

    base = math.floor(float(value))
    return float(base + 0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consensus accuracy test report.")
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--n-models", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=42)
    parser.add_argument("--edge-threshold", type=float, default=0.01)
    parser.add_argument("--consensus-threshold", type=float, default=0.45)
    parser.add_argument("--odds", type=float, default=1.90)
    parser.add_argument("--fixed-line", type=float, default=None)
    parser.add_argument(
        "--feature-dropout-rate",
        type=float,
        default=0.20,
        help="Per-model permanent feature dropout rate (0.0 to 0.95).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. If omitted, creates a timestamped file in log-test/.",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    if args.n_models != 30:
        print(
            f"[info] n_models recebido={args.n_models}; padronizando para 30 "
            "conforme arquitetura hibrida 70/30."
        )
    args.n_models = 30
    # Final calibration requested.
    args.edge_threshold = 0.01
    args.consensus_threshold = 0.45
    args.feature_dropout_rate = 0.20
    blackout_count = 3

    data = load_historical_dataset(cfg.data.raw_path, cfg.data.date_column)
    data = _ensure_season_column(data, cfg.data.date_column)

    data = _add_rolling_stats(data, cfg.features.rolling_window)
    data = _add_rolling_stats(data, 5)
    data = add_matchup_features(data, window=cfg.features.rolling_window)
    data = add_matchup_features(data, window=5)
    data = _add_total_corners_features(data, window=cfg.features.rolling_window)
    data = _add_total_corners_features(data, window=5)
    data = _add_total_goals_features(data, window=cfg.features.rolling_window)
    data = _add_total_goals_features(data, window=5)
    data["home_advantage"] = 1.0

    # Imputacao Zero policy: remove rows without enough historical context.
    # Use only essential rolling-corners columns to avoid dropping rows due to
    # optional stats that are not always present in all seasons/providers.
    history_cols = [
        "home_corners_for_last10",
        "home_corners_against_last10",
        "away_corners_for_last10",
        "away_corners_against_last10",
        "home_corners_for_last5",
        "home_corners_against_last5",
        "away_corners_for_last5",
        "away_corners_against_last5",
    ]
    history_cols = [col for col in history_cols if col in data.columns]
    if history_cols:
        data = data.dropna(subset=history_cols).reset_index(drop=True)

    train_mask, test_mask = _build_temporal_split(data["season"], cfg.model.random_state)
    weights = _build_recency_weights(data["season"])

    data = add_elo_ratings(
        data,
        home_team_col="home_team",
        away_team_col="away_team",
        home_score_col="home_goals",
        away_score_col="away_goals",
        season_col="season",
        config=EloConfig(),
    )
    data = add_team_target_encoding(
        data,
        team_col="home_team",
        target_col="home_corners",
        train_mask=train_mask,
        feature_name="home_team_team_enc",
    )
    data = add_team_target_encoding(
        data,
        team_col="away_team",
        target_col="away_corners",
        train_mask=train_mask,
        feature_name="away_team_team_enc",
    )

    train_data = data.loc[train_mask].copy()
    test_data = data.loc[test_mask].copy()
    selected = _select_mirrored_features(train_data=train_data, test_data=test_data)

    model_plan = _build_model_plan(args.n_models, args.seed_start)
    seed_values = [int(item["seed"]) for item in model_plan]
    pred_matrix = []
    model_param_rows: list[dict[str, float | int | str]] = []
    for item in model_plan:
        seed = int(item["seed"])
        algorithm = str(item["algorithm"])
        varied_params = dict(item["params"])
        blackout_cols = _select_blackout_columns_for_model(
            selected_features=selected,
            seed=seed,
            blackout_count=blackout_count,
        )
        selected_without_blackout = [
            col for col in selected if col not in set(blackout_cols)
        ]
        model_features = _build_feature_subset_for_model(
            selected_features=selected_without_blackout,
            seed=seed,
            dropout_rate=args.feature_dropout_rate,
        )
        if len(model_features) < 10:
            # Safety fallback to preserve trainability.
            model_features = selected_without_blackout[:10]

        train_block = train_data[model_features + ["home_corners", "away_corners"]].copy()
        test_block = test_data[model_features].copy()
        models = train_models(
            train_block,
            home_target="home_corners",
            away_target="away_corners",
            sample_weight=weights.loc[train_mask],
            random_state=seed,
            algorithm=algorithm,
            model_params=varied_params,
        )
        pred_home, pred_away = predict_expected_corners(models, test_block)
        pred_matrix.append((pred_home + pred_away).to_numpy(float))
        row: dict[str, float | int | str] = {
            "seed": seed,
            "algorithm": algorithm,
            "features_used": len(model_features),
            "features_dropped": len(selected) - len(model_features),
            "blackout_count": len(blackout_cols),
            "blackout_columns": ",".join(blackout_cols),
        }
        for key in (
            "learning_rate",
            "alpha",
            "l1_ratio",
            "max_depth",
            "colsample_bytree",
            "subsample",
            "reg_alpha",
            "reg_lambda",
            "max_features",
            "n_estimators",
        ):
            if key in varied_params:
                row[key] = (
                    float(varied_params[key])
                    if isinstance(varied_params[key], float)
                    else int(varied_params[key])
                    if isinstance(varied_params[key], int)
                    else str(varied_params[key])
                )
        model_param_rows.append(row)

    lambdas = np.vstack(pred_matrix)  # (n_models, n_matches)
    test_df = test_data.reset_index(drop=True)

    report_lines: list[str] = []
    session_dt = datetime.now()
    session_ts = session_dt.strftime("%Y-%m-%d %H:%M:%S")
    report_lines.append("=" * 72)
    report_lines.append(f"Sessao de Teste: {session_ts}")
    report_lines.append("=" * 72)
    report_lines.append("Relatorio de Consenso do Ensemble")
    report_lines.append(f"Modelos: {args.n_models}")
    report_lines.append(f"Seeds: {seed_values[0]}..{seed_values[-1]}")
    report_lines.append(f"Edge threshold: {args.edge_threshold:.2f}")
    report_lines.append(
        f"Consenso minimo: {args.consensus_threshold * 100:.0f}%"
    )
    report_lines.append(f"Odds usadas: {args.odds:.2f}")
    report_lines.append(
        "Diversificacao: mix 70/30 (boosters/ridge+elasticnet), "
        "learning_rate [0.01-0.10], colsample [0.4-0.9], subsample [0.5-0.9]"
    )
    report_lines.append(
        "Threshold Base: 45% | Margem Curta (<0.5): 50% | Edge: 0.01 | Dropout: 20% | Blackout: 3"
    )
    report_lines.append("Feature blackout por modelo: 3 colunas de estatisticas ignoradas por seed")
    report_lines.append(
        f"Data dropout por modelo: {args.feature_dropout_rate * 100:.0f}% "
        "(subconjunto fixo por seed)"
    )
    report_lines.append(
        "Regra de margem: se |media_lambda - linha| < 0.5, consenso minimo sobe para 50%"
    )
    report_lines.append("")

    total_decisions = 0
    total_eval = 0
    total_wins = 0

    for idx, row in test_df.iterrows():
        game = f"{row['home_team']} vs {row['away_team']}"
        lambda_values = lambdas[:, idx]
        mean_lambda = float(np.mean(lambda_values))
        std_lambda = float(np.std(lambda_values, ddof=1))
        if args.fixed_line is not None:
            line = _to_half_goal_line(float(args.fixed_line))
        else:
            line = _to_half_goal_line(mean_lambda)

        p_model = 1.0 - poisson.cdf(math.floor(line), lambda_values)
        edge_values = p_model - (1.0 / args.odds)
        votes = int(np.sum(edge_values >= args.edge_threshold))
        consensus = votes / args.n_models
        margin = abs(mean_lambda - line)
        effective_consensus_threshold = max(
            float(args.consensus_threshold),
            0.50 if margin < 0.5 else float(args.consensus_threshold),
        )
        decision = consensus >= effective_consensus_threshold

        low_count = int(np.sum(lambda_values < line))
        mid1_count = int(np.sum((lambda_values >= line) & (lambda_values < line + 1.0)))
        mid2_count = int(
            np.sum((lambda_values >= line + 1.0) & (lambda_values < line + 2.0))
        )
        high_count = int(np.sum(lambda_values >= line + 2.0))

        actual_total = float(row["home_corners"] + row["away_corners"])
        result = "Push"
        if actual_total > line:
            result = "Win"
        elif actual_total < line:
            result = "Lose"

        if decision:
            total_decisions += 1
            if result != "Push":
                total_eval += 1
                if result == "Win":
                    total_wins += 1

        report_lines.append(
            f"Jogo: {game} | Linha: Over {line:.1f} @ {args.odds:.3f}"
        )
        report_lines.append(
            f"1. Estatisticas do Ensemble ({args.n_models} Modelos)"
        )
        report_lines.append(
            f"Media lambda: {mean_lambda:.2f} | Desvio Padrao (sigma): {std_lambda:.2f} ({_dispersion_label(std_lambda)})"
        )
        report_lines.append("Distribuicao por Range (lambda):")
        report_lines.append(f"< {line:.1f}: {low_count} modelos")
        report_lines.append(f"{line:.1f} - {line + 1.0:.1f}: {mid1_count} modelos")
        report_lines.append(f"{line + 1.0:.1f} - {line + 2.0:.1f}: {mid2_count} modelos")
        report_lines.append(f">= {line + 2.0:.1f}: {high_count} modelos")
        report_lines.append(
            f"2. Votacao de Valor (Edge >= {args.edge_threshold:.2f})"
        )
        report_lines.append(
            f"Votos: {votes} / {args.n_models} ({consensus * 100:.0f}% de Consenso)"
        )
        report_lines.append(
            f"Threshold: {effective_consensus_threshold * 100:.0f}% (Minimo exigido)"
        )
        report_lines.append(f"Margem media-linha: {margin:.2f}")
        report_lines.append(
            f"Decisao: {'APOSTAR' if decision else 'NAO APOSTAR'} | Resultado real: {result} (total={actual_total:.0f})"
        )
        report_lines.append("")

    report_lines.append("Resumo Final")
    report_lines.append(f"Partidas no teste: {len(test_df)}")
    report_lines.append(f"Apostas recomendadas (consenso): {total_decisions}")
    report_lines.append(f"Apostas avaliaveis (sem push): {total_eval}")
    report_lines.append(f"Vitorias: {total_wins}")
    hit_rate = (total_wins / total_eval * 100.0) if total_eval else float("nan")
    report_lines.append(
        f"Acuracia (hit rate das apostas aceitas): {hit_rate:.2f}%"
        if total_eval
        else "Acuracia (hit rate das apostas aceitas): n/a"
    )
    sigma_per_match = np.std(lambdas, axis=0, ddof=1)
    report_lines.append("")
    report_lines.append("Monitoramento de Dispersao")
    report_lines.append(f"Sigma medio por jogo: {float(np.mean(sigma_per_match)):.2f}")
    report_lines.append(f"Sigma mediano por jogo: {float(np.median(sigma_per_match)):.2f}")
    report_lines.append(f"Sigma minimo/maximo por jogo: {float(np.min(sigma_per_match)):.2f} / {float(np.max(sigma_per_match)):.2f}")
    report_lines.append(f"Predicoes extremas (lambda_total < 7.0): {int(np.sum(lambdas < 7.0))}")
    report_lines.append(f"Predicoes extremas (lambda_total >= 13.0): {int(np.sum(lambdas >= 13.0))}")
    report_lines.append(
        f"Jogos com pelo menos 1 modelo >= 13.0: {int(np.sum(np.any(lambdas >= 13.0, axis=0)))}"
    )
    report_lines.append(
        f"Jogos com pelo menos 1 modelo < 7.0: {int(np.sum(np.any(lambdas < 7.0, axis=0)))}"
    )
    report_lines.append("")
    report_lines.append("Resumo dos Parametros por Modelo")
    for row in model_param_rows:
        base = f"seed={int(row['seed'])} | algo={row['algorithm']}"
        extras = []
        for key in (
            "features_used",
            "features_dropped",
            "blackout_count",
            "blackout_columns",
            "n_estimators",
            "learning_rate",
            "alpha",
            "l1_ratio",
            "max_depth",
            "colsample_bytree",
            "subsample",
            "reg_alpha",
            "reg_lambda",
            "max_features",
        ):
            if key not in row:
                continue
            value = row[key]
            if isinstance(value, float):
                extras.append(f"{key}={value:.2f}")
            else:
                extras.append(f"{key}={value}")
        report_lines.append(base + " | " + " | ".join(extras))

    report_content = "\n".join(report_lines).rstrip() + "\n"
    if args.output is None:
        ts_for_file = session_dt.strftime("%Y%m%d_%H%M%S")
        output_path = Path("log-test") / f"consensus_test_report_{ts_for_file}.txt"
    else:
        output_path = args.output

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding="utf-8")
    print(f"Relatorio salvo em: {output_path}")
    print(f"Partidas no teste: {len(test_df)}")
    print(f"Apostas recomendadas: {total_decisions}")
    if total_eval:
        print(f"Acuracia: {hit_rate:.2f}% ({total_wins}/{total_eval})")
    else:
        print("Acuracia: n/a (nenhuma aposta avaliavel)")


if __name__ == "__main__":
    main()
