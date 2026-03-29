# JA PREDICT BET - CHECKLIST COMPLETO DO PROJETO

## Objetivo do Sistema

Transformar um modelo de previsao de escanteios em um sistema de **deteccao de value bets**.

Fluxo principal:

modelo -> probabilidade -> odds -> edge -> decisao -> ROI

---

# FASE 1 - CORE (OBRIGATORIO)

## Odds, Probabilidade e Decisao

[x] Definir contrato de odds (schema padronizado) - Feito em `odds/collector.py`
[ ] Implementar normalizacao de odds (remover overround)
[x] Implementar calculo de implied probability (1 / odds) - Feito em `betting/engine.py`
[x] Implementar modulo de probabilidade (Poisson inicialmente) - Feito em `betting/engine.py`
[x] Implementar calculo de probabilidade para over/under (CDF) - Feito em `betting/engine.py`
[x] Implementar calculo de edge (P_modelo - P_odds) - Feito em `betting/engine.py`
[x] Implementar value_detector (threshold configuravel) - Consolidado em `betting/engine.py` (`should_bet`)
[x] Definir threshold inicial (ex: 0.03-0.05) - `config.yml` com `threshold: 0.05`
[x] Criar/validar modulo de decisao de valor - Feito em `betting/engine.py` + testes em `tests/betting/test_engine.py`

---

## Matching Partida x Odds

[ ] Melhorar robustez do matching (normalizacao + fuzzy matching para dados reais)
[ ] Definir estrategia de matching (nome + data + liga)
[ ] Implementar normalizacao de nomes de times
[ ] Implementar fuzzy matching (fallback)
[ ] Definir chave unica de partida (match_id idealmente)
[ ] Padronizar timezone e formato de data

---

# FASE 2 - MVP REAL

## Pipeline com Odds Reais

[x] Implementar coleta de odds (collector.py) - Feito, com suporte a local/http.
[x] Normalizar estrutura das odds coletadas - Feito em `odds/collector.py`.
[x] Integrar odds reais no pipeline (remover mock) - Feito, `mvp_pipeline.py` refatorado.
[ ] Validar consistencia entre dataset e odds

---

## Backtest Real (Value Betting)

[ ] Implementar calculo de ROI (prioridade maxima - sem isso pipeline nao e validavel)
[ ] Implementar calculo de yield (metrica de retorno principal do sistema)
[ ] Implementar lucro acumulado (rastreamento de ganhos e perdas)
[ ] Remover estrategia "over sempre"
[ ] Apostar apenas quando edge > threshold
[ ] Contabilizar numero de apostas
[ ] Definir e isolar um periodo de backtest final (hold-out) nao visto no treino
[ ] Separar metricas por:
- home
- away
- total

---

## Estrategia de Stake

[ ] Implementar stake fixa (flat) - MVP
[ ] Preparar estrutura para stake proporcional (futuro)

---

# FASE 3 - MODELO E PROBABILIDADE

## Modelo

[ ] FASE A (prioridade alta - indispensavel): validacao temporal anti-overfitting
[x] Fixar random_state (baseline oficial para comparacao) - `config.yml` com `random_state: 42`
[ ] Definir e congelar holdout temporal final (nao usar no tuning)
[x] Rodar validacao com TimeSeriesSplit / walk-forward no bloco treino+validacao - Base implementada em `pipeline/walk_forward.py`
[ ] Treinar modelo final com melhores parametros em treino+validacao
[ ] Avaliar uma unica vez no holdout final e registrar resultado oficial

[ ] FASE B (prioridade media - robustez e automacao)
[ ] Otimizar hiperparametros com Optuna usando media dos folds
[ ] Penalizar instabilidade entre folds (ex: score = media - k*desvio)
[ ] Aplicar pruning de correlacao dentro de cada fold (evitar leakage)
[ ] Rodar robustez com multiplos seeds apos tuning (analise de estabilidade)
[ ] Gerar relatorio versionado (best params, media/std CV, resultado holdout)

