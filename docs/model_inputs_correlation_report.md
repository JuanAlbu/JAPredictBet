# Entradas do Modelo e Analise de Correlacao (Atualizado)

**Data da Analise:** 31-Mar-2026 23:02
**Versao:** Post-P1.B2 (inclui Rolling Mean + STD + EMA)

## Contexto
- Pipeline de features com STD e EMA habilitados
- Rolling windows: [10, 5]
- Total de features numericas: **159**
- Linhas totais: 4109 | Linhas validas para correlacao: 3413

## Distribuicao de Features por Tipo

| Tipo | Quantidade | Exemplos |
|------|:---:|---------|
| rolling_mean | 56 | home_corners_for_last10, home_corners_against_last10 |
| rolling_std | 24 | home_corners_for_std_last10, home_corners_against_std_last10 |
| rolling_ema | 24 | home_corners_for_ema_last10, home_corners_against_ema_last10 |
| result_based | 24 | home_wins_last10, home_draws_last10 |
| matchup | 16 | home_attack_vs_away_defense_corners_last10, away_attack_vs_home_defense_corners_last10 |
| totals | 12 | home_total_corners_last10, away_total_corners_last10 |
| encoding | 2 | home_team_team_enc, away_team_team_enc |
| other | 1 | home_advantage |
| **TOTAL** | **159** | |

## Lista Completa de Features

- away_attack_vs_home_defense_corners_last10
- away_attack_vs_home_defense_corners_last5
- away_corners_against_ema_last10
- away_corners_against_ema_last5
- away_corners_against_last10
- away_corners_against_last5
- away_corners_against_std_last10
- away_corners_against_std_last5
- away_corners_for_ema_last10
- away_corners_for_ema_last5
- away_corners_for_last10
- away_corners_for_last5
- away_corners_for_std_last10
- away_corners_for_std_last5
- away_draws_last10
- away_draws_last5
- away_fouls_against_last10
- away_fouls_against_last5
- away_fouls_for_last10
- away_fouls_for_last5
- away_goals_against_ema_last10
- away_goals_against_ema_last5
- away_goals_against_last10
- away_goals_against_last5
- away_goals_against_std_last10
- away_goals_against_std_last5
- away_goals_for_ema_last10
- away_goals_for_ema_last5
- away_goals_for_last10
- away_goals_for_last5
- away_goals_for_std_last10
- away_goals_for_std_last5
- away_losses_last10
- away_losses_last5
- away_points_last10
- away_points_last5
- away_points_per_game_last10
- away_points_per_game_last5
- away_red_cards_against_last10
- away_red_cards_against_last5
- away_red_cards_for_last10
- away_red_cards_for_last5
- away_shots_against_ema_last10
- away_shots_against_ema_last5
- away_shots_against_last10
- away_shots_against_last5
- away_shots_against_std_last10
- away_shots_against_std_last5
- away_shots_for_ema_last10
- away_shots_for_ema_last5
- away_shots_for_last10
- away_shots_for_last5
- away_shots_for_std_last10
- away_shots_for_std_last5
- away_shots_on_target_against_last10
- away_shots_on_target_against_last5
- away_shots_on_target_for_last10
- away_shots_on_target_for_last5
- away_team_team_enc
- away_total_corners_last10
- away_total_corners_last5
- away_total_goals_last10
- away_total_goals_last5
- away_win_rate_last10
- away_win_rate_last5
- away_wins_last10
- away_wins_last5
- away_yellow_cards_against_last10
- away_yellow_cards_against_last5
- away_yellow_cards_for_last10
- away_yellow_cards_for_last5
- cards_last10_diff
- cards_last5_diff
- corners_last10_diff
- corners_last5_diff
- corners_pressure_index_last10
- corners_pressure_index_last5
- fouls_last10_diff
- fouls_last5_diff
- home_advantage
- home_attack_vs_away_defense_corners_last10
- home_attack_vs_away_defense_corners_last5
- home_corners_against_ema_last10
- home_corners_against_ema_last5
- home_corners_against_last10
- home_corners_against_last5
- home_corners_against_std_last10
- home_corners_against_std_last5
- home_corners_for_ema_last10
- home_corners_for_ema_last5
- home_corners_for_last10
- home_corners_for_last5
- home_corners_for_std_last10
- home_corners_for_std_last5
- home_draws_last10
- home_draws_last5
- home_fouls_against_last10
- home_fouls_against_last5
- home_fouls_for_last10
- home_fouls_for_last5
- home_goals_against_ema_last10
- home_goals_against_ema_last5
- home_goals_against_last10
- home_goals_against_last5
- home_goals_against_std_last10
- home_goals_against_std_last5
- home_goals_for_ema_last10
- home_goals_for_ema_last5
- home_goals_for_last10
- home_goals_for_last5
- home_goals_for_std_last10
- home_goals_for_std_last5
- home_losses_last10
- home_losses_last5
- home_points_last10
- home_points_last5
- home_points_per_game_last10
- home_points_per_game_last5
- home_red_cards_against_last10
- home_red_cards_against_last5
- home_red_cards_for_last10
- home_red_cards_for_last5
- home_shots_against_ema_last10
- home_shots_against_ema_last5
- home_shots_against_last10
- home_shots_against_last5
- home_shots_against_std_last10
- home_shots_against_std_last5
- home_shots_for_ema_last10
- home_shots_for_ema_last5
- home_shots_for_last10
- home_shots_for_last5
- home_shots_for_std_last10
- home_shots_for_std_last5
- home_shots_on_target_against_last10
- home_shots_on_target_against_last5
- home_shots_on_target_for_last10
- home_shots_on_target_for_last5
- home_team_team_enc
- home_total_corners_last10
- home_total_corners_last5
- home_total_goals_last10
- home_total_goals_last5
- home_win_rate_last10
- home_win_rate_last5
- home_wins_last10
- home_wins_last5
- home_yellow_cards_against_last10
- home_yellow_cards_against_last5
- home_yellow_cards_for_last10
- home_yellow_cards_for_last5
- shots_last10_diff
- shots_last5_diff
- shots_on_target_last10_diff
- shots_on_target_last5_diff
- total_corners_for_last10
- total_corners_for_last5
- total_goals_for_last10
- total_goals_for_last5

