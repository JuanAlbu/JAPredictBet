# JA PREDICT BET — ROADMAP (REVISÃO 06-MAI-2026)

**Data da Revisão:** 06 de Maio, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 ✅ | Onda 3 ✅ | Onda 4 parcial | P3-ARCH ✅ | P2-REFACTOR ✅ | **CI Pipeline ✅** | **ENR.1 ✅** | **FASE 0 ✅** | **SCRAPER.1 ✅** | **SCRAPER.2 ✅** — **254/254 testes** (21 arquivos). 106 features. 30 modelos treinados. Scraper migrado para REST by-date (20 TIDs rastreados de 19 ligas). Playwright com multi-scroll. Mapeamento `list[int]` para TIDs múltiplos.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 4 (F1) + 3 (F2) + 3 (F3) + 11 (F4) + 5 (F5) + 3 (F6) + 3 (F7) + 4 (F8) + 1 (Padronização) + 3 (R&D) + 2 (Stretch) = **42 total**

> Este documento contém **apenas itens em aberto**, organizados por fase de execução. Itens concluídos são registrados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## Observações LLM (05-MAI-2026)

- O Gatekeeper unificado avalia TODOS os mercados em uma única chamada LLM (Prompt Mestre V26).
- O 30-model ensemble é exclusivo do Mode 1 (Backtest) — NÃO é usado no Shadow Mode.
- Nenhum agente executa apostas reais — Shadow Mode é 100% observacional.
- Gemini AI Studio não está disponível no Brasil (limit: 0). Use OpenRouter ou Groq.
- CI pipeline com GitHub Actions (Ruff lint + MyPy type check + pytest com coverage ≥60%) operacional.
- ENR.1 (Estudo de Viabilidade de Contexto) concluído — [`docs/context_enrichment_study.md`](context_enrichment_study.md).
- Todos os 30 modelos do ensemble treinados e disponíveis em `artifacts/models/`.
- **Alerta P0:** Fallback 2024 nos standings está ativo em produção — Gatekeeper decide com tabela de **2 anos atrás** (ver FASE 0).

---

## 📊 Visão Geral das Fases

```
FASE 0 (🔴 P0 Crítica)     ██░░░░░░░░░░░░░░░░░░░░  1 item   |  30min   ← BUG — corrigir antes de tudo
FASE 1 (🧹 Limpeza)        ██████░░░░░░░░░░░░░░░░  4 itens  |  2-3h    ← Dead code + boundary + pyproject
FASE 2 (⚡ Quick Wins)      ██████░░░░░░░░░░░░░░░░  3 itens  |  4-8h    ← ThreadPool + Árbitro + H2H
FASE 3 (🏗️ Fundação)       ██████░░░░░░░░░░░░░░░░  3 itens  |  2-3d    ← Logging + tratamento de erros
FASE 4 (🧪 Testes)         ██████████████████████  11 itens |  3-5d    ← +5 módulos, cobertura ~55%→70%
FASE 5 (🎛️ Produto)        ████████████░░░░░░░░░░  5 itens  |  3-5d    ← SH4 + Dashboards + Auto-healing
FASE 6 (⚡ Performance)     ████████░░░░░░░░░░░░░░  3 itens  |  3-5d    ← Async completo + Bouncer V2 + Consensus sweep
FASE 7 (🧠 Contexto)       ████████░░░░░░░░░░░░░░  3 itens  |  1-2sem  ← RAG + Scout + xG Anchor
FASE 8 (🤖 Avançado)       ██████████░░░░░░░░░░░░  4 itens  |  2-4sem  ← LLM Consensus + Auditor + Telegram + Docker
Intercalado                 ██████░░░░░░░░░░░░░░░░  1 item   |  quando der
R&D/Stretch                 █████░░░░░░░░░░░░░░░░  5 itens  |  sem prazo
```

---

## 🟢 FASE 0 — Concluída ✅ (05-MAI-2026)

