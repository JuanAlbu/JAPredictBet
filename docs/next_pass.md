# JA PREDICT BET — ROADMAP P2+ (REVISÃO 11-APR-2026)

**Data da Revisão:** 11 de Abril, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 parcial — 166/166 testes passando (20 arquivos). 106 features. 30 modelos (11 XGB + 10 LGB + 5 Ridge + 4 EN).
**Histórico Completo:** Todos os itens concluídos (P0, P0-FIX, P1, Onda 1) documentados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).
**Próxima Ação:** Onda 4 — Gatekeeper Live Pipeline (SH4-SH9). Onda 2 residual (B3, B7, B8, C7).

---

## Visão Geral

Este documento contém **apenas itens em aberto**, organizados em ondas de execução por prioridade.
Itens concluídos são transferidos para [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) ao serem fechados.

**Itens em aberto:** 21 (P2) + 2 (P3) + 5 (R&D) = 28 total

---

## Onda 2 — Infraestrutura & Paridade de Features (Próximo)

**Objetivo:** Unificar config loading, corrigir paridade de features entre scripts, e resolver vulnerabilidade de pickle.
**Dependências:** ~~B6 desbloqueia B3~~ (feito). Itens ~~A9-A11~~ (feitos) corrigem divergências silenciosas de feature set.
**Impacto esperado:** Implementação 8→9/10, Production-Ready 8→9/10.

### Bloco 2A — Config & Pipeline

- [x] **P2.B6 - Centralizar `_load_config()` em `config.py`** ✅ (03-APR-2026)
  - `PipelineConfig.from_yaml(path)` criado. 5 scripts atualizados (run.py, consensus, hyperopt, correlation, update_pipeline).

- [ ] **P2.B3 - Reescrever `update_pipeline.py` (Non-Functional)**
  - **Bug 1:** ~~`PipelineConfig(**config_dict)` — crash~~ CORRIGIDO via P2.B6.
  - **Bug 2:** Feature engineering ausente — portar pipeline completo (rolling, STD, EMA, ELO, matchup, H2H, drop redundant).
  - **Bug 3:** `algorithms` hardcoded sem Ridge/ElasticNet.
  - **Referência:** `run.py` (config loading correto) e `mvp_pipeline.py` (feature pipeline completo).

- [ ] **P2.B7 - Verificar integridade de pickle antes de deserializar**
  - `run.py` linha 88: `pickle.load()` sem verificação de hash. O projeto já tem `_compute_artifact_hash`.
  - **Fix:** SHA256 do `.pkl` vs hash no JSON metadata antes de `pickle.load()`.

- [ ] **P2.B8 - Corrigir holdout temporal para ser realmente cronológico**
  - `_build_temporal_split()` documenta "últimos 3 meses", mas hoje embaralha linhas da temporada mais recente e separa uma fração aleatória.
  - **Risco:** validação otimista e falsa sensação de rigor temporal.
  - **Fix:** fazer split por data real (`date`) com corte cronológico explícito e alinhar documentação/nomes do modo strict holdout.

### Bloco 2B — Paridade de Feature Set

- [x] **P2.A9 - Sincronizar keywords de feature selection (mvp_pipeline vs train)** ✅ (03-APR-2026)
  - `_is_model_feature_candidate()` agora inclui `_rolling` e `_momentum`, sincronizado com `_is_allowed_feature()`.

- [x] **P2.A10 - Sincronizar features em `hyperopt_search.py`** ✅ (03-APR-2026)
  - Adicionado ELO ratings e team target encoding em `_prepare_data()`. Corrigida chamada `_valid_training_mask()` com assinatura errada.

- [x] **P2.A11 - Sincronizar features em `walk_forward.py`** ✅ (03-APR-2026)
  - Adicionados rolling STD, EMA, H2H e `drop_redundant_features()` em `_build_features()`. `WalkForwardConfig` expandido.

- [x] **P2.A12 - `_build_ensemble_schedule` respeita parâmetro `algorithms`** ✅ (03-APR-2026)
  - Hybrid mode agora só ativa quando `algorithms` contém tanto boosters quanto linear. `_build_hybrid_ensemble_schedule` parametrizado.

