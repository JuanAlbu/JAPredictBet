# JA PREDICT BET - ROADMAP DE EVOLUCAO (REVISAO 31-MAR-2026)

**Data da Revisao:** 31 de Março, 2026
**Revisao Anterior:** 30-MAR-2026
**Status Geral:** P0-FIX 100% CONCLUÍDO (todos os 4 bugs críticos corrigidos em 31-MAR-2026). P1 em execução.
**Proxima Acao:** Executar P1 (iniciar por P1-A: Integridade do Pipeline).

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

- [ ] **P1.A1 - Portar lógica 70/30 para `train.py`**
  - O mix 70/30 (21 boosters + 9 linear) existe apenas em `scripts/consensus_accuracy_report.py`. A função `train_and_save_ensemble()` em `src/japredictbet/models/train.py` não aplica esse mix. O pipeline de produção (`run.py`) usa `train.py`, portanto **não tem o ensemble híbrido**.
  - **Ação:** Unificar a lógica de scheduling do script no core.

- [ ] **P1.A2 - Centralizar dynamic margin rule no `engine.py`**
  - A regra de margem dinâmica (threshold +50% quando `|λ - line| < 0.5`) está implementada apenas no script (L545-548). O `ConsensusEngine` em `betting/engine.py` tem valores hardcoded (`tight_margin_threshold=0.5`, `tight_margin_consensus=0.50`) mas a lógica deveria ser configurável via `config.yml`.
  - **Ação:** Parametrizar `tight_margin_threshold` e `tight_margin_consensus` no config e no `ConsensusEngine`.

- [ ] **P1.A3 - Validar lambda values no `engine.py`**
  - Valores de λ extraídos dos modelos não são validados. NaN ou Inf propagam silenciosamente nos cálculos de probabilidade Poisson.
  - **Ação:** Adicionar guard `if not np.isfinite(lambda_total)` antes dos cálculos.

#### P1-B: Evolução de Features (Prioridade Alta)

- [ ] **P1.B1 - Calibração de Probabilidades (Brier/ECE):** Garantir aderência entre a probabilidade prevista e a frequência real dos resultados. (antigo P1.1)
- [ ] **P1.B2 - Rolling Features (Curto Prazo, Volatilidade e EMA):** Adicionar janelas de 3 e 5 jogos, incluir desvio padrão (STD) dos cantos e incorporar Time-Decay EMA para dar mais peso a jogos recentes. (antigo P1.2)
- [ ] **P1.B3 - Recorde de Momento e Contexto de Jogo:** Consolidar métrica de recorde (V-E-D) e adicionar features de "game state" para capturar o comportamento tático. (antigo P1.3)
- [ ] **P1.B4 - H2H e Cross-Features:** Adicionar média de cantos dos últimos 3 confrontos diretos (H2H) e criar features cruzadas entre ataque e defesa. (antigo P1.4)

#### P1-C: Otimização e Análise (Prioridade Média)

- [ ] **P1.C1 - Otimização de Hiperparâmetros:** Refinar os parâmetros de XGBoost, LightGBM e RF com um protocolo determinístico e auditável. Documentar origem dos valores atuais (ex: `learning_rate=0.08242879217471218` em train.py parece vir de hyperopt, mas não está documentado). (antigo P1.5)
- [ ] **P1.C2 - Importância de Features e Votos Ponderados (SHAP):** Monitorar a estabilidade da importância das features e implementar votos ponderados pelo SHAP no ensemble. Popular `docs/FEATURE_IMPORTANCE_GUIDE.md` com resultados reais (atualmente só tem framework sem dados). (antigo P1.6)
- [ ] **P1.C3 - Persistência de Hiperparâmetros (Auditoria):** Garantir que `alpha` e `l1_ratio` dos modelos lineares sejam persistidos de forma auditável. (antigo P1.7)

#### P1-D: Value e Risco (Prioridade Média-Baixa)

- [ ] **P1.D1 - Refino do Value Bet Engine:** Padronizar o cálculo de EV como `(Probabilidade * Odd) - 1`. (antigo P1.8)
- [ ] **P1.D2 - Auditoria de CLV (Closing Line Value):** Comparar a odd de entrada com a de fechamento para medir a qualidade do preço obtido. Completar TODO pendente em `docs/VALIDATION.md`. (antigo P1.9)
- [ ] **P1.D3 - Gestão de Risco (Kelly, Drawdown, Slippage):** Implementar staking com Quarter Kelly, simular drawdowns com Monte Carlo e aplicar stress tests de slippage. Completar validação de ROI temporal (500 Monte Carlo runs) pendente em VALIDATION.md. (antigo P1.10)

**Dependências Críticas:**
- P0-FIX.1 (hybrid schedule) é **pré-requisito** para P1.A1 (portar 70/30 para core).
- P0-FIX.2 (importance multi-model) é **pré-requisito** para P1.C2 (SHAP ponderado).
- P0-FIX.4 (pin versões) é **pré-requisito** de reprodutibilidade para qualquer experimento P1.
- P1.B2 (EMA) é pré-requisito para outras features de rolling.
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
- [ ] **P2.C4 - Sincronizar documentação contraditória:**
  - `EXECUTIVE_SUMMARY.md` flagga hardcodes que já foram corrigidos no script.
  - `VALIDATION_REPORT.md` diz "3 blockers", `PROJECT_CONTEXT.md` diz "100% complete".
  - `P0_COMPLETION_SUMMARY.md` afirma que hybrid schedule está completo, mas a função não existe no core.
  - `IMPLEMENTATION_CONSENSUS.md` spec diz 70/30 no core, core não tem.

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

### Matriz de Maturidade do Projeto (31-MAR-2026)

| Dimensão | Nota | Comentário |
|----------|------|------------|
| Arquitetura | 9/10 | Excelente design modular, bem documentada |
| Implementação | 6/10 | Core funcional mas com bugs críticos (P0-FIX) e gaps (70/30 fora do core) |
| Documentação | 7/10 | Abrangente mas com inconsistências entre documentos |
| Testes | 3/10 | ~40% de cobertura, módulos críticos (features, data, models) sem testes |
| Reprodutibilidade | 6/10 | SHA256 e seeds bons, mas requirements sem pinning |
| Production-Ready | 5/10 | Script funciona, pipeline core tem bugs e gaps |

---

### Changelog

| Data | Ação |
|------|------|
| 30-MAR-2026 | Criação do roadmap. P0 encerrado. |
| 31-MAR-2026 | Revisão completa de código: 26 arquivos Python, 3 configs, 17 docs. Adicionado P0-FIX (3 bugs bloqueantes). Reorganizado P1 em sub-grupos (A-D) por prioridade. Expandido P2 com gaps de testes e limpeza. Adicionado P3 (performance). Adicionada matriz de maturidade. |
| 31-MAR-2026 | P0-FIX 100% concluído: FIX.1 já estava OK, FIX.2 (`importance.py` multi-model dispatch), FIX.3 (config schema padronizado + validação), FIX.4 (requirements.txt com versões pinadas + requirements-dev.txt). 21 testes passando. |
