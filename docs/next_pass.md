# JA PREDICT BET — ROADMAP (REVISÃO 12-APR-2026)

**Data da Revisão:** 12 de Abril, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 4 parcial — 218/218 testes (21 arquivos). 106 features. 30 modelos.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 30 (P2) + 2 (P3) + 5 (R&D) = 37 total

> Este documento contém **apenas itens em aberto**. Itens concluídos são registados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## Prioridades Imediatas

1. **Treinar ensemble** — `artifacts/models/` está vazio → `python run.py --config config.yml`
2. **Revisão exaustiva de docs** — Passada 100% linha por linha em todos os docs restantes: ARCHITECTURE, BACKTESTING_STRATEGY, DATA_SCHEMA, FEATURE_ENGINEERING_PLAYBOOK, FEATURE_IMPORTANCE_GUIDE, MVP_PROJECT_PLAN, P0_COMPLETION_SUMMARY, PRODUCT_REQUIREMENTS, TRAINING_STRATEGY, WORK_MODEL. Padronizar datas, métricas (218 testes, 21 arquivos, 30 modelos, 106+ features, 37 pendentes), módulos e linguagem.
3. **Confirmar tournament IDs** — Bundesliga + Premier League no SSE Superbet (SH11)
4. **Onda 2 residual** — B3, B7, B8, C7 (pipeline integrity)
5. **Onda 4 residual** — SH4, SH11-SH14, SH17-SH19 (shadow pipeline completion)

---

## Onda 2 — Infraestrutura & Pipeline (4 itens)

**Objetivo:** Corrigir paridade de features, verificar integridade de artefatos, integrar hyperopt.

- [ ] **P2.B3 - Reescrever `update_pipeline.py` (Non-Functional)**
  - **Bug 1:** ~~`PipelineConfig(**config_dict)` — crash~~ CORRIGIDO via P2.B6.
  - **Bug 2:** Feature engineering ausente — portar pipeline completo (rolling, STD, EMA, ELO, matchup, H2H, drop redundant).
  - **Bug 3:** `algorithms` hardcoded sem Ridge/ElasticNet.
  - **Referência:** `run.py` (config loading) e `mvp_pipeline.py` (feature pipeline completo).

- [ ] **P2.B7 - Verificar integridade de pickle antes de deserializar**
  - `run.py` linha 88: `pickle.load()` sem verificação de hash. O projeto já tem `_compute_artifact_hash`.
  - **Fix:** SHA256 do `.pkl` vs hash no JSON metadata antes de `pickle.load()`.

- [ ] **P2.B8 - Corrigir holdout temporal para ser realmente cronológico**
  - `_build_temporal_split()` documenta "últimos 3 meses", mas embaralha linhas da temporada mais recente.
  - **Risco:** Validação otimista e falsa sensação de rigor temporal.
  - **Fix:** Split por data real (`date`) com corte cronológico explícito.

- [ ] **P2.C7 - Integrar params otimizados do hyperopt no ensemble**
  - `hyperopt_search.py` é READ-ONLY — melhores params não são aplicados automaticamente.
  - **Fix:** Atualizar `_build_variation_params()` em `train.py` para usar `artifacts/hyperopt/*_best_params.json`.

---

## Onda 3 — Testes & Limpeza (10 itens)

**Objetivo:** Elevar cobertura de ~55% para 70%+, remover dead code, padronizar estilo.

### Bloco 3A — Cobertura de Testes (7 itens)

- [ ] **P2.A1 - Testes para `features/`** (elo, rolling, matchup, team_identity)
  - 1/4 módulos com cobertura parcial. Faltam: NaN handling em ELO, edge cases rolling, divisão por zero em matchup, data leakage via train_mask.

- [ ] **P2.A2 - Testes para `data/ingestion.py`**
  - Parquet loading, CSV malformado, dataset vazio, colunas ausentes, NaN em data.

- [ ] **P2.A3 - Testes para `models/train.py`**
  - Ensemble scheduling (hybrid), feature selection, minimum training rows, XGBoost feature name sanitization.

- [ ] **P2.A5 - Suite de Testes de Leakage**
  - Garantir que rolling features usem apenas histórico passado.

- [ ] **P2.A6 - Teste de Regressão de Matching**
  - Evitar confusão entre equipes homônimas em ligas diferentes.

- [ ] **P2.A8 - Validar `train_mask` em `team_identity.py`**
  - Máscara vazia/inválida causa data leakage silencioso. Validar dimensão e tipo booleano.

- [ ] **P2.A13 - `build_variation_params` usa RNG inconsistente**
  - XGBoost usa `np.random.default_rng()`, LGB/RF/Ridge/EN usam listas hardcoded de 10 elementos.

### Bloco 3B — Limpeza & Consistência (3 itens)

