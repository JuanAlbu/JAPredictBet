# JAPredictBet

Sistema para identificar possiveis oportunidades de value betting em mercados de escanteios no futebol, usando estatistica e modelos de machine learning.

## Objetivo

- Estimar o numero esperado de escanteios por partida
- Calcular probabilidades para linhas Over/Under
- Comparar com odds de casas para detectar possivel valor

## Escopo do MVP

Inclui:
- ingestao de dataset historico
- engenharia de features com rolling averages
- modelagem estatistica (Poisson)
- comparacao com odds
- deteccao de value bets

Fora do escopo:
- apostas ao vivo
- automatizacao de apostas
- integracao com contas de casas

## Arquitetura (alto nivel)

Dataset -> Features -> Modelos -> Probabilidade -> Odds -> Value Bet

## Estrutura do projeto

- src/japredictbet/data: ingestao de dados
- src/japredictbet/features: geracao de features
- src/japredictbet/models: treino e inferencia
- src/japredictbet/probability: calculos estatisticos
- src/japredictbet/odds: coleta e normalizacao de odds
- src/japredictbet/betting: logica de comparacao de valor
- src/japredictbet/agents: orquestracao futura de acoes
- src/japredictbet/pipeline: pipeline end-to-end
- data/raw: dados brutos
- data/processed: dados processados
- docs: documentacao

## Requisitos

- Python 3.10+
- pandas, numpy, scikit-learn, xgboost, scipy, requests

## Como executar (MVP)

Este projeto ainda esta em fase inicial. Algumas partes sao stubs.

Etapas esperadas:
1. Colocar dataset em data/raw
2. Executar o pipeline (sera adicionado um entrypoint)

## Dataset esperado (exemplo de colunas)

- date
- home_team
- away_team
- home_corners
- away_corners
- home_shots
- away_shots

## Principios

- pipelines deterministicas
- reproducibilidade
- arquitetura modular
- clara separacao de responsabilidades

## Evolucao futura

- entrada via API no lugar de dataset
- agentes para orquestrar acoes e alertas
- melhoria dos modelos e novas fontes de dados

## Aviso de seguranca

Este projeto e uma ferramenta analitica. Nao realiza apostas reais, nem integra com contas de casas.