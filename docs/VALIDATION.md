## CHECKLIST DE VALIDACAO FINAL (01-APR-2026)

### Validacoes Tecnicas

**Estrutura de Codigo:**
- [x] Modulos separados por responsabilidade (data, features, models, betting, etc)
- [x] Configuracao centralizada em `config.yml` com parametros documentados
- [x] Ensemble de 30 modelos implementado e testado (21 boosters + 9 linear)
- [x] Consenso com threshold parametrizado funcionando
- [x] Dynamic margin rule implementada em `engine.py`
- [x] Lambda validation (NaN/Inf guard) implementada
- [x] Loggers por execucao em `log-test/` ativos
- [x] PEP8 compliance verificado em modulos principais
- [x] Docstrings nas funcoes core (train.py, engine.py, pipeline.py)
- [x] 87/87 testes passando (10 arquivos de teste)

**Integridade de Dados:**
- [x] Dataset raw em `data/raw/dataset.csv` validado
- [x] Mock odds em `data/raw/mock_odds.json` disponivel
- [x] Dados processados em `data/processed/` (11 arquivos CSV por season)
- [x] Leakage check: rolling features nao usam dados futuros

**Modelo e Predicao:**
- [x] Regressores de dois modelos por membro (home/away lambdas) - VALIDADO
- [x] Objetivo Poisson conforme `config.yml` - VALIDADO
- [x] Mix 70% boosting / 30% linear no core E experimental - IMPLEMENTADO
- [x] Feature set: 106 features (mean + STD + EMA + matchup + result + ELO - redundant)
- [x] Consensus script sincronizado com pipeline principal (01-APR-2026)
- [ ] CLV >= 55% de acerto em janela representativa - **PENDENTE (P1.D2)**
- [ ] Brier Score <= 0.20 consistente - **PENDENTE (P1.B1)**
- [ ] ROI temporal positivo apos 500 Monte Carlo - **PENDENTE (P1.D3)**

**Alignment com Constraints (AGENTS.md):**
- [x] Linguagem Python - OK
- [x] PEP8 style guide - OK
- [x] Bibliotecas preferidas (pandas, numpy, sklearn, xgboost, lightgbm, scipy) - OK
- [x] Folder structure preservada - OK
- [x] Docstrings presentes em modulos main - OK
- [x] Funcoes pequenas e modulares - PARCIALMENTE (algumas podem ser refatoradas)
- [x] Respeitadas module boundaries (data → features → models → betting) - OK
- [x] Duas premissas modelo mantidas: Poisson + dois modelos por membro - OK
- [x] Sem bets reais, sem conexao com bookmakers, sistema analitico puro - OK

**Resultados de Consenso (01-APR-2026):**
- [x] Dynamic lines (20 matches, 77 features): 2 bets, 100% accuracy
- [x] Fixed line 9.5 (20 matches): 16 bets, 31% accuracy
- [x] Random lines 5.5-11.5 (20 matches): 18 bets, 78% accuracy
- [x] Random lines 50-match: 10 bets, 100% accuracy
- [x] Dynamic lines (20 matches, 106 features): 3 bets, 33% accuracy
