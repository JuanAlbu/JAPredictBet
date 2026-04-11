# JA PREDICT BET — ROADMAP P2+ (REVISÃO 11-APR-2026)

**Data da Revisão:** 11 de Abril, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 parcial | Onda 4 parcial — 218/218 testes passando (21 arquivos). 106 features. 30 modelos (11 XGB + 10 LGB + 5 Ridge + 4 EN).
**Histórico Completo:** Todos os itens concluídos (P0, P0-FIX, P1, Onda 1, Onda 4 parcial) documentados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).
**Próxima Ação:** Onda 4 residual (SH4 preenchimento, SH11-SH19). Onda 2 residual (B3, B7, B8, C7).

### Sequência de Implementação Recomendada

| Passo | Item | Status | Descrição |
|-------|------|--------|-----------|
| 1 | SDK LLM + dotenv | ✅ feito | `openai>=1.14.0` + `python-dotenv>=1.0.1` em `requirements.txt` |
| 2 | `.env.example` | ✅ feito | Template com `OPENAI_API_KEY`, `API_FOOTBALL_KEY`, `SUPERBET_*` |
| 3 | **SH8** — `gatekeeper.py` | ✅ feito | Agente LLM (herda `BaseAgent`), system prompt V25, pré-filtro min_odd |
| 4 | **SH9** — `gatekeeper_live_pipeline.py` | ✅ feito | Orquestrador T-60: contexto → ensemble → Gatekeeper → shadow log |
| 5 | **SH5b** — Integração ConsensusEngine | ✅ feito | `evaluate_with_consensus()` integrado no pipeline |
| 6 | **SH6** — `shadow_observe.py` | ✅ feito | CLI entry point com `--dry-run`, `--verbose`, `--models-dir` |
| 7 | **SH7** — Testes Shadow | ✅ feito | `test_superbet.py` (20 tests) + `test_gatekeeper.py` (14 tests) + `test_analyst.py` (17 tests) |
| 7b | **SH20** — Feature Store | ✅ feito | `feature_store.py` + `refresh_features.py` — pre-computed rolling features (Option C) |
| 7c | **SH21** — Dynamic Tournament Whitelist | ✅ feito | `get_active_tournament_ids()` em `feature_store.py` — liga folders → Superbet IDs |
| 7d | **SH22** — Analyst Agent (multi-market) | ✅ feito | `analyst.py` — LLM evaluation de 1x2/BTTS/Over-Under (não-escanteios) |
| 7e | **SH23** — Pre-match architecture | ✅ feito | `pre_match_odds.py` + scraper auto-save JSON + `--pre-match` flag no shadow_observe |
| 8 | **SH4** — Team mapping | ⬜ pendente | Preenchimento manual de `superbet_teams.json` por liga |
| 9 | **SH10** — Superbet Scraper CLI | ✅ feito | `scripts/superbet_scraper.py` — SSE discovery + REST API full markets |
| 10 | **SH11** — Tournament IDs faltantes | ⬜ pendente | Adicionar Bundesliga + Premier League a `league_tournament_ids.json` |
| 11 | **SH12** — Filtro de mercados refinado | ⬜ pendente | Reduzir ruído de combo/player markets no display padrão |
| 12 | **SH13** — Integrar scraper no pipeline | ⬜ pendente | Alimentar `gatekeeper_live_pipeline` com odds do scraper REST |
| 13 | **SH14** — Limpeza temp files | ⬜ pendente | Remover `_probe_event.py`, `scraper_*.txt`, `probe_out.txt`, `_list_markets.py` |
| 14 | **SH15** — Corrigir threshold do consenso no live pipeline | ⬜ pendente | `gatekeeper_live_pipeline.py` usa `config.consensus_threshold` em vez de `config.value.consensus_threshold` |
| 15 | **SH16** — Implementar `--dry-run` real | ⬜ pendente | Pular OpenAI/Gatekeeper/Analyst quando `--dry-run` estiver ativo |
| 16 | **SH17** — Separar `Superbet-only` de modo T-60 | ⬜ pendente | Evitar avaliar jogos fora da janela quando `API_FOOTBALL_KEY` estiver ausente |
| 17 | **SH18** — Validar semântica do H2H no `FeatureStore` | ⬜ pendente | Garantir que features H2H sejam do par do confronto futuro, não da última linha isolada por time |
| 18 | **SH19** — Cobertura de integração da trilha Shadow | ⬜ pendente | Testar `gatekeeper_live_pipeline`, `ContextCollector`, `FeatureStore`, `pre-match` e `dry-run` |

