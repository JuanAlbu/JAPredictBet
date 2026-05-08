# JA PREDICT BET — HISTÓRICO DE ITENS CONCLUÍDOS

**Criado:** 03 de Abril, 2026
**Última atualização:** 07-MAI-2026
**Propósito:** Registro permanente de todos os itens de roadmap concluídos, com datas, evidências e detalhes de implementação. Itens são movidos do roadmap ativo (`next_pass.md`) para cá ao serem fechados.

---

## SCRAPER.1 — Migração do Scraper para REST by-date API (06-MAI-2026)

> **Status:** ✅ CONCLUÍDO — Scraper migrado de SSE para REST by-date API como fonte primária. Testado com sexta-feira (26 eventos) e quinta-feira (5 eventos filtrados).

### Problema
O Superbet é uma SPA (Single Page Application) que retorna 3227 bytes de HTML shell vazio. O feed SSE (`/subscription/v2/pt-BR/events/prematch`) só publica eventos 1-2 dias antes da partida, tornando impossível buscar jogos de 6+ dias no futuro. Tentativas com HTTPX direto em URLs do site retornavam apenas o shell SPA.

### Descoberta
Interceptação de tráfego de rede via Playwright (navegador headless Chromium) revelou um endpoint REST não documentado:

```
GET /v2/pt-BR/events/by-date?currentStatus=active&offerState=prematch
    &startDate=2026-05-08+03:00:00&endDate=2026-05-09+13:00:00&sportId=5
```

Este endpoint funciona diretamente via HTTPX (sem Playwright) e retorna **todos os eventos** para qualquer data futura — 354+ eventos brutos por dia.

### Implementação
| Alteração | Arquivo | Descrição |
|-----------|---------|-----------|
| Constante `BY_DATE_API_URL` | `scripts/superbet_scraper.py:67` | URL do endpoint by-date com query params |
| `_collect_raw_events_via_by_date_api()` | `scripts/superbet_scraper.py:280` | Função que consulta REST API, filtra por TIDs conhecidos |
| `_collect_raw_events_with_fallback()` | `scripts/superbet_scraper.py:353` | Tenta REST API primeiro, SSE como fallback |
| Flag `--use-sse` | `scripts/superbet_scraper.py:1088` | Força fallback manual ao SSE |

### Arquivos Modificados
- `scripts/superbet_scraper.py` — Adicionada função by-date, fallback, flag `--use-sse`
- `docs/ARCHITECTURE.md` — Seção do scraper atualizada com nova arquitetura

### Arquivos Criados (durante desenvolvimento)
- `scripts/_scrape_superbet_playwright.py` — Playwright scraper (interceptação de rede que levou à descoberta)
- `data/_playwright_sexta_feira.json` / `data/_playwright_quinta_feira.json` — Capturas de tráfego (removidos após consolidação)

### Arquivos Removidos (limpeza)
- `scripts/_test_by_date.py` — Teste temporário (funcionalidade incorporada)
- `scripts/_scrape_sexta.py` — Tentativa httpx que só retornava SPA shell
- 24 scripts `_*.py` de descoberta one-off
- 27 arquivos `data/_*` de investigação intermediária

### Testes Realizados
| Comando | Resultado |
|---------|-----------|
| `python scripts/superbet_scraper.py sexta` | 26 eventos filtrados, 18 na data alvo, odds completas |
| `python scripts/superbet_scraper.py quinta --leagues libertadores sul_americana europa_league` | 5 eventos (Flamengo, São Paulo, Aston Villa, etc.) |
| `python scripts/superbet_scraper.py quinta` | 5 eventos (todas as 19 ligas configuradas) |

### Lições Aprendidas
1. O Superbet expõe uma REST API rica que não está documentada — descoberta via interceptação Playwright
2. A API by-date aceita datas futuras arbitrárias e retorna todos os eventos, resolvendo a limitação do SSE
3. O endpoint por-evento (`/v2/pt-BR/events/{eventId}`) retorna 700+ mercados por jogo
4. Playwright foi necessário apenas para descobrir a API — a solução final usa HTTPX puro

---

## SCRAPER.2 — Multi-Scroll Playwright + Mapeamento `list[int]` com TID 51375 (06-MAI-2026)

> **Status:** ✅ CONCLUÍDO — Playwright agora executa 5 scrolls incrementais com waits de 2s para capturar seções lazy-loaded. TID 51375 (Sul-Americana Gr.H) adicionado ao mapeamento direto. `league_tournament_ids.json` suporta `list[int]`. Total: 20 TIDs rastreados.

