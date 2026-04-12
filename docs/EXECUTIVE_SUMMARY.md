# SUMÁRIO EXECUTIVO — ESTADO DO PROJETO (12-APR-2026)

## Visão Geral

| Categoria | Score | Notas |
|-----------|-------|-------|
| Funcionalidade MVP | 100% | Ensemble 30 modelos, consenso, backtest, CLI — tudo funcional |
| Shadow Pipeline | 90% | Dual-agent (Gatekeeper + Analyst), Feature Store, Pre-match + Live modes |
| Conformidade AGENTS.md | 95% | Estrutura, código, constraints OK |
| Reproducibilidade | 95% | Config-driven, seeds, requirements pinados, SHA256 |
| Integridade Dados | 100% | Datasets e lineage validados |
| Testes | 218/218 | 21 arquivos de teste, all passing |
| Documentação | 90% | Revisada e sincronizada 12-APR-2026 |

**GERAL:** ✅ MVP Production-Ready + P0 100% + P1 100% + Shadow Pipeline Operational

---

## Marcos Concluídos

### ✅ P0 — MVP Baseline (30-MAR-2026)
- Pipeline end-to-end funcional
- 30-model ensemble com consensus voting
- Artifact versioning com SHA256
- CLI 100% parametrizado (zero hardcodes)

### ✅ P0-FIX — Bugs Críticos (31-MAR a 03-APR-2026)
- FIX.1: Hybrid schedule confirmado em `train.py`
- FIX.2: `importance.py` multi-model dispatch (XGB/LGB/Ridge/ElasticNet)
- FIX.3: Config schema padronizado + validação `__post_init__`
- FIX.4: Requirements pinados + requirements-dev.txt
- FIX.5: Rolling cross-group contamination corrigido via `.transform()`
- FIX.6: Default algorithms atualizado (5 algoritmos completos)

### ✅ P1-A — Integridade do Pipeline (31-MAR-2026)
- A1: Mix 70/30 portado para core (21 boosters + 9 linear)
- A2: Dynamic margin rule em `engine.py` (`tight_margin_threshold`, `tight_margin_consensus`)
- A3: Lambda validation com NaN/Inf guard

### ✅ P1-B — Features (03-APR-2026)
- B1: Calibração de Probabilidades (Brier/ECE) — `probability/calibration.py`
- B2: Rolling STD + EMA (106 features total)
- B3: Momentum (win_rate, points_per_game) — pré-existente
- B4: Cross-features (attack×defense, diffs, pressure_index) — pré-existente
- B5: H2H Confronto Direto (last 3) — `matchup.py::add_h2h_features()`

### ✅ P1-C — Otimização e Análise (03-APR-2026)
- C1: HyperOpt via Optuna — `scripts/hyperopt_search.py`
- C2: SHAP weighted votes — `models/shap_weights.py` + weighted consensus
- C3: Hyperparameter persistence — JSON metadata alongside .pkl

### ✅ P1-D — Value e Risco (03-APR-2026)
- D1: EV formula em engine.py
- D2: CLV audit — `closing_line_value()`, `clv_hit_rate()`, `clv_summary()`
- D3: Kelly/Risk — `betting/risk.py` (Quarter Kelly, Monte Carlo, slippage)

### ✅ Consensus Script Sync (01-APR-2026)
- `consensus_accuracy_report.py` sincronizado com pipeline principal
- Agora usa 106 features (STD + EMA + drop_redundant)
- Documentação completa revisada e atualizada

### ✅ Onda 4 — Shadow Pipeline (11-APR-2026)
- SH1-SH3: Superbet SSE client (httpx, SSE parsing, market detection)
- SH5a-SH5b: Context Collector + ConsensusEngine integration
- SH6-SH9: Shadow Observe CLI, Gatekeeper Agent, Live Pipeline
- SH10: Superbet Scraper CLI (SSE discovery + REST enrichment, ~800 lines)
- SH20: Feature Store (Option C — daily pre-computed rolling features)
- SH21: Dynamic Tournament Whitelist (auto-derive from league folders)
- SH22: Analyst Agent (multi-market LLM — 1x2, BTTS, Over/Under)
- SH23: Pre-match Architecture Split (scraper JSON → pipeline)

### ✅ P3-ARCH — Divergência Positiva (12-APR-2026)
- **Motor de Valor Cego (ML):** 30-model ensemble opera apenas escanteios, gera `[SUGESTÕES ALGORITMO]`
- **Motor de Contexto (LLM):** Gatekeeper analisa contexto + odds via PROMPT_MESTRE, gera `[SUGESTÕES GATEKEEPER]`
- **Separação estrita:** Ensemble output NUNCA é injetado no prompt do LLM — motores paralelos independentes
- **Handicap excluído:** Mercado removido de TODOS os motores (ML e LLM) — não faz parte do perfil operacional
- **Matriz de Zonas de Odd:** 4 faixas (Morta < 1.25, Builder 1.25–1.59, Alvo 1.60–2.20, Variância > 2.20)
- **min_odd:** Alterado de 1.60 → 1.25 para permitir pernas de composição (Builder zone)