> **P0.FALLBACK — Remover fallback 2024 dos standings** resolvido em 3 commits:
> 1. Fallback `2024` → `None` nos 2 pontos de [`context_collector.py`](src/japredictbet/data/context_collector.py).
> 2. [`PROMPT_MESTRE.md`](docs/PROMPT_MESTRE.md) — Pilar 5 instruído a ignorar `home_standing: null`.
> 3. [`context_enrichment_study.md`](docs/context_enrichment_study.md) — Seção 3.4 registra web scraping (Soccerway, Flashscore) como desenvolvimento futuro.
>
> **Detalhes em:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md#fase-0--correção-crítica-p0-05-mai-2026)

---

## 🧹 FASE 1 — Limpeza Imediata (3 itens — ~2-3h)

**Objetivo:** Remover dead code confirmado, corrigir documentação obsoleta, resolver boundary architecture. Zero risco, remove ruído, libera caminho para fases seguintes.

- [ ] **P2.C1 / P2.C6 — Remover `add_rolling_features()` + teste associado**
  - **Problema:** [`add_rolling_features()`](src/japredictbet/features/rolling.py:9) NÃO é usada pelo pipeline principal nem por `walk_forward.py` — apenas pelo teste [`test_add_rolling_features_stays_within_team_group`](tests/features/test_rolling_cross_group.py:51).
  - **Ação:** Remover a função de [`rolling.py`](src/japredictbet/features/rolling.py). Remover o teste + o import `add_rolling_features` de [`test_rolling_cross_group.py`](tests/features/test_rolling_cross_group.py).
  - **Validação:** `findstr "add_rolling_features" src/ tests/` → vazio. `pytest tests/featues/test_rolling_cross_group.py -v` → todos passando.
  - **Esforço:** ~30min.

- [ ] **P2.C5 — Corrigir docstring obsoleta em `test_shadow_integration.py`**
  - **Problema:** Linha 13 de [`test_shadow_integration.py`](tests/pipeline/test_shadow_integration.py:13) menciona *"The 30-model ensemble and AnalystAgent are exclusive to Mode 1 (Backtest)"*. `AnalystAgent` foi removido completamente em 03-MAI-2026.
  - **Ação:** Substituir por: *"The 30-model ensemble is exclusive to Mode 1 (Backtest). Shadow Mode uses a single GatekeeperAgent (Prompt Mestre V26) evaluating all markets."*
  - **Validação:** `findstr "AnalystAgent" tests/` → vazio.
  - **Esforço:** ~2min.

- [ ] **P2.C2 — Resolver boundary `probability/` vs `betting/engine.py`**
  - **Problema:** A distribuição de Poisson vive em [`betting/engine.py`](src/japredictbet/betting/engine.py), violando a boundary de responsabilidade. O diretório `probability/` foi criado para funções estatísticas puras.
  - **Ação:** Mover funções Poisson (`poisson_pmf`, `poisson_probability`, `skellam`) para novo módulo `probability/poisson.py`. Atualizar imports em `engine.py`, `risk.py`, e testes. Manter compatibilidade — testes existentes devem continuar passando.
  - **Esforço:** ~1-2h (análise de dependências + mover + atualizar imports + validar testes).

- [ ] **Completar `pyproject.toml`**
  - **Problema:** O [`pyproject.toml`](pyproject.toml) atual tem only name + version + tool configs. Faltam metadata descritiva e entry points.
  - **Ação:** Adicionar `description`, `authors`, `classifiers`, `keywords`, `license`, `requires-python` (>=3.11), `dependencies` (principais: pandas, numpy, scikit-learn, xgboost, lightgbm, httpx, openai, python-dotenv, pyyaml) e `[project.scripts]` com entry points (`japredictbet-menu`, `japredictbet-scrape`, `japredictbet-shadow`).
  - **Esforço:** ~30min.
  - **Validação:** `pip install -e .` sem erros. `python -m japredictbet` não quebrar.

