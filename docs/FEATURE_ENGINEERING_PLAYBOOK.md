# Feature Engineering Playbook

## Overview

Feature engineering transforms raw match data into variables used by the model.

The project uses three feature categories.

---

# Team Identity Features

home_team_team_enc  
away_team_team_enc

Purpose:

Capture structural behaviour of teams that is not explained by
short-term statistics.

---

# Rolling Performance Features

Rolling statistics from the last N matches.

Default windows: [10, 5] matches.

## Rolling Mean (base)
home_corners_for_last10_home  
home_corners_against_last10_home  
away_corners_for_last10_away  
away_corners_against_last10_away  
home_shots_last10_home  
away_shots_last10_away

Statistics: corners, goals, shots, fouls, cards (for/against per venue).

## Rolling STD (P1.B2)
Volatility features per team/season.
Pattern: `{stat}_std_last{N}_{venue}`
Enabling flag: `features.rolling_use_std: true`

## Rolling EMA (P1.B2)
Exponential moving average with α = 2/(window+1).
Pattern: `{stat}_ema_last{N}_{venue}`
Enabling flag: `features.rolling_use_ema: true`

## Redundancy Cleanup
`drop_redundant_features()` removes perfectly correlated pairs.
Enabling flag: `features.drop_redundant: true`

Total features after cleanup: **106**.

---

# Matchup Features (P1.B4)

Features describing the interaction between teams via `add_matchup_features()`.

Generated features:

corners_attack_vs_defense  
shots_attack_vs_defense  
corners_pressure_index  
corners_diff, shots_diff, fouls_diff, cards_diff  
rating_difference

Current pipeline also adds:

- ELO-based team strength features (`add_elo_ratings()` in `elo.py`)
- total corners/goals derived features (`*_total*`)
- result-form rolling metrics (wins/draws/losses/win_rate/points_per_game)

---

# H2H Features (P1.B5)

Head-to-head features from `add_h2h_features()` in `matchup.py`.

Canonical pair matching: (A vs B) == (B vs A).

Generated features:

total_corners_h2h_last3  
total_goals_h2h_last3  
total_shots_h2h_last3

Shift(1) applied to avoid leakage. `min_periods=1` for pairs with < 3 encounters.
Config: `FeatureConfig.h2h_window = 3`.

---

# Feature Creation Rules

1. Use only past matches when computing rolling features
2. Do not include test data in feature creation
3. Maintain chronological order
4. Fit team target encoding only on train mask (avoid leakage)
