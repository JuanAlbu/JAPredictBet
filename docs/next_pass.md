# JA PREDICT BET — ROADMAP (REVISÃO 07-MAI-2026)

**Data da Revisão:** 07 de Maio, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 2 ✅ | Onda 3 ✅ | Onda 4 parcial | P3-ARCH ✅ | P2-REFACTOR ✅ | CI Pipeline ✅ | ENR.1 ✅ | FASE 0 ✅ | SCRAPER.1 ✅ | SCRAPER.2 ✅ — **254/254 testes** (21 arquivos). 106 features. 30 modelos treinados. Scraper migrado para REST by-date (20 TIDs rastreados de 19 ligas). Playwright com multi-scroll. Mapeamento `list[int]` para TIDs múltiplos.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 54 total (40 originais + 8 da varredura de 07-MAI + 6 da auditoria de 07-MAI-2026)

> Este documento contém **apenas itens em aberto**, organizados por fase de execução. Itens concluídos são registrados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## 🔴 P1 — Correções Críticas (Auditoria 07-MAI-2026) (2 itens — ~4-6h)

**Objetivo:** Fechar pontos cegos arquiteturais e blindar CI/CD identificados na auditoria de 07-MAI-2026. **Executar antes de qualquer nova feature.**

- [ ] **AUDIT.1 — Integração Cognitiva de News Context (Ponto Cego do Gatekeeper)**
  - **Tipo:** Correção Arquitetural.
  - **Problema:** O `MatchContext` não possui campo `news_context`, e o [`PROMPT_MESTRE.md`](docs/PROMPT_MESTRE.md) não instrui o Gatekeeper a analisar notícias externas. A IA é cega a eventos contextuais críticos (derbys, salários em atraso, poupança de titulares, crises internas) que impactam diretamente a qualidade da análise. Isso significa que o Gatekeeper aprova/rejeita com base apenas em dados estruturados (odds, escalações, standings), ignorando completamente fatores qualitativos externos.
  - **Ação:**
    1. Adicionar campo `news_context: str | None = None` ao dataclass [`MatchContext`](src/japredictbet/data/context_collector.py:105).
    2. Serializar `news_context` no método [`to_llm_context()`](src/japredictbet/data/context_collector.py:125) quando não for `None`.
    3. Popular `news_context` via pesquisa web (DuckDuckGo) no `ContextCollector` para jogos na Zona Alvo (1.60–2.20), integrando com o módulo `The Scout` (ENR.5 na FASE 7).
    4. Atualizar [`PROMPT_MESTRE.md`](docs/PROMPT_MESTRE.md) — adicionar sub-item **6. Contexto Noticioso** dentro da seção "🛡️ VALIDAÇÃO (5 PILARES)" (renomear para 6 pilares):
       ```
       6. Contexto Noticioso (quando `news_context` estiver presente)
       - derbies / rivalidades históricas → risco aumentado de imprevisibilidade
       - salários em atraso / crise financeira → queda de rendimento
       - poupança de titulares declarada → rotação confirmada
       - crise interna / troca de treinador → instabilidade tática
       - ⚠️ Se `news_context` for `null` ou ausente → pilar neutro, não pesa a favor nem contra
       ```
  - **Impacto:** Gatekeeper passa a ter visão qualitativa do contexto externo. Sem isso, o sistema tem um ponto cego arquitetural — análises que deveriam ser rejeitadas por red flags noticiosas passam despercebidas.
  - **Esforço:** ~3-4h (1h dataclass + serialização, 1h pesquisa web, 1h atualização do prompt).
  - **Pré-requisito para:** ENR.5 (The Scout — FASE 7), que expandirá a coleta para pesquisa ativa.

- [ ] **AUDIT.2 — Blindagem de Testes: Mocks para DuckDuckGo/Context Enricher**
  - **Tipo:** Dívida Técnica / CI/CD.
  - **Problema:** O diretório [`tests/data/`](tests/data/) está vazio — não há testes para o módulo de enriquecimento de contexto que faz chamadas de rede (API-Football, DuckDuckGo). Se a esteira do GitHub Actions rodar pesquisas reais na web, os IPs serão bloqueados por rate-limit ou timeout, quebrando o CI/CD.
  - **Ação:**
    1. Criar `tests/data/test_context_collector.py` com `unittest.mock.patch` isolando:
       - `httpx.Client.get` / `httpx.Client.post` (API-Football)
       - DuckDuckGo search (quando integrado via AUDIT.1 / ENR.5)
       - `SuperbetCollector.fetch_today_odds`
    2. Cenários: resposta vazia, timeout, JSON inválido, erro HTTP 429/500, fixture sem lineups, standings vazias, lesões vazias.
    3. Garantir que `_safe_call` e fallbacks (`Superbet-only mode`) são exercitados.
  - **Impacto:** CI/CD confiável, sem risco de bloqueio de IP. Cobertura de testes sobe em ~3-5%.
  - **Esforço:** ~2-3h.
  - **Dependência:** Executar antes ou junto com AUDIT.1 (os testes cobrirão o novo fluxo de `news_context`).

