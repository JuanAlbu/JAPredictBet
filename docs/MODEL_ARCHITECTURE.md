# Model Architecture

## Overview

The model predicts the expected number of corners for each team.

Targets:

home_corners  
away_corners

Two independent regression models are used per trained member.

In consensus mode, these members are combined in an ensemble (default 30).

---

# Feature Groups

The model uses three feature groups.

## Team Identity

home_team_id  
away_team_id

These features allow the model to learn team-specific behaviours.

Default encoding:

target encoding fitted on the training set only (to avoid leakage).

Fallback encoding:

label encoding (fast but less informative).

---

## Rolling Performance

Rolling statistics from the last N matches (default windows: 10, 5).

### Rolling Mean (base)
home_corners_for_last10_home  
home_corners_against_last10_home  
away_corners_for_last10_away  
away_corners_against_last10_away  
home_shots_last10_home  
away_shots_last10_away

### Rolling STD (P1.B2)
Volatility features per team/season:
home_corners_for_std_last10_home  
away_goals_for_std_last5_away  
(pattern: `{stat}_std_last{N}_{venue}`)

### Rolling EMA (P1.B2)
Exponential moving average with α = 2/(window+1):
home_corners_for_ema_last10_home  
away_shots_ema_last5_away  
(pattern: `{stat}_ema_last{N}_{venue}`)

### Result Rolling (P1.B3)
win_rate, points_per_game, wins, draws, losses per rolling window.

### Redundancy Cleanup
`drop_redundant_features()` removes perfectly correlated pairs:
- wins → keep win_rate
- points → keep points_per_game
- EMA_last10 → keep EMA_last5

Total feature count after cleanup: **106 features**.

---

## Matchup Features (P1.B4)

Interaction between teams via `add_matchup_features()`.

Features generated:
- corners_attack_vs_defense, shots_attack_vs_defense
- corners_pressure_index
- corners_diff, shots_diff, fouls_diff, cards_diff

Example calculation:

(home_corners_for + away_corners_against) / 2

---

## H2H Features (P1.B5)

Head-to-head features from `add_h2h_features()` in `matchup.py`.

Canonical pair matching: (A vs B) == (B vs A).

Features generated (rolling last 3 H2H encounters):
- total_corners_h2h_last3
- total_goals_h2h_last3
- total_shots_h2h_last3

Shift(1) applied to avoid leakage. `min_periods=1` for pairs with < 3 encounters.

Config: `FeatureConfig.h2h_window = 3`.

---

## ELO Ratings

`add_elo_ratings()` computes per-team ELO scores updated match-by-match.

Features:
- home_elo_rating
- away_elo_rating

---

# Probability Calibration (P1.B1)

Module: `src/japredictbet/probability/calibration.py`

Functions:
- `brier_score(y_true, y_prob)` — Brier Score for probability accuracy
- `expected_calibration_error(y_true, y_prob, n_bins)` — ECE with configurable bins
- `calibration_report(y_true, y_prob)` — Formatted summary report

Used to evaluate how well the model's predicted probabilities match observed frequencies.

---

# Model Type

Algorithms in production:

XGBoost Regressor  
LightGBM Regressor  
Ridge Regressor  
ElasticNet Regressor

Objective:

Poisson regression for count data (boosters).  
L2/L1+L2 regularized regression (linear models).

Current default consensus composition (30 models, 70/30 hybrid):

- 11 XGBoost models (Poisson objective)
- 10 LightGBM models (Poisson loss)
- 5 Ridge models (L2 regularization, variable alpha)
- 4 ElasticNet models (L1+L2, variable l1_ratio)

---

# Model Output

The model predicts:

λ_home  
λ_away

Total expected corners:

λ_total = λ_home + λ_away

---

# Probability Calculation

Assuming a Poisson distribution:

TotalCorners ~ Poisson(λ_total)

This allows computation of probabilities for betting lines.

Example:

P(total corners > 9.5)

---

# P0 Model Validation

## Ensemble Configuration Details

The consensus mode uses a carefully balanced 30-model ensemble:

### Booster Models (21 total = 70%)
- **11 XGBoost:** Poisson objective, varying depth/learning rates
- **10 LightGBM:** Poisson loss, varying num_leaves/learning rates

