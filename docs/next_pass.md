# JA PREDICT BET — ROADMAP (REVISÃO 03-MAI-2026)

**Data da Revisão:** 03 de Maio, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 ✅ | Onda 4 parcial | P3-ARCH ✅ | P2-REFACTOR ✅ — **254/254 testes** (21 arquivos). 106 features. 30 modelos.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 17 (Onda 3) + 1 (Onda 4) + 10 (Onda 5) + 4 (CKPT) + 4 (P3) + 3 (R&D) + 2 (Stretch) = 41 total

> Este documento contém **apenas itens em aberto**. Itens concluídos são registrados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## Prioridades Imediatas

1. **Treinar ensemble** — `artifacts/models/` não existe no estado atual → `python run.py --config config.yml`
2. **Onda 4 residual** — SH4 pendente (mapeamento manual), demais itens concluídos
3. **P3.ENG** — Execução assíncrona T-60 (próximo grande salto de performance)

---

## Observações LLM (03-MAI-2026)

- O Gatekeeper unificado avalia TODOS os mercados em uma única chamada LLM (Prompt Mestre V26).
- O 30-model ensemble é exclusivo do Mode 1 (Backtest) — NÃO é usado no Shadow Mode.
- Nenhum agente executa apostas reais — Shadow Mode é 100% observacional.
- Gemini AI Studio não está disponível no Brasil (limit: 0). Use OpenRouter ou Groq.

---

## Onda 3 — Testes & Limpeza (17 itens)

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

### Bloco 3B — Limpeza & Consistência (6 itens)

- [ ] **P2.C1 - Remover código morto**
  - ~~`value/value_engine.py` (217 linhas) — duplicada, com bugs próprios.~~ ✅ Já removido.
  - ~~`config_backup.yml` — usar git history.~~ ✅ Já removido.
  - Verificar se `rolling.py::add_rolling_features()` é usada pelo pipeline principal ou apenas testes.
  - **Confirmado 04-MAI:** `add_rolling_features()` NÃO é usada pelo pipeline principal nem por `walk_forward.py` — apenas pelo teste `test_rolling_cross_group.py`. Remover função + teste juntos.

- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`**
  - Poisson vive em `betting/engine.py`, violando boundary. Opções: (a) mover para `probability/poisson.py`, ou (b) atualizar docs.

- [ ] **P2.C3 - Padronizar código (linguagem + style)**
  - Mix português/inglês. Imports inline em `mvp_pipeline.py`. Config RandomForest enganoso no `algorithms`.

- [ ] **P2.C4 - Padronizar imports nos testes: `from src.japredictbet` → `from japredictbet`**
  - **6 arquivos** usam `from src.japredictbet...` (não-canônico), enquanto 16 arquivos usam `from japredictbet...` (canônico).
  - Funciona apenas porque PYTHONPATH inclui a raiz do projeto — frágil e inconsistente.
  - **Arquivos afetados:** `tests/features/test_rolling_cross_group.py`, `tests/features/test_rolling_p1b2.py`, `tests/betting/integration_p1a3.py`, `tests/betting/integration_p1a2.py`, `tests/betting/test_lambda_validation.py`, `tests/betting/test_p1a2_dynamic_margin.py`.

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

## Onda 5 — CI, Produto & Polish (13 itens)

**Objetivo:** Automatizar qualidade, melhorar observabilidade e experiência final.

### Bloco 5A — CI & Infraestrutura (5 itens)

- [ ] **P2.B1 - CI Básico (pytest em push)** — Coverage gate > 60%.
- [ ] **P2.B2 - Logging Estruturado por Aposta** — Lambdas, votos, edge, threshold, stake, resultado.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`** — Usar `utils/logging.py` existente.
- [ ] **P2.B5 - Completar `pyproject.toml`** — Metadata, entry points, dev dependencies.
- [ ] **P2.B9 - Blindar coleta de testes**
  - `python -m pytest -q` falha por coletar `test_output.txt` na raiz.
  - **Fix:** Definir `testpaths`/`python_files` no `pyproject.toml`.

### Bloco 5B — Produto (8 itens)

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

## Onda 6 — Arquitetura do Cockpit & Agentes V2 (4 Pilares)

**Objetivo:** Implementar os 4 pilares estratégicos para otimização de tokens, memória de longo prazo, operação remota e contexto externo.

