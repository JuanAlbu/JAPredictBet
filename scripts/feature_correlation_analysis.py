"""Feature Correlation Analysis — Post P1.B2 (STD + EMA).

Generates correlation report for the full feature set including
rolling mean, rolling STD, rolling EMA, matchup, ELO, and target encoding.

Usage:
    python scripts/feature_correlation_analysis.py --config config.yml
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.features.elo import add_elo_ratings, EloConfig
from japredictbet.features.matchup import add_matchup_features
from japredictbet.features.rolling import (
    add_stat_rolling,
    add_result_rolling,
    add_rolling_std,
    add_rolling_ema,
)
from japredictbet.features.team_identity import add_team_target_encoding
from japredictbet.pipeline.mvp_pipeline import (
    _add_rolling_stats,
    _add_rolling_std_features,
    _add_rolling_ema_features,
    _add_total_corners_features,
    _add_total_goals_features,
    _ensure_season_column,
    _build_temporal_split,
)


def _load_config(config_path: str) -> PipelineConfig:
    return PipelineConfig.from_yaml(config_path)


def build_feature_dataframe(config) -> pd.DataFrame:
    """Replicate the pipeline feature engineering to get the full feature set."""
    data = load_historical_dataset(config.data.raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)

    for window in config.features.rolling_windows:
        data = _add_rolling_stats(data, window, season_col="season")
        if config.features.rolling_use_std:
            data = _add_rolling_std_features(data, window, season_col="season")
        if config.features.rolling_use_ema:
            data = _add_rolling_ema_features(data, window, season_col="season")
        data = add_matchup_features(data, window=window)
        data = _add_total_corners_features(data, window=window)
        data = _add_total_goals_features(data, window=window)

    data["home_advantage"] = 1.0

    encoding_train_mask, _ = _build_temporal_split(
        data["season"], config.model.random_state
    )

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
        data, team_col="home_team", target_col="home_corners",
        train_mask=encoding_train_mask, feature_name="home_team_team_enc",
    )
    data = add_team_target_encoding(
        data, team_col="away_team", target_col="away_corners",
        train_mask=encoding_train_mask, feature_name="away_team_team_enc",
    )
    return data


def select_numeric_features(data: pd.DataFrame) -> pd.DataFrame:
    """Select only engineered numeric feature columns.
    
    Uses a whitelist approach: only keeps columns that match known
    engineered feature patterns (rolling, matchup, ELO, encoding, etc.).
    """
    import re
    numeric = data.select_dtypes(include=[np.number])

    # Whitelist patterns for engineered features
    feature_patterns = re.compile(
        r'('
        r'_for_last\d+|_against_last\d+|'
        r'_for_std_last\d+|_against_std_last\d+|'
        r'_for_ema_last\d+|_against_ema_last\d+|'
        r'_wins_last\d+|_draws_last\d+|_losses_last\d+|'
        r'_points_last\d+|_win_rate_last\d+|_points_per_game_last\d+|'
        r'attack_vs_|pressure_index|_diff$|'
        r'total_corners_|total_goals_|'
        r'_elo_|elo_rating|'
        r'_team_enc$|'
        r'^home_advantage$'
        r')'
    )
    feature_cols = [c for c in numeric.columns if feature_patterns.search(c)]
    return numeric[feature_cols]


def compute_correlation_matrix(features: pd.DataFrame) -> pd.DataFrame:
    """Compute Pearson correlation matrix on valid rows.
    
    Drops columns that are all-NaN, then uses pairwise complete obs.
    """
    clean = features.dropna(axis=1, how="all")
    return clean.corr(method="pearson")


def get_top_correlations(corr_matrix: pd.DataFrame, n: int = 50) -> list[tuple]:
    """Get top N absolute correlations (excluding self-correlation)."""
    pairs = []
    cols = corr_matrix.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append((cols[i], cols[j], corr_matrix.iloc[i, j]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs[:n]


def get_high_correlation_pairs(corr_matrix: pd.DataFrame, threshold: float = 0.85) -> list[tuple]:
    """Get all feature pairs with |correlation| > threshold."""
    pairs = []
    cols = corr_matrix.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            val = corr_matrix.iloc[i, j]
            if abs(val) > threshold:
                pairs.append((cols[i], cols[j], val))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs


def categorize_features(feature_cols: list[str]) -> dict:
    """Categorize features by type for analysis."""
    categories = {
        "rolling_mean": [],
        "rolling_std": [],
        "rolling_ema": [],
        "result_based": [],
        "matchup": [],
        "totals": [],
        "elo": [],
        "encoding": [],
        "other": [],
    }
    for col in feature_cols:
        if "_std_" in col:
            categories["rolling_std"].append(col)
        elif "_ema_" in col:
            categories["rolling_ema"].append(col)
        elif any(x in col for x in ("wins_", "draws_", "losses_", "points_", "win_rate_")):
            categories["result_based"].append(col)
        elif any(x in col for x in ("attack_vs", "pressure_index", "_diff")):
            categories["matchup"].append(col)
        elif col.startswith("total_") or "total_" in col:
            categories["totals"].append(col)
        elif "elo" in col:
            categories["elo"].append(col)
        elif "_enc" in col:
            categories["encoding"].append(col)
        elif any(x in col for x in ("_for_last", "_against_last")):
            categories["rolling_mean"].append(col)
        else:
            categories["other"].append(col)
    return categories


def analyze_mean_std_ema_correlation(corr_matrix: pd.DataFrame, features: list[str]) -> list[dict]:
    """Specifically analyze correlation between mean/std/ema variants of same stat."""
    results = []
    # Find base stats (rolling mean features)
    mean_features = [f for f in features if "_for_last" in f or "_against_last" in f]
    mean_features = [f for f in mean_features if "_std_" not in f and "_ema_" not in f]

    for mf in mean_features:
        # Derive corresponding std and ema feature names
        parts = mf.split("_for_last") if "_for_last" in mf else mf.split("_against_last")
        if len(parts) != 2:
            continue
        prefix = parts[0]
        direction = "for" if "_for_last" in mf else "against"
        window = parts[1]

        std_name = f"{prefix}_{direction}_std_last{window}"
        ema_name = f"{prefix}_{direction}_ema_last{window}"

        entry = {"base_feature": mf}
        if std_name in corr_matrix.columns and mf in corr_matrix.columns:
            entry["corr_mean_vs_std"] = round(corr_matrix.loc[mf, std_name], 4)
        if ema_name in corr_matrix.columns and mf in corr_matrix.columns:
            entry["corr_mean_vs_ema"] = round(corr_matrix.loc[mf, ema_name], 4)
        if std_name in corr_matrix.columns and ema_name in corr_matrix.columns:
            entry["corr_std_vs_ema"] = round(corr_matrix.loc[std_name, ema_name], 4)

        if len(entry) > 1:
            results.append(entry)
    return results


def generate_report(
    data: pd.DataFrame,
    features_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    top_pairs: list[tuple],
    high_pairs: list[tuple],
    categories: dict,
    cross_analysis: list[dict],
) -> str:
    """Generate the markdown report."""
    timestamp = datetime.now().strftime("%d-%b-%Y %H:%M")
    valid_rows = features_df.dropna().shape[0]

    import re
    windows = set()
    for c in features_df.columns:
        m = re.search(r'last(\d+)$', c)
        if m:
            windows.add(int(m.group(1)))
    windows_str = str(sorted(windows, reverse=True)) if windows else "N/A"

    lines = [
        "# Entradas do Modelo e Analise de Correlacao (Atualizado)",
        "",
        f"**Data da Analise:** {timestamp}",
        f"**Versao:** Post-P1.B2 (inclui Rolling Mean + STD + EMA)",
        "",
        "## Contexto",
        f"- Pipeline de features com STD e EMA habilitados",
        f"- Rolling windows: {windows_str}",
        f"- Total de features numericas: **{len(features_df.columns)}**",
        f"- Linhas totais: {len(data)} | Linhas validas para correlacao: {valid_rows}",
        "",
    ]

    # Feature categories
    lines.append("## Distribuicao de Features por Tipo")
    lines.append("")
    lines.append("| Tipo | Quantidade | Exemplos |")
    lines.append("|------|:---:|---------|")
    for cat_name, cat_features in categories.items():
        if cat_features:
            examples = ", ".join(cat_features[:2])
            lines.append(f"| {cat_name} | {len(cat_features)} | {examples} |")
    lines.append(f"| **TOTAL** | **{len(features_df.columns)}** | |")
    lines.append("")

    # All features list
    lines.append("## Lista Completa de Features")
    lines.append("")
    for col in sorted(features_df.columns):
        lines.append(f"- {col}")
    lines.append("")

    # Top correlations
    lines.append(f"## Top 50 Correlacoes (Pearson)")
    lines.append("")
    lines.append("| # | Feature A | Feature B | Correlacao |")
    lines.append("|:-:|-----------|-----------|:---:|")
    for i, (a, b, val) in enumerate(top_pairs, 1):
        marker = " **⚠️**" if abs(val) > 0.85 else ""
        lines.append(f"| {i} | {a} | {b} | {val:.4f}{marker} |")
    lines.append("")

    # High correlation pairs (danger zone)
    lines.append(f"## Pares com Correlacao > 0.85 (Risco de Multicolinearidade)")
    lines.append("")
    if high_pairs:
        lines.append(f"**Total: {len(high_pairs)} pares**")
        lines.append("")
        lines.append("| Feature A | Feature B | Correlacao | Recomendacao |")
        lines.append("|-----------|-----------|:---:|-------------|")
        for a, b, val in high_pairs:
            # Suggest which to drop
            if "_std_" in a or "_ema_" in a:
                rec = f"Considerar remover `{a}` (derivada)"
            elif "_std_" in b or "_ema_" in b:
                rec = f"Considerar remover `{b}` (derivada)"
            elif "total_" in a:
                rec = f"Considerar remover `{a}` (agregada)"
            elif "total_" in b:
                rec = f"Considerar remover `{b}` (agregada)"
            else:
                rec = "Avaliar qual carregar mais informacao"
            lines.append(f"| {a} | {b} | {val:.4f} | {rec} |")
        lines.append("")
    else:
        lines.append("Nenhum par encontrado acima do threshold. ✅")
        lines.append("")

    # Cross-analysis: Mean vs STD vs EMA
    lines.append("## Analise Cruzada: Mean vs STD vs EMA (Mesma Estatistica)")
    lines.append("")
    lines.append("Esta secao mostra a correlacao entre as 3 variantes (media, desvio padrao, EMA)")
    lines.append("da mesma estatistica base. Correlacoes altas indicam redundancia.")
    lines.append("")
    if cross_analysis:
        lines.append("| Feature Base | Mean↔STD | Mean↔EMA | STD↔EMA |")
        lines.append("|-------------|:---:|:---:|:---:|")
        for entry in cross_analysis:
            base = entry["base_feature"]
            ms = entry.get("corr_mean_vs_std", "—")
            me = entry.get("corr_mean_vs_ema", "—")
            se = entry.get("corr_std_vs_ema", "—")
            ms_str = f"{ms}" if isinstance(ms, str) else f"{ms:.4f}"
            me_str = f"{me}" if isinstance(me, str) else f"{me:.4f}"
            se_str = f"{se}" if isinstance(se, str) else f"{se:.4f}"
            lines.append(f"| {base} | {ms_str} | {me_str} | {se_str} |")
        lines.append("")
    else:
        lines.append("Nenhuma analise cruzada disponivel.")
        lines.append("")

    # Summary statistics
    all_corrs = []
    cols = corr_matrix.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            all_corrs.append(abs(corr_matrix.iloc[i, j]))
    all_corrs = np.array(all_corrs)

    lines.append("## Estatisticas Globais de Correlacao")
    lines.append("")
    lines.append(f"- Total de pares analisados: {len(all_corrs)}")
    lines.append(f"- Correlacao absoluta media: {all_corrs.mean():.4f}")
    lines.append(f"- Correlacao absoluta mediana: {np.median(all_corrs):.4f}")
    lines.append(f"- Pares com |r| > 0.90: {(all_corrs > 0.90).sum()}")
    lines.append(f"- Pares com |r| > 0.85: {(all_corrs > 0.85).sum()}")
    lines.append(f"- Pares com |r| > 0.70: {(all_corrs > 0.70).sum()}")
    lines.append(f"- Pares com |r| > 0.50: {(all_corrs > 0.50).sum()}")
    lines.append("")

    # Recommendations
    lines.append("## Recomendacoes")
    lines.append("")
    n_high = len(high_pairs)
    if n_high == 0:
        lines.append("✅ Nenhum par com correlacao critica (> 0.85). Feature set saudavel.")
    else:
        lines.append(f"⚠️ **{n_high} pares com correlacao > 0.85 detectados.**")
        lines.append("")

        # Count how many involve std/ema
        std_ema_pairs = [p for p in high_pairs if "_std_" in p[0] or "_std_" in p[1] or "_ema_" in p[0] or "_ema_" in p[1]]
        total_pairs = [p for p in high_pairs if "total_" in p[0] or "total_" in p[1]]

        lines.append("### Acoes Sugeridas")
        lines.append("")
        if std_ema_pairs:
            lines.append(f"1. **STD/EMA redundantes ({len(std_ema_pairs)} pares):** Se Mean↔EMA > 0.95, a EMA nao adiciona informacao nova. Considerar:")
            lines.append("   - Desativar EMA (`rolling_use_ema: false`) e medir impacto no accuracy")
            lines.append("   - Ou manter apenas EMA e remover rolling mean (EMA subsume a media)")
            lines.append("")
        if total_pairs:
            lines.append(f"2. **Features de totais redundantes ({len(total_pairs)} pares):** `total_corners_for` = `home_corners_for` + `away_corners_for`. Sao linearmente dependentes.")
            lines.append("   - Remover features de totais (informacao ja contida nos componentes)")
            lines.append("")
        lines.append("3. **Para modelos lineares (Ridge/ElasticNet — 30% do ensemble):**")
        lines.append("   - Multicolinearidade causa instabilidade nos coeficientes")
        lines.append("   - Considerar VIF (Variance Inflation Factor) para selecao mais rigorosa")
        lines.append("")
        lines.append("4. **Para modelos tree-based (XGBoost/LightGBM/RF — 70% do ensemble):**")
        lines.append("   - Multicolinearidade NAO afeta accuracy")
        lines.append("   - Mas dilui a importancia das features (interpretabilidade reduzida)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Feature correlation analysis")
    parser.add_argument("--config", default="config.yml", help="Config file path")
    parser.add_argument("--threshold", type=float, default=0.85, help="High correlation threshold")
    parser.add_argument("--top-n", type=int, default=50, help="Number of top correlations to show")
    args = parser.parse_args()

    print("=" * 60)
    print("FEATURE CORRELATION ANALYSIS — Post P1.B2")
    print("=" * 60)

    print("\n[1/5] Loading config...")
    config = _load_config(args.config)

    print("[2/5] Building features (replicating pipeline)...")
    data = build_feature_dataframe(config)
    features_df = select_numeric_features(data)
    print(f"      Total features: {len(features_df.columns)}")
    print(f"      Total rows: {len(data)}")

    print("[3/5] Computing correlation matrix...")
    corr_matrix = compute_correlation_matrix(features_df)
    valid_rows = features_df.dropna(axis=1, how="all").dropna().shape[0]
    print(f"      Valid rows (all features non-null): {valid_rows}")
    # Also show how many rows have at least 80% of features
    threshold_80 = int(len(features_df.columns) * 0.8)
    rows_80pct = (features_df.notna().sum(axis=1) >= threshold_80).sum()
    print(f"      Rows with >=80% features available: {rows_80pct}")

    print("[4/5] Analyzing correlations...")
    top_pairs = get_top_correlations(corr_matrix, n=args.top_n)
    high_pairs = get_high_correlation_pairs(corr_matrix, threshold=args.threshold)
    categories = categorize_features(list(features_df.columns))
    cross_analysis = analyze_mean_std_ema_correlation(corr_matrix, list(features_df.columns))

    print(f"      Top correlation: {top_pairs[0][0]} vs {top_pairs[0][1]} = {top_pairs[0][2]:.4f}")
    print(f"      Pairs with |r| > {args.threshold}: {len(high_pairs)}")

    print("[5/5] Generating report...")
    report = generate_report(data, features_df, corr_matrix, top_pairs, high_pairs, categories, cross_analysis)

    output_path = Path("docs/model_inputs_correlation_report.md")
    output_path.write_text(report, encoding="utf-8")
    print(f"\n✅ Report saved: {output_path}")

    # Also print summary to console
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Features: {len(features_df.columns)}")
    for cat, feats in categories.items():
        if feats:
            print(f"  {cat}: {len(feats)}")
    print(f"\nHigh correlation pairs (>{args.threshold}): {len(high_pairs)}")
    if high_pairs:
        print("\nTop 10 critical pairs:")
        for a, b, v in high_pairs[:10]:
            print(f"  {v:+.4f}  {a} <-> {b}")


if __name__ == "__main__":
    main()
