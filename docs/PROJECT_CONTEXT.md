# Project Context (Atualizado 30-MAR-2026)

## Status Atual
- **MVP Baseline:** ✅ ENTREGUE
- **P0 (Crítico):** ✅ 100% IMPLEMENTADO E VALIDADO (30-MAR-2026)
- **P1 (Alto Impacto):** 🔄 PRONTO PARA COMEÇAR

---

## Objective

The goal of this project is to build a system capable of identifying
potential value bets in football betting markets using statistical analysis
and machine learning.

The system focuses initially on:

corner markets

Example:

Over 9.5 corners

---

# Problem

Bookmaker odds represent implied probabilities that may not perfectly reflect
true event probabilities.

By modelling match statistics, it is possible to estimate the real probability
of certain events.

When the model probability exceeds the bookmaker implied probability,
a potential value betting opportunity exists.

---

# Approach

The system uses three main information layers:

1. Team Identity

Teams have structural characteristics such as tactical style and attacking
Team strength ratings (ELO-style) help capture evolving team quality.
intensity.

2. Recent Performance

Rolling statistics capture recent team behaviour.
Both short-term (last 3, 5) and medium-term (last 10) windows are used.
Recent form features include rolling goal averages and result-based metrics
(wins, draws, losses, points per game).
Rolling volatility (corner STD) added in P1 pipeline.

Training prioritizes recent matches using a time-aware split and recency weighting.
P0.6 implements strict 3-month temporal holdout for 95%+ reproducibility.

3. Matchup Interaction

The interaction between the attacking strength of one team and the defensive
profile of the opponent influences match events.
P1.5 will add H2H Last 3 confrontation history.

4. Consensus Safety Layer (P0.3 - Implementado)

The betting decision no longer depends on a single model output.
The pipeline now supports a 30-model ensemble with dynamic consensus voting.

For each match:

- each model generates lambda values
- each lambda is converted to a Poisson market probability
- each model votes "bet" when edge >= configured edge threshold
- consensus threshold is base 45%, with dynamic rule: **rises to 50% when |mean_lambda - line| < 0.5**
- the final decision is approved only if the agreement ratio reaches
  the effective consensus threshold

This implements a "safe prediction" behavior where low-agreement matches
are intentionally discarded.

The backtest layer also computes ROI and Yield by consensus threshold,
allowing direct analysis of return versus betting volume.

The model architecture remains based on two regressors per trained member
(`lambda_home` and `lambda_away`), now executed as an ensemble for safety.

The MVP execution now supports:

- automatic training of the 30-model ensemble with standardized artifacts
- deterministic balance: **70% boosting (XGBoost/LightGBM) + 30% linear (Ridge/ElasticNet)**
  - P0.2 implements automatic schedule for 25-35 model ensembles
  - P0.5 enables parallel training with n_jobs=-1 (3-5x speedup)
- robust team-name normalization for dataset/odds matching
- consensus sweep from 35% to 100% in configurable steps
- threshold-level ROI/Yield reporting with best-threshold ranking support
- safe fuzzy matching with configurable confidence threshold (`>=95` by default)
- automatic discard of ambiguous odds/dataset pairings to avoid synthetic linkage
- audit logs that record explicit odds-name to dataset-name mappings
- support for loading pre-trained ensemble artifacts from `artifacts/models`
- **full reproducibility tracking with SHA256 dataset/config hashing (P0.8)**

Operational note - P0 Complete State (30-MAR-2026):

- The production MVP pipeline keeps the configured ensemble strategy from `config.yml`
  (currently 30 members with 70/30 hybrid mix and dynamic consensus sweep).
- The experimental validation path in `scripts/consensus_accuracy_report.py` is now:
  - fully parameterized via CLI (--consensus-threshold, --edge-threshold, --blackout-count, etc.)
  - supports dynamic lines (default: mean_lambda per match)
  - supports fixed lines (--fixed-line N.5) for A/B testing
  - supports random lines (--random-lines --line-min M --line-max N) for stress testing
  - uses 30-member hybrid council (70% boosters, 30% linear models) per P0.2
  - implements dynamic consensus rule (base 45%, +50% on short margin) per P0.3
  - per-model data dropout (20%) and feature blackout (3 stats columns)
  - timestamped report generation in `log-test/` with full model audit trail
  - **all hardcodes removed (P0.1), fully respects CLI overrides and config.yml**
  
Testing & Validation (30-MAR-2026):
- Tested with 101 matches from full season data
- Tested with 50 recent matches + 180 days historical context
- Tested with random lines (5.5 - 11.5), fixed lines, and dynamic (mean_lambda)
- All tests runnable and producing valid reports in log-test/

---

# Initial Scope

The first version of the system focuses on:

football corner markets.

Future extensions may include:

- shots markets
- goals markets
- live betting analysis

---

## Contexto Histórico do MVP (Arquivado de next_pass.md em 30-MAR-2026)

### BASE ATUAL (MVP JA ENTREGUE)
*Foco: registrar rapidamente o que ja existe para evitar retrabalho.*

- [x] Ensemble deterministico de 30 modelos (10 XGB, 10 LGBM, 10 RF) - **VALIDADO**
- [x] Consenso com threshold configuravel e sweep de thresholds - **VALIDADO**
- [x] Matching robusto de equipes com fuzzy seguro e descarte de ambiguidades - **VALIDADO**
- [x] Backtest com metricas de ROI/Yield por threshold - **VALIDADO**
- [x] Arquitetura estabelecida em `src/japredictbet/` com modulos por responsabilidade - **VALIDADO**
- [x] Config centralizado em `config.yml` com parametros principais - **VALIDADO**

### TRILHA EXPERIMENTAL (CONSENSO) - JA ENTREGUE E VALIDADA ✅
*Foco: O script `scripts/consensus_accuracy_report.py` foi totalmente parametrizado e validado.*

- [x] CLI completo com suporte para thresholds, blackouts e controle de features.
- [x] Geração de logs com timestamp e relatórios de auditoria por modelo.
- [x] Suporte a conselho híbrido (boosting + linear) e regras de consenso dinâmicas.
- [x] Capacidade de stress testing com linhas de aposta fixas ou aleatórias.
- [x] **Status:** Todas as funcionalidades experimentais foram implementadas e validadas.
