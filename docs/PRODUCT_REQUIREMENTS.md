# Product Requirements Document

## Product Overview

The system identifies value betting opportunities in football corner markets by comparing model-generated probabilities with bookmaker odds.

---

## Target Users

Primary users:

- sports data analysts
- quantitative bettors
- sports analytics developers

---

## Product Goals

1. Estimate corner distributions for football matches
2. Calculate probabilities for betting lines
3. Compare probabilities with bookmaker odds
4. Detect potential value bets

---

## Core Features

### Feature 1 - Historical Data Processing

The system must:

- ingest historical match data
- compute rolling statistics
- enforce rolling-window isolation by group (team/season) to prevent cross-team data leakage
- generate training features
- include rolling windows for last 5 and last 10 matches
- add matchup and total-corners derived features
- add rolling goal averages and recent form metrics (wins/draws/losses/points)
- add rolling Standard Deviation and EMA features for recent form and consistency
- add H2H (Head-to-Head) features for the last N direct matchups
- include team strength ratings (ELO-style)
- standardize match statistics to the common cross-season set (corners, goals, shots, shots on target, fouls, cards, referee)

---

### Feature 2 - Model Training

The system must:

- train two machine learning models per ensemble member (home and away)
- predict home and away corner counts
- support retraining with new datasets
- apply a time-aware split using the most recent season for testing
- weight recent seasons more heavily during training
- include team identity encoding as model features
- use XGBoost with Poisson objective and deterministic seed
- generate and persist the 30-model ensemble artifacts with standardized names
- enforce balanced hybrid ensemble training: 70% boosters (XGBoost/LightGBM) + 30% linear (Ridge/ElasticNet)
- vary hyperparameters deterministically across model members
- allow loading pre-trained ensemble artifacts from disk to skip retraining
- save auditable JSON metadata with hyperparameters alongside each model file

---

### Feature 3 - Probability Calculation

The system must:

- convert expected corners to probability distributions
- calculate probabilities for betting lines

---

### Feature 4 - Odds Integration

The system must:

- retrieve pre-match odds
- support corner over/under markets
- normalize bookmaker data format
- normalize team names for robust dataset/odds matching
- apply safe fuzzy matching only above configurable similarity threshold (default `95`)
- reject and discard ambiguous matches (close competing candidates)
- log explicit pairing audit records (odds team name -> dataset team name)

---

### Feature 5 - Value Bet Detection

The system must:

- compute bookmaker implied probability
- compare with model probability
- detect value opportunities using Expected Value (EV) formula

---

### Feature 6 - Consensus Safety Decision

The system must:

- evaluate value using an ensemble of model predictions
- compute one vote per model based on `edge >= threshold`
- calculate agreement ratio and vote distribution
- support weighted voting based on model quality (e.g., SHAP-based weights)
- discard low-consensus matches ("insecure" bets)
- confirm bets only when agreement reaches configurable consensus threshold
- log an explicit status message for each decision
- support dynamic threshold escalation based on short margin scenarios
- enforce betting-line normalization to half-goal style (`X.5`)

---

### Feature 7 - Consensus Threshold Backtesting

The system must:

- run backtests across a consensus threshold grid
- default sweep from `0.35` to `1.00` when enabled in config
- support threshold increments of 5%
- return outputs that allow ROI vs volume comparison by threshold
- compute and expose threshold-level ROI and Yield metrics
- rank thresholds by financial quality and mark the best threshold
- support experimental sensitivity runs with fixed thresholds for controlled studies

---

### Feature 8 - Advanced Model Optimization

The system must:

- provide a script for automated hyperparameter optimization (e.g., using Optuna)
- search for the best parameters for all model types in the ensemble
- use cross-validation and a relevant metric (e.g., Poisson deviance)
- produce auditable JSON reports with the best found parameters

---

### Feature 9 - Probability & Value Auditing

The system must:

- compute probability calibration metrics (Brier Score, ECE) to validate model probabilities
- produce a calibration report to show the relationship between predicted confidence and actual accuracy
- compute Closing Line Value (CLV) to measure if the system is systematically beating the market's closing odds
- produce a CLV summary report (mean CLV, hit rate)

---

### Feature 10 - Risk Management Simulation

The system must:

- provide tools to simulate betting risk and bankroll management
- calculate optimal stake sizes using the Kelly Criterion (including fractional Kelly)
- run Monte Carlo simulations to estimate potential drawdowns and risk of ruin
- simulate the effect of odds slippage on performance

---

## Functional Requirements

The system must:

- process historical datasets
- compute rolling statistics
- train machine learning models
- compute Poisson probabilities
- fetch odds
- detect value bets
- evaluate consensus agreement
- produce auditable decision logs
- generate one immutable consensus report per execution for experiment tracking
- compute segmented financial performance (ROI/Yield) by consensus threshold
- use a standardized consensus audit report block for each evaluated bet

Experimental validation requirements:

- support fixed-size hybrid ensemble tests (boosters + linear models)
- support per-model feature dropout and feature blackout for diversity tests
- expose model-level audit parameters (algorithm, alpha/l1_ratio where applicable)

---

## Non-Functional Requirements

Performance:

- handle thousands of matches

Scalability:

- allow new leagues and datasets

Modularity:

- components must be independent

Reproducibility:

- training pipeline must be deterministic
- hyperparameter searches must be reproducible
- risk simulations must be deterministic via seeding

---

## Success Metrics

Model metrics:

MAE  
RMSE  
Brier Score  
Expected Calibration Error (ECE)

Betting metrics:

ROI  
Yield  
Hit rate  
Closing Line Value (CLV)

---

## P1 Completion Status (03-APR-2026)

### ✅ All P0 and P1 Requirements Implemented

| Category | Requirement | P1 Task | Status | Notes |
|---|---|---|---|---|
| **Pipeline** | Hybrid Ensemble | A1 | ✅ | 70/30 Booster/Linear mix |
| | Dynamic Margin | A2 | ✅ | `engine.py` |
| | NaN/Inf Guard | A3 | ✅ | Lambda validation |
| **Features** | Probability Calibration | B1 | ✅ | Brier Score, ECE in `probability/calibration.py` |
| | Advanced Rolling Stats | B2 | ✅ | Rolling STD + EMA |
| | Momentum & Cross-Features| B3/B4 | ✅ | `win_rate`, `pressure_index`, etc. |
| | H2H Confronto Direto | B5 | ✅ | `matchup.py::add_h2h_features()` |
| **Optimization**| Hyperparameter Search | C1 | ✅ | `scripts/hyperopt_search.py` with Optuna |
| | SHAP Weighted Votes | C2 | ✅ | `models/shap_weights.py` + engine integration |
| | Hyperparameter Persistence | C3 | ✅ | JSON metadata saved with model .pkl files |
| **Value/Risk** | EV Formula | D1 | ✅ | `expected_value()` in `engine.py` |
| | CLV Audit | D2 | ✅ | `closing_line_value()` in `engine.py` |
| | Risk/Staking Simulation | D3 | ✅ | Kelly, Drawdown, Slippage in `betting/risk.py` |

### Validation

- **Tests:** 158/158 passing across more than 15 test files.
- **Reproducibility:** All components, including hyperparameter search and risk simulations, are deterministic.
- **Auditability:** Model parameters, SHAP values, calibration reports, and CLV metrics provide deep insight into system behavior.

---

## Future Extensions

Possible future features:

- live betting analysis
- API-based input in place of datasets
- action-oriented agents for orchestration and alerts
- xG integration
- lineup prediction
- odds movement tracking
- automated alerts