### Problema
Após a migração para REST by-date API (SCRAPER.1), identificou-se um gap de 3 jogos que o Playwright não encontrava vs a REST API:

| Jogo | TID | Causa |
|------|-----|-------|
| Freiburg vs Braga | 688 | SPA renderiza apenas 1 evento por TID; múltiplos jogos no mesmo TID não apareciam |
| Ind Medellín vs Flamengo | 51372 | SPA renderiza apenas 1 evento por TID |
| O'Higgins vs São Paulo | 51375 | TID não estava no mapeamento direto — apenas em comentário no JSON |

### Melhoria 1 — Multi-Scroll Playwright
O scraper Playwright fazia um único `scrollTo(0, document.body.scrollHeight)` que não era suficiente para acionar todas as seções lazy-loaded da SPA.

**Antes:**
```python
page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
page.wait_for_timeout(3000)
```

**Depois:**
```python
page_height = page.evaluate("document.body.scrollHeight")
steps = 5
for i in range(1, steps + 1):
    scroll_to = int(page_height * (i / steps))
    page.evaluate(f"window.scrollTo(0, {scroll_to})")
    page.wait_for_timeout(2000)
page.wait_for_timeout(3000)
```

5 scrolls progressivos (20%, 40%, 60%, 80%, 100%) com 2s de espera entre cada um + 3s final. Isso garante que seções carregadas sob demanda sejam renderizadas.

### Melhoria 3 — Mapeamento Direto TID 51375
A Sul-Americana tem **dois** tournament IDs na temporada 2026:
- `51372` — Grupo A-F (já mapeado como `sul_americana`)
- `51375` — Grupo G-H (estava apenas em comentário no JSON, não no mapeamento ativo)

**Antes:**
```json
{ "sul_americana": 51372 }
```

**Depois:**
```json
{ "sul_americana": [51372, 51375] }
```

Isso exigiu mudança de tipo no `league_tournament_ids.json`: de `dict[str, int]` para `dict[str, int | list[int]]`.

### Arquivos Modificados

| Arquivo | Alteração |
|---------|-----------|
| [`data/mapping/league_tournament_ids.json`](data/mapping/league_tournament_ids.json) | `sul_americana` mudou de `51372` (int) para `[51372, 51375]` (list) |
| [`scripts/superbet_scraper.py`](scripts/superbet_scraper.py) | Multi-scroll Playwright (linhas 464-476); `_load_league_ids()` retorna `dict[str, int \| list[int]]`; `_build_tid_to_league()` achata listas em flat dict; `main()` usa `_flatten_tids()` para construir `tournament_filter` |
| [`src/japredictbet/data/feature_store.py`](src/japredictbet/data/feature_store.py) | `get_active_tournament_ids()` trata valores `list[int]` com `isinstance(v, list)` |
| [`scripts/_discover_tournaments.py`](scripts/_discover_tournaments.py) | `load_known_ids()` retorna `dict[str, int \| list[int]]`; `known_tids` itera com `isinstance()` |

### Testes Realizados

| Comando | Resultado |
|---------|-----------|
| `python scripts/superbet_scraper.py hoje --no-playwright --quick --no-save` | "20 ligas (TIDs: ... 51372, 51375)" ✅ |
| `python scripts/superbet_scraper.py hoje --quick --no-save` | Playwright com multi-scroll, sem erros ✅ |

### Impacto
- **20 TIDs rastreados** (up from 19)
- Sul-Americana agora captura **ambos os grupos** (G-H incluso)
- Playwright mais robusto para SPA com lazy-loading
- Nenhum teste existente quebrado — todos os consumidores do JSON tratam `list[int]`

---

## FASE 0 — Correção Crítica P0 (05-MAI-2026)

> **Status:** ✅ CONCLUÍDO — Fallback 2024 removido. Standings indisponíveis = `null` explícito. 254/254 testes sem regressão.

