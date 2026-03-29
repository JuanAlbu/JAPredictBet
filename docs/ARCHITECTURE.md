# System Architecture

## Overview

This document describes the architecture of the sports betting prediction system.

The system analyzes football matches to detect potential value betting opportunities
based on statistical modelling and bookmaker odds.

The architecture combines:

- historical match data
- feature engineering
- machine learning models
- a core betting engine

---

# System Pipeline

The high-level pipeline for backtesting is:

dataset
->
data preprocessing
->
feature engineering
->
model training
->
prediction
->
betting engine
->
value bet output

For live, single-event evaluation, the flow is:
(model predictions, odds) -> betting engine -> value bet output

---

# Components

## Data Ingestion

Sources:

- historical football datasets
- odds provider (API or local file)

Output:

- structured match dataset
- structured odds data

---

## Feature Engineering

Transforms raw match data into model features.

Includes:

- rolling statistics
- matchup interaction features
- team strength (ELO ratings)
- team identity features

---

## Model Training

Machine learning models are trained on historical data to produce predictions
(e.g., expected corners).

---

## Prediction Engine

The trained models predict lambda values for upcoming matches.

Example outputs:

- `lambda_home` (expected home corners)
- `lambda_away` (expected away corners)

---

## Betting Engine (`engine.py`)

This is the core of the system. It's a self-contained module that operates on a single-event basis (one match at a time).

It is responsible for:

1.  **Probability Calculation:** Converting model lambda values into market probabilities (e.g., P(Total > 10.5)) using statistical distributions like Poisson.
2.  **Odds Normalization:** Calculating implied probability from bookmaker odds and removing the overround.
3.  **Edge & EV Calculation:** Calculating the 'edge' (model probability vs. odds probability) and the Expected Value (EV) of a bet.
4.  **Bet Decision:** Determining if a bet should be placed based on a configurable edge threshold.

This engine provides a clean API (`evaluate_match`) that takes model predictions and odds data, and returns a full evaluation of all potential bets for that match.