- [ ] **P2.C1 - Remover código morto**
  - `value/value_engine.py` (217 linhas) — duplicada, com bugs próprios.
  - `config_backup.yml` — usar git history.
  - Verificar se `rolling.py::add_rolling_features()` é usada pelo pipeline principal ou apenas testes.

- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`**
  - Poisson vive em `betting/engine.py`, violando boundary. Opções: (a) mover para `probability/poisson.py`, ou (b) atualizar docs.

- [ ] **P2.C3 - Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Config RandomForest enganoso no `algorithms`.

---

## Onda 4 — Shadow Pipeline Residual (8 itens)

**Objetivo:** Completar integração do shadow pipeline com scraper REST, refinar filtros, cobertura de integração.
**Dependências:** P2.D4 (Telegram bot) depende desta trilha.
**Itens concluídos:** SH1-SH10, SH15-SH16, SH20-SH23 — ver [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

- [ ] **SH4 - Mapeamento Superbet → IDs internos**
  - `data/mapping/superbet_teams.json` (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` — equipes sem mapeamento geram WARNING e skip.

- [ ] **SH11 - Adicionar Bundesliga + Premier League ao mapeamento de ligas**
  - `data/mapping/league_tournament_ids.json` tem 12 ligas, faltam Bundesliga (1ª) e Premier League.
  - **Fix:** Localizar `tournament_id` no feed SSE Superbet.

- [ ] **SH12 - Refinar filtro de mercados no scraper**
  - Combos de jogador passam no filtro por substring match.
  - **Fix:** Match mais estrito (regex com word boundary) para mercados core.

- [ ] **SH13 - Integrar scraper REST no pipeline live**
  - Scraper é standalone. Pipeline live usa `SuperbetCollector` (SSE only, 3 mercados).
  - **Fix:** Extrair lógica REST para `superbet_client.py` (`fetch_full_event(event_id)`).

- [ ] **SH14 - Limpeza de arquivos temporários**
  - Remover: `_probe_event.py`, `_list_markets.py`, `scraper_*.txt`, `probe_out.txt`, `markets_result.txt`.

- [ ] **SH17 - Separar semântica de `Superbet-only` vs T-60**
  - `context_collector.py` retorna todos os snapshots quando `API_FOOTBALL_KEY` ausente, sem filtro de kickoff.
  - **Fix:** Aplicar filtro temporal alternativo ou segregar modo degradado.

- [ ] **SH18 - Validar H2H no `FeatureStore` para inferência ao vivo**
  - O store reduz para "última linha por time" — pode carregar H2H do último adversário, não do par futuro.
  - **Fix:** Recomputar H2H para o par consultado ou excluir H2H do `FeatureStore`.

- [ ] **SH19 - Criar testes de integração da trilha Shadow**
  - Faltam testes para `gatekeeper_live_pipeline`, `ContextCollector`, `FeatureStore`, `pre-match` e `dry-run`.

---

## Onda 5 — CI, Produto & Polish (8 itens)

**Objetivo:** Automatizar qualidade, melhorar observabilidade e experiência final.

### Bloco 5A — CI & Infraestrutura (5 itens)

- [ ] **P2.B1 - CI Básico (pytest em push)** — Coverage gate > 60%.
- [ ] **P2.B2 - Logging Estruturado por Aposta** — Lambdas, votos, edge, threshold, stake, resultado.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`** — Usar `utils/logging.py` existente.
- [ ] **P2.B5 - Completar `pyproject.toml`** — Metadata, entry points, dev dependencies.
- [ ] **P2.B9 - Blindar coleta de testes**
  - `python -m pytest -q` falha por coletar `test_output.txt` na raiz.
  - **Fix:** Definir `testpaths`/`python_files` no `pyproject.toml`.

### Bloco 5B — Produto (3 itens)

- [ ] **P2.D1 - Tratamento de Erros Robusto** — `try-except` em `fetch_odds` e pontos críticos.
- [ ] **P2.D2 - Dashboard de Saúde do Modelo** — Volume, hit rate, ROI, CLV, calibração por período.
- [ ] **P2.D4 - Bot de Alertas (Telegram)** — Notificação de oportunidades. **Dep:** Onda 4.

---

## P3 — Performance e Otimização (2 itens)

- [ ] **P3.1 - Otimizar loop de consensus sweep** — `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar.
- [ ] **P3.2 - Cache de computações caras** — Rolling stats recalculadas a cada execução. Cache com invalidação por data.

---

## R&D — Pesquisa e Desenvolvimento (5 itens)

- [ ] **Binomial Negativa Bivariada** — Migração de Poisson para modelos com sobredispersão.
- [ ] **Stacking Meta-Modelo** — Ponderação aprendida dos membros do ensemble.
- [ ] **Game State / Live Variables** — Impacto de estado de jogo em cantos.
- [ ] **GNN Tático** — Modelagem estrutural de interações entre jogadores.
- [ ] **Favourite-Longshot Bias** — Ajustes para vieses sistemáticos do mercado.
