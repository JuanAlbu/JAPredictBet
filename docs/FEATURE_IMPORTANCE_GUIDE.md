# Feature Importance Guide

## Objective

Feature importance analysis identifies which variables contribute most
to model predictions.

---

# Methods

Recommended methods:

XGBoost feature importance (`models/importance.py`)  
Permutation importance  
SHAP values (`models/shap_weights.py`) — supports XGBoost, LightGBM, RF (TreeExplainer), Ridge/ElasticNet (LinearExplainer)

## SHAP-based Model Weighting (P1.C2)

`compute_model_weights()` assigns quality-based weights to ensemble members.
`compute_shap_importance()` computes mean |SHAP values| per feature per model.
`compute_ensemble_feature_importance()` aggregates SHAP across all 30 models.

The `ConsensusEngine` supports weighted voting using these weights.

---

# Feature Groups to Evaluate

Team Identity

home_team_team_enc  
away_team_team_enc

Rolling Statistics

corners_last10  
shots_last10  

Matchup Features

attack_vs_defense  
rating_difference

H2H Features (P1.B5)

total_corners_h2h_last3  
total_goals_h2h_last3  
total_shots_h2h_last3

Additional groups in current pipeline:

- ELO features
- rolling result-form metrics
- rolling STD (volatility)
- rolling EMA (exponential moving average)
- derived totals (`*_total*`)

---

# Workflow

1. Train model
2. Compute feature importance
3. Remove weak features
4. Retrain model
5. Compare performance
6. Validate impact on consensus metrics (ROI/Yield/Hit Rate by threshold)
