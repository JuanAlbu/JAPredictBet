# IMPLEMENTATION_CONSENSUS.md - Diretrizes de Engenharia (Versão Final)

## 1. Objetivo Geral
Implementar o sistema de **Detecção de Value Bets** em escanteios utilizando a metodologia de **Análise de Concordância** desenvolvida no TCC de Juan Albuquerque (2023). O sistema deve utilizar um **Ensemble de 30 modelos** para validar a segurança das operações antes de disparar qualquer aposta.

## 2. O Conceito de Consenso (Base Teórica: TCC 2023)
* [cite_start]**Previsão Segura:** Uma entrada só é validada se $n\%$ das previsões do conjunto apontarem para o mesmo resultado[cite: 491].
* [cite_start]**Threshold de Concordância ($n$):** Parâmetro configurável (ex: 70% ou 100%) que define o rigor do sistema [cite: 492-494].
* [cite_start]**Relação Inversa:** Quanto maior o threshold, maior a acurácia esperada e menor o volume de apostas [cite: 552-555, 776-778].
* [cite_start]**Abstenção:** O sistema deve descartar a aposta (status: "Insegura") caso o consenso não atinja o threshold[cite: 498, 507].

## 3. Arquitetura do Conselho (30 Modelos)
Para garantir a diversidade e robustez, o conjunto será formado por 3 algoritmos principais, com 10 variações de hiperparâmetros cada:

### A. Algoritmos Selecionados
1.  [cite_start]**XGBoost Regressor:** Benchmark individual do TCC (58% de acurácia base)[cite: 731]. Deve usar objetivo `count:poisson`.
2.  **LightGBM Regressor:** Alta eficiência e suporte nativo à Distribuição de Poisson.
3.  [cite_start]**Random Forest:** Captura padrões distintos via aleatorização de recursos e múltiplas árvores [cite: 225-227].

## 4. Pipeline Técnico de Decisão
O Agente deve implementar o fluxo seguindo esta sequência lógica:

1.  [cite_start]**Geração de Lambdas:** Treinar as 30 variações (10 por algoritmo) variando parâmetros como profundidade das árvores, learning rate e número de estimadores[cite: 472, 481].
2.  **Cálculo de Probabilidade:** Para cada modelo $i$, converter $\lambda_{total, i}$ na probabilidade do mercado (ex: Over 9.5) via Poisson:
    $$P(X > k) = 1 - \sum_{j=0}^{k} \frac{e^{-\lambda} \cdot \lambda^j}{j!}$$.
3.  **Votação de Valor (Edge):** Cada modelo verifica se há vantagem contra a odd da casa ($P_{odds}$):
    - Voto Positivo se $Edge = P_{model} - P_{odds} \ge 0.05$.
4.  **Validação de Método:** Contabilizar a taxa de concordância. Se `votos_positivos / 30 >= threshold`, validar aposta.

## 5. Requisitos de Implementação para o Agente IA

### Módulo: `src/japredictbet/betting/engine.py`
* Implementar a classe `ConsensusEngine` para gerenciar o ensemble de 30 predições.
* **Output Obrigatório:** Exibir o nível de consenso em cada análise (ex: "Consenso: 21/30 - 70% | Status: Value Bet").

### Módulo: Backtesting & ROI
* Implementar o cálculo automático de **ROI e Yield** segmentado por nível de Threshold.
* O backtest deve permitir identificar o threshold que gera o melhor retorno financeiro acumulado.

## 6. Definição de Pronto (DoP)
* [cite_start]O sistema deve realizar a "Abstenção" em casos de baixa concordância[cite: 507].
* O threshold de consenso deve ser editável via arquivo `config.yml`.
* Todas as decisões (votos individuais e consenso final) devem ser registradas em logs.