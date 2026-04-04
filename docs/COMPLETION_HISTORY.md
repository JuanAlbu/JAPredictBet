# JA PREDICT BET — HISTÓRICO DE ITENS CONCLUÍDOS

**Criado:** 03 de Abril, 2026
**Propósito:** Registro permanente de todos os itens de roadmap concluídos, com datas, evidências e detalhes de implementação. Itens são movidos do roadmap ativo (`next_pass.md`) para cá ao serem fechados.

---

## P0 — Pipeline Core (100% FECHADO — 30-MAR-2026)

> 9 itens implementados e validados com 101 partidas reais + 50 recentes + stress test random lines.
> Detalhes completos em [`P0_COMPLETION_SUMMARY.md`](P0_COMPLETION_SUMMARY.md).

| Item | Descrição | Data |
|------|-----------|------|
| P0.1 | Remoção de 4 hardcodes do CLI | 30-MAR-2026 |
| P0.2 | Ensemble híbrido 70/30 (21 boosting + 9 linear) | 30-MAR-2026 |
| P0.3 | Dynamic margin rule (threshold +50% quando margem < 0.5) | 30-MAR-2026 |
| P0.4 | Dynamic feature selection refactor | 30-MAR-2026 |
| P0.5 | Parallel training (3-5x speedup) | 30-MAR-2026 |
| P0.6 | Strict temporal holdout | 30-MAR-2026 |
| P0.7 | Match key matching strategy | 30-MAR-2026 |
| P0.8 | Artifact versioning com SHA256 | 30-MAR-2026 |
| P0.3b | Encerramento formal — trilha P0 fechada | 30-MAR-2026 |

---

## P0-FIX — Bugs Críticos Bloqueantes (100% FECHADO — 03-APR-2026)

> Descobertos na revisão de código de 31-MAR-2026. Todos verificados em código e validados operacionalmente.

### FIX.1 — `_build_hybrid_ensemble_schedule()` não definida em `train.py`

- **Severidade:** BLOQUEANTE
- **Status:** ✅ RESOLVIDO — função já estava implementada na linha 415 do `train.py` (build 70% boosters + 30% linear). Roadmap anterior continha informação desatualizada.
- **Data:** 31-MAR-2026

### FIX.2 — `importance.py` assume XGBoost exclusivamente

- **Severidade:** BLOQUEANTE
- **Arquivo:** `src/japredictbet/models/importance.py`
- **Status:** ✅ RESOLVIDO — adicionado dispatch por tipo de modelo via `_extract_scores()`: XGBoost usa `get_booster().get_score()`, LightGBM e RandomForest usam `feature_importances_`, Ridge/ElasticNet usam `abs(coef_)`.
- **Data:** 31-MAR-2026

### FIX.3 — Schema de config inconsistente entre YAMLs

- **Severidade:** ALTO
- **Status:** ✅ RESOLVIDO — Corrigido em 4 lugares: `config_test_50matches.yml` e `config_backup.yml` atualizados para `rolling_windows: [10, 5]`; `scripts/consensus_accuracy_report.py` atualizado para usar `cfg.features.rolling_windows[0]`; `tests/pipeline/test_mvp_pipeline.py` corrigido para `FeatureConfig(rolling_windows=[10, 5])`; `config.py` adicionou `__post_init__` com validação de tipo.
- **Data:** 31-MAR-2026

### FIX.4 — Pinnar versões em `requirements.txt`

- **Severidade:** ALTO
- **Status:** ✅ RESOLVIDO — `requirements.txt` atualizado com versões exatas de todas as dependências de produção. Criado `requirements-dev.txt` com `-r requirements.txt` + `pytest==9.0.2`.
- **Data:** 31-MAR-2026

### FIX.5 — Contaminação cross-grupo em rolling features

- **Severidade:** BLOQUEANTE (qualidade de dados)
- **Arquivos:** `src/japredictbet/features/rolling.py` — funções `add_rolling_features()`, `add_stat_rolling()`, `add_result_rolling()`, `add_rolling_std()`
- **Problema:** O padrão `group[col].shift(1).rolling(window).mean()` aplica `.rolling()` na Series flat, cruzando fronteiras entre equipes.
- **Fix:** Migrado para `group.transform(lambda x: x.shift(1).rolling(window).mean())` em todas as funções.
- **Validação operacional:**
  - ✅ Retreino completo executado com `python run.py --config config.yml --skip-model-dir`
  - ✅ Cenário full validado (`scripts/consensus_accuracy_report.py --config config.yml`)
  - ✅ Cenário random-lines validado (`--random-lines --line-min 5.5 --line-max 11.5`)
  - ✅ Cenário recent subset destravado e validado
- **Testes:** `tests/features/test_rolling_cross_group.py`
- **Data:** 03-APR-2026

### FIX.6 — Default `algorithms` em `config.py` não inclui Ridge/ElasticNet