---

## Observações LLM (07-MAI-2026)

- O Gatekeeper unificado avalia TODOS os mercados em uma única chamada LLM (Prompt Mestre V26).
- O 30-model ensemble é exclusivo do Mode 1 (Backtest) — NÃO é usado no Shadow Mode.
- Nenhum agente executa apostas reais — Shadow Mode é 100% observacional.
- Gemini AI Studio não está disponível no Brasil (limit: 0). Use OpenRouter ou Groq.
- CI pipeline com GitHub Actions (Ruff lint + MyPy type check + pytest com coverage ≥60%) operacional.
- ENR.1 (Estudo de Viabilidade de Contexto) concluído — [`docs/context_enrichment_study.md`](context_enrichment_study.md).
- Todos os 30 modelos do ensemble treinados e disponíveis em `artifacts/models/`.
- **Alerta:** `config_backup.yml` ainda existe na raiz apesar do [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md) afirmar que foi removido em 03-MAI-2026. Corrigir na FASE 1.
- **Alerta:** `odds/collector.py` usa `requests` (bloqueante) enquanto todo o resto do projeto adotou `httpx`. Migrar na FASE 3.
- **Alerta (Auditoria 07-MAI-2026):** O `MatchContext` não possui campo `news_context` e o `PROMPT_MESTRE.md` não instrui o Gatekeeper a analisar notícias → Gatekeeper é cego a contexto qualitativo externo (derbies, crises, rotação). Corrigir via AUDIT.1.
- **Alerta (Auditoria 07-MAI-2026):** `tests/data/` está vazio — sem testes de isolamento de rede para o context collector. CI/CD vulnerável a rate-limit. Corrigir via AUDIT.2.

---

## 📊 Visão Geral das Fases

```
🔴 P1 (⚠️ Correções)       ██████████████████████  2 itens  |  4-6h    ← News Context + Test Mocks
FASE 1 (🧹 Limpeza)        ██████░░░░░░░░░░░░░░░░  7 itens  |  3-4h    ← Dead code + boundary + pyproject + faxina de arquivos
FASE 2 (⚡ Quick Wins)      ██████░░░░░░░░░░░░░░░░  4 itens  |  5-10h   ← ThreadPool + Árbitro + H2H + Fuzzy Match
FASE 3 (🏗️ Fundação)       ██████░░░░░░░░░░░░░░░░  5 itens  |  3-4d    ← Logging + tratamento de erros + migração httpx
FASE 4 (🧪 Testes)         ██████████████████████  10 itens |  3-5d    ← +5 módulos, cobertura ~55%→70%
FASE 5 (🎛️ Produto)        ████████████░░░░░░░░░░  7 itens  |  4-7d    ← SH4 + Dashboards + Auto-healing + Health Check + CLI
FASE 6 (⚡ Performance)     █████████░░░░░░░░░░░░░  4 itens  |  5-8d    ← Async completo + Notifier + Bouncer V2 + Cache API
FASE 7 (🧠 Contexto)       ██████████░░░░░░░░░░░░░  4 itens  |  1-2sem  ← Memória Leve + RAG + Scout + xG Anchor
FASE 8 (🤖 Avançado)       ██████████░░░░░░░░░░░░  4 itens  |  2-4sem  ← LLM Consensus + Auditor + Telegram + Docker
Intercalado                 ██████░░░░░░░░░░░░░░░░  1 item   |  quando der
R&D/Stretch                 █████░░░░░░░░░░░░░░░░  5 itens  |  sem prazo
```

---

## 🧹 FASE 1 — Limpeza Imediata (7 itens — ~3-4h)

**Objetivo:** Remover dead code confirmado, corrigir documentação obsoleta, resolver boundary architecture, organizar arquivos residuais. Zero risco, remove ruído, libera caminho para fases seguintes.

- [ ] **P2.C1/C6 — Remover `add_rolling_features()` + teste associado**
  - **Problema:** [`add_rolling_features()`](src/japredictbet/features/rolling.py:9) NÃO é usada pelo pipeline principal nem por `walk_forward.py` — apenas pelo teste [`test_add_rolling_features_stays_within_team_group`](tests/features/test_rolling_cross_group.py:51).
  - **Ação:** Remover a função de [`rolling.py`](src/japredictbet/features/rolling.py). Remover o teste + o import `add_rolling_features` de [`test_rolling_cross_group.py`](tests/features/test_rolling_cross_group.py).
  - **Validação:** `findstr "add_rolling_features" src/ tests/` → vazio. `pytest tests/features/test_rolling_cross_group.py -v` → todos passando.
  - **Esforço:** ~30min.

