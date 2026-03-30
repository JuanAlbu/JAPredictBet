# JA PREDICT BET - ROADMAP DE EVOLUCAO (CONSOLIDADO E EXECUTAVEL)

## Objetivo do Sistema
Transformar o JAPredictBet em um ecossistema quantitativo robusto para deteccao de Value Bets via consenso de modelos, com foco em integridade de dados, reprodutibilidade, calibracao e gestao de risco, mantendo as premissas do MVP (Poisson, arquitetura de dois modelos por membro e rolling features).

---

## BASE ATUAL (MVP JA ENTREGUE)
*Foco: registrar rapidamente o que ja existe para evitar retrabalho.*

- [x] Ensemble deterministico de 30 modelos (10 XGB, 10 LGBM, 10 RF).
- [x] Consenso com threshold configuravel e sweep de thresholds.
- [x] Matching robusto de equipes com fuzzy seguro e descarte de ambiguidades.
- [x] Backtest com metricas de ROI/Yield por threshold.

---

## FASE 1: INTEGRIDADE DE DADOS E INFRAESTRUTURA (PRIORIDADE P0)
*Foco: eliminar leakage, padronizar entrada e garantir rastreabilidade do pipeline.*

- [ ] **Holdout Temporal Estrito:** Isolar os ultimos 3 meses para validacao final out-of-sample.
- [ ] **Chave de Matching Definitiva:** Padronizar join por `Equipe + Data + Liga`.
- [ ] **Imputacao Zero em Campos Criticos:** Descartar linhas incompletas em vez de media.
- [ ] **Paralelizacao via n_jobs/backend:** Otimizar treino dos 30 modelos com recursos nativos.
- [ ] **Orquestracao de Pastas Fixas:** Consolidar fluxo `Raw -> Processed -> Models` no `update_pipeline.py`.
- [ ] **Validacao de Schema de Entrada:** Falhar cedo quando colunas obrigatorias estiverem ausentes ou tipos forem invalidos.
- [ ] **Versionamento de Artefatos e Dataset:** Registrar hash/versao de dataset, config e modelos por execucao.

---

## FASE 2: REFINAMENTO DO MODELO E ENGENHARIA (PRIORIDADE P1)
*Foco: melhorar performance sem quebrar as premissas da arquitetura atual.*

- [ ] **Calibracao de Probabilidades (Brier/ECE):** Garantir aderencia entre probabilidade prevista e frequencia real.
- [ ] **Rolling Curto Prazo:** Adicionar janelas de 3 e 5 jogos como features extras, mantendo 5 e 10.
- [ ] **Otimizacao de Hiperparametros:** Refinar XGB/LGBM/RF com protocolo deterministico.
- [ ] **Isolamento de Odds no Treino:** Usar odds apenas para avaliacao de valor, nunca como feature.
- [ ] **Walk-Forward de Validacao:** Complementar split temporal com walk-forward para reduzir risco de overfitting por regime.
- [ ] **Relatorio de Importancia/Estabilidade de Features:** Monitorar variacao de importancia entre janelas temporais.

---

## FASE 3: GESTAO DE RISCO E AUDITORIA FINANCEIRA (PRIORIDADE P1)
*Foco: validar edge real e proteger banca contra variancia e friccao de mercado.*

- [ ] **Refino do Value Bet Engine:** Padronizar calculo de EV `(Probabilidade * Odd) - 1`.
- [ ] **Quarter Kelly:** Implementar stake fracionada (25% Kelly) com limites de seguranca.
- [ ] **Auditoria de CLV:** Comparar odd de entrada vs fechamento para medir qualidade de preco.
- [ ] **Monte Carlo de Drawdown:** Simular sequencias de perdas para validar robustez da banca.
- [ ] **Stress Test de Slippage:** Recalcular ROI com penalidade de odd para aproximar execucao real.
- [ ] **Limites de Exposicao:** Definir teto de stake por liga/mercado/dia para reduzir concentracao de risco.

---

## FASE 4: QUALIDADE, MONITORAMENTO E PRODUTO (PRIORIDADE P2)
*Foco: confiabilidade operacional e escalabilidade segura do sistema.*

- [ ] **Suite de Testes de Leakage:** Garantir que rolling features usem apenas historico passado.
- [ ] **Teste de Regressao de Matching:** Evitar confusao entre equipes homonimas em ligas diferentes.
- [ ] **CI Basico (pytest em push):** Automatizar validacao minima de qualidade.
- [ ] **Logging Estruturado por Aposta:** Salvar decisao com lambdas, votos, edge, threshold, stake e resultado.
- [ ] **Dashboard de Saude do Modelo:** Acompanhar volume, hit rate, ROI, CLV e calibracao por periodo.
- [ ] **Integracao com APIs Real-time:** Conexao com provedores de odds e estatisticas.
- [ ] **Bot de Alertas (Telegram):** Notificacao de oportunidades aprovadas pelo consenso.
- [ ] **Estrategia Multi-Liga:** Especializar modelos por campeonato quando houver dados suficientes.

---

## FASE 5: PESQUISA E DESENVOLVIMENTO (R&D FUTURO)
*Nota: itens desta fase exigem atualizacao formal de `PROJECT_CONTEXT.md`, `ARCHITECTURE.md` e `PRODUCT_REQUIREMENTS.md` antes da implementacao.*

- [ ] **Estudo de Binomial Negativa Bivariada:** Avaliar migracao de Poisson para sobredispersao.
- [ ] **Stacking Meta-Modelo:** Avaliar ponderacao aprendida dos 30 membros do ensemble.
- [ ] **Game State / Live Variables:** Estudar impacto de estado de jogo em cantos.
- [ ] **GNN Tatico:** Avaliar modelagem estrutural de interacoes entre jogadores.
- [ ] **Favourite-Longshot Bias:** Pesquisar ajustes para vies sistematico de mercado.

---

## CHECKLIST DE VALIDACAO FINAL (MVP)
- [ ] CLV >= 55% de acerto em janela representativa.
- [ ] Brier Score <= 0.20 de forma consistente.
- [ ] ROI temporal positivo e estavel apos 500 simulacoes de Monte Carlo.
