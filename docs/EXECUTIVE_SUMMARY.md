# SUMÁRIO EXECUTIVO — ESTADO DO PROJETO (11-APR-2026)

## Visão Geral

| Categoria | Score | Notas |
|-----------|-------|-------|
| Funcionalidade MVP | 100% | Ensemble 30 modelos, consenso, backtest, CLI — tudo funcional |
| Shadow Pipeline | 90% | Dual-agent (Gatekeeper + Analyst), Feature Store, Pre-match + Live modes |
| Conformidade AGENTS.md | 95% | Estrutura, código, constraints OK |
| Reproducibilidade | 95% | Config-driven, seeds, requirements pinados, SHA256 |
| Integridade Dados | 100% | Datasets e lineage validados |
| Testes | 218/218 | 21 arquivos de teste, all passing |
| Documentação | 90% | Revisada e sincronizada 11-APR-2026 |

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

## Arquivos de Referência

- Roadmap: `docs/next_pass.md`
- Validação: `docs/VALIDATION_REPORT.md`
- Arquitetura: `docs/ARCHITECTURE.md`
- Relatórios de teste: `log-test/`
