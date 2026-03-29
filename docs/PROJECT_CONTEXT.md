# Project Context

## Objective

The goal of this project is to build a system capable of identifying
potential value bets in football betting markets using statistical analysis
and machine learning.

The system focuses initially on:

corner markets

Example:

Over 9.5 corners

---

# Problem

Bookmaker odds represent implied probabilities that may not perfectly reflect
true event probabilities.

By modelling match statistics, it is possible to estimate the real probability
of certain events.

When the model probability exceeds the bookmaker implied probability,
a potential value betting opportunity exists.

---

# Approach

The system uses three main information layers:

1. Team Identity

Teams have structural characteristics such as tactical style and attacking
Team strength ratings (ELO-style) help capture evolving team quality.
intensity.

2. Recent Performance

Rolling statistics capture recent team behaviour.
Both short-term (last 5) and medium-term (last 10) windows are used.
Recent form features include rolling goal averages and result-based metrics
(wins, draws, losses, points per game).

Training prioritizes recent matches using a time-aware split and recency weighting.

3. Matchup Interaction

The interaction between the attacking strength of one team and the defensive
profile of the opponent influences match events.

---

# Initial Scope

The first version of the system focuses on:

football corner markets.

Future extensions may include:

- shots markets
- goals markets
- live betting analysis