- [ ] **CKPT.1 - Otimização de Tokens: Filtro de Relevância (The Bouncer V2)**
  - **Escopo:** Expandir a lógica de pré-filtro no Python para poupar tokens. Em vez de passar o JSON bruto de odds para o LLM, o módulo `pre_match_odds.py` deve aplicar a função `get_interesting_lines()`.
  - **Critérios:**
    - **Zonagem:** Apenas odds entre 1.25 e 2.20 (Zonas Alvo + Composição). Odds > 2.20 entram na Zona de Variância com stake cortado.
    - **Exclusão:** Cortar mercados de handicap ou linhas extremamente "esticadas" (ex: Over 0.5 a 1.05).
  - **Nota pós-refactor:** O critério de correlação com algoritmo foi removido — o 30-model ensemble é exclusivo do Mode 1 (Backtest) e não está disponível no Shadow Mode.

- [ ] **CKPT.2 - Base Interna: Memória de Longo Prazo (Knowledge Store)**
  - **Escopo:** Reduzir latência e custos de API com uma base leve (SQLite ou TinyDB) integrada ao `FeatureStore`.
  - **Armazenamento:**
    - **Cache de Contexto:** Escalações, desfalques e histórico de confrontos dos últimos 7 dias.
    - **Histórico de Veredictos:** Armazenar por que o Gatekeeper rejeitou um jogo, evitando reprocessamento idêntico.
    - **Shadow Performance:** Base para `consensus_accuracy_report.py` ler rapidamente o ROI por liga e modelo.

- [ ] **CKPT.3 - Cockpit via Telegram: Operação Remota**
  - **Escopo:** Transformar o sistema num serviço de sinais pessoais através de um bot de Telegram. *(Absorve P2.D4 e P4.NOTIFY)*
  - **Implementação:** Novo módulo `src/japredictbet/interfaces/telegram_bot.py` via `python-telegram-bot`.
  - **Fluxo e Comandos:** O pipeline roda no T-60; jogos `APPROVED` enviam cards com botões de Acompanhar/Ignorar. Comandos suportados: `/resumo` (jogos mapeados para hoje), `/odds [time]` (consulta rápida de odds via Superbet), e `/stats` (relatório de performance mensal).

- [ ] **CKPT.4 - Agente de Pesquisa (The Scout): Contexto Externo**
  - **Escopo:** Evoluir o Gatekeeper Agent com um módulo "Scout" ativo focado em leitura de contexto de fontes externas (ex: notícias, desfalques de última hora).
  - **Fluxo:** Ao identificar jogo de alto interesse, o agente pesquisa na web ("desfalques", "provável escalação"), resume as 3 notícias mais relevantes e injeta o resultado no Prompt Mestre V26 no campo `[EXTERNAL_RESEARCH]`.

---

## P3 — Performance, Otimização e Arquitetura (4 itens)

- ~~**P3-ARCH - Divergência Positiva (12-APR-2026)** ✅~~ *(Movido para [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md))*
  - Motor de Valor Cego (ML): 30-model ensemble opera apenas escanteios, gera `[SUGESTÕES ALGORITMO]`.
  - Motor de Contexto (LLM): Gatekeeper analisa contexto + odds sem ML, gera `[SUGESTÕES GATEKEEPER]`.
  - Ensemble output NUNCA é injetado no prompt LLM — motores paralelos independentes.
  - Handicap excluído de TODOS os motores (ML e LLM).
  - Matriz de Zonas de Odd: 4 faixas (Morta < 1.25, Builder 1.25–1.59, Alvo 1.60–2.20, Variância > 2.20).
  - `min_odd` alterado de 1.60 → 1.25 para permitir pernas de composição.

- [ ] **P3.1 - Otimizar loop de consensus sweep** — `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar.

- [ ] **P3.ENG - Execução Assíncrona no T-60**
  - **Tipo:** Melhoria de Engenharia.
  - **Escopo:** Refatorar `gatekeeper.py`, `context_collector.py` e `gatekeeper_live_pipeline.py` usando `asyncio` e `httpx` assíncrono.
  - **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60, reduzindo tempo de varredura de minutos para segundos.
  - **Justificativa:** Proteger contra esmagamento da linha de fecho.
  - **Módulos:** `data/context_collector.py`, `agents/gatekeeper.py`, `pipeline/gatekeeper_live_pipeline.py`.

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
  - **Nota pós-refactor:** Prompt único via `PROMPT_MESTRE.md` V26 (multi-mercado). Não há mais `PROMPT_ANALYST.md`.

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