| Item | Descrição | Data |
|------|-----------|------|
| P0.FALLBACK | Remover fallback `2024` → `None` nos 2 pontos de `context_collector.py` (`collect_upcoming` + `enrich_pre_match_contexts`) | 05-MAI-2026 |
| P0.FALLBACK | Atualizar `PROMPT_MESTRE.md` — Pilar 5: instrução para tratar `home_standing: null` como "dados indisponíveis — não usar como fator de decisão" | 05-MAI-2026 |
| P0.FALLBACK | Verificar `to_llm_context()` — `_slim_standing()` já retorna `None` e só adiciona ao payload se não for None ✅ | 05-MAI-2026 |
| P0.FALLBACK | Registrar web scraping (Soccerway, Flashscore) como desenvolvimento futuro em `context_enrichment_study.md` Seção 3.4 | 05-MAI-2026 |

**Arquivos modificados:** `context_collector.py` (2 blocos), `PROMPT_MESTRE.md`, `context_enrichment_study.md`, `next_pass.md`, `PROJECT_CONTEXT.md`, `COMPLETION_HISTORY.md`

**Contexto:** O plano free da API-Football v3 só cobre temporadas até 2024. O fallback silencioso injetava standings de 2024 em análises de jogos de 2026 — dados piores que ausência, pois induziam o LLM a conclusões incorretas sobre o momento da equipe. A correção substitui o fallback por `None` explícito e instrui o Gatekeeper a ignorar standings indisponíveis.

---

## P2 Refactoring — Unified Architecture (03-MAI-2026)

> **Status:** ✅ COMPLETO — 254/254 testes passando. 7 fases executadas entre 03-04 MAI 2026.

| Item | Descrição | Data |
|------|-----------|------|
| P2-ARCH-1 | Gatekeeper + Analyst merge → single GatekeeperAgent (all markets via Prompt Mestre V26) | 03-MAI-2026 |
| P2-ARCH-2 | Shadow Pipeline simplified: single LLM motor (30-model ensemble = Mode 1 only) | 03-MAI-2026 |
| P2-ARCH-3 | Scraper pre-filter added (--min-odd + --markets whitelist) | 03-MAI-2026 |
| P2-ARCH-4 | `analyst.py` removed; `PROMPT_ANALYST.md` marked obsolete | 03-MAI-2026 |
| P2-ARCH-5 | `config.yml` / `config.py` — removed `feature_store_path` | 03-MAI-2026 |
| P2-ARCH-6 | 14 documentation files updated to reflect unified architecture | 03-MAI-2026 |
| P2-ARCH-7 | Test suite: 254/254 passing (27 gatekeeper + 40 shadow integration tests) | 03-MAI-2026 |

---

## P0 — Pipeline Core (10 de 10 — FECHADO em 03-MAI-2026)

> 9 itens implementados e validados com 101 partidas reais + 50 recentes + stress test random lines.
> **P0.6 reaberto (03-MAI-2026):** Código ainda usa `rng.shuffle()` em vez de split cronológico por data.
> **FIX P2.B8 (03-MAI-2026):** `_build_temporal_split()` reescrita com strict chronological holdout — sem shuffle, split por posição de índice (assume DataFrame ordenado por data). P0.6 fechado definitivamente.
> Detalhes completos em [`P0_COMPLETION_SUMMARY.md`](P0_COMPLETION_SUMMARY.md).

| Item | Descrição | Data |
|------|-----------|------|
| P0.1 | Remoção de 4 hardcodes do CLI | 30-MAR-2026 |
| P0.2 | Ensemble híbrido 70/30 (21 boosting + 9 linear) | 30-MAR-2026 |
| P0.3 | Dynamic margin rule (threshold +50% quando margem < 0.5) | 30-MAR-2026 |
| P0.4 | Dynamic feature selection refactor | 30-MAR-2026 |
| P0.5 | Parallel training (3-5x speedup) | 30-MAR-2026 |
| P0.6 | Strict temporal holdout (via P2.B8) | 03-MAI-2026 |
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

### P2.B6 — Centralizar `_load_config()` em `config.py` (RESOLVIDO — 03-APR-2026)

- `PipelineConfig.from_yaml(path)` criado.
- 5 scripts atualizados: `run.py`, `consensus_accuracy_report.py`, `hyperopt_search.py`, `model_inputs_correlation.py`, `update_pipeline.py`.

### P2.A9 — Sincronizar keywords de feature selection (RESOLVIDO — 03-APR-2026)

- `_is_model_feature_candidate()` agora inclui `_rolling` e `_momentum`, sincronizado com `_is_allowed_feature()`.

### P2.A10 — Sincronizar features em `hyperopt_search.py` (RESOLVIDO — 03-APR-2026)

