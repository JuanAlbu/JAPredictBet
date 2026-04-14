# JA PREDICT BET — ROADMAP (REVISÃO 13-APR-2026)

**Data da Revisão:** 13 de Abril, 2026
**Status Geral:** P0 ✅ | P0-FIX ✅ | P1 ✅ | Onda 1 ✅ | Onda 4 parcial | P3-ARCH ✅ — 218/218 testes (21 arquivos). 106 features. 30 modelos.
**Histórico Completo:** [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md)
**Itens pendentes:** 29 (P2) + 4 (P3) + 2 (P4) + 5 (R&D) = 40 total

> Este documento contém **apenas itens em aberto**. Itens concluídos são registados em [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

---

## Prioridades Imediatas

1. **Treinar ensemble** — `artifacts/models/` não existe no estado atual → `python run.py --config config.yml`
2. **⏳ DECISÃO AMANHÃ (13-APR-2026) — Provedor LLM gratuito:**
  - **Opção A — OpenRouter** (`meta-llama/llama-3.3-70b-instruct:free`): recomendado, gratuito, sem limite regional, API OpenAI-compatible já suportada.
  - **Opção B — Groq** (`llama-3.3-70b-versatile`): 100k tokens/dia, reset meia-noite UTC.
  - **Opção C — Gemini Flash** (`gemini-2.0-flash`): Google AI Studio, NÃO disponível no Brasil (limit: 0).
  - **Ação:** Criar chave em https://openrouter.ai/settings/keys, atualizar `.env` com:
    ```
    LLM_API_KEY="sk-or-..."
    LLM_BASE_URL="https://openrouter.ai/api/v1"
    LLM_MODEL="meta-llama/llama-3.3-70b-instruct:free"
    ```
    Rodar `python scripts/shadow_observe.py --pre-match hoje` para validar.
3. **Confirmar tournament IDs** — ✅ RESOLVIDO (Bundesliga=245, Premier League=106)
4. **Onda 2 residual** — B3, B7, B8, C7 (pipeline integrity)
5. **Onda 4 residual** — SH4, SH12-SH14, SH17-SH19, SH24 (shadow pipeline completion)
6. **P3.ENG** — Execução assíncrona T-60 (próximo grande salto de performance)

---

## Observações LLM (13-APR-2026)

- O Analyst só é chamado quando o Gatekeeper retorna GO, reduzindo o consumo de tokens em até 50%.
- Nenhum agente executa apostas reais — Shadow Mode é 100% observacional.
- Gemini AI Studio não está disponível no Brasil (limit: 0). Use OpenRouter ou Groq.

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
**Itens concluídos:** SH1-SH11, SH15-SH16, SH20-SH23 — ver [`COMPLETION_HISTORY.md`](COMPLETION_HISTORY.md).

- [ ] **SH4 - Mapeamento Superbet → IDs internos**
  - `data/mapping/superbet_teams.json` (template criado, preenchimento manual por liga).
  - `superbet_client.py` já aceita `team_mapping` — equipes sem mapeamento geram WARNING e skip.

- [ ] **SH12 - Refinar filtro de mercados no scraper**
  - Combos de jogador passam no filtro por substring match.
  - **Fix:** Match mais estrito (regex com word boundary) para mercados core.

- [ ] **SH13 - Integrar scraper REST no pipeline live**
  - Scraper é standalone. Pipeline live usa `SuperbetCollector` (SSE only, 3 mercados).
  - **Fix:** Extrair lógica REST para `superbet_client.py` (`fetch_full_event(event_id)`).

- [ ] **SH13.B - Hardening do scraper pre-match**
  - Tratar casos em que o endpoint SSE responde `200 OK`, mas não entrega eventos dentro do timeout.
  - Definir fallback oficial quando a página web tem jogos visíveis e o SSE/REST falha.
  - Objetivo: estabilizar a geração de snapshots pre-match para `hoje` e `amanhã`.

- [ ] **SH14 - Limpeza de arquivos temporários**
  - Remover: `_probe_event.py`, `_list_markets.py`, `scraper_*.txt`, `probe_out.txt`, `markets_result.txt`.

- [ ] **SH17 - Separar semântica de `Superbet-only` vs T-60**
  - `context_collector.py` retorna todos os snapshots quando `API_FOOTBALL_KEY` ausente, sem filtro de kickoff.
  - **Fix:** Aplicar filtro temporal alternativo ou segregar modo degradado.

- [ ] **SH18 - Validar H2H no `FeatureStore` para inferência ao vivo**
  - O store reduz para "última linha por time" — pode carregar H2H do último adversário, não do par futuro.
  - **Fix:** Recomputar H2H para o par consultado ou excluir H2H do `FeatureStore`.

- [ ] **SH24 - Enriquecer pre-match com API-Football (lineups, standings, injuries)**
  - Modo pre-match (`load_pre_match_contexts`) retorna `MatchContext` apenas com odds — sem escalações, classificação ou lesões.
  - Gatekeeper + Analyst decidem com contexto limitado vs Live T-60 que tem enriquecimento completo.
  - **Fix:** Após `load_pre_match_contexts()`, chamar `ApiFootballClient` para buscar `get_lineups()`, `get_injuries()`, `get_standings()` e popular os campos de cada `MatchContext`.
  - **Módulos:** `pipeline/gatekeeper_live_pipeline.py` (método `run()` bloco pre-match), `data/context_collector.py` (reutilizar lógica de enriquecimento).
  - **Dep:** `API_FOOTBALL_KEY` configurada no `.env`.

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
- [ ] **P2.D5 - Pipeline de Mercados Gerais via LLM**
  - **Escopo:** Criar pipeline pre-match para mercados gerais: buscar jogos via scraping da Superbet, buscar odds de outros mercados, enriquecer contexto, rodar análise LLM e gerar relatório final com apostas simples e compostas recomendadas conforme as regras do prompt.
  - **Fluxo:** `superbet_scraper.py` → snapshot JSON → `pre_match_odds.py` / `MatchContext` → enriquecimento contextual → análise LLM → relatório final.
  - **Saída esperada:** Relatório com picks simples, combinações sugeridas, justificativas, red flags e classificação final por entrada.
  - **Dependências:** SH13, SH17, SH24.
- [ ] **P2.D6 - Menu Central de Execução**
  - **Escopo:** Criar um menu/CLI central para operações principais do projeto, reduzindo dependência de comandos soltos e padronizando o fluxo operacional.
  - **Opções iniciais:**
    1. Atualizar planilha
    2. Treinar e atualizar parâmetros, pesos e calibrações necessárias
    3. Executar previsões
    4. Executar apenas escanteios
    5. Executar odds em geral
    6. Listar mais funções existentes
  - **Objetivo:** Unificar treino, atualização de artefatos e execução analítica em um ponto de entrada único.
  - **Módulos:** novo `scripts/menu.py` ou `run.py` expandido com modo interativo.
  - **Dependências:** P2.B3, P2.C7, P2.D5.
- [ ] **P2.D6.B - Bootstrap Operacional do Menu**
  - **Escopo:** Garantir que todas as opções do menu tenham pré-checagens e mensagens claras de prontidão operacional.
  - **Checklist mínima:** snapshot disponível, `artifacts/models` treinados, `feature_store.parquet` disponível, chaves LLM configuradas quando aplicável.
  - **Objetivo:** Separar claramente "menu pronto" de "pipeline pronto", evitando que o utilizador execute fluxos incompletos sem diagnóstico amigável.
  - **Dependências:** P2.D6, SH13.B, SH24.

---

## P3 — Performance, Otimização e Arquitetura (4 itens)

- [x] **P3-ARCH - Divergência Positiva (12-APR-2026)** ✅
  - Motor de Valor Cego (ML): 30-model ensemble opera apenas escanteios, gera `[SUGESTÕES ALGORITMO]`.
  - Motor de Contexto (LLM): Gatekeeper analisa contexto + odds sem ML, gera `[SUGESTÕES GATEKEEPER]`.
  - Ensemble output NUNCA é injetado no prompt LLM — motores paralelos independentes.
  - Handicap excluído de TODOS os motores (ML e LLM).
  - Matriz de Zonas de Odd: 4 faixas (Morta < 1.25, Builder 1.25–1.59, Alvo 1.60–2.20, Variância > 2.20).
  - `min_odd` alterado de 1.60 → 1.25 para permitir pernas de composição.

- [ ] **P3.1 - Otimizar loop de consensus sweep** — `O(rows × thresholds × 30 models)`. Vectorizar ou paralelizar.

- [ ] **P3.2 - Cache de computações caras** — Rolling stats recalculadas a cada execução. Cache com invalidação por data.

- [ ] **P3.ENG - Execução Assíncrona no T-60**
  - **Tipo:** Melhoria de Engenharia.
  - **Escopo:** Refatorar `gatekeeper.py`, `context_collector.py` e `gatekeeper_live_pipeline.py` usando `asyncio` e `httpx` assíncrono.
  - **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60, reduzindo tempo de varredura de minutos para segundos.
  - **Justificativa:** Proteger contra esmagamento da linha de fecho.
  - **Módulos:** `data/context_collector.py`, `agents/gatekeeper.py`, `agents/analyst.py`, `pipeline/gatekeeper_live_pipeline.py`.

- [ ] **P3.ANCHOR - Ancoragem Quantitativa para o Analyst Agent**
  - **Tipo:** Melhoria Analítica.
  - **Escopo:** Adicionar modelo estatístico base (Distribuição de Poisson via Expected Goals — xG) para Match Odds (1x2) e BTTS.
  - **Objetivo:** Impedir que o Analyst LLM aprove apostas baseado apenas em narrativa, obrigando cruzamento com "just price" matemático.
  - **Módulos:** `agents/analyst.py`, novo `probability/xg_anchor.py`, `docs/PROMPT_ANALYST.md`.

- [ ] **P3.LLM-CONSENSUS - Consenso entre Groq e Gemini Flash para resposta final**
  - **Tipo:** Melhoria de Arquitetura Analítica.
  - **Escopo:** Criar uma camada de consenso entre dois provedores LLM (ex.: Groq + Gemini Flash) para avaliação dos mercados gerais, inspirada na lógica de consenso já usada no ensemble de escanteios.
  - **Objetivo:** Reduzir variância de resposta de um único LLM e aumentar robustez da decisão final para picks simples e compostas.
  - **Regra base proposta:** cada modelo analisa o mesmo `MatchContext`; a resposta final só aprova entrada quando houver convergência mínima configurável entre os dois agentes.
  - **Saída esperada:** parecer consolidado com status final, justificativa comum, divergências relevantes e recomendação final única.
  - **Módulos:** `agents/analyst.py`, novo `agents/llm_consensus.py`, `pipeline/gatekeeper_live_pipeline.py`, `docs/PROMPT_ANALYST.md`.

---

## P4 — Automação e Operações (2 itens)

- [ ] **P4.HEAL - Auto-Healing de Nomes de Equipas**
  - **Tipo:** Melhoria de Dados.
  - **Escopo:** Script de fim do dia que recolhe equipas “órfãs” (nome Superbet sem match na API-Football) e usa LLM barato para deduzir o match correto.
  - **Objetivo:** Eliminar manutenção manual do `data/mapping/superbet_teams.json`.
  - **Módulos:** Novo `scripts/auto_heal_teams.py`, `data/mapping/superbet_teams.json`.
  - **Workflow:** Cron diário → recolhe orphans do shadow log → LLM resolve → append automático.

- [ ] **P4.NOTIFY - Desacoplamento da Decisão via Telegram**
  - **Tipo:** Melhoria Operacional.
  - **Escopo:** Criar `notifier.py` para disparar entradas APPROVED para Telegram.
  - **Objetivo:** Eliminar necessidade de ler logs no terminal para operar.
  - **Módulos:** Novo `pipeline/notifier.py`, `pipeline/gatekeeper_live_pipeline.py`.
  - **Payload:** Jogo, Odd, Stake, Classificação (Zona), Justificativa, Red Flags.

---

## R&D — Pesquisa e Desenvolvimento (5 itens)

- [ ] **Binomial Negativa Bivariada** — Migração de Poisson para modelos com sobredispersão.
- [ ] **Stacking Meta-Modelo** — Ponderação aprendida dos membros do ensemble.
- [ ] **Game State / Live Variables** — Impacto de estado de jogo em cantos.
- [ ] **GNN Tático** — Modelagem estrutural de interações entre jogadores.
- [ ] **Favourite-Longshot Bias** — Ajustes para vieses sistemáticos do mercado.
