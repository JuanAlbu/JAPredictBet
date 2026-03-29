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

Default window:

10 matches.

Examples:

home_corners_for_last10_home  
home_corners_against_last10_home  

away_corners_for_last10_away  
away_corners_against_last10_away  

home_shots_last10_home  
away_shots_last10_away

---

# Matchup Features

Features describing the interaction between teams.

Examples:

corners_attack_vs_defense  

shots_attack_vs_defense  

rating_difference

Current pipeline also adds:

- ELO-based team strength features
- total corners/goals derived features (`*_total*`)
- result-form rolling metrics (wins/draws/losses/points)

---

# Feature Creation Rules

1. Use only past matches when computing rolling features
2. Do not include test data in feature creation
3. Maintain chronological order
4. Fit team target encoding only on train mask (avoid leakage)
