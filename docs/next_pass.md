# JA PREDICT BET - ROADMAP DE EVOLUCAO (REVISAO 01-APR-2026)

**Data da Revisao:** 01 de Abril, 2026
**Revisao Anterior:** 31-MAR-2026
**Status Geral:** P0-FIX 100% CONCLUÍDO. P1-A 100% CONCLUÍDO. P1-B parcialmente concluído (B2-B4 prontos, B1 pendente). Consensus script sincronizado com pipeline (106 features).
**Proxima Acao:** Executar P1-B1 (Calibração), depois P1-C e P1-D.

---

## Roadmap e Próximas Ações

Esta é a fonte única de verdade para o planejamento futuro do projeto.
Atualizado com base na revisão completa de código, docs, configs e testes realizada em 31-MAR-2026.

---

### Encerramento P0 (Registro Expresso)

- [x] **P0.3b - Encerrado e documentado:** a trilha crítica de P0 foi concluída e o item fica oficialmente fechado para evitar reabertura indevida no planejamento de agentes.

---

### P0-FIX - Bugs Críticos Bloqueantes (Corrigir Antes de P1)

> Descobertos na revisão de código de 31-MAR-2026. Impedem execução correta do pipeline de produção.

- [x] **P0-FIX.1 - `_build_hybrid_ensemble_schedule()` não definida em `train.py`**
  - **Severidade:** BLOQUEANTE
  - **Arquivo:** `src/japredictbet/models/train.py`
  - **Status:** ✅ RESOLVIDO — função já estava implementada na linha 415 do `train.py` (build 70% boosters + 30% linear). Roadmap anterior continha informação desatualizada.

- [x] **P0-FIX.2 - `importance.py` assume XGBoost exclusivamente**
  - **Severidade:** BLOQUEANTE
  - **Arquivo:** `src/japredictbet/models/importance.py`
  - **Status:** ✅ RESOLVIDO — adicionado dispatch por tipo de modelo via `_extract_scores()`: XGBoost usa `get_booster().get_score()`, LightGBM e RandomForest usam `feature_importances_`, Ridge/ElasticNet usam `abs(coef_)`.

- [x] **P0-FIX.3 - Schema de config inconsistente entre YAMLs**
  - **Severidade:** ALTO
  - **Status:** ✅ RESOLVIDO — Corrigido em 4 lugares: `config_test_50matches.yml` e `config_backup.yml` atualizados para `rolling_windows: [10, 5]`; `scripts/consensus_accuracy_report.py` atualizado para usar `cfg.features.rolling_windows[0]`; `tests/pipeline/test_mvp_pipeline.py` corrigido para `FeatureConfig(rolling_windows=[10, 5])`; `config.py` adicionou `__post_init__` com validação de tipo.

- [x] **P0-FIX.4 - Pinnar versões em `requirements.txt`**
  - **Severidade:** ALTO
  - **Status:** ✅ RESOLVIDO — `requirements.txt` atualizado com versões exatas de todas as dependências de produção. Criado `requirements-dev.txt` com `-r requirements.txt` + `pytest==9.0.2`.

**Critério de Saída P0-FIX:** Pipeline `python run.py` executa sem erros com ensemble_size=30, importance funciona com todos os tipos de modelo, ambos os configs carregam sem erro, e todas as dependências têm versão pinada.

**✅ TODOS OS CRITÉRIOS ATENDIDOS — P0-FIX 100% CONCLUÍDO em 31-MAR-2026. 21 testes passando.**

---

### P1 - Alto Impacto (Em Execução)

**Foco:** Consolidar pipeline de produção, melhorar features, calibrar modelo e gestão de risco.

#### P1-A: Integridade do Pipeline (Prioridade Máxima Dentro de P1)

> Garantir que o pipeline core (`src/`) tenha paridade de funcionalidade com o script experimental.