- **Severidade:** ALTO
- **Arquivo:** `src/japredictbet/config.py`
- **Fix:** Default alterado para `("xgboost", "lightgbm", "randomforest", "ridge", "elasticnet")`.
- **Testes:** `tests/test_config_defaults.py`
- **Data:** 03-APR-2026

**Critério de Saída P0-FIX:** Pipeline `python run.py` executa sem erros com ensemble_size=30, importance funciona com todos os tipos de modelo, ambos os configs carregam sem erro, todas as dependências pinadas, rolling features operam estritamente dentro dos limites de cada grupo.

---

## P1 — Alto Impacto (100% CONCLUÍDO — 03-APR-2026)

> 13 itens implementados. 165 testes passando em 17 arquivos.

### P1-A: Integridade do Pipeline

| Item | Descrição | Data | Testes |
|------|-----------|------|--------|
| P1.A1 | Portar lógica 70/30 para `train.py` — Mix 21 boosters + 9 linear, scheduling, filenames, run.py discovery | 31-MAR-2026 | 13 testes em `tests/models/test_train.py` |
| P1.A2 | Dynamic margin rule no `engine.py` — `tight_margin_threshold` e `tight_margin_consensus` em config | 31-MAR-2026 | 8 unit + 4 integration |
| P1.A3 | Lambda validation — `_validate_lambda()` com guard `np.isfinite()` e λ ≥ 0 | 31-MAR-2026 | 26 unit + 5 integration |

### P1-B: Evolução de Features

| Item | Descrição | Data | Testes |
|------|-----------|------|--------|
| P1.B1 | Calibração de Probabilidades (Brier/ECE) — `probability/calibration.py` | 03-APR-2026 | 16 testes em `tests/probability/test_calibration.py` |
| P1.B2 | Rolling STD + EMA — `add_rolling_std()` e `add_rolling_ema()` com flags em config | 31-MAR-2026 | 11 testes |
| P1.B3 | Momento e Contexto — `add_result_rolling()` (win_rate, points rolling) | Pré-existente | Integrado no pipeline |
| P1.B4 | Cross-Features (Ataque×Defesa) — `add_matchup_features()` (pressure_index, diffs) | Pré-existente | Integrado no pipeline |
| P1.B5 | H2H Confronto Direto (Last 3) — `add_h2h_features()` em `matchup.py`, par canônico | 03-APR-2026 | 10 testes em `tests/features/test_h2h.py` |

### P1-C: Otimização e Análise

| Item | Descrição | Data | Testes |
|------|-----------|------|--------|
| P1.C1 | HyperOpt via Optuna — `scripts/hyperopt_search.py`, TPE sampler, 5-fold CV | 03-APR-2026 | Script standalone |
| P1.C2 | SHAP weighted votes — `models/shap_weights.py`, votação ponderada no consensus | 03-APR-2026 | 6 testes em `tests/betting/test_weighted_consensus.py` |
| P1.C3 | Persistência de Hiperparâmetros — JSON metadata alongside .pkl | 01-APR-2026 | Integrado |

### P1-D: Value e Risco

| Item | Descrição | Data | Testes |
|------|-----------|------|--------|
| P1.D1 | Value Bet Engine — `expected_value()` em engine.py | Pré-existente | Integrado |
| P1.D2 | CLV Audit — `closing_line_value()`, `clv_hit_rate()`, `clv_summary()` | 03-APR-2026 | 11 testes em `tests/betting/test_clv.py` |
| P1.D3 | Gestão de Risco — `betting/risk.py` (Quarter Kelly, Monte Carlo, slippage) | 03-APR-2026 | 18 testes em `tests/betting/test_risk.py` |

---

## P2 — Itens Concluídos (Onda 1 — 03-APR-2026)

### P2.C4 — Sincronizar documentação contraditória (100% RESOLVIDO)

14 arquivos corrigidos com 60+ inconsistências eliminadas:

| Arquivo | Correção |
|---------|----------|
| `ARCHITECTURE.md` | XGB/LGB artifact filenames corrigidos (xgb 1-11, lgbm 1-10) |
| `IMPLEMENTATION_CONSENSUS.md` | Seção 3 reescrita — era "10 XGB + 10 LGB + 10 RF", agora 4-algorithm hybrid (11+10+5+4); Seção 7 corrigida |
| `EXECUTIVE_SUMMARY.md` | Data 01→03-APR, testes 87→158, P1-B parcial→100%, adicionadas seções P1-C/P1-D e FIX.5/FIX.6 |
| `VALIDATION_REPORT.md` | Composição corrigida, tabela de testes reescrita (17 arquivos), Seção 7 P1 itens ✅ |
| `PROJECT_CONTEXT.md` | "11 LGBM"→"10 LGBM", FIX.5 DONE, testes 87→158, 10→17 arquivos |
| `TRAINING_STRATEGY.md` | Seção 2: "50% random split" → "~25% temporal holdout (3 meses)" |
| `AGENTS.md` | Adicionados lightgbm, optuna, shap; boundaries atualizadas |
| `README.md` | Status P1 100%, adicionados deps, disclaimer analytics-only |
| `DATA_SCHEMA.md` | Seção 7 ELO específico, adicionada Seção 8 H2H features |
| `FEATURE_ENGINEERING_PLAYBOOK.md` | Adicionada seção H2H features |
| `FEATURE_IMPORTANCE_GUIDE.md` | Adicionada seção SHAP, H2H, STD/EMA groups |
| `VALIDATION.md` | Ensemble corrigido, CLV/Brier/Monte Carlo atualizados |
| `MODEL_ARCHITECTURE.md` | XGB/LGB counts, seções H2H, ELO, Calibração, SHAP, CLV, Risk |
| `WORK_MODEL.md` | Nota sobre config_test_50matches.yml + P1 flags |