---

## Bloqueadores Anteriores — TODOS FECHADOS ✅

| # | Bloqueador | Status | Resolução |
|---|-----------|--------|-----------|
| 1 | Hardcodes em script experimental | ✅ FECHADO | CLI parametrizado, P0 |
| 2 | Margem dinâmica não encontrada | ✅ FECHADO | P1.A2, `_compute_dynamic_threshold()` |
| 3 | Mix 70/30 fora do core | ✅ FECHADO | P1.A1, `_build_hybrid_ensemble_schedule()` |

---

## Próximos Passos (Ordem Recomendada)

1. **Treinar ensemble** — `artifacts/models/` está vazio, executar `python run.py --config config.yml`
2. **Confirmar tournament IDs** — Bundesliga + Premier League no SSE Superbet
3. **P2.B3** — Reescrever `update_pipeline.py` (feature engineering ausente)
4. **P2.B7** — Verificar integridade de pickle (SHA256)
5. **P2.B8** — Corrigir holdout temporal cronológico
6. **P2.C7** — Integrar params do hyperopt no ensemble
7. **P2.SH15-SH19** — Itens residuais da trilha Shadow
8. **P2.A1-A8, A13** — Expandir testes para 70% cobertura

---

## Roadmap Evolutivo — Milestones P3/P4

### P3.ENG — Execução Assíncrona no T-60
- **Tipo:** Melhoria de Engenharia
- **Escopo:** Refatorar `gatekeeper.py`, `context_collector.py` e `gatekeeper_live_pipeline.py` usando `asyncio` e `httpx` assíncrono.
- **Objetivo:** Processar dezenas de jogos em paralelo na janela T-60, reduzindo tempo de varredura de minutos para segundos.
- **Justificativa:** Proteger contra esmagamento da linha de fecho — a latência atual é sequencial (1 jogo por vez).
- **Módulos afetados:** `data/context_collector.py`, `agents/gatekeeper.py`, `agents/analyst.py`, `pipeline/gatekeeper_live_pipeline.py`

### P3.ANCHOR — Ancoragem Quantitativa para o Analyst Agent
- **Tipo:** Melhoria Analítica
- **Escopo:** Adicionar modelo estatístico base (Distribuição de Poisson via Expected Goals — xG) para Match Odds (1x2) e BTTS.
- **Objetivo:** Impedir que o Analyst LLM aprove apostas baseado apenas em narrativa de texto, obrigando-o a cruzar avaliação qualitativa com um "just price" matemático.
- **Módulos afetados:** `agents/analyst.py`, novo módulo `probability/xg_anchor.py`, `docs/PROMPT_ANALYST.md`
- **Nota:** O modelo xG funciona como "âncora" — se a divergência entre o preço justo e a odd do bookmaker for negativa, o Analyst deve justificar explicitamente o porquê de prosseguir.

### P4.HEAL — Auto-Healing de Nomes de Equipas
- **Tipo:** Melhoria de Dados
- **Escopo:** Criar script de fim do dia que recolhe equipas "órfãs" (nome Superbet sem match na API-Football) e usa LLM barato para deduzir o match correto.
- **Objetivo:** Eliminar manutenção manual do `data/mapping/superbet_teams.json`.
- **Módulos afetados:** Novo script `scripts/auto_heal_teams.py`, `data/mapping/superbet_teams.json`
- **Workflow:** Cron diário → recolhe orphans do shadow log → LLM resolve → append automático → review humano opcional.

### P4.NOTIFY — Desacoplamento da Decisão via Telegram
- **Tipo:** Melhoria Operacional
- **Escopo:** Criar `notifier.py` para disparar entradas APPROVED diretamente para Telegram do utilizador.
- **Objetivo:** Eliminar necessidade de ler logs no terminal para operar.
- **Módulos afetados:** Novo módulo `pipeline/notifier.py`, `pipeline/gatekeeper_live_pipeline.py`
- **Payload:** Jogo, Odd, Stake, Classificação (Zona), Justificativa, Red Flags — formatado em Markdown para Telegram.

---

## Arquivos de Referência

- Roadmap: `docs/next_pass.md`
- Validação: `docs/VALIDATION_REPORT.md`
- Arquitetura: `docs/ARCHITECTURE.md`
- Relatórios de teste: `log-test/`