- [ ] **P2.C7 - Integrar params otimizados do hyperopt no ensemble**
  - `hyperopt_search.py` é READ-ONLY — os melhores params (ElasticNet=1.4799, XGBoost=1.4880, LightGBM=1.4934) não são aplicados automaticamente.
  - **Fix:** Atualizar `_build_variation_params()` em `train.py` e/ou `_build_diversified_*_params()` no consensus script para usar os params do `artifacts/hyperopt/*_best_params.json` como base de variação.

- [x] **P2.A14 - Corrigir drift de nomenclatura de features ELO** ✅ (11-APR-2026)
  - `mvp_pipeline.py` e `test_missing_feature_imputation.py` atualizados para `home_elo_rating` / `away_elo_rating`. `DATA_SCHEMA.md` sincronizado.

---

## Onda 3 — Testes & Limpeza

**Objetivo:** Elevar cobertura de ~60% para 70%+, remover dead code, padronizar estilo.
**Impacto esperado:** Testes 7→8/10.

### Bloco 3A — Cobertura de Testes

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
  - XGBoost usa `np.random.default_rng()`, LGB/RF/Ridge/EN usam listas hardcoded de 10 elementos. Se >10 modelos, params repetem.

### Bloco 3B — Limpeza & Consistência

- [ ] **P2.C1 - Remover código morto**
  - `value/value_engine.py` (217 linhas) — duplicada, com bugs próprios.
  - `config_backup.yml` — usar git history.
  - ~~`src/japredictbet/agents/`~~ — agora contém código real (`BaseAgent`, `AgentRegistry`). Removido da lista.
  - ~~`rolling.py::add_rolling_features()`~~ — usada em testes (`test_rolling_cross_group.py`). Verificar se pipeline principal a chama.

- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`**
  - Poisson vive em `betting/engine.py`, violando boundary. Opções: (a) mover para `probability/poisson.py`, ou (b) atualizar AGENTS.md e ARCHITECTURE.md.

- [ ] **P2.C3 - Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Regex `r"[^a-z0-9\\s]"` em raw string. Config RandomForest enganoso no `algorithms`.

- [x] **P2.C6 - Reconciliar documentação e estado real de validação** ✅ (11-APR-2026)
  - Test count atualizado para 166/166 (20 arquivos) em: `AGENTS.md`, `README.md`, `PROJECT_CONTEXT.md`, `PRODUCT_REQUIREMENTS.md`, `EXECUTIVE_SUMMARY.md`, `VALIDATION_REPORT.md`.
  - `TRAINING_STRATEGY.md` corrigido: holdout descrito como shuffle dentro da temporada (não cronológico estrito), 50%→25%.
  - `VALIDATION_REPORT.md` seção P0-FIX expandida de 3→6 items.
  - `DATA_SCHEMA.md` ELO columns corrigidas.

---

## Onda 4 — Gatekeeper Live Pipeline + SHADOW Mode (REVISÃO 11-APR-2026)

**Objetivo:** Pipeline paralelo de gestão de risco via LLM (Prompt Mestre V25) + coleta de odds Superbet em modo estritamente observacional. Nenhum módulo executa aposta real.
**Dependências:** P2.D4 (Telegram bot) depende desta trilha.
**Novas dependências pip:** `httpx>=0.28.0`
**Arquivos criados:**
- `src/japredictbet/odds/superbet_client.py` ✅
- `src/japredictbet/data/context_collector.py` ✅
- `src/japredictbet/agents/base.py` ✅
- `src/japredictbet/agents/registry.py` ✅
**Arquivos pendentes:**
- `src/japredictbet/agents/gatekeeper.py` — SH8
- `src/japredictbet/pipeline/gatekeeper_live_pipeline.py` — SH9
- `scripts/shadow_observe.py` — SH6
- `tests/odds/test_superbet.py` — SH7
- `data/mapping/superbet_teams.json` — SH4
**Config adicionada:** Blocos `gatekeeper`, `api_keys`, `superbet_shadow`, `api_football` em `config.yml` + dataclasses correspondentes em `config.py`.
**Nota técnica:** Endpoint Superbet é SSE, não REST JSON. Campo `matchName` usa `·` (middle dot U+00B7) como separador.

### Bloco 4A — Infra de Coleta (parcialmente implementado)

- [x] **P2.SH1 - Substituir `requests` por `httpx` no coletor** ✅ (11-APR-2026)
  - `superbet_client.py`: `httpx.Client` com timeout configurável, `User-Agent` de navegador, retry com exponential backoff (2→4→8s), tratamento HTTP 403/429/500.

- [x] **P2.SH2 - Parsing SSE do feed Superbet** ✅ (11-APR-2026)
  - `_iter_sse_events()` faz parsing linha-a-linha (`data:{json}`), tolerante a eventos malformados (try/except por evento, logging).

- [x] **P2.SH3 - Filtro de eventos e mercados** ✅ (11-APR-2026)
  - `sportId=5` (futebol), split `matchName` por `·`, detecção de mercados: `Total de Escanteios` (corners), `Resultado Final` / `1x2` (match odds), `Ambas Marcam` / `BTTS`.
  - Extração: `event_id`, `home_team`, `away_team`, `market_line`, `over_odds`, `under_odds`, `home/draw/away_odds`, `yes/no_odds`.

- [ ] **P2.SH4 - Mapeamento Superbet → IDs internos**
  - Arquivo: `data/mapping/superbet_teams.json` (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` param — equipes sem mapeamento geram WARNING e skip.
  - `context_collector.py` carrega mapping via `_load_team_mapping()` (None se arquivo ausente → sem filtro).