- Adicionado ELO ratings e team target encoding em `_prepare_data()`. Corrigida chamada `_valid_training_mask()`.

### P2.A11 — Sincronizar features em `walk_forward.py` (RESOLVIDO — 03-APR-2026)

- Adicionados rolling STD, EMA, H2H e `drop_redundant_features()` em `_build_features()`. `WalkForwardConfig` expandido.

### P2.A12 — `_build_ensemble_schedule` respeita parâmetro `algorithms` (RESOLVIDO — 03-APR-2026)

- Hybrid mode agora só ativa quando `algorithms` contém tanto boosters quanto linear. `_build_hybrid_ensemble_schedule` parametrizado.

### Itens Absorvidos

| Item Original | Absorvido Por | Motivo |
|---------------|--------------|--------|
| P2.A4 — Ampliar testes de `odds/collector.py` | P2.SH7 | Testes Shadow cobrem timeout, JSON inválido, resposta vazia com escopo mais completo |
| P2.A7 — Adicionar timeout em `odds/collector.py` | P2.SH1 | Migração para httpx inclui timeout configurável, User-Agent, error handling |
| P2.D3 — Integração com APIs Real-time | P2-SHADOW | Trilha SH1-SH7 implementa integração real-time em modo observacional |

---

## P2 — Onda 4 Itens Concluídos (11-APR-2026)

### Bloco 4A-4D: Superbet + Gatekeeper + Scraper

> Implementados entre 03-APR e 11-APR-2026. Shadow mode operacional com dual-agent (substituído por Gatekeeper unificado em 03-MAI-2026).

| Item | Descrição | Data |
|------|-----------|------|
| SH1 | httpx client com retry/backoff | 11-APR-2026 |
| SH2 | SSE parsing do feed Superbet | 11-APR-2026 |
| SH3 | Filtro de eventos e mercados (corners, 1x2, BTTS) | 11-APR-2026 |
| SH5a | Context Collector (API-Football + Superbet) | 11-APR-2026 |
| SH5b | Integração ConsensusEngine em Shadow Mode | 11-APR-2026 |
| SH6 | `shadow_observe.py` CLI | 11-APR-2026 |
| SH7 | Testes Shadow (20 + 14 + 17 = 51 testes) | 11-APR-2026 |
| SH8 | GatekeeperAgent (LLM corners, PROMPT_MESTRE V25) | 11-APR-2026 |
| SH9 | GatekeeperLivePipeline (T-60 orchestration) | 11-APR-2026 |
| SH10 | Superbet Scraper CLI (SSE + REST, ~800 linhas) | 11-APR-2026 |

### Bloco 4E: Feature Store + Analyst + Pre-match (11-APR-2026)

| Item | Descrição | Arquivos | Testes |
|------|-----------|----------|--------|
| SH20 | Feature Store (Option C — daily pre-computation) | `feature_store.py`, `refresh_features.py` | Integrado |
| SH21 | Dynamic Tournament Whitelist | `get_active_tournament_ids()` em feature_store.py | Integrado |
| SH22 | AnalystAgent (multi-market LLM: 1x2/BTTS/Over-Under) | `analyst.py`, `PROMPT_ANALYST.md` | 17 testes |
| SH23 | Pre-match Architecture Split | `pre_match_odds.py`, scraper auto-save, `--pre-match` flag | Integrado |

**Detalhes:**
- **Feature Store:** Lê CSVs de `data/raw/leagues/`, aplica rolling + H2H + ELO + matchup, salva Parquet com uma linha por equipe. Fuzzy matching (≥0.82) para variações de nome.
- **Dynamic Whitelist:** Elimina lista estática de tournament IDs. `get_active_tournament_ids()` escaneia pastas de leagues e faz match case-insensitive com `league_tournament_ids.json`.
- **AnalystAgent (obsoleto desde 03-MAI-2026):** Herdava `BaseAgent`. Avaliava mercados não-escanteios via OpenAI (PROMPT_ANALYST.md). Escopo migrado para GatekeeperAgent unificado (Prompt Mestre V26).
- **Pre-match Split:** `pre_match_odds.py` carrega JSON do scraper → `List[MatchContext]`. `shadow_observe.py --pre-match hoje` aciona modo pre-match. `ShadowEntry` expandido com campos `analyst_*`.

### SH15 — Corrigir namespace `consensus_threshold` (RESOLVIDO — 12-APR-2026)

