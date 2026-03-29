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
Betting Engine
        ↓
Value Opportunity Output

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

---

### 2. Feature Engineering

Features are derived from **rolling statistics of the last 10 matches**.

Example features:

home_corners_for_last10_home  
home_corners_against_last10_home  
away_corners_for_last10_away  

---

### 3. Machine Learning Model

Algorithm:

XGBoost Regressor

Objective:

count:poisson

Two independent models to predict `λ_home` and `λ_away`.

---

### 4. Odds Collector

Responsible for retrieving bookmaker odds from an API or local file.

Example structure:

match  
line  
over_odds  
under_odds  

---

### 5. Betting Engine (`engine.py`)

This is the central component for all betting logic. It takes lambda predictions and odds data for a single match and performs all necessary calculations:

- **Probability Modeling:** Converts lambdas to probabilities for different markets (e.g., P(Total > 10.5)) using Poisson distribution.
- **Odds Processing:** Calculates implied probability from odds.
- **Value Calculation:** Computes edge (model prob vs. odds prob) and Expected Value (EV).
- **Decision Making:** Determines if a bet is a "value bet" based on a threshold.


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
PyYAML

---

## Project Structure

project/
├── run.py
├── config.yml
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   └── japredictbet/
│       ├── betting/
│       │   └── engine.py
│       ├── features/
│       ├── models/
│       ├── odds/
│       └── pipeline/
├── tests/
└── docs/

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