## Top 50 Correlacoes (Pearson)

| # | Feature A | Feature B | Correlacao |
|:-:|-----------|-----------|:---:|
| 1 | home_corners_for_last10 | home_attack_vs_away_defense_corners_last10 | 0.8481 |
| 2 | home_corners_against_last5 | away_attack_vs_home_defense_corners_last5 | 0.7901 |
| 3 | away_corners_for_last5 | away_attack_vs_home_defense_corners_last5 | 0.7839 |
| 4 | home_corners_for_last10 | corners_last10_diff | 0.7684 |
| 5 | home_corners_for_last10 | total_corners_for_last10 | 0.7627 |
| 6 | home_shots_on_target_for_last10 | shots_on_target_last10_diff | 0.7350 |
| 7 | home_shots_on_target_against_last10 | home_shots_on_target_against_last5 | 0.7157 |
| 8 | home_corners_for_last10 | home_corners_for_last5 | 0.7130 |
| 9 | away_shots_on_target_for_last10 | away_shots_on_target_for_last5 | 0.7121 |
| 10 | away_shots_for_last10 | away_shots_for_last5 | 0.7100 |
| 11 | home_corners_for_last10 | home_total_corners_last10 | 0.7021 |
| 12 | away_goals_for_last5 | total_goals_for_last5 | 0.6973 |
| 13 | away_goals_for_std_last10 | away_goals_for_std_last5 | 0.6869 |
| 14 | away_shots_for_last10 | shots_last10_diff | -0.6819 |
| 15 | away_shots_on_target_for_last10 | shots_on_target_last10_diff | -0.6756 |
| 16 | away_goals_for_last5 | away_points_per_game_last5 | 0.6636 |
| 17 | away_goals_for_last5 | away_points_last5 | 0.6636 |
| 18 | away_corners_for_last5 | corners_last5_diff | -0.6628 |
| 19 | away_goals_against_std_last10 | away_goals_against_std_last5 | 0.6561 |
| 20 | home_shots_for_std_last10 | home_shots_for_std_last5 | 0.6560 |
| 21 | away_corners_for_last5 | total_corners_for_last5 | 0.6536 |
| 22 | away_goals_for_last5 | away_win_rate_last5 | 0.6508 |
| 23 | away_goals_for_last5 | away_wins_last5 | 0.6508 |
| 24 | away_goals_for_last5 | away_total_goals_last5 | 0.6443 |
| 25 | home_corners_for_last10 | home_attack_vs_away_defense_corners_last5 | 0.6400 |
| 26 | away_goals_against_last5 | away_losses_last5 | 0.6333 |
| 27 | away_goals_against_last5 | away_shots_on_target_against_last5 | 0.5974 |
| 28 | away_goals_against_last5 | away_points_last5 | -0.5923 |
| 29 | away_goals_against_last5 | away_points_per_game_last5 | -0.5923 |
| 30 | home_corners_for_last10 | home_shots_for_last10 | 0.5851 |
| 31 | away_goals_for_last5 | away_goals_for_std_last5 | 0.5771 |
| 32 | home_corners_against_last10 | home_shots_against_last10 | 0.5657 |
| 33 | home_corners_for_last10 | corners_pressure_index_last10 | 0.5590 |
| 34 | away_corners_against_last5 | away_shots_against_last5 | 0.5560 |
| 35 | home_corners_for_last10 | corners_last5_diff | 0.5495 |
| 36 | away_corners_for_last5 | away_total_corners_last5 | 0.5388 |
| 37 | home_corners_against_last5 | home_total_corners_last5 | 0.5384 |
| 38 | home_corners_for_last10 | total_corners_for_last5 | 0.5234 |
| 39 | home_shots_on_target_for_last10 | shots_on_target_last5_diff | 0.5223 |
| 40 | away_goals_against_last5 | away_goals_against_std_last5 | 0.5175 |
| 41 | away_goals_for_last5 | away_losses_last5 | -0.5106 |
| 42 | home_corners_for_last10 | home_total_corners_last5 | 0.4874 |
| 43 | away_goals_against_last5 | away_win_rate_last5 | -0.4869 |
| 44 | away_goals_against_last5 | away_wins_last5 | -0.4869 |
| 45 | away_shots_for_last10 | away_shots_on_target_for_last5 | 0.4696 |
| 46 | home_corners_for_last10 | shots_last10_diff | 0.4558 |
| 47 | away_shots_for_last5 | shots_on_target_last5_diff | -0.4548 |
| 48 | home_corners_for_last10 | home_shots_for_last5 | 0.4482 |
| 49 | away_shots_for_last10 | shots_on_target_last10_diff | -0.4455 |
| 50 | away_shots_for_last10 | away_shots_for_std_last10 | 0.4449 |

