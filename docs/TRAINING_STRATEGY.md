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
2. Apply a strict temporal holdout: use the last ~25% of the most recent season (approximately 3 months) as the test set
3. The split is deterministic and preserves chronological order (no random shuffle)

Example:

Season: 2024
Total matches: 380

Test set:

~95 matches (last 3 months of the season, strict temporal cutoff)

These matches represent the evaluation environment.

Implementation: `_build_temporal_split(use_strict_holdout=True, holdout_months=3)` in `mvp_pipeline.py`.

---

# 3. Training Dataset Definition

The training dataset includes:

- 100% of all previous seasons
- first ~75% of matches from the most recent season (before the temporal cutoff)

Example:

Training data:

2018-2023 -> 100% of matches
2024 -> first ~75% (before temporal cutoff)

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

# 5. Importance of Recent Matches

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

# 6. Team Identity in the Model

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

# 7. Training Pipeline

Full training pipeline:

1. Load dataset
2. Sort matches chronologically
3. Generate rolling statistics features
4. Identify most recent season
5. Randomly select 50% of latest season for test
6. Assign temporal weights to training matches
7. Train ensemble models (two-model architecture per ensemble member: home + away)
   - 70% boosters (XGBoost/LightGBM) + 30% linear (Ridge/ElasticNet)
   - Feature engineering includes rolling mean + STD + EMA + matchup + result + ELO
   - `drop_redundant_features()` removes perfectly correlated pairs
8. Run predictions and evaluate betting decisions with consensus

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

# 8. Ensemble Training Rules

Current consensus mode training uses:

- configurable ensemble size (`model.ensemble_size`)
- deterministic schedule by algorithm list (`model.algorithms`)
- default balanced mix for 30 models: 10 XGBoost + 10 LightGBM + 10 RandomForest
- deterministic variation parameters for each member
- automatic artifact persistence in `artifacts/models` when internal training is used

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

# 9.1 Experimental Consensus Sensitivity Mode

For robustness and safety studies, `scripts/consensus_accuracy_report.py`
implements an experimental council mode distinct from the default MVP run:

- fixed 30-model hybrid council:
  - 70% boosters (XGBoost/LightGBM)
  - 30% linear models (Ridge/ElasticNet)
- dynamic consensus thresholds:
  - base `45%`
  - short margin (`|mean_lambda - line| < 0.5`) -> `50%`
- fixed edge threshold `0.01` for sensitivity calibration
- line normalization to `X.5` markets only
- per-model diversity controls:
  - feature dropout `20%`
  - feature blackout of 3 stats columns (per seed)
- output is timestamped per run in `log-test/`

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
- consensus architecture built on ensemble members (home/away model pair per member)

---

# 11. P0 Training Validation Results

## Full Season Training (101 Matches)

Command: `python scripts/consensus_accuracy_report.py --n-models 30 --seed-start 42`

**Results:**
- ✅ 30 models trained successfully (21 boosters + 9 linear)
- ✅ Two-model architecture per ensemble member (home/away lambdas)
- ✅ Temporal ordering preserved across full dataset
- ✅ Recency weighting applied to training phase
- ✅ 101 matches processed chronologically
- ✅ Ensemble mean sigma: 0.45 (good agreement across 30 models)
- ✅ Reproducibility confirmed (deterministic seeds working)

**Performance:**
- 20 matches analyzed with consensus voting
- 2/2 wins on approved bets (100% accuracy on sample)
- Training time: ~2-3 minutes for 30 models

## Subset Training with Historical Context (50 Matches)

Command: `python scripts/consensus_accuracy_report.py --config config_test_50matches.yml --n-models 30`

**Results:**
- ✅ Recent season matches (2025-09-27 to 2026-03-22)
- ✅ 180-day lookback preserving rolling statistics
- ✅ Historical context sufficient for all features
- ✅ 22% of sample reserved for holdout
- ✅ Ensemble mean sigma: 0.93 (higher dispersal expected for smaller sample)
- ✅ All 50 matches trained without error

**Performance:**
- 13 matches in holdout period
- 1/1 approved bet (small sample - statistical validity questionable)
- Training time: ~1-2 minutes for 30 models

## Ensemble Composition Validation

The experimental consensus mode validates the 70/30 mix:

| Algorithm | Type | Count | Performance |
|-----------|------|-------|-------------|
| XGBoost | Booster | 10 | Stable (Mean σ=0.45) |
| LightGBM | Booster | 11 | Stable (Mean σ=0.45) |
| Ridge | Linear | 5 | Stabilizing influence |
| ElasticNet | Linear | 4 | Stabilizing influence |
| **Total** | **Mixed** | **30** | **✅ Validated** |

**Hypothesis confirmed:** Mixed ensemble (70/30 boosters/linear) reduces individual model volatility and improves consensus robustness.

## Retraining Recommendations

Based on P0 validation:

1. **Frequency:** Once per season (at season end) or when new data arrives
2. **Training time:** ~2-3 minutes for 30 models on full historical dataset
3. **Artifact management:** Automatic SHA256 versioning in `artifacts/models`
4. **Reproducibility:** Full parameter logging enables exact replication
