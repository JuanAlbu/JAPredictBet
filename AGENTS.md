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

## Current Project Status (Updated 01-APR-2026)

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

### P1 Progress (01-APR-2026)
- **P1-A (Pipeline):** ✅ 100% COMPLETE
  - A1: Hybrid 70/30 ensemble in core (21 boosters + 9 linear)
  - A2: Dynamic margin rule in engine.py
  - A3: Lambda validation (NaN/Inf guard)
- **P1-B (Features):** ✅ B2/B3/B4 COMPLETE — B1 (Calibration) pending
  - B2: Rolling STD + EMA (106 features)
  - B3: Momentum (win_rate, points_per_game)
  - B4: H2H & cross-features
- **P1-C/D:** Not started
- **Tests:** 87/87 passing (10 test files)
- **Consensus script:** Synchronized with pipeline (106 features)

### Next Priority
- P1.B1 (Probability Calibration — Brier Score, ECE)

### Important Notes for Agents
1. **Do NOT modify model assumptions** (Poisson objective, two-model architecture) without documentation updates
2. **Reproduce P0 tests** if making changes to core pipeline (`scripts/consensus_accuracy_report.py`)
3. **Test with multiple scenarios:** full dataset, recent subset, random lines
4. **Keep CLI parametrization intact** - important for flexibility
5. **Update documentation** when implementing P1 items (TRAINING_STRATEGY.md, MODEL_ARCHITECTURE.md, etc.)
6. **Reference test artifacts** in log-test/ directory for validation
7. **Feature set:** 106 features (rolling mean + STD + EMA + matchup + result + ELO - redundant)
8. **Ensemble composition:** 10 XGBoost + 11 LightGBM + 5 Ridge + 4 ElasticNet = 30 models
9. **CLI commands validated:**
   - Dynamic lines: `python scripts/consensus_accuracy_report.py --config config.yml`
   - Fixed lines: `python scripts/consensus_accuracy_report.py --fixed-line 9.5`
   - Random lines: `python scripts/consensus_accuracy_report.py --random-lines --line-min 5.5 --line-max 11.5`