- **Arquivo:** `src/japredictbet/pipeline/gatekeeper_live_pipeline.py`
- **Bug:** `self._config.consensus_threshold` → `self._config.value.consensus_threshold`. Atributo vive em `ValueConfig`, não `PipelineConfig`.
- **Fix:** Linha ~492 corrigida. Crash em runtime eliminado.

### SH16 — Implementar `--dry-run` de verdade (RESOLVIDO — 12-APR-2026)

- **Arquivos:** `scripts/shadow_observe.py`, `src/japredictbet/pipeline/gatekeeper_live_pipeline.py`
- **Bug:** Flag `--dry-run` era dead code — `sys.exit(1)` disparava antes por falta de `OPENAI_API_KEY`.
- **Fix (3 partes):**
  1. API key check gated: `if not os.getenv("OPENAI_API_KEY") and not args.dry_run:`
  2. `dry_run` flag threaded: `from_config()` → `run()` → `_evaluate_single_match()`
  3. Agents opcionais: quando `dry_run=True`, gatekeeper é `None`; avaliação retorna `GatekeeperResult(status="DRY_RUN")` stub.
- **Validação:** `python scripts/shadow_observe.py --pre-match hoje --dry-run` — 2 jogos processados, pipeline end-to-end sem API keys.
- **Testes:** 218/218 passando (sem regressão).

### P2.A14 — Corrigir drift de nomenclatura ELO (RESOLVIDO — 11-APR-2026)

- `mvp_pipeline.py` e `test_missing_feature_imputation.py` atualizados para `home_elo_rating` / `away_elo_rating`.
- `DATA_SCHEMA.md` sincronizado.

### P2.C6 — Reconciliar documentação (RESOLVIDO — 11-APR-2026)

- Test count atualizado para 166/166 (20 arquivos) em 6 docs.
- `TRAINING_STRATEGY.md` corrigido.
- `VALIDATION_REPORT.md` expandido.
- `DATA_SCHEMA.md` ELO columns corrigidas.

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
| 11-APR-2026 | **ONDA 4 PARCIAL** — P2.SH1-SH3. P2.SH5a-SH5b. P2.SH6-SH10. Superbet SSE client, Context Collector, Gatekeeper Agent, Live Pipeline, Shadow Observe, Scraper CLI. P2.A14 (ELO drift). P2.C6 (doc sync). Testes 165→201. |
| 11-APR-2026 | **SH20 — Feature Store (Option C)** — `feature_store.py` + `refresh_features.py`. Pre-computed rolling features daily (Parquet). `get_active_tournament_ids()` para whitelist dinâmica. |
| 11-APR-2026 | **SH21 — Dynamic Tournament Whitelist** — Ligas com dados históricos filtram automaticamente IDs do Superbet. 12 IDs mapeados (Bundesliga 1 e PL pendentes). |
| 11-APR-2026 | **SH22 — Analyst Agent (Multi-Market LLM)** — `analyst.py` + `PROMPT_ANALYST.md` + `test_analyst.py` (17 testes). Avalia 1x2, BTTS, Over/Under Goals. *(Obsoleto desde 03-MAI-2026 — escopo migrado para Gatekeeper unificado V26)* |
| 11-APR-2026 | **SH23 — Pre-match Architecture Split** — `pre_match_odds.py` (JSON loader), scraper auto-save, `--pre-match` flag no shadow_observe. Dois modos: pre-match (JSON) e live (SSE). |
| 11-APR-2026 | Testes 201→218. 21 arquivos de teste. `ShadowEntry` expandido com campos `analyst_*`. |
| 11-APR-2026 | Revisão completa de arquitetura: 26 módulos fonte, 10 scripts, 21 test files mapeados. Issues identificadas: `collector.py` legacy, `artifacts/models/` vazio, `update_pipeline.py` incompleto. |
| 12-APR-2026 | Reestruturação do roadmap: `next_pass.md` limpo para conter apenas itens pendentes (39 total). Itens concluídos de Onda 2 (B6, A9-A12) adicionados ao histórico. Contagem corrigida (18→32 P2). Duplicata D3 removida. Documentação padronizada. |
| 12-APR-2026 | **SH15 — consensus_threshold namespace fix** — `self._config.consensus_threshold` → `self._config.value.consensus_threshold` em `gatekeeper_live_pipeline.py`. |
| 12-APR-2026 | **SH16 — dry-run implementado** — API key bypass, dry_run threading, agents opcionais. Dry-run validado end-to-end (2 jogos, sem API keys). 218/218 testes. |
| 12-APR-2026 | **SH11 — Bundesliga + Premier League tournament IDs** — Scan SSE feed: Bundesliga=245 (Colônia vs Werder Bremen), Premier League=106 (Nottingham Forest vs Aston Villa, Sunderland vs Tottenham). `league_tournament_ids.json` atualizado: 12→14 ligas mapeadas, `_pending` removido. |

