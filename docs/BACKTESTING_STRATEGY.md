# Backtesting Strategy

## Overview

Backtesting evaluates betting strategies using historical data.

The goal is to simulate how the system would have performed
in past matches.

Obs: o treinamento deve apenas prever o numero de escanteios.
A logica de aposta e validacao deve ser aplicada no conjunto avaliado
com decisao por consenso (nao sao aceitas todas as previsoes automaticamente).

---

# Backtesting Pipeline

historical data
->
model prediction
->
probability calculation
->
value detection
->
consensus decision
->
bet simulation
->
profit calculation

---

# Model Output

The model predicts:

lambda_home  
lambda_away

Total expected corners:

lambda_total = lambda_home + lambda_away

Probabilities are calculated using Poisson distribution.

---

# Value Bet Calculation

Bookmaker probability:

P_odds = 1 / odds

Model probability:

P_model

Value:

value = P_model - P_odds

Bet only if:

value >= threshold
and agreement >= consensus_threshold

---

# Performance Metrics

ROI

ROI = profit / total_stake

Yield

Yield = profit / total_stake

Hit Rate

HitRate = wins / total_bets

---

# Exemplo de Teste (Consensus Over Total)

Modelos geram lambda_home e lambda_away; o sistema usa lambda_total por modelo.

Para uma linha fixa de odds (ex: Over 9.5 @ 1.90):

- cada modelo calcula P_model via Poisson
- cada modelo vota positivo se edge >= edge_threshold
- acordo final = votos_positivos / total_modelos
- aposta so e confirmada se o acordo atingir consensus_threshold

No backtest com sweep:

- a mesma partida e avaliada em multiplos thresholds
- o relatorio final compara ROI, Yield, Hit Rate e volume por threshold