## Pares com Correlacao > 0.85 (Risco de Multicolinearidade)

**Total: 36 pares**

| Feature A | Feature B | Correlacao | Recomendacao |
|-----------|-----------|:---:|-------------|
| home_points_last10 | home_points_per_game_last10 | 1.0000 | Avaliar qual carregar mais informacao |
| away_points_last10 | away_points_per_game_last10 | 1.0000 | Avaliar qual carregar mais informacao |
| home_points_last5 | home_points_per_game_last5 | 1.0000 | Avaliar qual carregar mais informacao |
| away_wins_last5 | away_win_rate_last5 | 1.0000 | Avaliar qual carregar mais informacao |
| away_points_last5 | away_points_per_game_last5 | 1.0000 | Avaliar qual carregar mais informacao |
| home_wins_last5 | home_win_rate_last5 | 1.0000 | Avaliar qual carregar mais informacao |
| away_wins_last10 | away_win_rate_last10 | 1.0000 | Avaliar qual carregar mais informacao |
| home_wins_last10 | home_win_rate_last10 | 1.0000 | Avaliar qual carregar mais informacao |
| home_points_last5 | home_win_rate_last5 | 0.9580 | Avaliar qual carregar mais informacao |
| home_win_rate_last5 | home_points_per_game_last5 | 0.9580 | Avaliar qual carregar mais informacao |
| home_wins_last5 | home_points_last5 | 0.9580 | Avaliar qual carregar mais informacao |
| home_wins_last5 | home_points_per_game_last5 | 0.9580 | Avaliar qual carregar mais informacao |
| home_wins_last10 | home_points_last10 | 0.9559 | Avaliar qual carregar mais informacao |
| home_win_rate_last10 | home_points_per_game_last10 | 0.9559 | Avaliar qual carregar mais informacao |
| home_wins_last10 | home_points_per_game_last10 | 0.9559 | Avaliar qual carregar mais informacao |
| home_points_last10 | home_win_rate_last10 | 0.9559 | Avaliar qual carregar mais informacao |
| away_points_last10 | away_win_rate_last10 | 0.9555 | Avaliar qual carregar mais informacao |
| away_win_rate_last10 | away_points_per_game_last10 | 0.9555 | Avaliar qual carregar mais informacao |
| away_wins_last10 | away_points_last10 | 0.9555 | Avaliar qual carregar mais informacao |
| away_wins_last10 | away_points_per_game_last10 | 0.9555 | Avaliar qual carregar mais informacao |
| away_wins_last5 | away_points_last5 | 0.9533 | Avaliar qual carregar mais informacao |
| away_win_rate_last5 | away_points_per_game_last5 | 0.9533 | Avaliar qual carregar mais informacao |
| away_points_last5 | away_win_rate_last5 | 0.9533 | Avaliar qual carregar mais informacao |
| away_wins_last5 | away_points_per_game_last5 | 0.9533 | Avaliar qual carregar mais informacao |
| home_shots_for_ema_last10 | home_shots_for_ema_last5 | 0.9493 | Considerar remover `home_shots_for_ema_last10` (derivada) |
| away_shots_for_ema_last10 | away_shots_for_ema_last5 | 0.9446 | Considerar remover `away_shots_for_ema_last10` (derivada) |
| away_shots_against_ema_last10 | away_shots_against_ema_last5 | 0.9441 | Considerar remover `away_shots_against_ema_last10` (derivada) |
| home_shots_against_ema_last10 | home_shots_against_ema_last5 | 0.9436 | Considerar remover `home_shots_against_ema_last10` (derivada) |
| home_goals_for_ema_last10 | home_goals_for_ema_last5 | 0.9389 | Considerar remover `home_goals_for_ema_last10` (derivada) |
| away_corners_against_ema_last10 | away_corners_against_ema_last5 | 0.9343 | Considerar remover `away_corners_against_ema_last10` (derivada) |
| home_corners_for_ema_last10 | home_corners_for_ema_last5 | 0.9330 | Considerar remover `home_corners_for_ema_last10` (derivada) |
| away_goals_for_ema_last10 | away_goals_for_ema_last5 | 0.9284 | Considerar remover `away_goals_for_ema_last10` (derivada) |
| home_corners_against_ema_last10 | home_corners_against_ema_last5 | 0.9250 | Considerar remover `home_corners_against_ema_last10` (derivada) |
| away_corners_for_ema_last10 | away_corners_for_ema_last5 | 0.9236 | Considerar remover `away_corners_for_ema_last10` (derivada) |
| away_goals_against_ema_last10 | away_goals_against_ema_last5 | 0.9230 | Considerar remover `away_goals_against_ema_last10` (derivada) |
| home_goals_against_ema_last10 | home_goals_against_ema_last5 | 0.9174 | Considerar remover `home_goals_against_ema_last10` (derivada) |