### Itens Absorvidos

| Item Original | Absorvido Por | Motivo |
|---------------|--------------|--------|
| P4.NOTIFY — Desacoplamento da Decisão via Telegram | CKPT.3 — Cockpit via Telegram | CKPT.3 cobre o mesmo objetivo com escopo maior (bot Telegram completo com comandos) |
| P2.D4 — Bot de Alertas (Telegram) | CKPT.3 — Cockpit via Telegram | Escopo coberto pelo Cockpit via Telegram, que oferece bot completo com comandos |

---

## Onda 2 — Infraestrutura & Pipeline (100% CONCLUÍDO — 03-MAI-2026)

**Objetivo:** Corrigir paridade de features, verificar integridade de artefatos, integrar hyperopt.

### P2.B3 — Reescrever `update_pipeline.py` (RESOLVIDO — 03-MAI-2026)

- **Bug 1:** ~~`PipelineConfig(**config_dict)` — crash~~ ✅ Corrigido — usa `PipelineConfig.from_yaml()`.
- **Bug 2:** Feature engineering ausente ✅ — Pipeline completo portado (rolling mean, STD, EMA, ELO, matchup, H2H, drop redundant, team target encoding).
- **Bug 3:** `algorithms` hardcoded sem Ridge/ElasticNet ✅ — Usa `config.model.algorithms` do YAML com fallback completo.
- **Arquivo:** [`scripts/update_pipeline.py`](scripts/update_pipeline.py)
- **Evidência:** Docstring do arquivo confirma todos os 3 bugs corrigidos. Código verificado.

### P2.B7 — Verificar integridade de pickle antes de deserializar (RESOLVIDO — 03-MAI-2026)

- **Arquivo:** [`run.py`](run.py)
- **Implementação:** `_verify_artifact_integrity()` em `run.py`:
  - Carrega `.json` metadata ao lado do `.pkl`
  - Computa SHA256 hash do `.pkl` via `_compute_artifact_hash()`
  - Compara com hash salvo no metadata
  - Legacy migration: se metadata não tem hash, computa e salva
  - `ValueError` em caso de mismatch
- **Chamado por:** `load_model_artifacts()` antes de cada `pickle.load()`

### P2.B8 — Corrigir holdout temporal para ser realmente cronológico (RESOLVIDO — 03-MAI-2026)

- **Arquivo:** [`src/japredictbet/pipeline/mvp_pipeline.py`](src/japredictbet/pipeline/mvp_pipeline.py)
- **Implementação:** `_build_temporal_split()` reescrita com:
  - `use_strict_holdout=True` (default)
  - Nenhum shuffle — split por posição de índice (assume DataFrame ordenado por data)
  - Holdout = últimos N% da temporada mais recente
  - Split determinístico (seed ignorado)
- **Impacto:** P0.6 fechado definitivamente.

### P2.C7 — Integrar params otimizados do hyperopt no ensemble (RESOLVIDO — 03-MAI-2026)

- **Arquivo:** [`src/japredictbet/models/train.py`](src/japredictbet/models/train.py)
- **Implementação:**
  - `_load_hyperopt_best_params(algorithm)` — carrega `artifacts/hyperopt/{algo}_best_params.json`
  - `build_variation_params()` — tenta hyperopt first, fallback para variações hardcoded
  - `_build_variation_from_hyperopt()` — perturba knobs chave em torno dos best params para manter diversidade do ensemble
- **Fallback:** Se não existem best params, usa variações determinísticas (10 por algoritmo)

---

## Onda 5 — Itens Concluídos (03-MAI-2026)