- [ ] **P2.C5 — Corrigir docstring obsoleta em `test_shadow_integration.py`**
  - **Problema:** Linha 13 de [`test_shadow_integration.py`](tests/pipeline/test_shadow_integration.py:13) menciona *"The 30-model ensemble and AnalystAgent are exclusive to Mode 1 (Backtest)"*. `AnalystAgent` foi removido completamente em 03-MAI-2026.
  - **Ação:** Substituir por: *"The 30-model ensemble is exclusive to Mode 1 (Backtest). Shadow Mode uses a single GatekeeperAgent (Prompt Mestre V26) evaluating all markets."*
  - **Validação:** `findstr "AnalystAgent" tests/` → vazio.
  - **Esforço:** ~2min.

- [ ] **P2.C2 — Resolver boundary `probability/` vs `betting/engine.py`**
  - **Problema:** A distribuição de Poisson vive em [`betting/engine.py`](src/japredictbet/betting/engine.py) (`poisson_over_prob`, `poisson_under_prob`), violando a boundary de responsabilidade. O diretório `probability/` foi criado para funções estatísticas puras e atualmente só contém `calibration.py`.
  - **Ação:** Mover funções Poisson para novo módulo `probability/poisson.py`. Atualizar imports em `engine.py`, `risk.py`, e testes. Manter compatibilidade — testes existentes devem continuar passando.
  - **Esforço:** ~1-2h (análise de dependências + mover + atualizar imports + validar testes).

- [ ] **Completar `pyproject.toml`**
  - **Problema:** O [`pyproject.toml`](pyproject.toml) atual tem apenas `name` + `version` + tool configs (ruff, mypy, pytest). Faltam metadata descritiva e entry points.
  - **Ação:** Adicionar `description`, `authors`, `classifiers`, `keywords`, `license`, `requires-python` (>=3.11), `dependencies` (principais: pandas, numpy, scikit-learn, xgboost, lightgbm, httpx, openai, python-dotenv, pyyaml) e `[project.scripts]` com entry points (`japredictbet-menu`, `japredictbet-scrape`, `japredictbet-shadow`).
  - **Esforço:** ~30min.
  - **Validação:** `pip install -e .` sem erros. `python -m japredictbet` não quebrar.

