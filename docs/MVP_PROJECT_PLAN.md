# Predict — MVP Project Plan

## 1. Project Overview

Predict is a system designed to identify **value betting opportunities in football corner markets**.

The system analyzes football matches using:

- historical match statistics
- machine learning
- statistical probability modeling
- bookmaker odds comparison

The goal is to detect inefficiencies between:

model probability  
vs  
bookmaker implied probability

When the model probability is higher than the bookmaker probability, a **value bet** may exist.

---

# 2. Product Planning

## Objective

Build a system capable of:

1. Predicting expected corners in football matches
2. Converting predictions into probability distributions
3. Comparing probabilities with bookmaker odds
4. Identifying potential value betting opportunities

---

## Initial Market Focus

Sport:

Football

Statistic analyzed:

Corners

Market:

Over/Under corners

Example:

Over 9.5 corners

---

## MVP Scope

Included in MVP:

- historical dataset ingestion
- feature engineering
- machine learning model
- probability modeling
- odds ingestion
- value bet detection
- basic backtesting

---

## Out of Scope (MVP)

- live betting
- player-level statistics
- lineup prediction
- betting automation
- arbitrage detection
- multi-sport support

---

# 3. System Architecture

## High-Level Flow

Historical Dataset
        ↓
Feature Engineering
        ↓
Machine Learning Model
        ↓
Expected Corners Prediction
        ↓
Poisson Probability Distribution
        ↓
Odds Collector
        ↓
Value Bet Detection
        ↓
Opportunity Output

---

## System Components

### 1. Data Ingestion

Responsible for loading historical datasets.

Example fields:

date  
home_team  
away_team  
home_corners  
away_corners  
home_shots  
away_shots  

---

### 2. Feature Engineering

Features are derived from **rolling statistics of the last 10 matches**.

Separated by home and away performance.

Example features:

home_corners_for_last10_home  
home_corners_against_last10_home  
away_corners_for_last10_away  
away_corners_against_last10_away  
home_shots_last10_home  
away_shots_last10_away  

Rules:

- dataset sorted by date
- only previous matches used
- matches without enough history removed

---

### 3. Machine Learning Model

Algorithm:

XGBoost Regressor

Objective:

count:poisson

Two independent models:

Model A → predict home corners  
Model B → predict away corners  

Outputs:

λ_home  
λ_away  

---

### 4. Probability Engine

Total expected corners:

λ_total = λ_home + λ_away

Assumption:

TotalCorners ~ Poisson(λ_total)

Used to calculate probabilities such as:

P(total > 8.5)  
P(total > 9.5)  
P(total > 10.5)

---

### 5. Odds Collector

Responsible for retrieving bookmaker odds.

Odds will be fetched using **sports odds APIs**.

Example structure:

match  
market  
line  
over_odds  
under_odds  

---

### 6. Value Bet Engine

Convert odds to probability:

P_odds = 1 / odd

Compare with model probability:

value = P_model − P_odds

If value exceeds threshold:

Value Bet detected.

Example threshold:

5%

---

# 4. Implementation

## Programming Language

Python

---

## Core Libraries

pandas  
numpy  
scikit-learn  
xgboost  
scipy  
requests  

---

## Project Structure

project/

data/
    raw/
    processed/

features/
    feature_engineering.py

models/
    train_model.py
    predict.py

probability/
    poisson_model.py

odds/
    odds_collector.py

betting/
    value_detector.py

analysis/
    backtest.py

docs/

---

# 5. Core Pipeline

1. Load dataset
2. Sort matches by date
3. Compute rolling statistics
4. Generate features
5. Remove matches without sufficient history
6. Train machine learning models
7. Predict expected corners
8. Compute probability distribution
9. Fetch bookmaker odds
10. Detect value betting opportunities

---

# 6. Example Prediction

Match:

Chelsea vs Arsenal

Model prediction:

λ_home = 6.3  
λ_away = 4.8  

Total expected corners:

λ_total = 11.1

Probability:

P(total > 9.5) = 64%

Bookmaker odds:

1.90

Implied probability:

52.6%

Value:

+11.4%

---

# 7. Technical Requirements

Environment:

Python 3.10+

Dependencies:

pandas  
numpy  
xgboost  
scikit-learn  
scipy  
requests  

Optional tools:

jupyter notebook  
mlflow  
dvc

---

# 8. Future Improvements

Possible future enhancements:

### Data

Expected goals (xG)  
possession statistics  
pressure metrics  

### Modeling

Negative Binomial models  
ensemble models  
Bayesian approaches  

### System

live betting analysis  
odds movement tracking  
alerts system  
multi-bookmaker comparison  

---

# 9. Success Metrics

Model Metrics:

MAE  
RMSE  

Betting Metrics:

ROI  
Yield  
Hit Rate  

---

# 10. Project Principles

- reproducible experiments
- modular architecture
- deterministic pipelines
- clear separation of responsibilities
- scalable system design