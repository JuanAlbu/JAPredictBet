## CHECKLIST DE VALIDACAO FINAL (MVP - 30-MAR-2026)

### Validacoes Tecnicas

**Estrutura de Codigo:**
- [x] Modulos separados por responsabilidade (data, features, models, betting, etc)
- [x] Configuracao centralizada em `config.yml` com parametros documentados
- [x] Ensemble de 30 modelos implementado e testado
- [x] Consenso com threshold parametrizado funcionando
- [x] Loggers por execucao em `log-test/` ativos
- [x] PEP8 compliance verificado em modulos principais
- [x] Docstrings nas funcoes core (train.py, engine.py, pipeline.py)

**Integridade de Dados:**
- [x] Dataset raw em `data/raw/dataset.csv` validado
- [x] Mock odds em `data/raw/mock_odds.json` disponivel
- [x] Dados processados em `data/processed/` (11 arquivos CSV por season)
- [x] Leakage check: rolling features nao usam dados futuros

**Modelo e Predicao:**
- [x] Regressores de dois modelos por membro (home/away lambdas) - VALIDADO
- [x] Objetivo Poisson conforme `config.yml` - VALIDADO
- [x] Mix 70% boosting / 30% linear no experimental - IMPLEMENTADO
- [ ] CLV >= 55% de acerto em janela representativa - **AINDA NAO VALIDADO**
- [ ] Brier Score <= 0.20 consistente - **AINDA NAO VALIDADO**
- [ ] ROI temporal positivo apos 500 Monte Carlo - **AINDA NAO VALIDADO**

**Alignment com Constraints (AGENTS.md):**
- [x] Linguagem Python - OK
- [x] PEP8 style guide - OK
- [x] Bibliotecas preferidas (pandas, numpy, sklearn, xgboost, scipy) - OK
- [x] Folder structure preservada - OK
- [x] Docstrings presentes em modulos main - OK
- [x] Funcoes pequenas e modulares - PARCIALMENTE (algumas podem ser refatoradas)
- [x] Respeitadas module boundaries (data → features → models → betting) - OK
- [x] Duas premissas modelo mantidas: Poisson + dois modelos por membro - OK
- [x] Sem bets reais, sem conexao com bookmakers, sistema analitico puro - OK