- [ ] **NEW.1 — Remover `config_backup.yml` ou corrigir documentação**
  - **Problema:** [`config_backup.yml`](config_backup.yml) existe na raiz do projeto, mas o [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md#onda-5--itens-concluídos-03-mai-2026) (linha 502) afirma que foi removido em 03-MAI-2026. Inconsistência entre documentação e realidade.
  - **Ação:** Avaliar se o arquivo ainda é necessário como referência. Se não for, removê-lo. Se for, corrigir o `COMPLETION_HISTORY.md`.
  - **Esforço:** ~5min.

- [ ] **NEW.2 — Limpar scripts de investigação `_*.py` remanescentes**
  - **Problema:** 3 scripts `_*.py` ainda existem em `scripts/`: [`_cross_ref_2024.py`](scripts/_cross_ref_2024.py), [`_discover_tournaments.py`](scripts/_discover_tournaments.py), [`_scrape_superbet_playwright.py`](scripts/_scrape_superbet_playwright.py). O histórico (SCRAPER.1) diz que 24 scripts `_*.py` foram removidos, mas estes 3 permanecem.
  - **Ação:**
    - `_cross_ref_2024.py` — cross-reference de 2024, provavelmente obsoleto → remover.
    - `_discover_tournaments.py` — ferramenta de descoberta de TIDs, útil para manutenção → manter ou renomear sem `_`.
    - `_scrape_superbet_playwright.py` — ferramenta de debug Playwright, útil → manter ou renomear sem `_`.
  - **Esforço:** ~10min.

- [ ] **NEW.3 — Adicionar `.coverage` ao `.gitignore`**
  - **Problema:** Arquivo [`.coverage`](.coverage) está na raiz do projeto (gerado pelo pytest-cov) e não está listado no `.gitignore`.
  - **Ação:** Adicionar `.coverage` ao [`.gitignore`](.gitignore).
  - **Esforço:** ~2min.

## ⚡ FASE 2 — Quick Wins de Performance e Contexto (4 itens — ~5-10h)

**Objetivo:** Baixo esforço, alto impacto. Reduzir latência do pipeline de minutos para segundos, preencher gaps críticos de contexto que já têm dados disponíveis, e eliminar descarte de jogos por divergência de nomes.

- [ ] **P3.ENG quick-win — `ThreadPoolExecutor` no loop de avaliação**
  - **Tipo:** Melhoria de Performance.
  - **Situação atual:** O loop `for match_ctx in matches` em [`gatekeeper_live_pipeline.py`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py) é sequencial — 30 jogos × ~5s cada = ~150s. Confirmado: 0 ocorrências de `concurrent.futures` no código.
  - **Ação:** Envolver o loop com `concurrent.futures.ThreadPoolExecutor(max_workers=8)`, processando `_evaluate_single_match()` em paralelo. Cada worker chama o LLM independentemente.
  - **Impacto:** Latência ~150s → ~20s (30 jogos com 8 workers).
  - **Esforço:** ~30min-1h.
  - **Pré-requisito para:** P3.ENG completo (migração asyncio na Fase 6).

- [ ] **ENR.3 — Árbitro no MatchContext**
  - **Tipo:** Correção de Gap Operacional.
  - **Problema:** O dataclass [`RefereeInfo`](src/japredictbet/data/context_collector.py:63) já existe mas **nunca é populado** — busca `\.referee\s*=` retornou 0 resultados. O campo `referee` JÁ VEM no response do endpoint `fixtures` da API-Football (campo `fixture.referee`) — nenhuma chamada extra necessária. O `to_llm_context()` já serializa `RefereeInfo` se não for None (linha 169-170).
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

- [ ] **AUDIT.3 — Fuzzy Matching de Nomes de Times (thefuzz/rapidfuzz)**
  - **Tipo:** Correção de Perda de Dados.
  - **Problema:** Discrepâncias entre nomes na Superbet (ex: "Internacional RS") e na API-Football (ex: "Internacional") causam descarte silencioso de jogos elegíveis. O [`_match_superbet_odds()`](src/japredictbet/data/context_collector.py:666) e o [`_find_standing()`](src/japredictbet/data/context_collector.py:789) usam matching por substring (`in`), que é frágil e falha com variações de nome comuns (FC vs F.C., siglas de estado, acentos). O `enrich_pre_match_contexts()` (linha 589-598) também sofre do mesmo problema.
  - **Estimativa de impacto:** ~10-15% dos jogos scrapingdos são descartados por mismatch de nome de time.
  - **Ação:**
    1. Adicionar `rapidfuzz` (mais rápida que `thefuzz`) ao [`requirements.txt`](requirements.txt).
    2. Criar função `_fuzzy_match_teams(superbet_name: str, api_name: str, threshold: float = 0.85) -> bool` usando `rapidfuzz.fuzz.token_sort_ratio()` ou `partial_ratio()`.
    3. Substituir matching por substring em `_match_superbet_odds()`, `_find_standing()`, e `enrich_pre_match_contexts()` pela função fuzzy.
    4. Se confiança > 85%, o sistema automaticamente adiciona o par ao [`superbet_teams.json`](data/mapping/superbet_teams.json) (append automático ao mapeamento).
  - **Impacto:** Recuperação de ~10-15% de jogos que seriam descartados. Redução de manutenção manual do `superbet_teams.json`.
  - **Esforço:** ~1-2h.
  - **Dependência:** Complementa P2.D8 (Auto-Healing) na FASE 5, mas é independente e de execução mais simples.
  - **Pré-requisito para:** SH4 (preenchimento automático acelera o mapeamento manual).

---

## 🏗️ FASE 3 — Fundação de Observabilidade (5 itens — ~3-4 dias)

**Objetivo:** Logging estruturado, tratamento de erros, e modernização de dependências legadas. **Pré-requisito silencioso** para tudo que vem depois — sem isso, debugar fases avançadas será torturante.

- [ ] **P2.B4 — Migrar `run.py` de `print()` para `logging`**
  - **Situação atual:** 10 chamadas `print()` em [`run.py`](run.py:140-253). Nenhum `print()` em `src/`. O módulo [`utils/logging.py`](src/japredictbet/utils/logging.py) já existe e está pronto para uso.
  - **Ação:** Substituir todos os `print()` por `logger.info()` / `logger.error()`. Configurar nível de log via `config.yml`.
  - **Esforço:** ~1h.

- [ ] **P2.B2 — Logging Estruturado por Aposta**
  - **Escopo:** Cada decisão do Gatekeeper deve gerar um log estruturado com: lambdas, votos do ensemble (Mode 1), edge, threshold aplicado, stake calculado, resultado final.
  - **Módulos:** `utils/logging.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Pré-requisito para:** P2.D7 (Dashboard de Sessão).
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D1 — Tratamento de Erros Robusto**
  - **Situação atual:** Já existe boa cobertura de `try-except` em `gatekeeper.py`, `feature_store.py`, `context_collector.py`, `gatekeeper_live_pipeline.py`, `shap_weights.py`, `superbet_client.py`. O gap está em `run.py` (usa try-except genérico no outer block) e nos scripts CLI (`shadow_observe.py`, `superbet_scraper.py`, `menu.py`).
  - **Escopo:** Adicionar `try-except` em pontos críticos dos scripts CLI: `fetch_odds`, chamadas API-Football, chamadas LLM, escrita de shadow log. Pipeline não deve quebrar completamente por falha em um único jogo. Erros devem ser logados e o jogo skipado com status `ERROR`.
  - **Esforço:** ~1 dia.

- [ ] **NEW.4 — Migrar `odds/collector.py` de `requests` para `httpx`**
  - **Problema:** [`odds/collector.py`](src/japredictbet/odds/collector.py) é o único módulo em `src/` que usa `requests` (bloqueante). Todo o resto do projeto adotou `httpx` (suporte a async, melhor performance). É importado por [`mvp_pipeline.py`](src/japredictbet/pipeline/mvp_pipeline.py:34) para o Mode 1 (Backtest).
  - **Ação:** Substituir `requests.get()` / `requests.post()` por `httpx.Client()`. Manter mesma interface para não quebrar o Mode 1.
  - **Esforço:** ~30min-1h.

- [ ] **NEW.5 — Adicionar retry/backoff ao cliente API-Football**
  - **Problema:** Apenas o [`SuperbetClient`](src/japredictbet/odds/superbet_client.py) tem lógica de retry com backoff. O `ContextCollector` (API-Football) em [`context_collector.py`](src/japredictbet/data/context_collector.py) não tem — falhas de rede causam perda silenciosa de contexto (standings, lineups, injuries).
  - **Ação:** Adicionar decorator ou wrapper com `tenacity` ou implementação manual de retry (3 tentativas, backoff exponencial 1s→2s→4s) nas chamadas HTTP do `ContextCollector`.
  - **Esforço:** ~1-2h.

---

## 🧪 FASE 4 — Cobertura de Testes (10 itens — ~3-5 dias)

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

### Bloco 4B — Ampliar Cobertura Existente (6 itens)

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

- [ ] **NEW.6 — Adicionar testes para `odds/collector.py`**
  - Após migração para `httpx` na FASE 3, adicionar cobertura: mock de resposta HTTP, JSON inválido, timeout, resposta vazia.

---

## 🎛️ FASE 5 — Produto & Dados (7 itens — ~4-7 dias)

**Objetivo:** Completar integração multi-liga (SH4), melhorar UX (menu bootstrap, dashboards, health check), automatizar manutenção (auto-healing) e unificar interface CLI.

- [~] **SH4 — Mapeamento Superbet → IDs internos** (parcial — apenas Brasileirão preenchido)
  - [`data/mapping/superbet_teams.json`](data/mapping/superbet_teams.json) (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` — equipes sem mapeamento geram WARNING e skip.
  - **Tournament IDs:** 20 TIDs rastreados de 19 ligas em [`data/mapping/league_tournament_ids.json`](data/mapping/league_tournament_ids.json). O formato suporta `int` (maioria das ligas) ou `list[int]` (ligas com múltiplos TIDs).
  - **Pendente:** preencher mapeamento de nomes de times para as demais 18 ligas (apenas Brasileirão preenchido atualmente).
  - **Esforço:** Trabalho manual — ~2-3 dias para todas as ligas.

- [ ] **P2.D6.B — Bootstrap Operacional do Menu**
  - **Escopo:** Garantir que todas as opções do menu tenham pré-checagens e mensagens claras de prontidão operacional.
  - **Checklist mínima:** snapshot disponível, `artifacts/models` treinados ✅, `feature_store.parquet` disponível, chaves LLM configuradas quando aplicável.
  - **Objetivo:** Separar claramente "menu pronto" de "pipeline pronto", evitando que o usuário execute fluxos incompletos sem diagnóstico amigável.
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D7 — Dashboard de Sessão (Saldo do Dia)**
  - **Tipo:** Produto / Observabilidade.
  - **Escopo:** Ler o shadow log (`shadow_log.jsonl`), agregar métricas de sessão do dia corrente e exibir no menu.
  - **Métricas:** saldo do dia (u), yield (ROI), entradas aprovadas vs rejeitadas, sequência atual (greens vs reds), total de entradas no dia.
  - **Origem:** Integração do SNIPER V25 — Controle de Sessão.
  - **Módulos:** `scripts/menu.py`, novo `scripts/session_dashboard.py` (leitor do shadow log).
  - **Dependências:** P2.B2 (Fase 3 — logging estruturado).
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D2 — Dashboard de Saúde do Modelo**
  - **Tipo:** Observabilidade / Backtest.
  - **Escopo:** Painel de métricas agregadas de performance dos 30 modelos do ensemble (Mode 1).
  - **Métricas:** Volume de apostas, hit rate, ROI, CLV médio, calibração (Brier/ECE) por período (semanal/mensal).
  - **Módulos:** `scripts/consensus_accuracy_report.py` (extensão), novo `scripts/model_health_dashboard.py`.
  - **Dependências:** Fase 3 (logging estruturado) para ter dados confiáveis de saída do Mode 1.
  - **Esforço:** ~1-2 dias.

- [ ] **P2.D8 — Auto-Healing de Nomes de Equipas**
  - **Tipo:** Melhoria de Dados.
  - **Escopo:** Script de fim do dia que recolhe equipas "órfãs" (nome Superbet sem match na API-Football) e usa LLM barato para deduzir o match correto.
  - **Objetivo:** Eliminar manutenção manual do [`superbet_teams.json`](data/mapping/superbet_teams.json).
  - **Módulos:** Novo `scripts/auto_heal_teams.py`, `data/mapping/superbet_teams.json`.
  - **Workflow:** Cron diário → recolhe orphans do shadow log → LLM resolve → append automático.
  - **Dependência:** SH4 (mapeamento é o baseline que o auto-healing expande).
  - **Esforço:** ~1-2 dias.

- [ ] **NEW.7 — Health Check de APIs (pré-pipeline)**
  - **Tipo:** Confiabilidade Operacional.
  - **Problema:** O pipeline inicia sem verificar se as APIs externas estão acessíveis, podendo falhar no meio da execução.
  - **Ação:** Criar `scripts/health_check.py` que testa conectividade com API-Football, OpenRouter/OpenAI, e Superbet antes de iniciar o pipeline. Integrar ao `menu.py` como pré-condição para opções que dependem de rede.
  - **Esforço:** ~2-3h.

- [ ] **NEW.8 — CLI unificado (consolidar entry points)**
  - **Problema:** Atualmente existem 4 entry points separados: `menu.py`, `shadow_observe.py`, `superbet_scraper.py`, `run.py`. A experiência do usuário é fragmentada.
  - **Ação:** Criar CLI unificado com subcomandos usando `argparse`:
    - `japredictbet menu` → cockpit interativo
    - `japredictbet scrape [hoje|amanha|data]` → coleta de odds
    - `japredictbet shadow [--pre-match hoje] [--dry-run]` → shadow mode
    - `japredictbet train` → treinamento do ensemble (Mode 1)
    - `japredictbet audit` → relatório de consenso
    - `japredictbet health` → health check
  - **Módulos:** Novo `src/japredictbet/cli.py`, atualizar `pyproject.toml` entry points.
  - **Dependência:** pyproject.toml completo (FASE 1).
  - **Esforço:** ~1-2 dias.

---

## ⚡ FASE 6 — Performance & Notificação (4 itens — ~5-8 dias)

**Objetivo:** Otimizações que reduzem tempo de execução e custo de tokens, mais notificação imediata para operação remota. Aproveita ganhos da Fase 2 (ThreadPoolExecutor) e avança para solução assíncrona completa.

> ⚠️ **Nota de urgência (Auditoria 07-MAI-2026):** O loop sequencial em [`gatekeeper_live_pipeline.py`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py:238) é um risco operacional real — em dias com 20+ jogos simultâneos, o tempo de avaliação sequencial (~150s) pode ultrapassar a janela T-60, fazendo o sistema perder o timing de fechamento das odds. A migração para `asyncio` é crítica e deve ser priorizada sobre features cosméticas.

- [ ] **P3.ENG completo — Migração `asyncio` + `httpx` assíncrono** ⚠️
  - **Tipo:** Melhoria de Engenharia — **Prioridade elevada**.
  - **Escopo:** Refatorar [`gatekeeper_live_pipeline.py`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py), [`gatekeeper.py`](src/japredictbet/agents/gatekeeper.py) e [`context_collector.py`](src/japredictbet/data/context_collector.py) para `asyncio` com `httpx.AsyncClient`.
  - **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60 com latência mínima, evitando perda do timing de fechamento das odds.
  - **Pré-requisito:** P3.ENG quick-win (Fase 2 — ThreadPoolExecutor). A migração asyncio é o próximo passo natural e deve substituir o ThreadPoolExecutor por `asyncio.gather()` com `httpx.AsyncClient` para chamadas paralelas à API-Football e OpenAI.
  - **Justificativa:** Proteger contra esmagamento da linha de fecho. Com 30 jogos e 8 workers async, latência cai de ~150s (sequencial) para ~5-8s (paralelo real).
  - **Esforço:** ~2-3 dias.

- [ ] **AUDIT.4 — Cockpit Notificador: Alerta Telegram para APPROVED**
  - **Tipo:** Melhoria Operacional — Quick Win.
  - **Problema:** O sistema atual exige que o usuário leia o terminal ou o `shadow_bets.log` manualmente para saber quais entradas foram aprovadas. Isso impede operação remota (celular) e reduz a velocidade de reação a oportunidades que exigem execução imediata.
  - **Ação:**
    1. Criar [`src/japredictbet/utils/notifier.py`](src/japredictbet/utils/notifier.py) com classe `TelegramNotifier` usando `python-telegram-bot`.
    2. Configurar via variáveis de ambiente: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
    3. Integrar ao final do loop em [`gatekeeper_live_pipeline.py`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py:238): sempre que `gatekeeper_status == "APPROVED"`, disparar mensagem formatada com: Jogo, Mercado, Odd, Stake, Classificação (Zona), Edge, Justificativa, Red Flags.
    4. Formatar mensagem em Markdown para Telegram (suporta negrito, código, links).
  - **Impacto:** Operação 100% remota via celular. Não depende de FASE 8 (Telegram Bot completo) — é um quick-win de notificação unilateral, sem comandos interativos.
  - **Esforço:** ~1-2h.
  - **Dependência:** Nenhuma. Independente do restante da FASE 8.
  - **Diferença vs CKPT.2 (FASE 8):** O AUDIT.4 é notificação passiva (push de APPROVED). O CKPT.2 é um bot interativo completo com comandos (`/resumo`, `/odds`, `/stats`).

- [ ] **CKPT.1 — Otimização de Tokens: Filtro de Relevância (The Bouncer V2)**
  - **Escopo:** Expandir a lógica de pré-filtro no Python para poupar tokens. Em vez de passar o JSON bruto de odds para o LLM, o módulo `pre_match_odds.py` deve aplicar a função `get_interesting_lines()`.
  - **Critérios:**
    - **Zonagem:** Apenas odds entre 1.25 e 2.20 (Zonas Alvo + Composição). Odds > 2.20 entram na Zona de Variância com stake cortado.
    - **Exclusão:** Cortar mercados de handicap ou linhas extremamente "esticadas" (ex: Over 0.5 a 1.05).
  - **Esforço:** ~1 dia.

- [ ] **NEW.9 — Cache de respostas API-Football**
  - **Problema:** Durante a janela T-60, múltiplos jogos da mesma liga disparam chamadas repetidas à API-Football para standings e fixtures. Com o plano free (100 req/dia), isso consome cota desnecessariamente.
  - **Ação:** Implementar cache em memória (dicionário com TTL de 5 minutos) ou em disco (SQLite) para respostas da API-Football. Reutilizar dados de fixtures e standings entre avaliações de jogos da mesma liga.
  - **Esforço:** ~2-3h.

---

## 🧠 FASE 7 — Contexto Avançado (4 itens — ~1-2 semanas)

**Objetivo:** Conhecimento de longo prazo (RAG), pesquisa externa ativa (The Scout), memória operacional leve (shadow_bets.log) e ancoragem quantitativa para 1x2/BTTS. **Pré-requisito para Fase 8** (Telegram e Deploy dependem de análises de alta qualidade).

- [ ] **AUDIT.5 — Memória Operacional Leve: Injeção de Histórico do `shadow_bets.log` no MatchContext**
  - **Tipo:** Melhoria Cognitiva — Quick Win pré-RAG.
  - **Problema:** O Gatekeeper não aprende com os erros passados. Um mesmo padrão de análise falha pode se repetir para as mesmas equipes em jogos consecutivos porque o LLM não tem acesso ao histórico de veredictos anteriores. Exemplo: se o Gatekeeper aprovou Over 9.5 escanteios para "Flamengo vs Palmeiras" na semana passada e o resultado foi under, ele repetirá o mesmo erro sem ter consciência do histórico.
  - **Ação:**
    1. Criar rotina leve `_inject_recent_history(match_ctx: MatchContext, n_lines: int = 200) -> MatchContext` que:
       - Lê as últimas `n_lines` do [`shadow_bets.log`](logs/shadow_bets.log) (evitando carregar o arquivo inteiro).
       - Filtra as entradas correspondentes às equipes em campo (`home_team` e `away_team` do `match_ctx`).
       - Extrai um resumo: mercado avaliado, status (APPROVED/NO BET), justificativa, red_flags.
       - Injeta no `MatchContext` como campo `recent_history: str | None`.
    2. Serializar `recent_history` no [`to_llm_context()`](src/japredictbet/data/context_collector.py:125).
    3. Atualizar [`PROMPT_MESTRE.md`](docs/PROMPT_MESTRE.md) para instruir o Gatekeeper a:
       - Consultar `recent_history` antes de avaliar.
       - Se houver APPROVED recente para o mesmo mercado/equipe → verificar se o cenário mudou.
       - Se houver NO BET recente → verificar se novas informações justificam reconsideração.
       - Nunca repetir a mesma análise falha sem nova evidência.
    4. Integrar ao pipeline em [`_evaluate_single_match()`](src/japredictbet/pipeline/gatekeeper_live_pipeline.py:281) antes da chamada `_call_gatekeeper()`.
  - **Impacto:** Gatekeeper ganha "memória de curto prazo" sem necessidade de embeddings, vector DB ou infraestrutura complexa. Evita repetição de erros de análise. Custo $0 adicional.
  - **Esforço:** ~2-3h.
  - **Dependência:** Nenhuma. Esta é uma versão leve e independente que complementa — mas não substitui — o ENR.2 (Knowledge Store completo com embeddings).
  - **Nota:** Esta é a implementação "RAG Leve" mencionada na auditoria. O ENR.2 (abaixo) é a versão completa com embeddings e vector search.

- [ ] **ENR.2 — Knowledge Store: Memória de Longo Prazo (RAG)**
  - **Tipo:** Infraestrutura de Dados / Agentes.
  - **Escopo:** Implementar base de conhecimento leve (SQLite/LanceDB + embeddings `sentence-transformers`) integrada ao `FeatureStore` para que o Gatekeeper "lembre" de comportamentos passados.
  - **Armazenamento:**
    - **Cache de Contexto:** Escalações, desfalques e H2H dos últimos 7 dias — evita chamadas repetidas à API-Football.
    - **Histórico de Veredictos:** Armazenar por que o Gatekeeper rejeitou ou aprovou cada jogo, permitindo aprendizado com erros passados.
    - **Shadow Performance:** Base para `consensus_accuracy_report.py` e `session_dashboard.py` lerem rapidamente ROI por liga, mercado e horário.
    - **Perfil de Arbitragem:** Registrar padrões históricos de árbitros.
  - **Módulos:** `data/feature_store.py`, novo `data/knowledge_store.py`.
  - **Custo mensal:** $0 (tudo local).
  - **Esforço:** ~12-20h.
  - **Referência:** [`docs/context_enrichment_study.md`](context_enrichment_study.md#5-enr2--knowledge-store-memória-de-longo-prazo-rag)
  - **Dependência:** AUDIT.5 (Memória Operacional Leve) é um quick-win que pode ser implementado imediatamente enquanto o ENR.2 completo é desenvolvido.

- [ ] **ENR.5 — The Scout: Agente de Pesquisa Web para Contexto Externo**
  - **Tipo:** Agente / Integração.
  - **Escopo:** Módulo "Scout" ativo que pesquisa notícias e contexto externo para jogos na Zona Alvo (1.60–2.20).
  - **Fluxo:** Ao identificar jogo na Zona Alvo → pesquisa web → resume 3 insights mais relevantes → injeta no Prompt Mestre como `[EXTERNAL_RESEARCH]`.
  - **Tecnologias candidatas:** DuckDuckGo Search (gratuito) ou Tavily API (pago, melhor qualidade).
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
  - **Objetivo:** Complementar o [`consensus_accuracy_report.py`](scripts/consensus_accuracy_report.py) com um auditor narrativo que sugere ajustes de pesos, calibração, Kelly Criterion e identifica ligas/mercados com desempenho atípico.
  - **Módulos:** `models/predict.py`, `scripts/consensus_accuracy_report.py`, novo `agents/backtest_auditor.py`.
  - **Dependência:** Fase 4 (testes de predict/train) para garantir que o output do Mode 1 está bem testado antes de auditá-lo.

- [ ] **CKPT.2 — Cockpit via Telegram: Operação Remota**
  - **Escopo:** Transformar o sistema num serviço de sinais pessoais através de um bot de Telegram.
  - **Implementação:** Novo módulo `src/japredictbet/interfaces/telegram_bot.py` via `python-telegram-bot`.
  - **Comandos:** `/resumo` (jogos do dia), `/odds [time]` (consulta Superbet), `/stats` (performance mensal).
  - **Dependências:** Fase 7 (contexto enriquecido para qualidade das análises), Fase 6 (async para respostas rápidas).

- [ ] **CKPT.3 — Deploy Cloud & Containerização (Docker)**
  - **Tipo:** Infraestrutura / DevOps.
  - **Escopo:** Criar `Dockerfile` e configurar deploy contínuo em plataforma cloud (Railway, Render ou AWS EC2) para execução 24/7 do pipeline T-60.
  - **Entregáveis:** `Dockerfile`, `docker-compose.yml` (opcional), script de deploy, documentação de infraestrutura.
  - **Pré-requisitos:** CKPT.2 (Telegram) para notificações remotas, Fase 7 (Knowledge Store) para cache entre execuções.

---

## 🔧 Padronização (1 item — intercalado, baixa prioridade)

> Executar em momentos de "baixa" entre fases. Não bloqueia nada.

- [ ] **P2.C3 — Padronizar código (linguagem + style)**
  - Mix português/inglês em docstrings e comentários. Imports inline em `mvp_pipeline.py`. Config RandomForest enganoso no `algorithms`.
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