---

## Visão Geral

Este documento contém **apenas itens em aberto**, organizados em ondas de execução por prioridade.
Itens concluídos são transferidos para [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) ao serem fechados.

**Itens em aberto:** 18 (P2) + 2 (P3) + 5 (R&D) = 25 total

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
**Novas dependências pip:** `httpx>=0.28.0`, `openai>=1.14.0`, `python-dotenv>=1.0.1`
**Credenciais:** `.env.example` criado na raiz (`.env` protegido por `.gitignore`).
**Arquivos criados:**
- `src/japredictbet/odds/superbet_client.py` ✅
- `src/japredictbet/data/context_collector.py` ✅
- `src/japredictbet/agents/base.py` ✅
- `src/japredictbet/agents/registry.py` ✅
**Arquivos pendentes:**
- `src/japredictbet/agents/gatekeeper.py` ✅
- `src/japredictbet/pipeline/gatekeeper_live_pipeline.py` ✅
- `scripts/shadow_observe.py` ✅
- `tests/odds/test_superbet.py` ✅
- `tests/agents/test_gatekeeper.py` ✅
- `tests/agents/test_analyst.py` ✅
- `src/japredictbet/agents/analyst.py` ✅
- `src/japredictbet/odds/pre_match_odds.py` ✅
- `src/japredictbet/data/feature_store.py` ✅
- `scripts/refresh_features.py` ✅
- `docs/PROMPT_ANALYST.md` ✅
- `data/mapping/superbet_teams.json` — SH4 (template criado ✅, preenchimento manual pendente)
**Config adicionada:** Blocos `gatekeeper`, `api_keys`, `superbet_shadow`, `api_football` em `config.yml` + dataclasses correspondentes em `config.py`.
**Nota técnica:** Endpoint Superbet usa SSE para discovery e REST JSON para enrichment (`/v2/pt-BR/events/{eventId}`). Campo `matchName` usa `·` (middle dot U+00B7) como separador. Preços em formato centesimal (>=100 → /100).

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

### Bloco 4D — Superbet Scraper CLI (11-APR-2026)

- [x] **P2.SH10 - Superbet Scraper (SSE + REST API)** ✅ (11-APR-2026)
  - `scripts/superbet_scraper.py` (~800 linhas).
  - **Fase 1 — SSE Discovery:** Conecta a dois endpoints SSE (prematch para jogos futuros, all para live). Coleta `event_id`, equipes, liga, horário.
  - **Fase 2 — REST Enrichment:** Para cada evento, `GET /v2/pt-BR/events/{eventId}` retorna TODOS os mercados (700+ por jogo, 3000+ seleções). Parsing completo de odds centesimais (>=100 → /100).
  - **Mercados cobertos:** Resultado Final, Total de Gols, Dupla Chance, Ambas as Equipes Marcam, Total de Escanteios, Total de Cartões, Total de Finalizações, Total de Chutes no Gol, Handicap, Handicap Asiático, combos de jogador.
  - **CLI:** `python scripts/superbet_scraper.py <dia>` — aceita `hoje`, `amanha`, `domingo`, `YYYY-MM-DD`, `todos`.
  - **Flags:** `--leagues`, `--stream-seconds`, `--json`, `--all-markets`, `--quick` (SSE only), `--debug`, `--verbose`, `--no-save`.
  - **Auto-save:** `data/odds/pre_match/{date}.json` com snapshot completo.
  - **Filtro:** `MARKETS_OF_INTEREST` (15 padrões) + `PLAYER_MARKET_KEYWORDS` (4 padrões).
  - **Nota técnica:** Preços centesimais (250 → 2.50). Middle-dot `·` (U+00B7) como separador em `matchName`. URLs com normalização NFKD para caracteres especiais.