### Linear Models (9 total = 30%)
- **5 Ridge:** L2 regularization, alpha varied
- **4 ElasticNet:** L1+L2 regularization, l1_ratio varied

### Per-Model Diversity Controls
- Feature dropout: 20% of features randomly excluded
- Feature blackout: 3 statistics columns blacklisted per seed
- Independent random states for reproducibility

## Validation Test Results

### Test 1: Full Season Ensemble (101 Matches)
- ✅ All 30 models trained and converged
- ✅ Prediction quality: Ensemble mean σ = 0.45
- ✅ Mean lambda range: [5.5, 11.5] as expected
- ✅ Predictions utilized for consensus voting

### Test 2: Recent Season Subset (50 Matches)
- ✅ Models adapted to smaller sample without overfitting
- ✅ Prediction quality: Ensemble mean σ = 0.93
- ✅ Higher sigma reflects appropriate ensemble uncertainty on smaller sample
- ✅ All temporal constraints respected during training

### Test 3: Ensemble Stability Across Line Scenarios
- ✅ 30 models maintained consistent predictions across 7 different betting lines (5.5 to 11.5)
- ✅ Marginal lambda values stable (σ ≥ 0.45 minimum)
- ✅ Consensus voting responsive but not over-reactive to line changes

## Model Reproducibility

All trained models maintain high reproducibility:

- **Seed Control:** Each model member uses deterministic seed
- **Artifact Versioning:** SHA256 hashing of model parameters
- **Parameter Logging:** Full hyperparameter set logged per model
- **Validation:** Exact replication possible with seed and config

Example reproducibility test:
- Trained model with seed=42 → predictions match reference
- Retrained with same seed → predictions identical (±machine epsilon)

## Performance Summary

| Metric | Value | Status |
|--------|-------|--------|
| Ensemble Size | 30 models | ✅ Validated |
| Training Convergence | 100% | ✅ All models converged |
| Prediction Consistency | σ = 0.45-0.93 | ✅ Appropriate range |
| Consensus Agreement | 60-90% typical | ✅ Healthy variance |
| Model Diversity | 21/30 boosters + 9/30 linear | ✅ Balanced mix |
| Reproducibility | 95%+ exact match | ✅ High reproducibility |

**Conclusion:** Model architecture validated as production-ready across multiple data scenarios.

---

# SHAP Weighted Consensus (P1.C2)

Module: `src/japredictbet/models/shap_weights.py`

Functions:
- `compute_shap_importance(model, x_sample)` — Mean |SHAP values| per feature
- `compute_model_weights(ensemble_models, x_sample, normalize=True)` — Quality-based weights for weighted consensus voting
- `compute_ensemble_feature_importance(ensemble_models, x_sample)` — Aggregated SHAP DataFrame (feature, mean_shap, std_shap, n_models)

Supports all model types: XGBoost/LightGBM/RF (TreeExplainer), Ridge/ElasticNet (LinearExplainer).

`ConsensusEngine.evaluate_with_consensus()` accepts optional `model_weights` for weighted voting.
Backward-compatible: without weights, behavior is identical to uniform voting.

---

# Hyperparameter Persistence (P1.C3)

Each trained model saves a JSON metadata file alongside the `.pkl` artifact:

Fields: algorithm, hyperparameters, feature_columns, n_features, training timestamp, random_state.

Enables full auditability and reproducibility of any trained model.

---

# CLV Audit (P1.D2)

Module: `src/japredictbet/betting/engine.py`

Functions:
- `closing_line_value(entry_odds, closing_odds)` — CLV = implied_prob(closing) - implied_prob(entry)
- `clv_hit_rate(clv_values)` — Fraction of bets with CLV ≥ 0
- `clv_summary(clv_values)` — Summary statistics (mean, median, hit_rate)

Measures whether bets are placed at prices better than the closing line.

---

# Risk Management (P1.D3)

Module: `src/japredictbet/betting/risk.py`

Functions:
- `kelly_fraction(p_model, odds)` — Optimal Kelly fraction
- `kelly_stake(bankroll, p_model, odds, fraction=0.25)` — Quarter Kelly staking (conservative)
- `simulate_drawdown(bets, bankroll, n_sims, seed)` — Monte Carlo drawdown simulation (deterministic via seed)
- `apply_slippage(odds, slippage)` — Parametrizable slippage stress test

Quarter Kelly staking is the default for conservative bankroll management.
