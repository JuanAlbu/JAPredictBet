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
- generate training features
- include rolling windows for last 5 and last 10 matches
- add matchup and total-corners derived features
- add rolling goal averages and recent form metrics (wins/draws/losses/points)
- include team strength ratings (ELO-style)
- standardize match statistics to the common cross-season set (corners, goals, shots, shots on target, fouls, cards, referee)

---

### Feature 2 - Model Training

The system must:

- train two machine learning models
- predict home and away corner counts
- support retraining with new datasets
- apply a time-aware split using the most recent season for testing
- weight recent seasons more heavily during training
- include team identity encoding as model features
- use XGBoost with Poisson objective and deterministic seed

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

---

### Feature 5 - Value Bet Detection

The system must:

- compute bookmaker implied probability
- compare with model probability
- detect value opportunities

### Feature 6 - Consensus Safety Decision

The system must:

- evaluate value using an ensemble of model predictions
- compute one vote per model based on `edge >= threshold`
- calculate agreement ratio and vote distribution
- discard low-consensus matches ("insecure" bets)
- confirm bets only when agreement reaches configurable consensus threshold
- log an explicit status message for each decision

### Feature 7 - Consensus Threshold Backtesting

The system must:

- run backtests across a consensus threshold grid
- support threshold increments of 5%
- return outputs that allow ROI vs volume comparison by threshold
- compute and expose threshold-level ROI and Yield metrics

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
- compute segmented financial performance (ROI/Yield) by consensus threshold
- use a standardized consensus audit report block for each evaluated bet

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

---

## Success Metrics

Model metrics:

MAE  
RMSE  

Betting metrics:

ROI  
Yield  
Hit rate

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
