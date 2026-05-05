# JA PREDICT BET — ROADMAP (REVISÃO 05-MAI-2026)

**Data da Revisão:** 05 de Maio, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 ✅ | Onda 4 parcial | P3-ARCH ✅ | P2-REFACTOR ✅ | **CI Pipeline ✅** | **ENR.1 ✅** — **254/254 testes** (21 arquivos). 106 features. 30 modelos treinados.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 16 (Onda 3) + 1 (Onda 4) + 7 (Onda 5) + 3 (Onda 6) + 4 (Onda 7) + 5 (P3) + 3 (R&D) + 2 (Stretch) = **41 total**

> Este documento contém **apenas itens em aberto**. Itens concluídos são registrados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## Prioridades Imediatas

1. **Resolver gaps de dead code (P2.C1/C6)** — `add_rolling_features()` + teste associado confirmados como código morto. Remover ambos junto com P2.C1 + P2.C6.
2. **Onda 4 residual** — SH4 pendente (mapeamento manual), demais itens concluídos
3. **P3.ENG** — Execução assíncrona T-60 (próximo grande salto de performance)

---

## Observações LLM (05-MAI-2026)

- O Gatekeeper unificado avalia TODOS os mercados em uma única chamada LLM (Prompt Mestre V26).
- O 30-model ensemble é exclusivo do Mode 1 (Backtest) — NÃO é usado no Shadow Mode.
- Nenhum agente executa apostas reais — Shadow Mode é 100% observacional.
- Gemini AI Studio não está disponível no Brasil (limit: 0). Use OpenRouter ou Groq.
- **Novo:** CI pipeline com GitHub Actions (Ruff lint + MyPy type check + pytest com coverage ≥60%) operacional.
- **Novo:** ENR.1 (Estudo de Viabilidade de Contexto) concluído — [`docs/context_enrichment_study.md`](context_enrichment_study.md).
- **Novo:** Todos os 30 modelos do ensemble treinados e disponíveis em `artifacts/models/`.

---

## Onda 3 — Testes & Limpeza (16 itens)

**Objetivo:** Elevar cobertura de ~55% para 70%+, remover dead code, padronizar estilo.

### Bloco 3A — Cobertura de Testes (11 itens)

- [ ] **P2.A1 - Testes para `features/`** (elo, rolling, matchup, team_identity)
  - NaN handling em ELO, edge cases rolling, divisão por zero em matchup, data leakage via train_mask.

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

### Bloco 3B — Limpeza & Consistência (5 itens)

- [ ] **P2.C1 - Remover código morto**
  - ~~`value/value_engine.py` (217 linhas) — duplicada, com bugs próprios.~~ ✅ Já removido.
  - ~~`config_backup.yml` — usar git history.~~ ✅ Já removido.
  - Verificar se `rolling.py::add_rolling_features()` é usada pelo pipeline principal ou apenas testes.
  - **Confirmado 04-MAI:** `add_rolling_features()` NÃO é usada pelo pipeline principal nem por `walk_forward.py` — apenas pelo teste `test_rolling_cross_group.py`. Remover função + teste juntos.

- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`**
  - Poisson vive em `betting/engine.py`, violando boundary. Opções: (a) mover para `probability/poisson.py`, ou (b) atualizar docs.

- [ ] **P2.C3 - Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Config RandomForest enganoso no `algorithms`.

- [ ] **P2.C5 - Corrigir docstring obsoleta em `test_shadow_integration.py`**
  - Linha 13: *"The 30-model ensemble and AnalystAgent are exclusive to Mode 1 (Backtest)"*.
  - `AnalystAgent` foi removido completamente em 03-MAI-2026 (P2 Refactoring). Corrigir para: *"The 30-model ensemble is exclusive to Mode 1 (Backtest). Shadow Mode uses a single GatekeeperAgent (Prompt Mestre V26) evaluating all markets."*

- [ ] **P2.C6 - Remover `test_add_rolling_features_stays_within_team_group` junto com `add_rolling_features()`**
  - [`test_rolling_cross_group.py::test_add_rolling_features_stays_within_team_group`](tests/features/test_rolling_cross_group.py:51) testa [`add_rolling_features()`](src/japredictbet/features/rolling.py:9) — função confirmada como código morto (usada apenas por este teste).
  - **Ação:** Remover teste + função juntos como parte de P2.C1.

---

## Onda 4 — Shadow Pipeline Residual (1 item pendente — 7 concluídos)

**Objetivo:** Completar integração do shadow pipeline com scraper REST, refinar filtros, cobertura de integração.
**Dependências:** CKPT.3 (Cockpit Telegram) depende desta trilha (absorveu P2.D4).
**Itens concluídos:** SH1-SH24 (SH4 parcial) — ver [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

- [~] **SH4 - Mapeamento Superbet → IDs internos** (parcial — apenas Brasileirão preenchido)
  - `data/mapping/superbet_teams.json` (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` — equipes sem mapeamento geram WARNING e skip.
  - **Pendente:** preencher mapeamento para as demais 9 ligas (Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga, MLS, Bundesliga, Premier League, Jupiler Pro League)