- [x] **P1.A1 - Portar lógica 70/30 para `train.py`** ✅ COMPLETO (31-MAR-2026)
  - Mix 70/30 (21 boosters + 9 linear) agora implementado no `src/japredictbet/models/train.py`
  - **Status:** ✅ CONCLUÍDO
    - Ridge/ElasticNet params adicionados a `build_variation_params()` (10 variações cada)
    - Filenames atualizado em `_build_model_filename()` (ridge → "ridge", elasticnet → "elastic")
    - Ensemble scheduling (`_build_hybrid_ensemble_schedule()`) alternates 21 boosters + 9 linear
    - run.py updated para descobrir ridge_model_*.pkl e elastic_model_*.pkl
    - Config files updated (config.yml, config_test_50matches.yml, config_backup.yml) com Ridge/ElasticNet in algorithms
    - 13 novos testes em tests/models/test_train.py - all passing
    - 34/34 testes totais passando
  - **Critério de Saída Atendido:** Todos os 30 modelos (21+9) treinam sem erro, ensemble discovers e carrega corretamente
  - **Pr Nota:** Branch `feature/p1a-ensemble` pronto para criar

- [x] **P1.A2 - Centralizar dynamic margin rule no `engine.py`** ✅ COMPLETO (31-MAR-2026)
  - `tight_margin_threshold` e `tight_margin_consensus` adicionados ao `ValueConfig` em config.py
  - `ConsensusEngine.__init__()` aceita e armazena estes parâmetros como variáveis de instância
  - `_compute_dynamic_threshold()` usa variáveis de instância em vez de defaults hardcoded
  - `config.yml` atualizado com os novos campos
  - `mvp_pipeline.py` passa valores do config para o engine
  - 8 testes unitários + 4 cenários de integração — todos passando

- [x] **P1.A3 - Validar lambda values no `engine.py`** ✅ COMPLETO (31-MAR-2026)
  - `_validate_lambda()` adicionada com guard `np.isfinite()` e λ ≥ 0
  - Integrada em `_extract_lambda_total()`, `report_consensus()`, `evaluate_with_consensus()`
  - 26 testes unitários + 5 cenários de integração — todos passando

**✅ P1-A 100% CONCLUÍDO — 77 testes totais passando.**

#### P1-B: Evolução de Features (Prioridade Alta)

- [ ] **P1.B1 - Calibração de Probabilidades (Brier/ECE):** Garantir aderência entre a probabilidade prevista e a frequência real dos resultados. (antigo P1.1)
  - **Status:** NÃO INICIADO — Nenhuma implementação de Brier Score ou ECE encontrada no codebase.
  - **Próximo passo prioritário dentro de P1.**

- [x] **P1.B2 - Rolling Features (Curto Prazo, Volatilidade e EMA)** ✅ COMPLETO (31-MAR-2026)
  - `add_rolling_std()` em rolling.py — desvio padrão rolling por equipe/temporada
  - `add_rolling_ema()` em rolling.py — EMA com alpha configurável (α = 2/(window+1))
  - Flags `rolling_use_std` e `rolling_use_ema` em FeatureConfig e config.yml
  - Pipeline chama condicionalmente via `_add_rolling_std_features()` e `_add_rolling_ema_features()`
  - 11 testes unitários — todos passando

- [x] **P1.B3 - Recorde de Momento e Contexto de Jogo** ✅ JÁ IMPLEMENTADO
  - `add_result_rolling()` em rolling.py gera: wins, draws, losses, win_rate, points (rolling por janela)
  - Integrado no pipeline via `_add_result_rolling_features()`
  - **Nota:** Verificado no codebase — feature já existia antes desta sessão.

- [x] **P1.B4 - Cross-Features (Ataque×Defesa)** ✅ JÁ IMPLEMENTADO
  - `add_matchup_features()` em matchup.py gera: home_attack_vs_away_defense, corners_pressure_index, diffs
  - Cross-features ataque×defesa + features de diferença (corners, shots, fouls, cards)
  - **Nota:** São features baseadas nas rolling stats gerais de cada equipa, NÃO confronto direto entre pares.

