# JA PREDICT BET — ROADMAP P2+ (REVISÃO 03-APR-2026)

**Data da Revisão:** 03 de Abril, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ — 165/165 testes passando (17 arquivos). 106 features. 30 modelos (11 XGB + 10 LGB + 5 Ridge + 4 EN).
**Histórico Completo:** Todos os itens concluídos (P0, P0-FIX, P1, Onda 1) documentados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).
**Próxima Ação:** Onda 2 — Infraestrutura e Correções de Paridade.

---

## Visão Geral

Este documento contém **apenas itens em aberto**, organizados em ondas de execução por prioridade.
Itens concluídos são transferidos para [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) ao serem fechados.

**Itens em aberto:** 31 (P2) + 2 (P3) + 5 (R&D) = 38 total

---

## Onda 2 — Infraestrutura & Paridade de Features (Próximo)

**Objetivo:** Unificar config loading, corrigir paridade de features entre scripts, e resolver vulnerabilidade de pickle.
**Dependências:** B6 desbloqueia B3. Itens A9-A11 corrigem divergências silenciosas de feature set.
**Impacto esperado:** Implementação 8→9/10, Production-Ready 8→9/10.

### Bloco 2A — Config & Pipeline

- [ ] **P2.B6 - Centralizar `_load_config()` em `config.py`**
  - 4 scripts duplicam lógica de config com variações (list→tuple de `algorithms` feita só em `run.py`).
  - **Fix:** Criar `PipelineConfig.from_yaml(path)` com lógica única. Substituir em todos os scripts.

- [ ] **P2.B3 - Reescrever `update_pipeline.py` (Non-Functional)**
  - **Bug 1:** `PipelineConfig(**config_dict)` — crash. Usar `PipelineConfig.from_yaml()` (P2.B6).
  - **Bug 2:** Feature engineering ausente — portar pipeline completo (rolling, STD, EMA, ELO, matchup, H2H, drop redundant).
  - **Bug 3:** `algorithms` hardcoded sem Ridge/ElasticNet.
  - **Dependência:** P2.B6
  - **Referência:** `run.py` (config loading correto) e `mvp_pipeline.py` (feature pipeline completo).

- [ ] **P2.B7 - Verificar integridade de pickle antes de deserializar**
  - `run.py` linha 88: `pickle.load()` sem verificação de hash. O projeto já tem `_compute_artifact_hash`.
  - **Fix:** SHA256 do `.pkl` vs hash no JSON metadata antes de `pickle.load()`.

### Bloco 2B — Paridade de Feature Set

- [ ] **P2.A9 - Sincronizar keywords de feature selection (mvp_pipeline vs train)**
  - `_is_model_feature_candidate()` usa keywords diferentes de `_is_allowed_feature()`.
  - **Fix:** Extrair para constante compartilhada ou sincronizar.

- [ ] **P2.A10 - Sincronizar features em `hyperopt_search.py`**
  - `_prepare_data()` não adiciona ELO nem team target encoding. Hiperparâmetros otimizados num feature set diferente de produção.

- [ ] **P2.A11 - Sincronizar features em `walk_forward.py`**
  - `_build_features()` faltam rolling STD, EMA, H2H e `drop_redundant_features()`.

- [ ] **P2.A12 - `_build_ensemble_schedule` ignora parâmetro `algorithms`**
  - Para `ensemble_size` 25-35, `_build_hybrid_ensemble_schedule()` ignora config `algorithms`. Config `("xgboost",)` com size=30 receberia silenciosamente 4 algoritmos.
  - **Fix:** Validar compatibilidade ou fazer o schedule respeitar o parâmetro.

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
  - `src/japredictbet/agents/` — scaffolding vazio.
  - `rolling.py::add_rolling_features()` — dead code, nunca chamada.

- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`**
  - Poisson vive em `betting/engine.py`, violando boundary. Opções: (a) mover para `probability/poisson.py`, ou (b) atualizar AGENTS.md e ARCHITECTURE.md.

- [ ] **P2.C3 - Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Regex `r"[^a-z0-9\\s]"` em raw string. Config RandomForest enganoso no `algorithms`.

---

## Onda 4 — SHADOW Mode (Superbet Observacional)

**Objetivo:** Conectar coleta de odds reais ao `ConsensusEngine` em modo estritamente observacional, sem execução financeira.
**Dependências:** P2.D4 (Telegram bot) depende desta trilha.
**Novas dependências pip:** `httpx>=0.27.0`, `httpx-sse>=0.4.0`
**Novos arquivos:** `src/japredictbet/odds/superbet.py`, `data/mapping/superbet_teams.json`, `scripts/shadow_observe.py`, `tests/odds/test_superbet.py`
**Nota técnica:** Endpoint Superbet é SSE, não REST JSON. Campo `matchName` usa `·` (middle dot U+00B7) como separador.

- [ ] **P2.SH1 - Substituir `requests` por `httpx` no coletor**
  - Timeout configurável, `User-Agent` de navegador, tratamento HTTP 403/429/500.

- [ ] **P2.SH2 - Parsing SSE do feed Superbet**
  - Endpoint: `https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/all`
  - Stream linha-a-linha (`data:{json}\nretry:N\n`), cada evento <10KB.
  - Tolerante a eventos malformados (try/except por evento) e reconexão com backoff.
  - **Campos chave:** `eventId`, `matchName`, `sportId`, `categoryId`, `tournamentId`, `odds[].marketId`, `odds[].marketName`, `odds[].price`, `odds[].code`

- [ ] **P2.SH3 - Filtro de eventos e mercados de escanteios**
  - `sportId=5` (futebol), mercado `Total de Escanteios` (Over/Under).
  - Extração: `event_id`, `home_team`, `away_team`, `market_line`, `over_odds`, `under_odds`.
  - Split `matchName` por `·` (middle dot). Feed mistura esportes reais, virtuais e eSports.

- [ ] **P2.SH4 - Mapeamento Superbet → IDs internos**
  - Arquivo: `data/mapping/superbet_teams.json`. Equipes sem mapeamento geram WARNING e skip.

- [ ] **P2.SH5 - Integração com `ConsensusEngine` em Shadow Mode**
  - Para cada jogo válido, chamar `evaluate_with_consensus()` e registrar auditoria.
  - Shadow log: `logs/shadow_bets.log` com timestamp, match_id, odds, p_model_mean, edge, votos, status.
  - **Regra de segurança:** nenhum módulo deve executar aposta real.

- [ ] **P2.SH6 - Script executável de observação**
  - `SuperbetCollector` com CLI. Falhas de rede não derrubam execução. Resumo final em console.

- [ ] **P2.SH7 - Testes dedicados da trilha Shadow**
  - SSE multi-eventos, JSON malformado, HTTP 403/429/500, timeout, reconexão, time sem mapeamento, mercado inválido, esporte não-futebol, chamada ao ConsensusEngine, shadow log completo.

---

## Onda 5 — CI, Produto & Polish

**Objetivo:** Automatizar qualidade, melhorar observabilidade e experiência final.

### Bloco 5A — CI & Infraestrutura

- [ ] **P2.B1 - CI Básico (pytest em push)** — Coverage gate > 60%.
- [ ] **P2.B2 - Logging Estruturado por Aposta** — Lambdas, votos, edge, threshold, stake, resultado.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`** — Usar `utils/logging.py` existente.
- [ ] **P2.B5 - Completar `pyproject.toml`** — Metadata, entry points, dev dependencies.

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

## Matriz de Maturidade (03-APR-2026)

| Dimensão | Nota | Comentário |
|----------|------|------------|
| Arquitetura | 9/10 | Design modular, bem documentada |
| Implementação | 8/10 | P0+P1 completos; penalizado por `update_pipeline.py` non-functional e divergências de feature set |
| Documentação | 8/10 | 60 inconsistências corrigidas (P2.C4). Incrementais futuros apenas |
| Testes | 7/10 | 165 testes (17 arquivos), ~60% cobertura. `data/ingestion.py` sem testes |
| Reprodutibilidade | 9/10 | SHA256, seeds, requirements pinados, config-driven, configs sincronizados |
| Production-Ready | 8/10 | Pipeline completo com calibração, risk e CLV. Penalizado por pickle sem hash e update_pipeline |

---

## Referências Rápidas

| Recurso | Arquivo |
|---------|---------|
| Histórico completo (P0, P0-FIX, P1, Onda 1) | [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) |
| Detalhes P0 (9 itens) | [`P0_COMPLETION_SUMMARY.md`](P0_COMPLETION_SUMMARY.md) |
| Sumário executivo | [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) |
| Arquitetura do sistema | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Validação e testes | [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) |