---

## Onda 5 — CI, Produto & Polish (7 itens)

**Objetivo:** Automatizar qualidade, melhorar observabilidade e experiência final.

### Bloco 5A — CI & Infraestrutura (3 itens)

- ~~**P2.B1 - CI Básico (pytest em push)** — Coverage gate > 60%.~~ ✅ **Concluído 05-MAI-2026** — GitHub Actions com Ruff lint, MyPy type check, pytest + coverage ≥60%, Python 3.11 e 3.12.
- [ ] **P2.B2 - Logging Estruturado por Aposta** — Lambdas, votos, edge, threshold, stake, resultado.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`** — Usar `utils/logging.py` existente.
- ~~**P2.B5/P2.B9 - Blindar coleta de testes** — `testpaths` e `python_files` no `pyproject.toml`.~~ ✅ **Concluído 05-MAI-2026**.
- [ ] **Completar `pyproject.toml`** — Metadata, entry points, dev dependencies.

### Bloco 5B — Produto (4 itens)

- [ ] **P2.D1 - Tratamento de Erros Robusto** — `try-except` em `fetch_odds` e pontos críticos.
- [ ] **P2.D2 - Dashboard de Saúde do Modelo** — Volume, hit rate, ROI, CLV, calibração por período.
- [x] **P2.D4 - Bot de Alertas (Telegram)** ✅ *(Absorvido por CKPT.3)* — Escopo coberto pelo Cockpit via Telegram.
- [x] **P2.D5 - Pipeline de Mercados Gerais via LLM** ✅ *(Implementado pelo P2 Refactoring 03-MAI-2026)*
  - O Gatekeeper unificado (Prompt Mestre V26) já avalia TODOS os mercados (escanteios, 1x2, BTTS, Over/Under Gols, 1º Tempo) em uma única chamada LLM.
  - Fluxo já operacional: `superbet_scraper.py` → snapshot JSON → `pre_match_odds.py` / `MatchContext` → `GatekeeperLivePipeline._call_gatekeeper()` → shadow log.
- [x] **P2.D6 - Menu Central de Execução** ✅ — Ver [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md#onda-5--itens-concluídos-03-mai-2026).
- [ ] **P2.D6.B - Bootstrap Operacional do Menu**
  - **Escopo:** Garantir que todas as opções do menu tenham pré-checagens e mensagens claras de prontidão operacional.
  - **Checklist mínima:** snapshot disponível, `artifacts/models` treinados, `feature_store.parquet` disponível, chaves LLM configuradas quando aplicável.
  - **Objetivo:** Separar claramente "menu pronto" de "pipeline pronto", evitando que o usuário execute fluxos incompletos sem diagnóstico amigável.
  - **Dependências:** P2.D6, SH13.B, SH24.

- [ ] **P2.D7 - Dashboard de Sessão (Saldo do Dia)**
  - **Tipo:** Produto / Observabilidade.
  - **Escopo:** Ler o shadow log (`shadow_log.jsonl`), agregar métricas de sessão do dia corrente e exibir no menu.
  - **Métricas:** saldo do dia (u), yield (ROI), entradas aprovadas vs rejeitadas, sequência atual (greens vs reds), total de entradas no dia.
  - **Origem:** Integração do SNIPER V25 — Controle de Sessão era o único gap real após análise cruzada.
  - **Saída esperada:** Painel no terminal (`scripts/menu.py` opção 6 ou sub-menu) com resumo executivo do dia.
  - **Módulos:** `scripts/menu.py`, novo `scripts/session_dashboard.py` (leitor do shadow log).
  - **Dependências:** Shadow log operacional (já implementado em `gatekeeper_live_pipeline.py:_write_shadow_log`).

- [ ] **P2.D8 - Auto-Healing de Nomes de Equipas**
  - **Tipo:** Melhoria de Dados. *(Movido de P4.HEAL)*
  - **Escopo:** Script de fim do dia que recolhe equipas "órfãs" (nome Superbet sem match na API-Football) e usa LLM barato para deduzir o match correto.
  - **Objetivo:** Eliminar manutenção manual do `data/mapping/superbet_teams.json`.
  - **Módulos:** Novo `scripts/auto_heal_teams.py`, `data/mapping/superbet_teams.json`.
  - **Workflow:** Cron diário → recolhe orphans do shadow log → LLM resolve → append automático.

---

## Onda 6 — Arquitetura do Cockpit, Infra & Otimização (3 Pilares)

**Objetivo:** Otimização de tokens para LLM, operação remota via Telegram e infraestrutura cloud.

- [ ] **CKPT.1 - Otimização de Tokens: Filtro de Relevância (The Bouncer V2)**
  - **Escopo:** Expandir a lógica de pré-filtro no Python para poupar tokens. Em vez de passar o JSON bruto de odds para o LLM, o módulo `pre_match_odds.py` deve aplicar a função `get_interesting_lines()`.
  - **Critérios:**
    - **Zonagem:** Apenas odds entre 1.25 e 2.20 (Zonas Alvo + Composição). Odds > 2.20 entram na Zona de Variância com stake cortado.
    - **Exclusão:** Cortar mercados de handicap ou linhas extremamente "esticadas" (ex: Over 0.5 a 1.05).
  - **Nota pós-refactor:** O critério de correlação com algoritmo foi removido — o 30-model ensemble é exclusivo do Mode 1 (Backtest) e não está disponível no Shadow Mode.

- [ ] **CKPT.2 - Cockpit via Telegram: Operação Remota**
  - **Escopo:** Transformar o sistema num serviço de sinais pessoais através de um bot de Telegram. *(Absorve P2.D4 e P4.NOTIFY)*
  - **Implementação:** Novo módulo `src/japredictbet/interfaces/telegram_bot.py` via `python-telegram-bot`.
  - **Fluxo e Comandos:** O pipeline roda no T-60; jogos `APPROVED` enviam cards com botões de Acompanhar/Ignorar. Comandos suportados: `/resumo` (jogos mapeados para hoje), `/odds [time]` (consulta rápida de odds via Superbet), e `/stats` (relatório de performance mensal).
  - **Dependências:** Onda 7 (Enriquecimento de Contexto) para qualidade das análises; P3.ENG para execução assíncrona.

- [ ] **CKPT.3 - Deploy Cloud & Containerização (Docker)**
  - **Tipo:** Infraestrutura / DevOps.
  - **Escopo:** Criar `Dockerfile` e configurar deploy contínuo em plataforma cloud (Railway, Render ou AWS EC2) para execução 24/7 do pipeline T-60.
  - **Objetivo:** Eliminar dependência do computador pessoal ligado. Permitir que o cron job rode de hora em hora automaticamente.
  - **Pré-requisitos:** CKPT.2 (Telegram) para notificações remotas. Onda 7 (Knowledge Store) para cache entre execuções.
  - **Entregáveis:** `Dockerfile`, `docker-compose.yml` (opcional), script de deploy, documentação de infraestrutura.
  - **Origem:** Plano Gemini — FASE 3 (Cloud Deploy).

---

## Onda 7 — Enriquecimento de Contexto para o Gatekeeper (4 itens)

**Objetivo:** Elevar a precisão do Gatekeeper LLM enriquecendo o `MatchContext` com dados que hoje estão ausentes (árbitro, H2H recente, notícias externas) e com memória de longo prazo (RAG) para evitar repetir erros. Esta onda é **pré-requisito para a Onda 6** (Cockpit Telegram e Deploy Cloud dependem de análises de alta qualidade).

**Motivação:** O diagnóstico de 05-MAI-2026 revelou que o `MatchContext` atual cobre odds + escalações + lesões + tabela, mas tem **3 gaps críticos**: (a) `RefereeInfo` nunca populado, (b) H2H recente ausente no Shadow Mode, (c) zero contexto externo (notícias, desfalques de última hora, perfil histórico de árbitros/times).

### Bloco 7A — Estudo e Planejamento (✅ CONCLUÍDO)

- [x] **ENR.1 - Estudo de Viabilidade: Fontes, Tecnologias e Custo/Benefício**
  - **Status:** ✅ **Concluído 04-MAI-2026.**
  - **Entregue:** [`docs/context_enrichment_study.md`](context_enrichment_study.md) cobrindo:
    - Fontes de dados avaliadas (API-Football, DuckDuckGo, Tavily, NewsAPI, RSS)
    - Comparação custo/benefício detalhada
    - Recomendação faseada (4 fases)
    - Riscos e mitigações (incluindo alerta crítico sobre standings com fallback 2024)
    - Métricas de sucesso

### Bloco 7B — Memória de Longo Prazo (RAG) (1 item)

- [ ] **ENR.2 - Knowledge Store: Memória de Longo Prazo (RAG)**
  - **Tipo:** Infraestrutura de Dados / Agentes.
  - **Escopo:** Implementar base de conhecimento leve (SQLite + embeddings) integrada ao `FeatureStore` para que o Gatekeeper "lembre" de comportamentos passados.
  - **Origem:** Ex-CKPT.2 + Gemini FASE 2.
  - **Armazenamento:**
    - **Cache de Contexto:** Escalações, desfalques e H2H dos últimos 7 dias — evita chamadas repetidas à API-Football.
    - **Histórico de Veredictos:** Armazenar por que o Gatekeeper rejeitou ou aprovou cada jogo, evitando reprocessamento idêntico e permitindo aprendizado com erros passados.
    - **Shadow Performance:** Base para `consensus_accuracy_report.py` e `session_dashboard.py` lerem rapidamente ROI por liga, mercado e horário.
    - **Perfil de Arbitragem:** Registrar padrões históricos de árbitros (média de cartões, faltas, escanteios por jogo apitado; viés casa/fora). Na avaliação de um jogo, o sistema consulta o perfil do árbitro da partida e injeta no prompt (ex: "Wilton Pereira Sampaio apitou 3 jogos do Flamengo esse ano, média 6 cartões/jogo, 60% dos jogos com over 4.5 cartões").
  - **Módulos:** `data/feature_store.py`, novo `data/knowledge_store.py`.

### Bloco 7C — Contexto por Partida (3 itens)

- [ ] **ENR.3 - Árbitro no MatchContext (Quick Win)**
  - **Tipo:** Correção de Gap Operacional.
  - **Escopo:** Popular o campo `MatchContext.referee` (dataclass [`RefereeInfo`](src/japredictbet/data/context_collector.py:63) já existe mas nunca é populado).
  - **Ação:** Adicionar chamada ao endpoint `fixtures/{id}` da API-Football (que retorna `referee` no response) durante a coleta de contexto em `ContextCollector.collect_upcoming()` e `enrich_pre_match_contexts()`.
  - **Módulos:** `data/context_collector.py` (adicionar `ApiFootballClient.get_referee()` e popular `ctx.referee`).
  - **Dependência:** Nenhuma — API-Football já está integrada com chave configurada.
  - **Referência:** Estudo completo em [`docs/context_enrichment_study.md`](context_enrichment_study.md#33-enr3--árbitro-quick-win).

- [ ] **ENR.4 - H2H Recente no MatchContext**
  - **Tipo:** Melhoria de Contexto.
  - **Escopo:** Trazer o histórico de confronto direto (H2H) para o Shadow Mode. O [`matchup.py`](src/japredictbet/features/matchup.py) já implementa `add_h2h_features()` para o Mode 1 (Backtest), mas o Shadow Mode não tem acesso a esse dado.
  - **Ação:**
    - Adicionar `ApiFootballClient.get_h2h(fixture_id)` usando o endpoint `fixtures/headtohead`.
    - Popular novo campo `MatchContext.h2h` com resumo dos últimos 3 confrontos (placar, escanteios, gols).
    - Serializar no `to_llm_context()` para injeção no prompt.
  - **Módulos:** `data/context_collector.py`, `data/context_collector.py::MatchContext`.
  - **Dependência:** ENR.3 (aproveitar a mesma chamada de API para fixtures).

- [ ] **ENR.5 - The Scout: Agente de Pesquisa Web para Contexto Externo**
  - **Tipo:** Agente / Integração.
  - **Escopo:** Evoluir o Gatekeeper com um módulo "Scout" ativo que pesquisa notícias e contexto externo para jogos de alto interesse.
  - **Origem:** Ex-CKPT.4 + Gemini FASE 1.
  - **Fluxo:**
    1. Ao identificar jogo com odds na Zona Alvo (1.60–2.20), o sistema dispara pesquisa web.
    2. Pesquisa por `"[home_team] [away_team] escalação desfalques notícias"`.
    3. Resume as 3 notícias/insights mais relevantes.
    4. Injeta no Prompt Mestre V26 como campo `[EXTERNAL_RESEARCH]`.
  - **Tecnologias candidatas:** DuckDuckGo Search (gratuito) ou Tavily API (pago, melhor qualidade) — definido pelo estudo ENR.1.
  - **Módulos:** `agents/gatekeeper.py` (integração), novo `data/web_scout.py`.
  - **Dependências:** ENR.2 (cache para evitar pesquisas repetidas).

---

## P3 — Performance, Otimização e Arquitetura (5 itens)

- ~~**P2-UNIFY — Arquitetura Unificada (03-MAI-2026)** ✅~~ *(Movido para [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md))*
  - Motor de Valor Cego (ML): 30-model ensemble opera apenas escanteios, gera `[SUGESTÕES ALGORITMO]`.
  - Motor de Contexto (LLM): Gatekeeper analisa contexto + odds sem ML, gera `[SUGESTÕES GATEKEEPER]`.
  - Ensemble output NUNCA é injetado no prompt LLM — motores paralelos independentes.
  - Handicap excluído de TODOS os motores (ML e LLM).
  - Matriz de Zonas de Odd: 4 faixas (Morta < 1.25, Builder 1.25–1.59, Alvo 1.60–2.20, Variância > 2.20).
  - `min_odd` alterado de 1.60 → 1.25 para permitir pernas de composição.
  - *(antes chamado "P3-ARCH / Divergência Positiva" — renomeado para refletir a arquitetura unificada real)*

- [ ] **P3.1 - Otimizar loop de consensus sweep** — `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar.

