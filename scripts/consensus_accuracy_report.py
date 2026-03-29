"""Generate per-match ensemble consensus report on the temporal test split.

This script trains an ensemble of corner-prediction models with different
random seeds, then evaluates value-vote consensus for each test match.
"""

from __future__ import annotations

import argparse
import math
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Consensus accuracy test report.")
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--n-models", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=42)
    parser.add_argument("--edge-threshold", type=float, default=0.05)
    parser.add_argument("--consensus-threshold", type=float, default=0.70)
    parser.add_argument("--odds", type=float, default=1.90)
    parser.add_argument("--fixed-line", type=float, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/consensus_test_report.txt"),
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)

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
    test_x = test_data[selected].copy()

    seed_values = list(range(args.seed_start, args.seed_start + args.n_models))
    pred_matrix = []
    for seed in seed_values:
        models = train_models(
            train_data[selected + ["home_corners", "away_corners"]].copy(),
            home_target="home_corners",
            away_target="away_corners",
            sample_weight=weights.loc[train_mask],
            random_state=seed,
        )
        pred_home, pred_away = predict_expected_corners(models, test_x)
        pred_matrix.append((pred_home + pred_away).to_numpy(float))

    lambdas = np.vstack(pred_matrix)  # (n_models, n_matches)
    test_df = test_data.reset_index(drop=True)

    report_lines: list[str] = []
    report_lines.append("Relatorio de Consenso do Ensemble")
    report_lines.append(f"Modelos: {args.n_models}")
    report_lines.append(f"Seeds: {seed_values[0]}..{seed_values[-1]}")
    report_lines.append(f"Edge threshold: {args.edge_threshold:.2f}")
    report_lines.append(
        f"Consenso minimo: {args.consensus_threshold * 100:.0f}%"
    )
    report_lines.append(f"Odds usadas: {args.odds:.2f}")
    report_lines.append("")

    total_decisions = 0
    total_eval = 0
    total_wins = 0

    for idx, row in test_df.iterrows():
        game = f"{row['home_team']} vs {row['away_team']}"
        lambda_values = lambdas[:, idx]
        mean_lambda = float(np.mean(lambda_values))
        std_lambda = float(np.std(lambda_values, ddof=1))
        line = (
            float(args.fixed_line)
            if args.fixed_line is not None
            else float(np.floor(mean_lambda * 2.0) / 2.0)
        )

        p_model = 1.0 - poisson.cdf(math.floor(line), lambda_values)
        edge_values = p_model - (1.0 / args.odds)
        votes = int(np.sum(edge_values >= args.edge_threshold))
        consensus = votes / args.n_models
        decision = consensus >= args.consensus_threshold

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
            f"Threshold: {args.consensus_threshold * 100:.0f}% (Minimo exigido)"
        )
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Relatorio salvo em: {args.output}")
    print(f"Partidas no teste: {len(test_df)}")
    print(f"Apostas recomendadas: {total_decisions}")
    if total_eval:
        print(f"Acuracia: {hit_rate:.2f}% ({total_wins}/{total_eval})")
    else:
        print("Acuracia: n/a (nenhuma aposta avaliavel)")


if __name__ == "__main__":
    main()
