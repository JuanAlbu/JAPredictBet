# Feature Importance Guide

## Objective

Feature importance analysis identifies which variables contribute most
to model predictions.

---

# Methods

Recommended methods:

XGBoost feature importance  
Permutation importance  
SHAP values

---

# Feature Groups to Evaluate

Team Identity

home_team_id  
away_team_id

Rolling Statistics

corners_last10  
shots_last10  

Matchup Features

attack_vs_defense  
rating_difference

---

# Workflow

1. Train model
2. Compute feature importance
3. Remove weak features
4. Retrain model
5. Compare performance