- [ ] **P2.SH11 - Adicionar Bundesliga + Premier League ao mapeamento de ligas**
  - `data/mapping/league_tournament_ids.json` tem 12 ligas mas faltam Bundesliga (1ª) e Premier League.
  - **Fix:** Localizar `tournament_id` correto no feed SSE Superbet e adicionar ao JSON.
  - **Nota:** Bundesliga 2 (ID existente) ≠ Bundesliga 1.

- [ ] **P2.SH12 - Refinar filtro de mercados no scraper**
  - Com `--all-markets` desligado, combos de jogador com keywords tipo "Ambas as equipes marcam" passam no filtro por substring match.
  - **Fix:** Match mais estrito (exact ou regex com word boundary) para mercados core vs combos.
  - Considerar flag `--player-markets` separado para exibir/ocultar mercados de jogador.

- [ ] **P2.SH13 - Integrar scraper REST no pipeline live**
  - Scraper é standalone (`scripts/`). Pipeline live (`gatekeeper_live_pipeline.py`) usa `SuperbetCollector` (SSE only, 3 mercados).
  - **Fix:** Extrair lógica REST do scraper para `superbet_client.py` (método `fetch_full_event(event_id)`) e alimentar `MatchContext` com odds completas.
  - **Impacto:** Gatekeeper LLM receberia 15+ mercados em vez de 3, melhorando análise de value.

- [ ] **P2.SH14 - Limpeza de arquivos temporários**
  - Remover: `_probe_event.py`, `_list_markets.py`, `scraper_*.txt`, `probe_out.txt`, `markets_result.txt`.
  - **Nota:** Manter `data/odds/pre_match/*.json` (snapshots úteis).

- [ ] **P2.SH15 - Corrigir uso de `consensus_threshold` no live pipeline**
  - `gatekeeper_live_pipeline.py` ainda referencia `self._config.consensus_threshold`, mas o valor real mora em `self._config.value.consensus_threshold`.
  - **Risco:** o consenso cai no `except`, fica silenciosamente `None` e o Gatekeeper roda sem suporte do ensemble.

- [ ] **P2.SH16 - Implementar `--dry-run` de verdade**
  - `scripts/shadow_observe.py` expõe `--dry-run`, mas o fluxo ainda exige `OPENAI_API_KEY` e instancia `GatekeeperAgent` / `AnalystAgent`.
  - **Fix:** pular chamadas OpenAI e permitir execução local de coleta + consenso + logging sem credenciais LLM.

- [ ] **P2.SH17 - Separar semântica de `Superbet-only` vs T-60**
  - `context_collector.py` hoje retorna todos os snapshots do Superbet quando `API_FOOTBALL_KEY` está ausente, sem filtro de kickoff, mas continua logando como janela T-60.
  - **Risco:** o pipeline avalia jogos fora da janela operacional e mistura modo degradado com modo T-60.
  - **Fix:** ou aplicar filtro temporal alternativo, ou renomear/segregar explicitamente o modo degradado.

- [ ] **P2.SH18 - Validar H2H no `FeatureStore` para inferência ao vivo**
  - O store reduz para "última linha por time" e depois compõe `home` + `away`; isso pode carregar features H2H do último adversário de cada time, não do par do confronto futuro.
  - **Risco:** consenso roda com features semanticamente incorretas mesmo quando o pipeline não quebra.
  - **Fix:** recomputar H2H para o par consultado ou excluir H2H do `FeatureStore` até haver reconstrução correta.

- [ ] **P2.SH19 - Criar testes de integração da trilha Shadow**
  - Hoje há boa cobertura unitária para `test_superbet.py`, `test_gatekeeper.py` e `test_analyst.py`, mas faltam testes para `gatekeeper_live_pipeline`, `ContextCollector`, `FeatureStore`, `pre-match` e `dry-run`.
  - **Risco:** regressões de integração passam despercebidas, especialmente em fallback/degradação silenciosa.

