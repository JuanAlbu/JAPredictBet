# AGENTS.md

## Purpose

This document defines guidelines for AI agents, assistants, or automated tools interacting with the project repository.

It ensures consistency when generating code, modifying components, or extending the system.

---

## Agent Responsibilities

Agents may assist with:

- generating code
- improving model performance
- implementing new features
- refactoring modules
- writing documentation

Agents must not:

- modify core model assumptions without documentation
- introduce breaking architecture changes
- alter dataset schema silently

---

## Project Principles

1. Deterministic pipelines
2. Reproducible experiments
3. Modular architecture
4. Clear data lineage

---

## Coding Standards

Language:

Python

Style guide:

PEP8

Preferred libraries:

pandas  
numpy  
scikit-learn  
xgboost  
lightgbm  
scipy  
optuna  
shap  
httpx  

---

## Development Rules

Agents should:

- preserve folder structure
- document new modules
- keep functions small and modular
- include docstrings
- avoid unnecessary dependencies

---

## Architecture Boundaries

Agents must respect module boundaries:

data → ingestion + live context collection (T-60)  
features → feature generation  
models → training and inference  
probability → calibration metrics (Brier, ECE)  
betting → odds comparison, Poisson probability, consensus, risk management  
odds → Superbet SSE feed collection, market extraction  
agents → LLM-based decision agents (Gatekeeper), base framework  
pipeline → orchestration (MVP pipeline + Gatekeeper Live Pipeline)

---

## Model Constraints

Model assumptions must remain:

- count data prediction
- poisson objective
- two-model architecture
- rolling averages

Changes to these assumptions require documentation updates.

---

## Documentation Policy

Every major change must update:

PROJECT_CONTEXT.md  
ARCHITECTURE.md  
PRODUCT_REQUIREMENTS.md

Completed roadmap items must be moved to:

COMPLETION_HISTORY.md

Active roadmap (open items only):

next_pass.md

---

## Agent Safety

Agents must never:

- place real bets
- connect to bookmaker accounts
- perform automated wagering

The system is strictly an **analytics tool**.

---

## Current Project Status (Updated 03-APR-2026)

### P0 Completion ✅
- **Status:** 100% COMPLETE
- **Validation:** Tested with 101 real matches + 50 recent matches + random line stress tests
- **Production Ready:** Yes
- **Key Achievements:**
  - All 9 P0 items implemented and validated
  - 30-model ensemble consensus fully functional
  - Dynamic margin rule operational
  - Parallel training enabled (3-5x speedup)
  - Full CLI parametrization complete
  - Zero hardcodes remaining
  - Artifact versioning with SHA256 hashing

### P1 Completion ✅ (03-APR-2026)
- **Status:** 100% COMPLETE
- **Tests:** 201/201 passing (23 test files)
- **P1-A (Pipeline):** ✅ COMPLETE
  - A1: Hybrid 70/30 ensemble (21 boosters + 9 linear)
  - A2: Dynamic margin rule in engine.py
  - A3: Lambda validation (NaN/Inf guard)
- **P1-B (Features):** ✅ COMPLETE
  - B1: Probability Calibration (Brier Score, ECE) — `probability/calibration.py`
  - B2: Rolling STD + EMA (106+ features)
  - B3: Momentum (win_rate, points_per_game)
  - B4: Cross-features (attack×defense, diffs, pressure_index)
  - B5: H2H Last 3 confronto direto — `matchup.py::add_h2h_features()`
- **P1-C (Optimization):** ✅ COMPLETE
  - C1: HyperOpt via Optuna — `scripts/hyperopt_search.py`
  - C2: SHAP weighted votes — `models/shap_weights.py` + weighted consensus
  - C3: Hyperparameter persistence — JSON metadata alongside .pkl
- **P1-D (Value/Risk):** ✅ COMPLETE
  - D1: EV formula in engine.py
  - D2: CLV audit — `closing_line_value()`, `clv_hit_rate()`, `clv_summary()`
  - D3: Kelly/Risk — `betting/risk.py` (Quarter Kelly, Monte Carlo, slippage)
- **Consensus script:** Synced with all P1 features (H2H + 106 rolling features)

