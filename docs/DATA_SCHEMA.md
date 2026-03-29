# Data Schema

## Overview

This document defines the official dataset structure used in the project.

The schema ensures:

- consistent data ingestion
- reproducible feature engineering
- clear separation between raw data and derived features
- compatibility with the machine learning pipeline

The dataset combines:

- match metadata
- match statistics
- betting odds (optional)
- derived features used by the model

---

# 1. Raw Dataset Schema

The raw dataset follows the structure commonly found in football-data datasets.

Example columns:

| Column | Type | Description |
|------|------|-------------|
| Div | string | League division |
| Date | date | Match date |
| Time | string | Match kickoff time |
| HomeTeam | string | Home team |
| AwayTeam | string | Away team |
| FTHG | integer | Full time home goals |
| FTAG | integer | Full time away goals |
| FTR | string | Full time result (H/D/A) |
| HS | integer | Home shots |
| AS | integer | Away shots |
| HST | integer | Home shots on target |
| AST | integer | Away shots on target |
| HC | integer | Home corners |
| AC | integer | Away corners |
| HF | integer | Home fouls committed |
| AF | integer | Away fouls committed |
| HY | integer | Home yellow cards |
| AY | integer | Away yellow cards |
| HR | integer | Home red cards |
| AR | integer | Away red cards |

These variables describe match events such as shots, corners, fouls, and cards.

---

# 2. Core Identifiers

These fields uniquely identify each match.

| Column | Type | Description |
|------|------|-------------|
| match_id | string | Unique match identifier |
| season | string | Season identifier |
| league | string | League name |
| date | date | Match date |
| home_team | string | Home team name |
| away_team | string | Away team name |

---

# 3. Target Variables

The machine learning model predicts corner counts.

Targets:

| Column | Type | Description |
|------|------|-------------|
| home_corners | integer | Number of home corners |
| away_corners | integer | Number of away corners |

Derived target:

| Column | Type | Description |
|------|------|-------------|
| total_corners | integer | home_corners + away_corners |

---

# 4. Team Identity Features

These features represent the identity of teams.

| Column | Type | Description |
|------|------|-------------|
| home_team_team_enc | float | Target encoding for home team |
| away_team_team_enc | float | Target encoding for away team |

Encoding method:

Default -> target encoding fitted on train split only.

Fallback encoding:

Label encoding (optional, less informative).

Purpose:

Capture structural team behavior that is not explained by statistics alone.

---

# 5. Rolling Performance Features

These features represent recent team performance.

Rolling window: **last N matches (default = 10)**.

Example features:

| Column | Type | Description |
|------|------|-------------|
| home_corners_for_last10_home | float | Avg home corners in last 10 home games |
| home_corners_against_last10_home | float | Avg corners conceded at home |
| away_corners_for_last10_away | float | Avg away corners in last 10 away games |
| away_corners_against_last10_away | float | Avg corners conceded away |
| home_shots_last10_home | float | Avg home shots in last 10 home games |
| away_shots_last10_away | float | Avg away shots in last 10 away games |

---

# 6. Matchup Features

These features represent interaction between teams.

Example features:

| Column | Type | Description |
|------|------|-------------|
| corners_attack_vs_defense | float | Home attack vs away defense |
| shots_attack_vs_defense | float | Offensive pressure comparison |
| rating_difference | float | Team strength difference |

Example calculation:

expected_home_pressure =
(home_corners_for_last10_home +
away_corners_against_last10_away) / 2

---

# 7. Optional Team Strength Features

Team strength indicators may be added.

Examples:

| Column | Type | Description |
|------|------|-------------|
| home_team_rating | float | Team strength rating |
| away_team_rating | float | Team strength rating |
| rating_difference | float | Difference between ratings |

Possible rating systems:

- ELO rating
- power ratings
- model-learned parameters

Current implementation includes ELO-style features in the training pipeline.

---

# 8. Betting Odds Data (Optional)

Odds data can be included for backtesting.

Example columns:

| Column | Type | Description |
|------|------|-------------|
| odds_over_9_5 | float | Bookmaker odds for over 9.5 corners |
| odds_under_9_5 | float | Bookmaker odds for under 9.5 corners |
| bookmaker | string | Bookmaker source |
| closing_odds | float | Closing market odds |

Odds allow evaluation of **value betting strategies**.

---

# 9. Derived Probability Fields

After model prediction, the following variables are generated.

| Column | Type | Description |
|------|------|-------------|
| lambda_home | float | Expected home corners |
| lambda_away | float | Expected away corners |
| lambda_total | float | Expected total corners |

These values are used to compute probabilities using a Poisson distribution.

---

# 10. Final Model Feature Set

Example final feature vector:

home_team_team_enc  
away_team_team_enc  

home_corners_for_last10_home  
home_corners_against_last10_home  

away_corners_for_last10_away  
away_corners_against_last10_away  

home_shots_last10_home  
away_shots_last10_away  

rating_difference  

---

# 11. Dataset Layers

The dataset is divided into layers.

Raw data layer:

original match statistics

Feature layer:

engineered rolling features

Model layer:

encoded features used for training

Prediction layer:

model outputs and probabilities

---

# 12. Data Integrity Rules

The following rules must be respected:

1. Dataset must be sorted chronologically
2. Feature engineering must use only past matches
3. Test data must never be used during feature creation
4. Team encoding must be stable across seasons

These rules prevent **data leakage**.

---

# Summary

The dataset consists of four main information layers:

1. Match metadata
2. Match statistics
3. Engineered features
4. Model predictions

This schema ensures the data pipeline remains consistent and reproducible.