## Analise Cruzada: Mean vs STD vs EMA (Mesma Estatistica)

Esta secao mostra a correlacao entre as 3 variantes (media, desvio padrao, EMA)
da mesma estatistica base. Correlacoes altas indicam redundancia.

| Feature Base | Mean↔STD | Mean↔EMA | STD↔EMA |
|-------------|:---:|:---:|:---:|
| home_corners_for_last10 | 0.3795 | 0.2008 | 0.0839 |
| home_corners_against_last10 | 0.4353 | 0.1567 | 0.0985 |
| away_corners_for_last10 | 0.3584 | 0.1418 | 0.0385 |
| away_corners_against_last10 | 0.3898 | 0.1744 | 0.0413 |
| home_goals_for_last10 | 0.4976 | 0.1871 | 0.0944 |
| home_goals_against_last10 | 0.5765 | 0.1578 | 0.0769 |
| away_goals_for_last10 | 0.5765 | 0.1752 | 0.0870 |
| away_goals_against_last10 | 0.5080 | 0.1892 | 0.0811 |
| home_shots_for_last10 | 0.3748 | 0.2160 | 0.0904 |
| home_shots_against_last10 | 0.4428 | 0.2091 | 0.0972 |
| away_shots_for_last10 | 0.4449 | 0.1988 | 0.1153 |
| away_shots_against_last10 | 0.4037 | 0.2084 | 0.0481 |
| home_corners_for_last5 | 0.3669 | 0.3433 | 0.1383 |
| home_corners_against_last5 | 0.4477 | 0.3233 | 0.1707 |
| away_corners_for_last5 | 0.4123 | 0.2979 | 0.1262 |
| away_corners_against_last5 | 0.3768 | 0.3324 | 0.0939 |
| home_goals_for_last5 | 0.5034 | 0.3298 | 0.1672 |
| home_goals_against_last5 | 0.5586 | 0.3224 | 0.1705 |
| away_goals_for_last5 | 0.5771 | 0.3367 | 0.1809 |
| away_goals_against_last5 | 0.5175 | 0.3369 | 0.1683 |
| home_shots_for_last5 | 0.3702 | 0.3737 | 0.1489 |
| home_shots_against_last5 | 0.4087 | 0.3467 | 0.1323 |
| away_shots_for_last5 | 0.3917 | 0.3393 | 0.1519 |
| away_shots_against_last5 | 0.3464 | 0.3512 | 0.0706 |

## Estatisticas Globais de Correlacao

- Total de pares analisados: 12561
- Correlacao absoluta media: nan
- Correlacao absoluta mediana: nan
- Pares com |r| > 0.90: 36
- Pares com |r| > 0.85: 36
- Pares com |r| > 0.70: 122
- Pares com |r| > 0.50: 359

## Recomendacoes

⚠️ **36 pares com correlacao > 0.85 detectados.**

### Acoes Sugeridas

1. **STD/EMA redundantes (12 pares):** Se Mean↔EMA > 0.95, a EMA nao adiciona informacao nova. Considerar:
   - Desativar EMA (`rolling_use_ema: false`) e medir impacto no accuracy
   - Ou manter apenas EMA e remover rolling mean (EMA subsume a media)

3. **Para modelos lineares (Ridge/ElasticNet — 30% do ensemble):**
   - Multicolinearidade causa instabilidade nos coeficientes
   - Considerar VIF (Variance Inflation Factor) para selecao mais rigorosa

4. **Para modelos tree-based (XGBoost/LightGBM/RF — 70% do ensemble):**
   - Multicolinearidade NAO afeta accuracy
   - Mas dilui a importancia das features (interpretabilidade reduzida)