| Item | Descrição | Data | Evidência |
|------|-----------|------|-----------|
| P2.D6 | Menu Central de Execução (v1.0) | 03-MAI-2026 | [`scripts/menu.py`](scripts/menu.py) — 296 linhas, 5 opções operacionais (extrair odds, shadow mode, dry-run, auditoria, manutenção). **Refatorado para v2.0 em 07-MAI-2026** (ver changelog). |
| P2.C1 (parcial) | `value/value_engine.py` removido | 03-MAI-2026 | Arquivo não existe no projeto — diretório `value/` ausente |
| P2.C1 (parcial) | `config_backup.yml` removido | 03-MAI-2026 | Arquivo não existe no projeto |
| Prioridade #2 | Decisão provedor LLM (OpenRouter escolhido) | 03-MAI-2026 | Decisão tomada, documentada em [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) |

---

## Changelog (Continuação)

| Data | Ação |
|------|------|
| 03-MAI-2026 | **Validação profunda do roadmap.** P2.D6 (menu.py) descoberto como já implementado. value_engine e config_backup já removidos. P4.NOTIFY absorvido por CKPT.3. Prioridades #2 e #3 arquivadas. 15 issues encontrados e corrigidos. Datas atualizadas para 03-MAI-2026. |
| 03-MAI-2026 | **ONDA 2 CONCLUÍDA** — B3 (update_pipeline.py completo), B7 (hash verification em run.py), B8 (temporal split cronológico), C7 (hyperopt integration em train.py). P0.6 fechado via B8. |
| 03-MAI-2026 | **SH12 — Refinar filtro de mercados** — Regex word boundary implementado no scraper para mercados core. |
| 03-MAI-2026 | **SH13 — Integrar scraper REST no pipeline live** — `fetch_full_event()` extraído para `superbet_client.py`. |
| 03-MAI-2026 | **SH13.B — Hardening do scraper pre-match** — SSE timeout tratado, fallback definido. |
| 03-MAI-2026 | **SH14 — Limpeza de arquivos temporários** — `_probe_event.py`, `_list_markets.py`, `scraper_*.txt`, `probe_out.txt`, `markets_result.txt` removidos. |
| 03-MAI-2026 | **SH17 — Superbet-only vs T-60 semantics** — Filtro temporal alternativo aplicado em modo degradado (sem API-Football). |
| 03-MAI-2026 | **SH18 — H2H FeatureStore validation** — H2H features excluídas do `FeatureStore` table (recomputadas no par consultado). |
| 03-MAI-2026 | **SH19 — Testes de integração Shadow (42/42)** — `test_shadow_integration.py` corrigido: 11 issues fixados (dataclass fields, fixture formatting, API assinaturas, FeatureStore build via construtor direto). |
| 03-MAI-2026 | **SH24 — Enriquecer pre-match com API-Football** — `enrich_pre_match_contexts()` chamado no `run()` pre-match block. Lineups, standings e injuries populados. |
| 03-MAI-2026 | Testes 218→260. 21 arquivos de teste. SH19 42/42 integração. |

---

## Onda 5 — CI Pipeline + Imports Fix + Context Study (05-MAI-2026)

> **Status:** ✅ CI Pipeline completo, P2.C4 (imports) corrigido, P2.B5 (blindar testes) resolvido, ENR.1 (context study) concluído, ensemble treinado.

**Itens concluídos em 05-MAI-2026:**