### Bloco 4B — Contexto T-60 (implementado)

- [x] **P2.SH5a - Context Collector (API-Football + Superbet)** ✅ (11-APR-2026)
  - `src/japredictbet/data/context_collector.py`:
    - `ApiFootballClient` — fixtures do dia, lineups confirmadas, injuries/suspensions, standings.
    - `ContextCollector` — orquestra Superbet + API-Football, filtra janela T-60, fuzzy match de equipes.
    - `MatchContext` dataclass com serialização JSON para injeção no LLM.
  - API keys resolvidas de env vars (`${API_FOOTBALL_KEY}`) — nunca commitadas.
  - Cada chamada à API isolada via `_safe_call()` — falha parcial não derruba pipeline.

### Bloco 4C — Gatekeeper Agent + Pipeline (✅ implementado)

- [x] **P2.SH5b - Integração com `ConsensusEngine` em Shadow Mode** ✅ (11-APR-2026)
  - `gatekeeper_live_pipeline.py` integra `ConsensusEngine.evaluate_with_consensus()` para cada jogo.
  - Shadow log: `logs/shadow_bets.log` em formato JSONL com timestamp, event_id, odds, ensemble stats, gatekeeper decision.
  - **Regra de segurança:** nenhum módulo executa aposta real.

- [x] **P2.SH6 - Script executável de observação** ✅ (11-APR-2026)
  - `scripts/shadow_observe.py` com CLI (`--config`, `--models-dir`, `--dry-run`, `-v`).
  - Carrega `.env` via `python-dotenv`. Resumão final formatado no console.

- [x] **P2.SH7 - Testes dedicados da trilha Shadow** ✅ (11-APR-2026)
  - `tests/odds/test_superbet.py`: SSE parsing (5), team names (3), market detection (3), odds extraction (5), dataclasses (3), sport filter (1) = 20 testes.
  - `tests/agents/test_gatekeeper.py`: pre-filter (4), LLM parsing (6), failure handling (1), BaseAgent contract (2), constructor (1) = 14 testes.
  - `tests/agents/test_analyst.py`: pre-filter (3), LLM parsing (5), market evaluation (4), failure handling (2), constructor (3) = 17 testes.
  - Total: 218/218 passando (21 arquivos).

- [x] **P2.SH8 - Agente Gatekeeper (LLM + decisão)** ✅ (11-APR-2026)
  - `src/japredictbet/agents/gatekeeper.py` herdando de `BaseAgent`.
  - Encapsula `PROMPT_MESTRE V25 FINAL` como system prompt.
  - `evaluate_match(match_context_json)` → JSON com `status` (APPROVED / NO BET), `stake`, `odd_superbet`, `justificativa`.
  - Pré-filtro Python hardcoded: bloqueia se odd Superbet < `min_odd` (1.60) antes de enviar ao LLM.
  - **Dependência:** `OPENAI_API_KEY` configurada em `.env` (template em `.env.example`).
  - **SDK:** `openai>=1.14.0` (já em `requirements.txt`).

- [x] **P2.SH9 - Pipeline Gatekeeper Live (orquestração T-60)** ✅ (11-APR-2026)
  - `src/japredictbet/pipeline/gatekeeper_live_pipeline.py`.
  - Fluxo: Collect matches → Load ensemble → Consensus vote → Gatekeeper LLM → Cap entries → JSONL shadow log.
  - Factory method `from_config()` constrói pipeline completo a partir de `PipelineConfig`.
  - Max 5 entradas/dia (`gatekeeper.max_entries_per_day`).

### Bloco 4E — Feature Store, Analyst Agent & Pre-match (✅ implementado — 11-APR-2026)