---

## ⚡ FASE 2 — Quick Wins de Performance e Contexto (3 itens — ~4-8h)

**Objetivo:** Baixo esforço, alto impacto. Reduzir latência do pipeline de minutos para segundos e preencher gaps críticos de contexto que já têm dados disponíveis.

- [ ] **P3.ENG quick-win — `ThreadPoolExecutor` no loop de avaliação**
  - **Tipo:** Melhoria de Performance.
  - **Situação atual:** O loop `for match_ctx in matches` em [`gatekeeper_live_pipeline.py:238`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py:238) é sequencial — 30 jogos × ~5s cada = ~150s.
  - **Ação:** Envolver o loop com `concurrent.futures.ThreadPoolExecutor(max_workers=8)`, processando `_evaluate_single_match()` em paralelo. Cada worker chama o LLM independentemente.
  - **Impacto:** Latência ~150s → ~20s (30 jogos com 8 workers).
  - **Esforço:** ~30min-1h. **Nota:** Isto NÃO está implementado — 0 ocorrências de `concurrent.futures` no código atual. Precisa ser implementado do zero.
  - **Pré-requisito para:** P3.ENG completo (migração asyncio na Fase 6).

- [ ] **ENR.3 — Árbitro no MatchContext**
  - **Tipo:** Correção de Gap Operacional.
  - **Problema:** O dataclass [`RefereeInfo`](src/japredictbet/data/context_collector.py:63) já existe mas **nunca é populado**. O campo `referee` JÁ VEM no response do endpoint `fixtures` da API-Football (campo `fixture.referee`) — nenhuma chamada extra necessária.
  - **Ação:** Extrair `referee` do response de `fixtures` em `ContextCollector.collect_upcoming()` e `enrich_pre_match_contexts()`. Popular `ctx.referee` com `RefereeInfo(name=...)`. Serializar no `to_llm_context()` para injeção no prompt.
  - **Impacto:** Pilar 3 da validação (Arbitragem) passa a funcionar. Custo $0 em API.
  - **Esforço:** ~2-4h.
  - **Referência:** [`docs/context_enrichment_study.md`](context_enrichment_study.md#33-enr3--árbitro-quick-win)

- [ ] **ENR.4 — H2H Recente no MatchContext**
  - **Tipo:** Melhoria de Contexto.
  - **Problema:** O Shadow Mode não tem acesso a histórico de confronto direto. O [`matchup.py`](src/japredictbet/features/matchup.py) já implementa `add_h2h_features()` para o Mode 1 (Backtest), mas o Shadow Mode não usa.
  - **Ação:** Adicionar `ApiFootballClient.get_h2h(team_a_id, team_b_id)` usando endpoint `fixtures/headtohead`. Popular novo campo `MatchContext.h2h` com resumo dos últimos 3 confrontos (placar, gols). Serializar no `to_llm_context()`.
  - **Impacto:** Análise 1x2 e Over/Under com histórico real de confronto.
  - **Esforço:** ~2-4h.
  - **Dependência:** Aproveita mesmo fluxo de API do ENR.3 (executar preferencialmente na sequência).

---

## 🏗️ FASE 3 — Fundação de Observabilidade (3 itens — ~2-3 dias)

**Objetivo:** Logging estruturado e tratamento de erros. **Pré-requisito silencioso** para tudo que vem depois — sem isso, debugar fases avançadas será torturante.

- [ ] **P2.B4 — Migrar `run.py` de `print()` para `logging`**
  - **Situação atual:** 10 chamadas `print()` em [`run.py`](run.py:140-253). O módulo [`utils/logging.py`](src/japredictbet/utils/logging.py) já existe e está pronto para uso.
  - **Ação:** Substituir todos os `print()` por `logger.info()` / `logger.error()`. Configurar nível de log via `config.yml`.
  - **Esforço:** ~1h.

- [ ] **P2.B2 — Logging Estruturado por Aposta**
  - **Escopo:** Cada decisão do Gatekeeper deve gerar um log estruturado com: lambdas, votos do ensemble (Mode 1), edge, threshold aplicado, stake calculado, resultado final.
  - **Módulos:** `utils/logging.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Pré-requisito para:** P2.D7 (Dashboard de Sessão).
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D1 — Tratamento de Erros Robusto**
  - **Escopo:** Adicionar `try-except` em pontos críticos: `fetch_odds`, chamadas API-Football, chamadas LLM, escrita de shadow log.
  - **Objetivo:** Pipeline não deve quebrar completamente por falha em um único jogo. Erros devem ser logados e o jogo skipado com status `ERROR`.
  - **Esforço:** ~1 dia.

---

## 🧪 FASE 4 — Cobertura de Testes (11 itens — ~3-5 dias)

**Objetivo:** Elevar cobertura de ~55% para 70%+. Prioridade: novos módulos (importance, predict, walk_forward, scraper) → ampliar existentes (features, ingestion, train) → suites transversais (leakage, matching).

### Bloco 4A — Novos Módulos (4 itens)

- [ ] **P2.A14 - Testes para `models/importance.py`**
  - `_extract_scores()`: dispatch por tipo de modelo (XGBoost gain, LightGBM feature_importances_, linear abs(coef_)).
  - `compute_feature_importance()`: feature_columns vazio, modelo sem API de importância (TypeError).
  - `select_top_features()`: filtro top_n + min_gain combinados, DataFrame vazio.
  - **Módulo:** `tests/models/test_importance.py` (novo).

- [ ] **P2.A15 - Testes para `models/predict.py`**
  - `predict_expected_corners()`: feature_columns ausente (ValueError), colunas faltando no input, NaN handling via feature_fill_values.
  - Clipping de predições negativas para 0.
  - Output com Series indexadas corretamente (home + away).
  - **Módulo:** `tests/models/test_predict.py` (novo).

- [ ] **P2.A16 - Testes para `pipeline/walk_forward.py`**
  - `_compute_metrics()`: MAE e RMSE com valores conhecidos, máscara de NaN em actual/pred.
  - `evaluate_walk_forward()`: mock data com 2+ seasons, verificação de colunas `train_seasons`/`test_season`/`features_used`.
  - Dataset com season única (ValueError esperado).
  - `_add_total_corners_features()` e `_add_total_goals_features()`: colunas ausentes não quebram.
  - **Módulo:** `tests/pipeline/test_walk_forward.py` (novo).

- [ ] **P2.A17 - Testes para `scripts/superbet_scraper.py`**
  - `_apply_snapshot_filter()`: min_odd filtra corretamente, market_filter por keyword, lista vazia.
  - `_resolve_target_date()`: dia da semana (hoje/amanhã), data ISO, alias inválido → None.
  - `_is_market_of_interest()` e `_is_player_market()`: mercados válidos, mercados de jogador, falsos positivos.
  - `_parse_teams()`: nome com "vs", nome com " - ", fallback split.
  - **Módulo:** `tests/scripts/test_superbet_scraper.py` (novo).
  - **Nota:** Testar funções extract/transform; não testar `_stream_sse()` (requer rede real).

### Bloco 4B — Ampliar Cobertura Existente (5 itens)

- [ ] **P2.A3 - Ampliar testes para `models/train.py`**
  - Ensemble scheduling (hybrid mode ativação condicional), feature selection com `_is_model_feature_candidate()`, minimum training rows, XGBoost feature name sanitization (caracteres especiais).

- [ ] **P2.A13 - Corrigir RNG inconsistente em `build_variation_params`**
  - XGBoost usa `np.random.default_rng()`, LGB/RF/Ridge/EN usam listas hardcoded de 10 elementos. Unificar para RNG determinístico com seed.

- [ ] **P2.A1 - Testes para `features/` (elo, rolling, matchup, team_identity)**
  - NaN handling em ELO, edge cases rolling, divisão por zero em matchup, data leakage via train_mask.

- [ ] **P2.A2 - Testes para `data/ingestion.py`**
  - Parquet loading, CSV malformado, dataset vazio, colunas ausentes, NaN em data.

- [ ] **P2.A5 + P2.A6 + P2.A8 — Suites Transversais de Segurança (3 sub-itens)**
  - **P2.A5 — Suite de Leakage:** Garantir que rolling features usem apenas histórico passado.
  - **P2.A6 — Regressão de Matching:** Evitar confusão entre equipes homônimas em ligas diferentes.
  - **P2.A8 — Validar `train_mask` em `team_identity.py`:** Máscara vazia/inválida causa data leakage silencioso. Validar dimensão e tipo booleano.

- [ ] **P3.1 - Otimizar loop de consensus sweep**
  - `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar. **Nota:** Embora seja item P3, convém implementar junto com os testes de `models/` pois mexe no mesmo módulo.

---

## 🎛️ FASE 5 — Produto & Dados (5 itens — ~3-5 dias)

**Objetivo:** Completar integração multi-liga (SH4), melhorar UX (menu bootstrap, dashboards) e automatizar manutenção (auto-healing).

- [~] **SH4 — Mapeamento Superbet → IDs internos** (parcial — apenas Brasileirão preenchido)
  - [`data/mapping/superbet_teams.json`](data/mapping/superbet_teams.json) (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` — equipes sem mapeamento geram WARNING e skip.
  - **Tournament IDs:** 20 TIDs rastreados de 19 ligas em [`data/mapping/league_tournament_ids.json`](data/mapping/league_tournament_ids.json). O formato agora suporta `int` (maioria das ligas) ou `list[int]` (ligas com múltiplos TIDs, ex.: `sul_americana: [51372, 51375]`). 18 ligas com TID único + 1 liga (sul_americana) com 2 TIDs = **20 TIDs no total**.
  - **Nota:** O `league_tournament_ids.json` foi alterado para suportar `list[int]` como valor. Todos os consumidores (superbet_scraper.py, feature_store.py, _discover_tournaments.py) foram atualizados para lidar com ambos os tipos.
  - **Pendente:** preencher mapeamento de nomes de times para as demais 18 ligas (apenas Brasileirão preenchido atualmente).
  - **Esforço:** Trabalho manual — ~2-3 dias para todas as ligas.

- [ ] **P2.D6.B — Bootstrap Operacional do Menu**
  - **Escopo:** Garantir que todas as opções do menu tenham pré-checagens e mensagens claras de prontidão operacional.
  - **Checklist mínima:** snapshot disponível, `artifacts/models` treinados ✅, `feature_store.parquet` disponível, chaves LLM configuradas quando aplicável.
  - **Objetivo:** Separar claramente "menu pronto" de "pipeline pronto", evitando que o usuário execute fluxos incompletos sem diagnóstico amigável.
  - **Dependências:** ~~P2.D6~~ ✅, ~~SH13.B~~ ✅, ~~SH24~~ ✅.
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D7 — Dashboard de Sessão (Saldo do Dia)**
  - **Tipo:** Produto / Observabilidade.
  - **Escopo:** Ler o shadow log (`shadow_log.jsonl`), agregar métricas de sessão do dia corrente e exibir no menu.
  - **Métricas:** saldo do dia (u), yield (ROI), entradas aprovadas vs rejeitadas, sequência atual (greens vs reds), total de entradas no dia.
  - **Origem:** Integração do SNIPER V25 — Controle de Sessão era o único gap real após análise cruzada.
  - **Saída esperada:** Painel no terminal (`scripts/menu.py` opção 6 ou sub-menu) com resumo executivo do dia.
  - **Módulos:** `scripts/menu.py`, novo `scripts/session_dashboard.py` (leitor do shadow log).
  - **Dependências:** P2.B2 (Fase 3 — logging estruturado).
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D2 — Dashboard de Saúde do Modelo**
  - **Tipo:** Observabilidade / Backtest.
  - **Escopo:** Painel de métricas agregadas de performance dos 30 modelos do ensemble (Mode 1).
  - **Métricas:** Volume de apostas, hit rate, ROI, CLV médio, calibração (Brier/ECE) por período (semanal/mensal).
  - **Objetivo:** Permitir diagnóstico rápido de degradação do ensemble ao longo do tempo.
  - **Módulos:** `scripts/consensus_accuracy_report.py` (extensão), novo `scripts/model_health_dashboard.py`.
  - **Dependências:** Fase 3 (logging estruturado) para ter dados confiáveis de saída do Mode 1.
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D8 — Auto-Healing de Nomes de Equipas**
  - **Tipo:** Melhoria de Dados. *(Movido de P4.HEAL)*
  - **Escopo:** Script de fim do dia que recolhe equipas "órfãs" (nome Superbet sem match na API-Football) e usa LLM barato para deduzir o match correto.
  - **Objetivo:** Eliminar manutenção manual do [`superbet_teams.json`](data/mapping/superbet_teams.json).
  - **Módulos:** Novo `scripts/auto_heal_teams.py`, `data/mapping/superbet_teams.json`.
  - **Workflow:** Cron diário → recolhe orphans do shadow log → LLM resolve → append automático.
  - **Dependência:** SH4 (Fase 5 — mapeamento é o baseline que o auto-healing expande).
  - **Esforço:** ~1-2 dias.

---

## ⚡ FASE 6 — Performance (3 itens — ~3-5 dias)

**Objetivo:** Otimizações que reduzem tempo de execução e custo de tokens. Aproveita ganhos da Fase 2 (ThreadPoolExecutor) e avança para solução completa.

- [ ] **P3.ENG completo — Migração `asyncio` + `httpx` assíncrono**
  - **Tipo:** Melhoria de Engenharia.
  - **Escopo:** Refatorar `gatekeeper.py`, `context_collector.py` e `gatekeeper_live_pipeline.py` para `asyncio` com `httpx` assíncrono.
  - **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60 com latência mínima.
  - **Pré-requisito:** P3.ENG quick-win (Fase 2 — ThreadPoolExecutor). A migração asyncio é o próximo passo natural.
  - **Justificativa:** Proteger contra esmagamento da linha de fecho.
  - **Esforço:** ~2-3 dias.

- [ ] **CKPT.1 — Otimização de Tokens: Filtro de Relevância (The Bouncer V2)**
  - **Escopo:** Expandir a lógica de pré-filtro no Python para poupar tokens. Em vez de passar o JSON bruto de odds para o LLM, o módulo `pre_match_odds.py` deve aplicar a função `get_interesting_lines()`.
  - **Critérios:**
    - **Zonagem:** Apenas odds entre 1.25 e 2.20 (Zonas Alvo + Composição). Odds > 2.20 entram na Zona de Variância com stake cortado.
    - **Exclusão:** Cortar mercados de handicap ou linhas extremamente "esticadas" (ex: Over 0.5 a 1.05).
  - **Nota:** O critério de correlação com algoritmo foi removido — o 30-model ensemble é exclusivo do Mode 1 (Backtest).
  - **Esforço:** ~1 dia.

- [x] **P3.1 - Otimizar loop de consensus sweep** *(executar junto com Fase 4 — Bloco 4B)*
  - `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar.

---

## 🧠 FASE 7 — Contexto Avançado (3 itens — ~1-2 semanas)

**Objetivo:** Conhecimento de longo prazo (RAG), pesquisa externa ativa (The Scout) e ancoragem quantitativa para 1x2/BTTS. **Pré-requisito para Fase 8** (Telegram e Deploy dependem de análises de alta qualidade).

- [ ] **ENR.2 — Knowledge Store: Memória de Longo Prazo (RAG)**
  - **Tipo:** Infraestrutura de Dados / Agentes.
  - **Escopo:** Implementar base de conhecimento leve (SQLite/LanceDB + embeddings `sentence-transformers`) integrada ao `FeatureStore` para que o Gatekeeper "lembre" de comportamentos passados.
  - **Armazenamento:**
    - **Cache de Contexto:** Escalações, desfalques e H2H dos últimos 7 dias — evita chamadas repetidas à API-Football.
    - **Histórico de Veredictos:** Armazenar por que o Gatekeeper rejeitou ou aprovou cada jogo, permitindo aprendizado com erros passados.
    - **Shadow Performance:** Base para `consensus_accuracy_report.py` e `session_dashboard.py` lerem rapidamente ROI por liga, mercado e horário.
    - **Perfil de Arbitragem:** Registrar padrões históricos de árbitros. Na avaliação de um jogo, o sistema consulta o perfil e injeta no prompt.
  - **Módulos:** `data/feature_store.py`, novo `data/knowledge_store.py`.
  - **Custo mensal:** $0 (tudo local).
  - **Esforço:** ~12-20h.
  - **Referência:** [`docs/context_enrichment_study.md`](context_enrichment_study.md#5-enr2--knowledge-store-memória-de-longo-prazo-rag)

- [ ] **ENR.5 — The Scout: Agente de Pesquisa Web para Contexto Externo**
  - **Tipo:** Agente / Integração.
  - **Escopo:** Módulo "Scout" ativo que pesquisa notícias e contexto externo para jogos na Zona Alvo (1.60–2.20).
  - **Fluxo:**
    1. Ao identificar jogo na Zona Alvo, dispara pesquisa web.
    2. Pesquisa por `"[home_team] [away_team] escalação desfalques notícias"`.
    3. Resume as 3 notícias/insights mais relevantes.
    4. Injeta no Prompt Mestre V26 como campo `[EXTERNAL_RESEARCH]`.
  - **Tecnologias candidatas:** DuckDuckGo Search (gratuito) ou Tavily API (pago, melhor qualidade) — definido pelo estudo ENR.1.
  - **Módulos:** `agents/gatekeeper.py` (integração), novo `data/web_scout.py`.
  - **Dependências:** ENR.2 (cache para evitar pesquisas repetidas do mesmo jogo em 6h).
  - **Esforço:** ~8-12h.

- [ ] **P3.ANCHOR — Ancoragem Quantitativa (xG) para 1x2 e BTTS**
  - **Tipo:** Melhoria Analítica.
  - **Escopo:** Adicionar modelo estatístico base (Distribuição de Poisson via Expected Goals — xG) para Match Odds (1x2) e BTTS.
  - **Objetivo:** Impedir que o Gatekeeper LLM aprove apostas baseado apenas em narrativa, obrigando cruzamento com "just price" matemático.
  - **Módulos:** `agents/gatekeeper.py`, novo `probability/xg_anchor.py`, [`PROMPT_MESTRE.md`](docs/PROMPT_MESTRE.md).
  - **Esforço:** ~2-3 dias.

---

## 🤖 FASE 8 — LLM Avançado + Cockpit + Deploy (4 itens — ~2-4 semanas)

**Objetivo:** Consenso multi-LLM para robustez, auditor LLM para backtest, operação remota via Telegram, deploy cloud 24/7.

- [ ] **P3.LLM-CONSENSUS — Consenso entre dois provedores LLM**
  - **Tipo:** Melhoria de Arquitetura Analítica.
  - **Escopo:** Criar uma camada de consenso entre dois provedores LLM (ex.: Groq + Gemini Flash via OpenRouter) para avaliação multi-mercado.
  - **Objetivo:** Reduzir variância de resposta de um único LLM e aumentar robustez da decisão final.
  - **Regra proposta:** Cada modelo analisa o mesmo `MatchContext`; resposta final só aprova com convergência mínima configurável.
  - **Módulos:** `agents/gatekeeper.py`, novo `agents/llm_consensus.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Dependência:** Contexto enriquecido (Fase 7) para que ambos os LLMs tenham dados de qualidade.

- [ ] **P3.LLM-AUDITOR — Auditor LLM para Backtest (Modo 1)**
  - **Tipo:** Melhoria Analítica.
  - **Escopo:** Criar um agente LLM específico para o Mode 1 (Backtest) que lê o relatório de saída dos 30 modelos do ensemble.
  - **Objetivo:** Complementar o [`consensus_accuracy_report.py`](scripts/consensus_accuracy_report.py) com um auditor narrativo que sugere:
    - Ajustes de pesos dos modelos no ensemble
    - Recomendações de calibração (Brier, ECE)
    - Ajustes nas regras de Kelly Criterion
    - Identificação de ligas ou mercados com desempenho atípico
  - **Módulos:** `models/predict.py`, `scripts/consensus_accuracy_report.py`, novo `agents/backtest_auditor.py`.
  - **Dependência:** Fase 4 (testes de predict/train) para garantir que o output do Mode 1 está bem testado antes de auditá-lo.

- [ ] **CKPT.2 — Cockpit via Telegram: Operação Remota**
  - **Escopo:** Transformar o sistema num serviço de sinais pessoais através de um bot de Telegram. *(Absorve P2.D4 e P4.NOTIFY)*
  - **Implementação:** Novo módulo `src/japredictbet/interfaces/telegram_bot.py` via `python-telegram-bot`.
  - **Comandos:** `/resumo` (jogos do dia), `/odds [time]` (consulta Superbet), `/stats` (performance mensal).
  - **Dependências:** Fase 7 (contexto enriquecido para qualidade das análises), Fase 6 (async para respostas rápidas).

- [ ] **CKPT.3 — Deploy Cloud & Containerização (Docker)**
  - **Tipo:** Infraestrutura / DevOps.
  - **Escopo:** Criar `Dockerfile` e configurar deploy contínuo em plataforma cloud (Railway, Render ou AWS EC2) para execução 24/7 do pipeline T-60.
  - **Objetivo:** Eliminar dependência do computador pessoal ligado.
  - **Entregáveis:** `Dockerfile`, `docker-compose.yml` (opcional), script de deploy, documentação de infraestrutura.
  - **Pré-requisitos:** CKPT.2 (Telegram) para notificações remotas, Fase 7 (Knowledge Store) para cache entre execuções.

---

## 🔧 Padronização (1 item — intercalado, baixa prioridade)

> Executar em momentos de "baixa" entre fases. Não bloqueia nada.

- [ ] **P2.C3 — Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Config RandomForest enganoso no `algorithms`.
  - Pode ser feito incrementalmente — um arquivo por vez quando houver tempo ocioso.

---

## R&D — Pesquisa e Desenvolvimento (3 itens)

- [ ] **Stacking Meta-Modelo** — Ponderação aprendida dos membros do ensemble.
- [ ] **Game State / Live Variables** — Impacto de estado de jogo em cantos.
- [ ] **Favourite-Longshot Bias** — Ajustes para vieses sistemáticos do mercado.

---

## Stretch Goals — Fora do Roadmap Ativo (2 itens)

> Itens de pesquisa acadêmica ou engenharia avançada, sem prazo ou prioridade definidos. Mantidos para referência futura.

- [ ] **Binomial Negativa Bivariada** — Migração de Poisson para modelos com sobredispersão.
- [ ] **GNN Tático** — Modelagem estrutural de interações entre jogadores.
