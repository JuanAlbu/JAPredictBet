# JA PREDICT BET - ROADMAP E CHECKLIST DO PROJETO

## Objetivo do Sistema
Transformar um modelo de previsão de cantos (escanteios) num sistema automatizado e robusto de **deteção de value bets** baseado em Consenso.

Fluxo principal:
`dataset -> 30 modelos (poisson) -> edge individual -> consenso -> filtro de variância -> decisão de aposta -> ROI real`

---

# 🟢 FASE 0 - MVP CONCLUÍDO (BASE FUNCIONAL)

- [x] Contrato e recolha de odds padronizados (`odds/collector.py`).
- [x] Motor de probabilidade (Poisson) e Edge (`betting/engine.py`).
- [x] Validação de "Previsão Segura" via Consenso (Threshold dinâmico).
- [x] Ensemble de 30 Modelos (10 XGB, 10 LGBM, 10 RF).
- [x] Matching robusto com Fuzzy Match, Threshold de Segurança e Rejeição de Ambiguidade.
- [x] Pipeline de Backtest a calcular ROI, Yield e Lucro Agregado por Threshold.
- [x] Integridade de dados garantida (Zero Imputação em campos críticos).

---

# 🔴 FASE 1 - PRIORIDADE MÁXIMA (P0 - BLOQUEANTES)

O objetivo desta fase é garantir que o ROI reportado no backtest não é fruto de vazamento de dados (leakage) e que é reprodutível no mundo real.

- [ ] **Holdout Temporal Cego:** Definir e isolar um período final do dataset (ex: últimos 3 meses) que os modelos *nunca* viram durante o treino ou tuning. O ROI oficial deve vir apenas deste bloco.
- [ ] **Chave de Matching Definitiva:** Atualizar o matching para utilizar `Nome da Equipa + Data do Jogo` (evita misturar jogos de ligas/taças diferentes que ocorrem na mesma semana).
- [ ] **Paralelização de Treinamento (`n_jobs`):** Implementar `joblib` ou `multiprocessing` no `train.py` para treinar os 30 modelos simultaneamente e viabilizar backtests rápidos.

---

# 🟠 FASE 2 - REALISMO DE MERCADO E MLOPS (P1)

Ajustes necessários para que a performance teórica do backtest sobreviva às condições reais das casas de apostas.

- [ ] **Pipeline de Atualização Contínua (CT):** Implementar `update_pipeline.py` para automatizar a ingestão de novas planilhas e o retreino do Ensemble de 30 modelos.
- [ ] **Penalidade de Slippage:** Simular no backtest uma queda de odd (ex: descontar 0.03 de cada odd) para representar o atraso entre o alerta do sistema e a aposta real.
- [ ] **Hard Block de Desvio Padrão:** Abortar a aposta se o $\sigma$ (variância) dos 30 modelos for superior a um limite $X$, mesmo que o consenso atinja os 70%.
- [ ] **Log Estruturado por Aposta:** Guardar um ficheiro CSV/JSON no backtest com cada entrada, contendo: odd, média $\lambda$, desvio padrão, votos favoráveis, stake e resultado.
- [ ] **Separação de Métricas:** Exibir o ROI isolado por mercado (Home, Away, Total) no relatório final.

---

# 🟡 FASE 3 - REFINAMENTO DE MODELO E DADOS (P2)

Melhorias algorítmicas e arquiteturais para ganho de precisão e segurança.

- [ ] **Otimização de Hiperparâmetros (Optuna):** Criar script `tune_hyperparameters.py` para otimizar as variações base dos 3 algoritmos usando a média dos folds, gerando um `best_params.json` a ser consumido pelo treino.
- [ ] **Gestão de Banca (Bankroll):** Substituir a Stake Fixa (1.0) pelo **Critério de Kelly Fracionado**, onde o volume financeiro apostado é proporcional ao tamanho do Edge e ao nível de Consenso.
- [ ] **Novas Features de Contexto:** Criar feature binária ou categórica a diferenciar "Mata-Mata" (Eliminatórias) de "Pontos Corridos" (Liga).
- [ ] **Validação de Configurações:** Implementar validação estrita (ex: Pydantic) para o `config.yml` na inicialização do `run.py`.

---

# 🔵 FASE 4 - TESTES E QUALIDADE (P2)

- [ ] **Testes de Ingestão e Vazamento:** Criar testes unitários para garantir que nenhuma feature do futuro (ex: resultado final) vaza para as *rolling features* pré-jogo.
- [ ] **Teste de Regressão de Homónimos:** Garantir que o sistema não confunde equipas com nomes idênticos em ligas diferentes.
- [ ] **CI/CD Básico:** Configurar GitHub Actions para correr a suíte de testes do `pytest` a cada *push* na *branch* principal.

---

# ⚪ FASE 5 - MELHORIAS AVANÇADAS E FUTURO (P3)

- [ ] **Monitorização de CLV (Closing Line Value):** Implementar a remoção do *overround* (odd justa) estritamente para auditoria. Medir se as previsões do modelo estão a bater a linha de fecho das casas asiáticas (Pinnacle).
- [ ] **Votação Ponderada (Weighted Consensus):** Atribuir pesos maiores no voto para algoritmos/variações que provarem maior acurácia no backtest longo.
- [ ] **Line Shopping:** Integrar múltiplas fontes de odds para procurar a melhor cotação disponível no mercado antes do cálculo do Edge.
- [ ] **Integração com Agentes/Bots:** Preparar *endpoint* para que um *bot* de Telegram consuma os alertas de "Value Bet" em tempo real.