### Bloco 4B — Contexto T-60 (implementado)

- [x] **P2.SH5a - Context Collector (API-Football + Superbet)** ✅ (11-APR-2026)
  - `src/japredictbet/data/context_collector.py`:
    - `ApiFootballClient` — fixtures do dia, lineups confirmadas, injuries/suspensions, standings.
    - `ContextCollector` — orquestra Superbet + API-Football, filtra janela T-60, fuzzy match de equipes.
    - `MatchContext` dataclass com serialização JSON para injeção no LLM.
  - API keys resolvidas de env vars (`${API_FOOTBALL_KEY}`) — nunca commitadas.
  - Cada chamada à API isolada via `_safe_call()` — falha parcial não derruba pipeline.

### Bloco 4C — Gatekeeper Agent + Pipeline (pendente)

- [ ] **P2.SH5b - Integração com `ConsensusEngine` em Shadow Mode**
  - Para cada jogo válido, chamar `evaluate_with_consensus()` e registrar auditoria.
  - Shadow log: `logs/shadow_bets.log` com timestamp, match_id, odds, p_model_mean, edge, votos, status.
  - **Regra de segurança:** nenhum módulo deve executar aposta real.

- [ ] **P2.SH6 - Script executável de observação**
  - `scripts/shadow_observe.py` com CLI. Falhas de rede não derrubam execução. Resumo final em console.

- [ ] **P2.SH7 - Testes dedicados da trilha Shadow**
  - `tests/odds/test_superbet.py`: SSE multi-eventos, JSON malformado, HTTP 403/429/500, timeout, reconexão, time sem mapeamento, mercado inválido, esporte não-futebol.
  - `tests/data/test_context_collector.py`: fixtures, lineups, injuries, standings, fuzzy match, MatchContext serialização.

- [ ] **P2.SH8 - Agente Gatekeeper (LLM + decisão)**
  - `src/japredictbet/agents/gatekeeper.py` herdando de `BaseAgent`.
  - Encapsula `PROMPT_MESTRE V25 FINAL` como system prompt.
  - `evaluate_match(match_context_json)` → JSON com `status` (APPROVED / NO BET), `stake`, `odd_superbet`, `justificativa`.
  - Pré-filtro Python hardcoded: bloqueia se odd Superbet < `min_odd` (1.60) antes de enviar ao LLM.
  - **Dependência:** `llm_api_key` configurada em env var `${LLM_API_KEY}`.

