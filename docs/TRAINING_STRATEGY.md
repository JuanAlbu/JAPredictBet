# Training Strategy - Temporal Machine Learning Training

## Overview

Football performance changes over time due to:

- tactical evolution
- coaching changes
- squad turnover
- league tempo changes
- injuries and transfers

Because of this, older matches become less representative of current team performance.

This project adopts a time-aware training strategy designed to:

- prioritize recent football dynamics
- still leverage historical patterns
- avoid temporal data leakage
- preserve team identity

The training strategy balances two goals:

1. Maintain a large dataset for statistical stability
2. Prioritize recent matches that better represent current team behavior

---

# 1. Chronological Dataset Ordering

The dataset must always be sorted by match date before any processing.

Example:

2018 season
2019 season
2020 season
2021 season
2022 season
2023 season
2024 season

Important rule:

The full dataset must never be randomly shuffled.

Temporal order must always be preserved.

Exception:

A random split is allowed only inside the most recent season to define the test set.

---

# 2. Test Dataset Definition

The test dataset is derived only from the most recent season.

Procedure:

1. Identify the most recent season
2. Randomly select 50% of matches from that season using a fixed seed
3. Assign those matches to the test dataset

Example:

Season: 2024
Total matches: 380

Test set:

190 matches randomly selected

These matches represent the evaluation environment.

---

# 3. Training Dataset Definition

The training dataset includes:

- 100% of all previous seasons
- remaining 50% of matches from the most recent season

Example:

Training data:

2018-2023 -> 100% of matches
2024 -> remaining 50%

This ensures the model learns from:

- long-term patterns
- recent team performance

---

# 4. Recency Weighting Strategy

Not all matches should contribute equally during training.

Recent matches must have greater influence.

This is implemented through time-based weighting using sample weights.

Default (simple) strategy:

Linearly scale weights by season from oldest to newest.

Example weighting by season:

| Season | Weight |
|------|------|
| Oldest season | 1.0 |
| ... | ... |
| Most recent season | 2.0 |

These weights are applied as sample weights during model training.

Example concept:

model.fit(X_train, y_train, sample_weight=weights)

---

# 5. Exponential Time Decay (Advanced Option)

Instead of discrete season weights, an exponential decay function can be used.

Example:

weight = exp(-lambda * age_of_match)

Where:

age_of_match = number of days since the match occurred

This method is widely used in football prediction models such as Dixon-Coles models.

The purpose is to ensure:

recent matches -> higher influence
older matches -> progressively lower influence

---

# 6. Importance of Recent Matches

Recent matches contain more relevant information about:

- team form
- tactical systems
- player availability
- coaching changes
- squad quality

Time weighting helps balance:

more data -> statistical stability
recent data -> predictive relevance

---

# 7. Team Identity in the Model

Statistics alone cannot fully capture team behavior.

Different teams have different styles, including:

- attacking intensity
- defensive structure
- pressing strategy
- pace of play

Therefore team identity must be preserved.

Required model inputs:

home_team
away_team

Default encoding strategy:

- target encoding fitted on the training set only
- apply the learned encodings to the test set to avoid leakage

Fallback encoding strategy:

- label encoding (fast but less informative)

---

# 8. Training Pipeline

Full training pipeline:

1. Load dataset
2. Sort matches chronologically
3. Generate rolling statistics features
4. Identify most recent season
5. Randomly select 50% of latest season for test
6. Assign temporal weights to training matches
7. Train ML model
8. Evaluate using test dataset

Pipeline summary:

dataset
->
feature engineering
->
temporal split
->
recency weighting
->
model training
->
evaluation

---

# 9. Evaluation Metrics

Model performance must be evaluated using two groups of metrics.

Prediction metrics:

MAE
RMSE

Betting metrics:

ROI = (profit / stake)
Yield = (profit / turnover)
Hit Rate = winning bets / total bets

Prediction accuracy alone does not guarantee profitable betting strategies.

---

# 10. Retraining Strategy

Football evolves constantly.

The model must be retrained periodically.

Recommended retraining frequency:

- once per season
or
- whenever a significant dataset update occurs

Retraining ensures the model adapts to evolving team dynamics.

---

# Summary

Key principles of this training strategy:

- dataset sorted chronologically
- only the latest season used for testing
- 50% of the latest season reserved for test
- remaining 50% of latest season included in training
- all previous seasons used for training
- recency weighting applied to prioritize recent matches
- team identity included as model features
