# Backtesting Strategy

## Overview

Backtesting evaluates betting strategies using historical data.

The goal is to simulate how the system would have performed
in past matches.

Obs: o treinamento deve apenas prever o numero de escanteios.
A logica de aposta e validacao deve ser aplicada somente no conjunto de teste.
No teste, todas as previsoes viram aposta (over sempre). A linha e definida
pela regra de arredondamento (x.5 mais proximo ou x.5 anterior).

---

# Backtesting Pipeline

historical data
↓
model prediction
↓
probability calculation
↓
value detection
↓
bet simulation
↓
profit calculation

---

# Model Output

The model predicts:

λ_home  
λ_away

Total expected corners:

λ_total = λ_home + λ_away

Probabilities are calculated using Poisson distribution.

---

# Value Bet Calculation

Bookmaker probability:

P_odds = 1 / odds

Model probability:

P_model

Value:

value = P_model − P_odds

Bet if:

value ≥ threshold

---

# Performance Metrics

ROI

ROI = profit / total_stake

Yield

Yield = profit / total_stake

Hit Rate

HitRate = wins / total_bets

---

# Exemplo de Teste (Over com arredondamento para x.5 anterior)

Saida do modelo (away): 5.8 escanteios

Aposta: Away team mais de 5.5 escanteios na partida

Regra: usar x.5 anterior (linha = floor(previsao * 2) / 2)

Resultado do teste:

- Away team = 5 ou menos escanteios -> errou
- Away team = 6 ou mais escanteios -> acertou

---

# Exemplo de Teste (Over total da partida com arredondamento para x.5 anterior)

Saida do modelo (home): 6.1 escanteios  
Saida do modelo (away): 5.8 escanteios  
Total previsto: 11.9 escanteios

Aposta: Over 11.5 escanteios na partida

Regra: usar x.5 anterior (linha = floor(total_previsto * 2) / 2)

Resultado do teste (total real):

- Total = 11 escanteios -> errou
- Total = 12 escanteios -> acertou

Obs: o teste pode ser feito tanto no total da partida (somando home+away) quanto
individualmente por time, usando a mesma regra de x.5 anterior e a mesma linha de corte.
