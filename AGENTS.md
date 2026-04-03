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
scipy  

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

data → ingestion only  
features → feature generation  
models → training and inference  
probability → statistical calculations  
betting → odds comparison logic

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
- **Tests:** 158/158 passing (15+ test files)
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
- P2 items (see docs/next_pass.md)

### Important Notes for Agents
1. **Do NOT modify model assumptions** (Poisson objective, two-model architecture) without documentation updates
2. **Reproduce P0 tests** if making changes to core pipeline (`scripts/consensus_accuracy_report.py`)
3. **Test with multiple scenarios:** full dataset, recent subset, random lines
4. **Keep CLI parametrization intact** - important for flexibility
5. **Update documentation** when implementing P2 items
6. **Reference test artifacts** in log-test/ directory for validation
7. **Feature set:** 106+ features (rolling mean + STD + EMA + matchup + result + ELO + H2H - redundant)
8. **Ensemble composition:** 10 XGBoost + 11 LightGBM + 5 Ridge + 4 ElasticNet = 30 models
9. **New modules (P1):**
   - `src/japredictbet/probability/calibration.py` — Brier Score, ECE
   - `src/japredictbet/models/shap_weights.py` — SHAP-based model quality weights
   - `src/japredictbet/betting/risk.py` — Kelly, drawdown, slippage
   - `scripts/hyperopt_search.py` — Optuna hyperparameter optimization
10. **CLI commands validated:**
    - Dynamic lines: `python scripts/consensus_accuracy_report.py --config config.yml`
    - Fixed lines: `python scripts/consensus_accuracy_report.py --fixed-line 9.5`
    - Random lines: `python scripts/consensus_accuracy_report.py --random-lines --line-min 5.5 --line-max 11.5`
    - HyperOpt: `python scripts/hyperopt_search.py --config config.yml --algorithm all --n-trials 50`