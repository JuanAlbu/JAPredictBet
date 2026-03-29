# Instruções de Implementação: Consenso de Modelos (Análise de Concordância)

## 1. Objetivo
[cite_start]Implementar uma camada de decisão baseada no conceito de **"Previsão Segura"** detalhado no TCC de Juan Albuquerque (2023)[cite: 6, 491]. [cite_start]O sistema deve evoluir de um modelo único para um **Ensemble de 50 modelos** (5 algoritmos x 10 variações) que votam sobre a existência de valor em uma aposta de escanteios[cite: 470, 523].

## 2. Conceitos Chave (Baseados no TCC)
- [cite_start]**Previsão Segura:** Resultado onde n% das previsões do conjunto apontam para a mesma decisão[cite: 491].
- [cite_start]**Threshold de Concordância ($n$):** Limite mínimo de votos para validar uma aposta, variando de 34% a 100%[cite: 492].
- [cite_start]**Abstenção:** Se o consenso for inferior ao threshold, o sistema deve descartar a aposta (status: "Insegura")[cite: 115, 507].

## 3. Requisitos Técnicos do MVP
- **Input:** Lista de $\lambda_{home}$ e $\lambda_{away}$ gerada por cada um dos 50 modelos.
- **Probabilidade:** Usar a Distribuição de Poisson para converter cada $\lambda_{total}$ na probabilidade do mercado (ex: Over 9.5).
- **Cálculo de Edge Individual:** Cada modelo $i$ calcula seu próprio $Edge_i = P_{model, i} - P_{odds}$.
- **Votação Binária:** - Se $Edge_i \ge 0.05$ (threshold de valor configurado), o voto é `1` (Apostar).
    - Caso contrário, o voto é `0` (Não Apostar).

## 4. Tarefas para o Agente

### Tarefa 1: Refatorar `src/japredictbet/betting/engine.py`
- Criar a classe `ConsensusEngine`.
- Implementar o método `evaluate_with_consensus(predictions_list, odds_data, threshold=0.7)`.
- O método deve:
    1. Calcular a probabilidade de Poisson para cada predição na `predictions_list`.
    2. Contabilizar quantos modelos identificaram $Edge \ge 0.05$.
    3. Calcular a taxa de concordância: `agreement = votos_positivos / total_modelos`.
    4. Retornar `should_bet = True` apenas se `agreement >= threshold`.

### Tarefa 2: Implementar Log de Auditoria
- Cada decisão deve registrar a distribuição de votos (ex: "35/50 modelos concordam").
- [cite_start]Seguir o princípio do TCC: "Quanto maior o threshold, maior a acurácia esperada e menor o volume de jogos"[cite: 550, 778].

### Tarefa 3: Atualizar o Pipeline de Backtest
- [cite_start]Permitir rodar o backtest variando o threshold de concordância em passos de 5% para encontrar o ponto ideal de ROI vs. Volume de Apostas[cite: 548, 611].

## 5. Referência de Performance Esperada
Conforme os resultados do TCC (Premier League):
- [cite_start]**Threshold 34%:** Acurácia base (ex: 55.9%)[cite: 601].
- [cite_start]**Threshold 100%:** Acurácia máxima alvo (ex: 83.3%) [cite: 601-602].

## 6. Definição de Pronto (DoP)
- O script `run.py` deve aceitar uma lista de modelos carregados.
- O output deve indicar claramente: "Aposta descartada por falta de consenso (Agreement: 40%)" ou "Aposta confirmada (Agreement: 90%)".