- [x] **P2.SH20 - Feature Store (Option C — Daily Pre-computation)** ✅ (11-APR-2026)
  - `src/japredictbet/data/feature_store.py`: `FeatureStore.build()/.save()/.load()/.get_match_features()`.
  - Lê CSVs de `data/raw/leagues/`, aplica feature engineering completo, salva Parquet com uma linha por equipe.
  - Fuzzy matching (similarity >= 0.82) para variações de nome de equipe.
  - `scripts/refresh_features.py`: CLI para rebuild diário (`--leagues-dir`, `--output`, `--config`).

- [x] **P2.SH21 - Dynamic Tournament Whitelist** ✅ (11-APR-2026)
  - `get_active_tournament_ids()` em `feature_store.py`: escaneia pastas de `data/raw/leagues/`, faz match case-insensitive com `league_tournament_ids.json`.
  - Substitui lista estática de tournament IDs no config. Pipeline Live filtra automaticamente por ligas com dados históricos.

- [x] **P2.SH22 - Analyst Agent (Multi-Market LLM)** ✅ (11-APR-2026)
  - `src/japredictbet/agents/analyst.py`: `AnalystAgent(BaseAgent)` para mercados não-escanteios.
  - Avalia 1x2, BTTS, Over/Under Goals via LLM (PROMPT_ANALYST.md como system prompt).
  - Output: `AnalystResult` com lista de `MarketEvaluation` (status, stake, edge, red_flags).
  - Pré-filtro Python: rejeita se nenhuma odd não-corner ≥ `min_odd`.
  - `docs/PROMPT_ANALYST.md`: system prompt dedicado.
  - `tests/agents/test_analyst.py`: 17 testes.

- [x] **P2.SH23 - Pre-match Architecture Split** ✅ (11-APR-2026)
  - `src/japredictbet/odds/pre_match_odds.py`: Carrega snapshots JSON do scraper → `List[MatchContext]`.
  - Helpers: `_is_corner_market()`, `_is_match_odds_market()`, `_is_btts_market()`.
  - `scripts/superbet_scraper.py`: Auto-save para `data/odds/pre_match/{date}.json`, flag `--no-save`.
  - `scripts/shadow_observe.py`: Flag `--pre-match DATE` (aceita `hoje`, `amanha`, `YYYY-MM-DD`).
  - `gatekeeper_live_pipeline.py`: `run(pre_match_date=...)` carrega de JSON em vez de SSE.
  - `ShadowEntry` expandido com campos `analyst_status`, `analyst_best_pick`, `analyst_markets`.
  - **Dois modos operacionais:** Pre-match (scraper → JSON → pipeline) e Live (SSE + API-Football → pipeline).

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
| Arquitetura | 9.5/10 | Design modular. Gatekeeper + Analyst dual-agent pipeline. Feature Store (Option C). Pre-match + Live modes |
| Implementação | 9/10 | P0+P1+Onda4 completos. Scraper CLI + Pre-match loader + Analyst Agent. Penalizado por `update_pipeline.py` non-functional, holdout não-cronológico e hyperopt params não integrados |
| Documentação | 8.5/10 | Drift corrigido (C6). AGENTS.md, ARCHITECTURE.md, next_pass.md sincronizados |
| Testes | 8/10 | 218 testes (21 arquivos). Superbet + Gatekeeper + Analyst cobertos. `data/ingestion.py` e `features/` com cobertura parcial |
| Reprodutibilidade | 9/10 | SHA256, seeds, requirements pinados, config-driven, `.env.example` |
| Production-Ready | 8/10 | Shadow pipeline operacional. Dual-agent (corners + multi-market). Penalizado por pickle sem hash, hyperopt params não integrados, `artifacts/models/` vazio |

---

## Referências Rápidas

| Recurso | Arquivo |
|---------|---------|
| Histórico completo (P0, P0-FIX, P1, Onda 1) | [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) |
| Detalhes P0 (9 itens) | [`P0_COMPLETION_SUMMARY.md`](P0_COMPLETION_SUMMARY.md) |
| Sumário executivo | [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) |
| Arquitetura do sistema | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Validação e testes | [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) |
