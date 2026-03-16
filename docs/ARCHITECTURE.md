# System Architecture

## Overview

This document describes the architecture of the sports betting prediction system.

The system analyzes football matches to detect potential value betting opportunities
based on statistical modelling and bookmaker odds.

The architecture combines:

- historical match data
- feature engineering
- machine learning models
- probability modelling
- odds comparison

---

# System Pipeline

The full pipeline is:

dataset
↓
data preprocessing
↓
feature engineering
↓
team encoding
↓
model training
↓
prediction
↓
probability estimation
↓
odds comparison
↓
value bet detection

---

# Components

## Data Ingestion

Sources:

- historical football datasets
- optional odds APIs
- optional statistics APIs

Output:

structured match dataset.

---

## Feature Engineering

Transforms raw match data into model features.

Includes:

- rolling statistics (last 5 and last 10)
- matchup interaction features
- total corners aggregates
- team strength (ELO ratings)

- rolling statistics
- team identity features
- matchup interaction features

---

## Model Training

Machine learning models are trained using:

- historical matches
- recency weighting
- team identity encoding

Training rules defined in:

TRAINING_STRATEGY.md

---

## Prediction Engine

The model predicts:

expected_home_corners  
expected_away_corners

These values represent expected corner counts.

---

## Probability Module

Expected values are converted into probabilities using
Poisson distribution.

Example:

λ_total = λ_home + λ_away

P(total corners > line)

---

## Value Bet Detection

The system compares:

model probability  
vs  
bookmaker implied probability

If the difference exceeds a threshold, the system identifies a potential value bet.