- [ ] **P1.B5 - H2H Confronto Direto (Last 3):** Média de cantos, golos e shots nos últimos N confrontos diretos entre o par específico de equipas. Diferente de B4 (cross-features gerais), esta feature filtra o histórico por par home×away. (sugerido por análise Gemini 01-APR-2026)
  - **Status:** NÃO INICIADO
  - **Implementação:** Nova função `add_h2h_features()` em `matchup.py`
  - **Features esperadas:** `h2h_corners_mean_last3`, `h2h_goals_mean_last3`, `h2h_shots_mean_last3`
  - **Risco:** Pares com < 3 confrontos terão NaN → necessita fallback (média geral ou drop)
  - **Prioridade:** Após P1.B1 (Calibração)

#### P1-C: Otimização e Análise (Prioridade Média)

- [ ] **P1.C1 - Otimização de Hiperparâmetros:** Refinar os parâmetros de XGBoost, LightGBM e RF com um protocolo determinístico e auditável. Documentar origem dos valores atuais (ex: `learning_rate=0.08242879217471218` em train.py parece vir de hyperopt, mas não está documentado). (antigo P1.5)
- [ ] **P1.C2 - Importância de Features e Votos Ponderados (SHAP):** Monitorar a estabilidade da importância das features e implementar votos ponderados pelo SHAP no ensemble. Popular `docs/FEATURE_IMPORTANCE_GUIDE.md` com resultados reais (atualmente só tem framework sem dados). (antigo P1.6)
- [ ] **P1.C3 - Persistência de Hiperparâmetros (Auditoria):** Garantir que `alpha` e `l1_ratio` dos modelos lineares sejam persistidos de forma auditável. (antigo P1.7)

#### P1-D: Value e Risco (Prioridade Média-Baixa)

- [x] **P1.D1 - Refino do Value Bet Engine** ✅ JÁ IMPLEMENTADO
  - Fórmula `expected_value()` em engine.py: `(p_model * (odds - 1)) - (1 - p_model)`
  - Uso consistente em `evaluate_bet()` e toda lógica de consensus. (antigo P1.8)
- [ ] **P1.D2 - Auditoria de CLV (Closing Line Value):** Comparar a odd de entrada com a de fechamento para medir a qualidade do preço obtido. Completar TODO pendente em `docs/VALIDATION.md`. (antigo P1.9)
- [ ] **P1.D3 - Gestão de Risco (Kelly, Drawdown, Slippage):** Implementar staking com Quarter Kelly, simular drawdowns com Monte Carlo e aplicar stress tests de slippage. Completar validação de ROI temporal (500 Monte Carlo runs) pendente em VALIDATION.md. (antigo P1.10)

**Dependências Críticas (Atualizadas):**
- ~~P0-FIX.1 (hybrid schedule) é pré-requisito para P1.A1~~ ✅ RESOLVIDO
- ~~P0-FIX.2 (importance multi-model) é pré-requisito para P1.C2~~ ✅ RESOLVIDO
- ~~P0-FIX.4 (pin versões) é pré-requisito de reprodutibilidade~~ ✅ RESOLVIDO
- ~~P1.B2 (EMA) é pré-requisito para outras features de rolling~~ ✅ RESOLVIDO
- P1.B1 (calibração) é pré-requisito conceitual para P1.D3 (Kelly — precisa de probabilidades calibradas).
- P1.B1 (calibração) deve preceder P1.B5 (H2H) — validar impacto das 106 features antes de adicionar mais.
- P1.C2 (importância de features) é pré-requisito para votos ponderados com SHAP.

---

### P2 - Qualidade, Testes e Infraestrutura (A Planejar)

**Foco:** Aumentar a robustez, automatizar a validação e preparar o sistema para um ambiente de produção.

#### P2-A: Cobertura de Testes (Prioridade Alta - Cobertura Atual ~40%)

> Módulos inteiros sem nenhum teste. A meta é atingir 70% de cobertura.