- [ ] **P2.SH9 - Pipeline Gatekeeper Live (orquestração T-60)**
  - `src/japredictbet/pipeline/gatekeeper_live_pipeline.py`.
  - Fluxo: Busca jogos Superbet → Agenda T-60 → Coleta escalação (API-Football) → Pré-filtro Python (min_odd) → `GatekeeperAgent.evaluate_match()` → Salva Lista do Dia no shadow log.
  - Max 5 entradas/dia (`gatekeeper.max_entries_per_day`).

---

## Onda 5 — CI, Produto & Polish

**Objetivo:** Automatizar qualidade, melhorar observabilidade e experiência final.

### Bloco 5A — CI & Infraestrutura

- [ ] **P2.B1 - CI Básico (pytest em push)** — Coverage gate > 60%.
- [ ] **P2.B2 - Logging Estruturado por Aposta** — Lambdas, votos, edge, threshold, stake, resultado.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`** — Usar `utils/logging.py` existente.
- [ ] **P2.B5 - Completar `pyproject.toml`** — Metadata, entry points, dev dependencies.
- [ ] **P2.B9 - Blindar coleta de testes no repositório**
  - `python -m pytest tests -q` passa, mas `python -m pytest -q` falha por coletar `test_output.txt` na raiz.
  - **Fix:** definir `testpaths`/`python_files` no `pyproject.toml` e impedir artefatos de relatório de entrarem na coleta.

### Bloco 5B — Produto

- [ ] **P2.D1 - Tratamento de Erros Robusto** — `try-except` em `fetch_odds` e pontos críticos.
- [ ] **P2.D2 - Dashboard de Saúde do Modelo** — Volume, hit rate, ROI, CLV, calibração por período.
- [ ] **P2.D4 - Bot de Alertas (Telegram)** — Notificação de oportunidades. **Dependência:** Onda 4 (SHADOW).

---

## P3 — Performance e Otimização (Futuro)

- [ ] **P3.1 - Otimizar loop de consensus sweep** — `mvp_pipeline.py` (L256-276): `O(rows × thresholds × 30 models)` sem batch. Vectorizar ou paralelizar.
- [ ] **P3.2 - Cache de computações caras** — Rolling stats recalculadas a cada execução. Cache com invalidação por data.

---

## R&D — Pesquisa e Desenvolvimento (A Pesquisar)

- [ ] **Binomial Negativa Bivariada** — Migração de Poisson para modelos com sobredispersão.
- [ ] **Stacking Meta-Modelo** — Ponderação aprendida dos membros do ensemble.
- [ ] **Game State / Live Variables** — Impacto de estado de jogo em cantos.
- [ ] **GNN Tático** — Modelagem estrutural de interações entre jogadores.
- [ ] **Favourite-Longshot Bias** — Ajustes para vieses sistemáticos do mercado.

---

## Matriz de Maturidade (11-APR-2026)

| Dimensão | Nota | Comentário |
|----------|------|------------|
| Arquitetura | 9/10 | Design modular, bem documentada. Agent framework + Gatekeeper Live Pipeline adicionados |
| Implementação | 8.5/10 | P0+P1 completos; feature parity corrigida (A9-A12), ELO naming fix (A14). Penalizado por `update_pipeline.py` non-functional, holdout não-cronológico e hyperopt params não integrados |
| Documentação | 8.5/10 | 60 inconsistências corrigidas (P2.C4). Drift documental corrigido (C6): AGENTS.md, ARCHITECTURE.md, PROJECT_CONTEXT.md sincronizados |
| Testes | 7/10 | 166 testes (20 arquivos), ~60% cobertura. `data/ingestion.py` e `features/` com cobertura parcial |
| Reprodutibilidade | 9/10 | SHA256, seeds, requirements pinados, config-driven, configs sincronizados |
| Production-Ready | 7.5/10 | Pipeline completo com calibração, risk e CLV. Penalizado por pickle sem hash, update_pipeline non-functional, e hyperopt params não integrados |

---

## Referências Rápidas

| Recurso | Arquivo |
|---------|---------|
| Histórico completo (P0, P0-FIX, P1, Onda 1) | [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) |
| Detalhes P0 (9 itens) | [`P0_COMPLETION_SUMMARY.md`](P0_COMPLETION_SUMMARY.md) |
| Sumário executivo | [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) |
| Arquitetura do sistema | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Validação e testes | [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) |