| Item | Descrição | Evidência |
|------|-----------|-----------|
| P2.B1 | CI Básico (GitHub Actions com Ruff lint + MyPy type check + pytest coverage ≥60%, Python 3.11/3.12) | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — 3 jobs (lint, test 3.11, test 3.12) |
| P2.B5/B9 | Blindar coleta de testes — `testpaths` e `python_files` configurados no `pyproject.toml` | [`pyproject.toml`](pyproject.toml#:60) — `testpaths = ["tests"]`, `python_files = ["test_*.py"]` |
| P2.C4 | Padronizar imports nos testes — 6 arquivos corrigidos de `src.japredictbet` → `japredictbet` | Commits: `f5ba6e3`, `7c0e852`. Nenhum arquivo de teste usa mais `src.` prefix |
| ENR.1 | Estudo de Viabilidade de Enriquecimento de Contexto | [`docs/context_enrichment_study.md`](docs/context_enrichment_study.md) — 350+ linhas, 4 fases, análise completa de 6 fontes de dados |
| Ensemble | 30 modelos treinados em `artifacts/models/` | 11 XGB + 10 LGBM + 5 Ridge + 4 ElasticNet — todos com `.pkl` + `.json` metadata |
| P2.C1 (parcial) | Verificação de código morto — `add_rolling_features()` confirmada como não-usada | Função e teste associado ainda existem (pendente remoção) |

### Detalhamento das implementações

#### P2.B1 — CI Pipeline (GitHub Actions)

- **Arquivo:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- **Jobs:**
  - `lint:` Ruff lint + format check + MyPy type check em Python 3.11
  - `test:` Matrix Python 3.11 + 3.12, pytest com coverage report, gate ≥60%
- **Triggers:** Push/PR em branches `main` nos paths `src/`, `scripts/`, `tests/`, `requirements*.txt`, `pyproject.toml`
- **Concorrência:** Cancelamento automático de runs anteriores no mesmo PR
- **Cache:** `actions/setup-python@v5` com cache pip

#### P2.B5/B9 — Blindar coleta de testes

- [`pyproject.toml`](pyproject.toml#:60): `testpaths = ["tests"]` + `python_files = ["test_*.py"]` + `python_functions = ["test_*"]`
- Elimina falsos positivos de coleta (ex: `test_output.txt` na raiz)

#### P2.C4 — Padronização de imports

- **6 arquivos corrigidos:** `test_rolling_cross_group.py`, `test_rolling_p1b2.py`, `integration_p1a3.py`, `integration_p1a2.py`, `test_lambda_validation.py`, `test_p1a2_dynamic_margin.py`
- **Padrão utilizado:** `from japredictbet.xxx import yyy` (sem prefixo `src.`)
- **Validação:** `findstr "src.japredictbet" tests/**/*.py` retorna vazio

#### ENR.1 — Estudo de Viabilidade de Contexto

- **Arquivo:** [`docs/context_enrichment_study.md`](docs/context_enrichment_study.md) (04-MAI-2026)
- **Commit:** `39da387 docs: ENR.1 — Estudo de Viabilidade de Enriquecimento de Contexto (Onda 7)`
- **Cobertura:**
  - Diagnóstico do fluxo atual (pre-match e live T-60)
  - Análise de 6 fontes de dados (API-Football, DuckDuckGo, Tavily, NewsAPI, GNews, RSS)
  - Custo/benefício detalhado por fonte
  - Recomendação faseada em 4 fases (Quick Wins → RAG → The Scout → Refinamento)
  - Alerta crítico sobre standings com fallback 2024
  - Riscos e mitigações
  - Métricas de sucesso
  - Apêndices com exemplos de response da API-Football

---

## Changelog (Continuação)

| Data | Ação |
|------|------|
| 05-MAI-2026 | **FASE 0 CONCLUÍDA** — P0.FALLBACK: fallback 2024 removido de `context_collector.py` (2 pontos), `PROMPT_MESTRE.md` atualizado (Pilar 5), `context_enrichment_study.md` expandido (Seção 3.4 — web scraping futuro). 254/254 testes. |
| 05-MAI-2026 | **Revisão profunda do backlog.** Descobertas: (a) `artifacts/models/` já tem 30 modelos treinados (desmentindo prioridade #1 do roadmap anterior), (b) CI pipeline já implementado (P2.B1 concluído), (c) imports padronizados (P2.C4 concluído), (d) `pyproject.toml` já blindado contra falsa coleta (P2.B5/B9 concluído), (e) ENR.1 (context study) já concluído (commit 39da387). Total de 5 itens removidos do backlog ativo. `next_pass.md` reescrito: 46→41 itens pendentes, data atualizada para 05-MAI-2026. |
| 07-MAI-2026 | **Auditoria de arquitetura — 5 blocos analisados.** Roadmap atualizado: 48→54 itens. Novos itens: AUDIT.1 (News Context — 6º pilar no Prompt Mestre), AUDIT.2 (Test Mocks para DuckDuckGo/API-Football), AUDIT.3 (Fuzzy Matching com rapidfuzz), AUDIT.4 (Telegram Notifier), AUDIT.5 (RAG Lite / Memory). |
| 07-MAI-2026 | **Menu refatorado para v2.0.** [`scripts/menu.py`](scripts/menu.py): 296→355 linhas, 5→6 opções. Correções: descrição "ML+LLM" → "Gatekeeper LLM", Analisar agora reutiliza JSON do scraper sem re-scraping, manutenção semanal remove `run.py` (retreino agora sob demanda). Fluxo encadeado com `_executar_encadeado()`. Toggle `[V]` verbose. Ruff/MyPy/pytest (254/254) validados. Commit `8a7d121`. |