### Next Priority
- Onda 4 residual: SH4 (team mapping preenchimento manual)
- Onda 2 residual: B3, B7, B8, C7

### Important Notes for Agents
1. **Do NOT modify model assumptions** (Poisson objective, two-model architecture) without documentation updates
2. **Reproduce P0 tests** if making changes to core pipeline (`scripts/consensus_accuracy_report.py`)
3. **Test with multiple scenarios:** full dataset, recent subset, random lines
4. **Keep CLI parametrization intact** - important for flexibility
5. **Update documentation** when implementing P2 items
6. **Reference test artifacts** in log-test/ directory for validation
7. **Feature set:** 106+ features (rolling mean + STD + EMA + matchup + result + ELO + H2H - redundant)
8. **Ensemble composition:** 11 XGBoost + 10 LightGBM + 5 Ridge + 4 ElasticNet = 30 models
9. **New modules (P1):**
   - `src/japredictbet/probability/calibration.py` — Brier Score, ECE
   - `src/japredictbet/models/shap_weights.py` — SHAP-based model quality weights
   - `src/japredictbet/betting/risk.py` — Kelly, drawdown, slippage
   - `scripts/hyperopt_search.py` — Optuna hyperparameter optimization
10. **New modules (P2 — Gatekeeper Live Pipeline):**
    - `src/japredictbet/odds/superbet_client.py` — Superbet SSE collector (httpx, backoff, market extraction)
    - `src/japredictbet/data/context_collector.py` — T-60 context aggregation (API-Football lineups, injuries, standings + Superbet odds)
    - `src/japredictbet/agents/base.py` — BaseAgent framework
    - `src/japredictbet/agents/registry.py` — Agent registry
    - `src/japredictbet/agents/gatekeeper.py` — LLM Gatekeeper agent (OpenAI, Prompt Mestre V25, pre-filter min_odd)
    - `src/japredictbet/pipeline/gatekeeper_live_pipeline.py` — T-60 orchestration (collect → consensus → LLM → shadow log)
    - `scripts/shadow_observe.py` — CLI entry point for shadow-mode observation
    - `.env.example` — Credential template (OPENAI_API_KEY, API_FOOTBALL_KEY, SUPERBET_*)
    - Config blocks: `gatekeeper`, `api_keys`, `superbet_shadow`, `api_football` em `config.yml`
    - Deps: `openai>=1.14.0`, `python-dotenv>=1.0.1`, `httpx>=0.28.0`
    - API keys via env vars — **NUNCA commitados** (`.env` no `.gitignore`)
11. **Agent Safety (reforço):** O sistema é estritamente analytics. Nenhum módulo executa aposta real. Shadow mode é observacional.
12. **New modules (Superbet Scraper — 11-APR-2026):**
    - `scripts/superbet_scraper.py` — CLI scraper standalone (SSE discovery + REST API enrichment)
    - SSE endpoints: `prematch` (jogos futuros) e `all` (live)
    - REST API: `GET /v2/pt-BR/events/{eventId}` — retorna 700+ mercados por jogo
    - Preços centesimais (>=100 → /100). Middle-dot `·` (U+00B7) como separator em matchName
    - Auto-save: `data/odds/pre_match/{date}.json`
    - **Pendências:** SH11 (Bundesliga+PL IDs), SH12 (filtro mercados), SH13 (integrar no pipeline), SH14 (cleanup temp files)
13. **CLI commands validated:**
    - Dynamic lines: `python scripts/consensus_accuracy_report.py --config config.yml`
    - Fixed lines: `python scripts/consensus_accuracy_report.py --fixed-line 9.5`
    - Random lines: `python scripts/consensus_accuracy_report.py --random-lines --line-min 5.5 --line-max 11.5`
    - HyperOpt: `python scripts/hyperopt_search.py --config config.yml --algorithm all --n-trials 50`
    - Scraper hoje: `python scripts/superbet_scraper.py hoje`
    - Scraper futuro: `python scripts/superbet_scraper.py domingo --stream-seconds 90`
    - Scraper quick (SSE only): `python scripts/superbet_scraper.py amanha --quick`
    - Scraper all markets: `python scripts/superbet_scraper.py hoje --all-markets`