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

Rolling statistics from the last N matches.

Example:

home_corners_for_last10_home  
home_corners_against_last10_home  

away_corners_for_last10_away  
away_corners_against_last10_away  

home_shots_last10_home  
away_shots_last10_away

---

## Matchup Features

Interaction between teams.

Example:

attack_vs_defense

Example calculation:

(home_attack + opponent_defense) / 2

---

# Model Type

Recommended algorithms:

XGBoost Regressor  
LightGBM Regressor  
RandomForest Regressor

Objective:

Poisson regression for count data.

Current default consensus composition:

- 10 XGBoost models
- 10 LightGBM models
- 10 RandomForest models

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