[ ] Validar calibracao do modelo (calibration curve)
[ ] Ajustar bias (se houver superestimacao)
[ ] Testar modelo direto para total corners
[ ] Testar distribuicao alternativa (negative binomial)

---

## Features

[ ] Criar manifesto de features finais
[ ] Garantir consistencia das janelas (5 e 10)
[ ] Validar ausencia de leakage nas rolling features
[ ] Validar dependencias do dataset (ex: ELO precisa de gols)

---

## Qualidade de Dados

[ ] Checar duplicatas
[ ] Validar datas invalidas
[ ] Normalizar nomes de times
[ ] Tratar missing values

---

# FASE 4 - ENGENHARIA

## Persistencia

[ ] Salvar modelos treinados (artifacts/)
[ ] Salvar metricas por execucao
[ ] Versionar modelos (timestamp/hash)
[ ] Salvar features utilizadas
[ ] Implementar versionamento de datasets (ex: com DVC)

---

## Logging

[ ] Logar cada aposta com:
- features
- odds
- prob_modelo
- edge
- decisao
- resultado

[ ] Permitir auditoria e analise posterior

---

## Execucao e Configuracao

[x] Criar entrypoint do pipeline - Feito (`run.py` + `config.yml`).
[ ] Criar script de treino
[ ] Criar script de backtest
[ ] Implementar validacao de configuracao na inicializacao (ex: com Pydantic)
[ ] Configurar pipeline de CI (ex: GitHub Actions) para rodar testes a cada commit

---

## Testes

[x] Teste de probabilidade
[x] Teste de calculo de edge - Coberto por `tests/betting/test_engine.py`
[x] Teste de decisao de aposta (threshold) - Coberto por `tests/betting/test_engine.py`
[ ] Teste de ingestao de dados
[ ] Teste de feature engineering
[ ] Teste de leakage

---

# FASE 5 - DOCUMENTACAO E PADRONIZACAO

[ ] Padronizar nomes de features
[ ] Definir encoding padrao (target encoding)
[ ] Confirmar algoritmo (XGBoost como default)
[ ] Atualizar documentacao do pipeline
[ ] Corrigir encoding (lambda, setas, simbolos)

[ ] Definir claramente:
- target do modelo (home/away vs total)
- decisao baseada em distribuicao (nao apenas lambda)

---

# FASE 6 - MELHORIAS AVANCADAS

## Estrategia

[ ] Implementar line shopping (multiplas casas)
[ ] Comparar odds entre bookmakers

---

## Modelo

[ ] Adicionar odds como feature
[ ] Implementar ensemble de modelos

---

## Arquitetura

[ ] Definir contrato de entrada via API
[ ] Preparar integracao com agentes

---

# METRICAS FINAIS DO SISTEMA

O sucesso do sistema NAO sera medido por:

* MAE
* RMSE
* Hit rate

E sim por:

[ ] ROI
[ ] Yield
[ ] EV (Expected Value)
[ ] Consistencia ao longo do tempo

---

# PRINCIPIOS IMPORTANTES

* Modelo nao decide aposta -> probabilidades decidem
* Hit rate nao garante lucro
* Odds sao obrigatorias no sistema
* Edge e o nucleo da estrategia
* Menos apostas com maior qualidade > mais apostas

---

# STATUS ATUAL DO PROJETO

- Modelo preditivo solido
- Features avancadas implementadas
- Pipeline de treino funcional
- Engine de probabilidade e valor implementada
- Coletor de Odds integrado
- Base de testes automatizados criada (15 testes passando)
- Pipeline executavel de ponta a ponta
- Split temporal e pesos por recencia ativos no treino
- Walk-forward implementado para validacao de modelo

Proximo passo critico:

-> Implementar o Backtest Real para validar o ROI.

---

# VISAO FINAL

O sistema completo deve ser capaz de:

1. Receber jogos e odds
2. Prever corners
3. Converter para probabilidade
4. Identificar vantagem
5. Executar decisao de aposta
6. Medir retorno financeiro

---