- [ ] **P2.A1 - Testes para `features/` (elo, rolling, matchup, team_identity):** 0/4 módulos têm cobertura. Testar: NaN handling em ELO, janelas rolling edge cases, divisão por zero em matchup ratios, **data leakage via train_mask inválido**.
- [ ] **P2.A2 - Testes para `data/ingestion.py`:** Testar: Parquet loading, CSV malformado, dataset vazio, colunas ausentes, valores NaN em data.
- [ ] **P2.A3 - Testes para `models/train.py`:** Testar: ensemble scheduling (incluindo hybrid), feature selection, minimum training rows, XGBoost feature name sanitization.
- [ ] **P2.A4 - Ampliar testes de `odds/collector.py`:** Atual: 2 testes (mínimo). Adicionar: timeout de rede, JSON inválido, resposta vazia, campos ausentes, odds < 1.0.
- [ ] **P2.A5 - Suite de Testes de Leakage:** Garantir que rolling features usem apenas histórico passado. (antigo P2 Core)
- [ ] **P2.A6 - Teste de Regressão de Matching:** Evitar confusão entre equipes homônimas em ligas diferentes. (antigo P2 Core)
- [ ] **P2.A7 - Adicionar timeout em `odds/collector.py`:** `requests.get()` é chamado sem timeout e pode travar indefinidamente. Adicionar `timeout=30` (configurável via config). (movido de P1.A3 — defensivo, não bloqueia funcionalidade)
- [ ] **P2.A8 - Validar train_mask em `team_identity.py`:** A função `add_team_target_encoding()` aceita qualquer `train_mask` sem validação. Máscara vazia ou inválida causa data leakage silencioso. Validar que mask não está vazia, é booleana, e tem dimensão compatível. (movido de P1.A4 — defensivo, não bloqueia funcionalidade)

#### P2-B: Infraestrutura e CI (Prioridade Média)