- [ ] **P3.ENG - Execução Assíncrona no T-60**
  - **Tipo:** Melhoria de Engenharia.
  - **Escopo:** Refatorar `gatekeeper.py`, `context_collector.py` e `gatekeeper_live_pipeline.py` usando `asyncio` e `httpx` assíncrono.
  - **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60, reduzindo tempo de varredura de minutos para segundos.
  - **Justificativa:** Proteger contra esmagamento da linha de fecho.
  - **Módulos:** `data/context_collector.py`, `agents/gatekeeper.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Quick-win (04-MAI-2026):** `concurrent.futures.ThreadPoolExecutor(max_workers=8)` no loop de `_evaluate_single_match()` em [`gatekeeper_live_pipeline.py:253`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py:253). Esforço ~30min, reduz latência de ~150s para ~20s (30 jogos). Migração asyncio completa na sequência.

- [ ] **P3.ANCHOR - Ancoragem Quantitativa para o Gatekeeper Agent**
  - **Tipo:** Melhoria Analítica.
  - **Escopo:** Adicionar modelo estatístico base (Distribuição de Poisson via Expected Goals — xG) para Match Odds (1x2) e BTTS.
  - **Objetivo:** Impedir que o Gatekeeper LLM aprove apostas baseado apenas em narrativa, obrigando cruzamento com "just price" matemático.
  - **Módulos:** `agents/gatekeeper.py`, novo `probability/xg_anchor.py`, `docs/PROMPT_MESTRE.md`.

- [ ] **P3.LLM-CONSENSUS - Consenso entre Groq e Gemini Flash para resposta final**
  - **Tipo:** Melhoria de Arquitetura Analítica.
  - **Escopo:** Criar uma camada de consenso entre dois provedores LLM (ex.: Groq + Gemini Flash) para avaliação dos mercados gerais, inspirada na lógica de consenso já usada no ensemble de escanteios.
  - **Objetivo:** Reduzir variância de resposta de um único LLM e aumentar robustez da decisão final para picks simples e compostas.
  - **Regra base proposta:** cada modelo analisa o mesmo `MatchContext`; a resposta final só aprova entrada quando houver convergência mínima configurável entre os dois agentes.
  - **Saída esperada:** parecer consolidado com status final, justificativa comum, divergências relevantes e recomendação final única.
  - **Módulos:** `agents/gatekeeper.py`, novo `agents/llm_consensus.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Nota pós-refactor:** Prompt único via `PROMPT_MESTRE.md` V26 (multi-mercado). Módulo Analyst removido — escopo unificado no Gatekeeper.

- [ ] **P3.LLM-AUDITOR - Auditor LLM para Backtest (Modo 1)**
  - **Tipo:** Melhoria Analítica.
  - **Escopo:** Criar um agente LLM específico para o Mode 1 (Backtest) que lê o relatório de saída dos 30 modelos do ensemble.
  - **Objetivo:** Complementar o [`consensus_accuracy_report.py`](scripts/consensus_accuracy_report.py) (que opera com thresholds puramente numéricos) com um auditor narrativo. O LLM lê o output de [`predict.py`](src/japredictbet/models/predict.py) e sugere, em linguagem natural:
    - Ajustes de pesos dos modelos no ensemble
    - Recomendações de calibração (Brier, ECE)
    - Ajustes nas regras de Kelly Criterion com base na variância encontrada
    - Identificação de ligas ou mercados com desempenho atípico
  - **Módulos:** `models/predict.py`, `scripts/consensus_accuracy_report.py`, novo `agents/backtest_auditor.py`.
  - **Origem:** Plano Gemini — FASE FUTURA (LLM no Modo 1).

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