### P2.C5 — Sincronizar configs de teste/backup com P1 feature flags (RESOLVIDO)

- `config_test_50matches.yml` e `config_backup.yml` — adicionados 6 P1 flags: `rolling_use_std`, `rolling_use_ema`, `drop_redundant`, `h2h_window`, `tight_margin_threshold`, `tight_margin_consensus`
- 165/165 testes passando após sincronização

### Itens Absorvidos

| Item Original | Absorvido Por | Motivo |
|---------------|--------------|--------|
| P2.A4 — Ampliar testes de `odds/collector.py` | P2.SH7 | Testes Shadow cobrem timeout, JSON inválido, resposta vazia com escopo mais completo |
| P2.A7 — Adicionar timeout em `odds/collector.py` | P2.SH1 | Migração para httpx inclui timeout configurável, User-Agent, error handling |
| P2.D3 — Integração com APIs Real-time | P2-SHADOW | Trilha SH1-SH7 implementa integração real-time em modo observacional |

---

## Changelog Completo

| Data | Ação |
|------|------|
| 30-MAR-2026 | Criação do roadmap. P0 encerrado. |
| 31-MAR-2026 | Revisão completa de código: 26 arquivos Python, 3 configs, 17 docs. Adicionado P0-FIX (3 bugs bloqueantes). Reorganizado P1 em sub-grupos (A-D) por prioridade. Expandido P2 com gaps de testes e limpeza. Adicionado P3 (performance). Adicionada matriz de maturidade. |
| 31-MAR-2026 | P0-FIX 100% concluído: FIX.1 já estava OK, FIX.2 (`importance.py` multi-model dispatch), FIX.3 (config schema padronizado + validação), FIX.4 (requirements.txt com versões pinadas + requirements-dev.txt). 21 testes passando. |
| 31-MAR-2026 | P1.A1 (ensemble híbrido), P1.A2 (dynamic margin), P1.A3 (lambda validation), P1.B2 (STD+EMA) implementados. 87 testes passando. |
| 01-APR-2026 | Consensus script (`consensus_accuracy_report.py`) sincronizado com pipeline principal: agora usa 106 features (STD+EMA+drop_redundant). Documentação completa revisada e atualizada. |
| 03-APR-2026 | P1 100% concluído: B1 (calibração Brier/ECE), B5 (H2H last 3), C1 (Optuna hyperopt), C2 (SHAP weighted votes), C3 (hyperparameter persistence), D2 (CLV audit), D3 (Kelly/risk). 158 testes passando em 17 arquivos. |
| 03-APR-2026 | Adicionada trilha P2-SHADOW (Superbet Shadow Mode) com 7 items. Corrigido spec SH2: endpoint é SSE, não JSON monolítico — `ijson` substituído por SSE parsing. |
| 03-APR-2026 | Revisão profunda de código e documentação: 80 problemas encontrados (20 em código, 60 em docs). P0-FIX reaberto com FIX.5 (rolling cross-group), FIX.6 (default algorithms). Adicionados P2.A9-A12, P2.B6, P2.B7, P2.C5. |
| 03-APR-2026 | Reavaliação do roadmap: 3 itens absorvidos (A4→SH7, A7→SH1, D3→SHADOW). P0-FIX.7 (regex) movido para P2.C3. Dependências cruzadas documentadas (B6→B3, SHADOW→D4). |
| 03-APR-2026 | Revisão completa de P0-FIX: todos os 6 itens verificados em código. Pipeline P0 production-ready. |
| 03-APR-2026 | P0-FIX hotfix: rolling cross-group corrigido via `transform(...)` em 4 funções + testes de regressão. FIX.6 fechado com tuple completa. |
| 03-APR-2026 | Execução operacional do FIX.5: retreino completo + validações full, random-lines, recent subset. |
| 03-APR-2026 | Desbloqueio do `recent subset`: fallback determinístico para features esparsas. Validações full, recent e random-lines executadas com sucesso. |
| 03-APR-2026 | **ONDA 1 CONCLUÍDA** — P2.C4 (60 inconsistências em 14 docs) + P2.C5 (configs sincronizados com P1 flags). Matriz Docs 5→8/10, Testes 158→165. |
| 03-APR-2026 | Reorganização do roadmap: itens concluídos movidos para `COMPLETION_HISTORY.md`. Roadmap reescrito com foco em itens abertos, priorizado em 4 ondas. |
