# JA PREDICT BET — CHECKLIST COMPLETO DO PROJETO

## 🎯 Objetivo do Sistema

Transformar um modelo de previsão de escanteios em um sistema de **detecção de value bets**.

Fluxo principal:

modelo → probabilidade → odds → edge → decisão → ROI

---

# 🔴 FASE 1 — CORE (OBRIGATÓRIO)

## Odds, Probabilidade e Decisão

[x] Definir contrato de odds (schema padronizado) - Feito em `odds/collector.py`
[ ] Implementar normalização de odds (remover overround)
[x] Implementar cálculo de implied probability (1 / odds) - Feito em `betting/value_detector.py`
[x] Implementar módulo de probabilidade (Poisson inicialmente) - Feito em `probability/poisson.py`
[x] Implementar cálculo de probabilidade para over/under (CDF) - Feito em `probability/poisson.py`
[x] Implementar cálculo de edge (P_modelo - P_odds) - Feito em `betting/value_detector.py`
[x] Implementar value_detector (threshold configurável) - Feito em `betting/value_detector.py`
[ ] Definir threshold inicial (ex: 0.03–0.05)
[ ] Criar/validar arquivo `betting/value_detector.py` (arquivo necessário para testes)

---

## Matching Partida ↔ Odds

[ ] Melhorar robustez do matching (normalização + fuzzy matching para dados reais)
[ ] Definir estratégia de matching (nome + data + liga)
[ ] Implementar normalização de nomes de times
[ ] Implementar fuzzy matching (fallback)
[ ] Definir chave única de partida (match_id idealmente)
[ ] Padronizar timezone e formato de data

---

# 🟡 FASE 2 — MVP REAL

## Pipeline com Odds Reais

[x] Implementar coleta de odds (collector.py) - Feito, com suporte a local/http.
[x] Normalizar estrutura das odds coletadas - Feito em `odds/collector.py`.
[x] Integrar odds reais no pipeline (remover mock) - Feito, `mvp_pipeline.py` refatorado.
[ ] Validar consistência entre dataset e odds

---

## Backtest Real (Value Betting)

[ ] Implementar cálculo de ROI (prioridade máxima - sem isso pipeline não é validável)
[ ] Implementar cálculo de yield (métrica de retorno principal do sistema)
[ ] Implementar lucro acumulado (rastreamento de ganhos e perdas)
[ ] Remover estratégia "over sempre"
[ ] Apostar apenas quando edge > threshold
[ ] Contabilizar número de apostas
[ ] Definir e isolar um período de backtest final (hold-out) não visto no treino
[ ] Separar métricas por:
- home
- away
- total

---

## Estratégia de Stake

[ ] Implementar stake fixa (flat) — MVP
[ ] Preparar estrutura para stake proporcional (futuro)

---

# 🟢 FASE 3 — MODELO E PROBABILidade

## Modelo

[ ] Validar calibração do modelo (calibration curve)
[ ] Ajustar bias (se houver superestimação)
[ ] Testar modelo direto para total corners
[ ] Testar distribuição alternativa (negative binomial)

---

## Features

[ ] Criar manifesto de features finais
[ ] Garantir consistência das janelas (5 e 10)
[ ] Validar ausência de leakage nas rolling features
[ ] Validar dependências do dataset (ex: ELO precisa de gols)

---

## Qualidade de Dados

[ ] Checar duplicatas
[ ] Validar datas inválidas
[ ] Normalizar nomes de times
[ ] Tratar missing values

---

# 🔵 FASE 4 — ENGENHARIA

## Persistência

[ ] Salvar modelos treinados (artifacts/)
[ ] Salvar métricas por execução
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
- decisão
- resultado

[ ] Permitir auditoria e análise posterior

---

## Execução e Configuração

[x] Criar entrypoint do pipeline - Feito (`run.py` + `config.yml`).
[ ] Criar script de treino
[ ] Criar script de backtest
[ ] Implementar validação de configuração na inicialização (ex: com Pydantic)
[ ] Configurar pipeline de CI (ex: GitHub Actions) para rodar testes a cada commit

---

## Testes

[x] Teste de probabilidade
[x] Teste de cálculo de edge - Coberto por `test_value_detector`
[x] Teste de value_detector
[ ] Teste de ingestão de dados
[ ] Teste de feature engineering
[ ] Teste de leakage

---

# 🟣 FASE 5 — DOCUMENTAÇÃO E PADRONIZAÇÃO

[ ] Padronizar nomes de features
[ ] Definir encoding padrão (target encoding)
[ ] Confirmar algoritmo (XGBoost como default)
[ ] Atualizar documentação do pipeline
[ ] Corrigir encoding (λ, setas, símbolos)

[ ] Definir claramente:
- target do modelo (home/away vs total)
- decisão baseada em distribuição (não apenas λ)

---

# 🟠 FASE 6 — MELHORIAS AVANÇADAS

## Estratégia

[ ] Implementar line shopping (múltiplas casas)
[ ] Comparar odds entre bookmakers

---

## Modelo

[ ] Adicionar odds como feature
[ ] Implementar ensemble de modelos

---

## Arquitetura

[ ] Definir contrato de entrada via API
[ ] Preparar integração com agentes

---

# 📊 MÉTRICAS FINAIS DO SISTEMA

O sucesso do sistema NÃO será medido por:

* MAE
* RMSE
* Hit rate

E sim por:

[ ] ROI
[ ] Yield
[ ] EV (Expected Value)
[ ] Consistência ao longo do tempo

---

# 🚨 PRINCÍPIOS IMPORTANTES

* Modelo não decide aposta → probabilidades decidem
* Hit rate não garante lucro
* Odds são obrigatórias no sistema
* Edge é o núcleo da estratégia
* Menos apostas com maior qualidade > mais apostas

---

# ✅ STATUS ATUAL DO PROJETO

✔ Modelo preditivo sólido
✔ Features avançadas implementadas
✔ Pipeline de treino funcional
✔ Engine de probabilidade e valor implementada
✔ Coletor de Odds integrado
✔ Base de testes automatizados criada
✔ Pipeline executável de ponta a ponta

🔜 Próximo passo crítico:

→ Implementar o Backtest Real para validar o ROI.

---

# 🎯 VISÃO FINAL

O sistema completo deve ser capaz de:

1. Receber jogos e odds
2. Prever corners
3. Converter para probabilidade
4. Identificar vantagem
5. Executar decisão de aposta
6. Medir retorno financeiro

---