- [ ] **P2.B1 - CI Básico (pytest em push):** Automatizar validação mínima de qualidade com coverage gate > 60%. (antigo P2 Core)
- [ ] **P2.B2 - Logging Estruturado por Aposta:** Salvar decisão com lambdas, votos, edge, threshold, stake e resultado. (antigo P2 Core)
- [ ] **P2.B3 - Completar `update_pipeline.py`:** Atualmente o script não implementa feature engineering (comentário diz "por brevidade, assumimos que data_features é o DF já com rolling features"). Integrar pipeline de features completo.
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`:** Usar o módulo de logging já existente em `utils/logging.py`.
- [ ] **P2.B5 - Completar `pyproject.toml`:** Adicionar metadata (author, description, license, requires-python), entry points (`[project.scripts]`), e dev dependencies.

#### P2-C: Limpeza e Consistência (Prioridade Média-Baixa)

- [ ] **P2.C1 - Remover código morto:**
  - `value/value_engine.py` (217 linhas) - lógica 100% duplicada em `japredictbet.betting.engine`, não é importado por nenhum módulo ativo.
  - `config_backup.yml` - backup manual desnecessário (usar git history).
  - `src/japredictbet/agents/` - scaffolding vazio (`NotImplementedError`), sem uso.
- [ ] **P2.C2 - Resolver módulo `probability/` vazio:** Toda lógica de probabilidade Poisson vive em `betting/engine.py`, violando a boundary definida no AGENTS.md (`probability → statistical calculations`). Opções: (a) mover funções Poisson para `probability/`, ou (b) atualizar ARCHITECTURE.md para refletir a realidade.
- [ ] **P2.C3 - Padronizar linguagem dos comentários:** Código tem mix de português e inglês (engine.py, mvp_pipeline.py). Escolher um idioma e padronizar.
- [ ] **P2.C4 - Sincronizar documentação contraditória:** ✅ PARCIALMENTE RESOLVIDO (01-APR-2026)
  - ✅ `VALIDATION_REPORT.md` reescrito — 3 blockers marcados como resolvidos
  - ✅ `EXECUTIVE_SUMMARY.md` atualizado — blockers fechados
  - ✅ `PROJECT_CONTEXT.md` atualizado — status P1 correto
  - ✅ `MODEL_ARCHITECTURE.md` atualizado — composição correta (10 XGB + 11 LGB + 5 Ridge + 4 ElasticNet)
  - Restante: verificar se `P0_COMPLETION_SUMMARY.md` e `IMPLEMENTATION_CONSENSUS.md` precisam de ajustes menores.

#### P2-D: Produto (Postergar Sem Bloquear)

- [ ] **P2.D1 - Tratamento de Erros Robusto:** Implementar `try-except` em pontos críticos (ex: `fetch_odds`) para evitar falhas abruptas.
- [ ] **P2.D2 - Dashboard de Saúde do Modelo:** Acompanhar volume, hit rate, ROI, CLV e calibração por período.
- [ ] **P2.D3 - Integração com APIs Real-time:** Conexão com provedores de odds e estatísticas.
- [ ] **P2.D4 - Bot de Alertas (Telegram):** Notificação de oportunidades aprovadas pelo consenso.

---

### P3 - Performance e Otimização (Futuro)

- [ ] **P3.1 - Otimizar loop de consensus sweep:** `mvp_pipeline.py` (L256-276) tem loop `O(rows × thresholds × 30 models)` sem batch. Vectorizar com numpy ou paralelizar.
- [ ] **P3.2 - Cache de computações caras:** Feature engineering recalcula rolling stats a cada execução. Implementar cache com invalidação por data.

---

### R&D - Pesquisa e Desenvolvimento Futuro (A Pesquisar)

**Foco:** Explorar técnicas avançadas de modelagem e análise de mercado.

- [ ] **Estudo de Binomial Negativa Bivariada:** Avaliar migração de Poisson para modelos que lidam com sobredispersão.
- [ ] **Stacking Meta-Modelo:** Avaliar ponderação aprendida dos membros do ensemble.
- [ ] **Game State / Live Variables:** Estudar impacto de estado de jogo em cantos (expansão do P1.B3).
- [ ] **GNN Tático:** Avaliar modelagem estrutural de interações entre jogadores.
- [ ] **Favourite-Longshot Bias:** Pesquisar ajustes para vieses sistemáticos do mercado de apostas.

---

### Matriz de Maturidade do Projeto (01-APR-2026)

| Dimensão | Nota | Comentário |
|----------|------|------------|
| Arquitetura | 9/10 | Excelente design modular, bem documentada |
| Implementação | 8/10 | Core funcional, P0-FIX resolvido, P1-A/B(parcial) completos, 106 features |
| Documentação | 8/10 | Abrangente, revisada e sincronizada (01-APR-2026) |
| Testes | 5/10 | 87 testes passando (10 arquivos), mas módulos features/data sem cobertura dedicada |
| Reprodutibilidade | 8/10 | SHA256, seeds, requirements pinados, config-driven |
| Production-Ready | 7/10 | Pipeline e script experimental sincronizados, calibração (B1) pendente |

---

### Changelog

| Data | Ação |
|------|------|
| 30-MAR-2026 | Criação do roadmap. P0 encerrado. |
| 31-MAR-2026 | Revisão completa de código: 26 arquivos Python, 3 configs, 17 docs. Adicionado P0-FIX (3 bugs bloqueantes). Reorganizado P1 em sub-grupos (A-D) por prioridade. Expandido P2 com gaps de testes e limpeza. Adicionado P3 (performance). Adicionada matriz de maturidade. |
| 31-MAR-2026 | P0-FIX 100% concluído: FIX.1 já estava OK, FIX.2 (`importance.py` multi-model dispatch), FIX.3 (config schema padronizado + validação), FIX.4 (requirements.txt com versões pinadas + requirements-dev.txt). 21 testes passando. |
| 31-MAR-2026 | P1.A1 (ensemble híbrido), P1.A2 (dynamic margin), P1.A3 (lambda validation), P1.B2 (STD+EMA) implementados. 87 testes passando. |
| 01-APR-2026 | Consensus script (`consensus_accuracy_report.py`) sincronizado com pipeline principal: agora usa 106 features (STD+EMA+drop_redundant). Documentação completa revisada e atualizada. |
