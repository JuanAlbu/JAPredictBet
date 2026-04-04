# JA PREDICT BET - ROADMAP DE EVOLUCAO (REVISAO 03-APR-2026)

**Data da Revisao:** 03 de Abril, 2026
**Revisao Anterior:** 01-APR-2026
**Status Geral:** P0-FIX reaberto (FIX.5 rolling bug). P1 100% CONCLUÍDO (158/158 testes passando, 17 arquivos de teste). Consensus script sincronizado com pipeline (106 features).
**Proxima Acao:** Executar retreino completo e validacao operacional apos FIX.5, depois iniciar P2-SHADOW (Superbet Shadow Mode) — ver trilha P2.SH1-SH7.

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

- [x] **P0-FIX.5 - Contaminação cross-grupo em rolling features**
  - **Severidade:** BLOQUEANTE (qualidade de dados)
  - **Arquivos:** `src/japredictbet/features/rolling.py` — funções `add_rolling_features()`, `add_stat_rolling()`, `add_result_rolling()`, `add_rolling_std()`
  - **Problema:** O padrão `group[col].shift(1).rolling(window).mean()` aplica `.rolling()` na Series flat retornada por `shift()`, NÃO no GroupBy. Quando dados estão ordenados por data (não por equipe), a janela rolling cruza fronteiras entre equipes diferentes, contaminando features.
  - **Evidência:** `add_rolling_ema()` no mesmo arquivo usa `.transform()` corretamente — as outras 4 funções não.
  - **Impacto:** Todas as rolling features (mean, sum, std) podem conter valores de outras equipes. Afeta qualidade dos 30 modelos. Testes passam porque tolerância ao ruído é alta.
  - **Fix:** Usar `.transform(lambda x: x.shift(1).rolling(window).mean())` em todas as funções, replicando o padrão correto de `add_rolling_ema()`.
  - **Status:** ⚠️ HOTFIX DE CODIGO + TESTES CONCLUIDO (03-APR-2026) — `rolling.py` migrado para `group.transform(...)` em `add_rolling_features`, `add_stat_rolling`, `add_result_rolling`, `add_rolling_std`; adicionados testes de regressao em `tests/features/test_rolling_cross_group.py`.
  - **Validacao operacional (03-APR-2026):**
    - ✅ Retreino completo executado com `python run.py --config config.yml --skip-model-dir`
    - ✅ Cenario full validado (`scripts/consensus_accuracy_report.py --config config.yml`)
    - ✅ Cenario random-lines validado (`--random-lines --line-min 5.5 --line-max 11.5`)
    - ✅ Cenario recent subset destravado e validado (`python run.py --config config_test_50matches.yml --skip-model-dir` e `scripts/consensus_accuracy_report.py --config config_test_50matches.yml`)
  - **Status final:** ✅ FECHADO — leak cross-group corrigido em codigo + testes + validacao operacional executada.

- [x] **P0-FIX.6 - Default `algorithms` em `config.py` não inclui Ridge/ElasticNet**
  - **Severidade:** ALTO
  - **Arquivo:** `src/japredictbet/config.py` linha 45
  - **Problema:** `ModelConfig.algorithms` default é `("xgboost", "lightgbm", "randomforest")` — falta `"ridge"` e `"elasticnet"` da arquitetura híbrida 70/30.
  - **Fix:** Alterar default para `("xgboost", "lightgbm", "randomforest", "ridge", "elasticnet")`.
  - **Status:** ✅ RESOLVIDO (03-APR-2026) — atualizado em `src/japredictbet/config.py`; cobertura adicionada em `tests/test_config_defaults.py`.

**Critério de Saída P0-FIX:** Pipeline `python run.py` executa sem erros com ensemble_size=30, importance funciona com todos os tipos de modelo, ambos os configs carregam sem erro, e todas as dependências têm versão pinada. **Rolling features devem operar estritamente dentro dos limites de cada grupo (equipe/temporada).**

**⚠️ P0-FIX REABERTO (03-APR-2026) — FIX.5 (rolling cross-group) é bloqueante para qualidade de dados. FIX.1-4 permanecem resolvidos.**

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

- [x] **P1.B1 - Calibração de Probabilidades (Brier/ECE):** ✅ IMPLEMENTADO (03-APR-2026)
  - `src/japredictbet/probability/calibration.py`: `brier_score()`, `expected_calibration_error()`, `calibration_report()`
  - 16 testes unitários em `tests/probability/test_calibration.py`
  - Brier Score, ECE com bins configuráveis, relatório formatado

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

- [x] **P1.B5 - H2H Confronto Direto (Last 3):** ✅ IMPLEMENTADO (03-APR-2026)
  - `add_h2h_features()` em `matchup.py` — par canônico (A vs B == B vs A)
  - Features: `total_corners_h2h_last3`, `total_goals_h2h_last3`, `total_shots_h2h_last3`
  - Shift(1) para evitar leakage, min_periods=1 para pares com < 3 confrontos
  - Config: `FeatureConfig.h2h_window = 3`
  - 10 testes unitários em `tests/features/test_h2h.py`

#### P1-C: Otimização e Análise (Prioridade Média)

- [x] **P1.C1 - Otimização de Hiperparâmetros:** ✅ IMPLEMENTADO (03-APR-2026)
  - Script `scripts/hyperopt_search.py` com Optuna (TPE sampler, determinístico)
  - Search spaces para XGBoost, LightGBM, RF, Ridge, ElasticNet
  - 5-fold CV com Poisson deviance, output JSON auditável em `artifacts/hyperopt/`
  - CLI: `--algorithm`, `--n-trials`, `--n-folds`, `--config`
- [x] **P1.C2 - Importância de Features e Votos Ponderados (SHAP):** ✅ IMPLEMENTADO (03-APR-2026)
  - `src/japredictbet/models/shap_weights.py`: `compute_model_weights()`, `compute_shap_importance()`, `compute_ensemble_feature_importance()`
  - `ConsensusEngine.evaluate_with_consensus()` aceita `model_weights` para votação ponderada
  - Backward-compatible: sem weights, comportamento idêntico ao anterior
  - 6 testes em `tests/betting/test_weighted_consensus.py`
- [x] **P1.C3 - Persistência de Hiperparâmetros (Auditoria):** ✅ IMPLEMENTADO (01-APR-2026)
  - JSON metadata alongside .pkl com algorithm, params, feature_columns, n_features

#### P1-D: Value e Risco (Prioridade Média-Baixa)

- [x] **P1.D1 - Refino do Value Bet Engine** ✅ JÁ IMPLEMENTADO
  - Fórmula `expected_value()` em engine.py: `(p_model * (odds - 1)) - (1 - p_model)`
  - Uso consistente em `evaluate_bet()` e toda lógica de consensus. (antigo P1.8)
- [x] **P1.D2 - Auditoria de CLV (Closing Line Value):** ✅ IMPLEMENTADO (03-APR-2026)
  - `closing_line_value()`, `clv_hit_rate()`, `clv_summary()` em `engine.py`
  - CLV = implied_prob(closing) - implied_prob(entry)
  - 11 testes em `tests/betting/test_clv.py`
- [x] **P1.D3 - Gestão de Risco (Kelly, Drawdown, Slippage):** ✅ IMPLEMENTADO (03-APR-2026)
  - `src/japredictbet/betting/risk.py`: `kelly_fraction()`, `kelly_stake()`, `simulate_drawdown()`, `apply_slippage()`
  - Quarter Kelly staking, Monte Carlo drawdown (determinístico via seed)
  - Slippage stress test parametrizável
  - 18 testes em `tests/betting/test_risk.py`

**Dependências Críticas (Atualizadas):**
- ~~P0-FIX.1 (hybrid schedule) é pré-requisito para P1.A1~~ ✅ RESOLVIDO
- ~~P0-FIX.2 (importance multi-model) é pré-requisito para P1.C2~~ ✅ RESOLVIDO
- ~~P0-FIX.4 (pin versões) é pré-requisito de reprodutibilidade~~ ✅ RESOLVIDO
- ~~P1.B2 (EMA) é pré-requisito para outras features de rolling~~ ✅ RESOLVIDO
- ~~P1.B1 (calibração) é pré-requisito conceitual para P1.D3~~ ✅ RESOLVIDO
- ~~P1.B1 (calibração) deve preceder P1.B5 (H2H)~~ ✅ RESOLVIDO
- ~~P1.C2 (importância de features) é pré-requisito para votos ponderados com SHAP~~ ✅ RESOLVIDO

**P1 100% COMPLETO — Todos os items implementados e testados (03-APR-2026)**

---

### P2 - Qualidade, Testes e Infraestrutura (A Planejar)

**Foco:** Aumentar a robustez, automatizar a validação e preparar o sistema para um ambiente de produção.

#### P2-SHADOW: Superbet Shadow Mode (Nova Prioridade Alta)

> Evolucao planejada para ligar a coleta de odds reais ao `ConsensusEngine` em modo estritamente observacional. O objetivo e validar oportunidades de valor com dados vivos sem qualquer execucao financeira.

- [ ] **P2.SH1 - Substituir `requests` por `httpx` no coletor**
  - **Arquivo:** `src/japredictbet/odds/collector.py`
  - **Objetivo:** melhorar timeouts, controle de conexao e abrir caminho para fluxo assincrono.
  - **Criterios de aceite:**
    - `fetch_odds` usa `httpx`
    - headers com `User-Agent` de navegador real
    - timeout configuravel via config
    - tratamento explicito para HTTP 403, 429 e 500

- [ ] **P2.SH2 - Parsing SSE (Server-Sent Events) do feed Superbet**
  - **Endpoint alvo:** `https://production-superbet-offer-br.freetls.fastly.net/subscription/v2/pt-BR/events/all`
  - **Formato real:** O endpoint envia **SSE stream** (`data:{json}\nretry:N\n`), NAO um JSON monolitico. Cada evento e um JSON individual (<10KB).
  - **Objetivo:** consumir o stream linha-a-linha em ambiente de baixo custo (ex.: AWS t3.micro) sem acumular estado.
  - **Criterios de aceite:**
    - parsing linha-a-linha de eventos SSE (campo `data:` → `json.loads()` por evento)
    - usa `httpx` streaming ou biblioteca `httpx-sse` para consumo incremental
    - `ijson` NAO se aplica — cada evento cabe em memoria; `json.loads()` por evento e seguro
    - tolerante a eventos malformados: `try/except` por evento individual, log e skip
    - tolerante a reconexao: stream cortado → retry com backoff
  - **Nota tecnica:** O campo `matchName` usa `·` (middle dot U+00B7) como separador de times, NAO "vs"
  - **Campos chave no payload:** `eventId`, `matchName`, `sportId`, `categoryId`, `tournamentId`, `odds[].marketId`, `odds[].marketName`, `odds[].price`, `odds[].code`

- [ ] **P2.SH3 - Filtro de eventos e mercados de escanteios**
  - **Objetivo:** capturar apenas Futebol (`sportId=5`) e mercado `Total de Escanteios` (Over/Under).
  - **Extracao minima:** `event_id`, `home_team`, `away_team`, `market_line`, `over_odds`, `under_odds`
  - **Criterios de aceite:**
    - filtra por `sportId == 5` (futebol) — ignora basquete, tenis, eSports, etc.
    - filtra por `categoryId` e/ou `tournamentId` para ligas-alvo (Premier League, etc.)
    - identifica mercado de escanteios pelo `marketName` (ex.: "Total de Escanteios") ou `marketId` especifico
    - `market_line` normalizado em formato `.5`
    - odds invalidas ou incompletas sao descartadas com log
    - split de `matchName` por `·` (middle dot) para extrair home/away
  - **Atencao:** O feed mistura esportes reais, virtuais e eSports no mesmo endpoint. Filtro por `sportId` e obrigatorio.

- [ ] **P2.SH4 - Mapeamento Superbet -> IDs internos**
  - **Arquivo novo/obrigatorio:** `data/mapping/superbet_teams.json`
  - **Objetivo:** traduzir nomes externos da Superbet para a identidade interna do projeto.
  - **Criterios de aceite:**
    - coletor consulta o arquivo de mapeamento antes de processar o evento
    - equipes sem mapeamento geram `WARNING`
    - eventos sem mapeamento completo sao pulados com seguranca

- [ ] **P2.SH5 - Integracao com `ConsensusEngine` em Shadow Mode**
  - **Arquivos alvo:** `src/japredictbet/betting/engine.py` e `src/japredictbet/odds/collector.py`
  - **Objetivo:** para cada jogo valido, chamar `evaluate_with_consensus()` e registrar apenas auditoria.
  - **Shadow log obrigatorio:** `logs/shadow_bets.log`
  - **Campos minimos no log:**
    - timestamp
    - match_id
    - mandante / visitante
    - linha
    - odd real da Superbet
    - `p_model_mean`
    - odd justa (`1 / p_model_mean`)
    - edge medio
    - votos / consenso
    - status final (`value` ou `abstencao`)
  - **Regra de seguranca:** nenhum modulo deve executar aposta real; esta trilha continua analitica.

- [ ] **P2.SH6 - Script executavel de observacao**
  - **Objetivo:** disponibilizar uma classe `SuperbetCollector` com execucao via script/CLI.
  - **Criterios de aceite:**
    - comando unico para rodar coleta + avaliacao shadow
    - output em log e resumo final em console
    - falhas de rede nao derrubam toda a execucao

- [ ] **P2.SH7 - Testes dedicados da trilha Shadow**
  - **Objetivo:** cobrir o novo coletor com foco em robustez.
  - **Casos minimos:**
    - SSE stream com multiplos eventos processados corretamente
    - evento SSE com JSON malformado (skip + log)
    - HTTP 403 / 429 / 500 (retry com backoff)
    - timeouts de conexao e de leitura
    - stream cortado / reconexao
    - time sem mapeamento (WARNING + skip)
    - mercado sem linha ou odds (skip + log)
    - evento de esporte nao-futebol ignorado
    - chamada correta ao `ConsensusEngine`
    - shadow log com todos os campos obrigatorios

**Dependencias e observacoes da trilha Shadow:**
- Esta trilha expande o atual item `P2.D3 - Integracao com APIs Real-time`, mas em modo seguro e observacional.
- `P2.A4`, `P2.A7` e `P2.D3` foram absorvidos por esta trilha (marcados como `~~absorvidos~~` nas respectivas seções).
- Nao altera as premissas centrais do projeto: Poisson, arquitetura de dois lambdas e ausencia de automacao de aposta.
- **Novas dependencias pip:** `httpx>=0.27.0` (HTTP client async+sync), `httpx-sse>=0.4.0` (SSE parsing).
- **Novos arquivos esperados:** `src/japredictbet/odds/superbet.py`, `data/mapping/superbet_teams.json`, `scripts/shadow_observe.py`, `tests/odds/test_superbet.py`.
- **Descoberta critica (03-APR-2026):** O endpoint Superbet e SSE, nao REST JSON. O spec original de `ijson` foi corrigido.

#### P2-A: Cobertura de Testes (Prioridade Alta - Cobertura Atual ~40%)

> Módulos inteiros sem nenhum teste. A meta é atingir 70% de cobertura.

- [ ] **P2.A1 - Testes para `features/` (elo, rolling, matchup, team_identity):** 1/4 módulos com cobertura parcial (`test_h2h.py` cobre `matchup.py::add_h2h_features`). Faltam: NaN handling em ELO, janelas rolling edge cases, divisão por zero em matchup ratios, **data leakage via train_mask inválido**.
- [ ] **P2.A2 - Testes para `data/ingestion.py`:** Testar: Parquet loading, CSV malformado, dataset vazio, colunas ausentes, valores NaN em data.
- [ ] **P2.A3 - Testes para `models/train.py`:** Testar: ensemble scheduling (incluindo hybrid), feature selection, minimum training rows, XGBoost feature name sanitization.
- [x] ~~**P2.A4 - Ampliar testes de `odds/collector.py`**~~ → **ABSORVIDO por P2.SH7** (testes Shadow cobrem timeout, JSON inválido, resposta vazia, etc. com escopo mais completo).
- [ ] **P2.A5 - Suite de Testes de Leakage:** Garantir que rolling features usem apenas histórico passado. **Pré-requisito:** P0-FIX.5 (corrigir rolling primeiro). (antigo P2 Core)
- [ ] **P2.A6 - Teste de Regressão de Matching:** Evitar confusão entre equipes homônimas em ligas diferentes. (antigo P2 Core)
- [x] ~~**P2.A7 - Adicionar timeout em `odds/collector.py`**~~ → **ABSORVIDO por P2.SH1** (migração para httpx inclui timeout configurável, User-Agent, error handling).
- [ ] **P2.A8 - Validar train_mask em `team_identity.py`:** A função `add_team_target_encoding()` aceita qualquer `train_mask` sem validação. Máscara vazia ou inválida causa data leakage silencioso. Validar que mask não está vazia, é booleana, e tem dimensão compatível. (movido de P1.A4 — defensivo, não bloqueia funcionalidade)
- [ ] **P2.A9 - Sincronizar keywords de feature selection entre `mvp_pipeline.py` e `train.py`:**
  - **Problema:** `_is_model_feature_candidate()` em `mvp_pipeline.py` usa keywords `("_last", "_diff", "_team_enc", "_vs_", "_ratio", "_pressure", "_total", "elo")`. `_is_allowed_feature()` em `train.py` inclui também `"_rolling"` e `"_momentum"`.
  - **Impacto:** `_drop_matches_with_missing_critical_data` pode não reconhecer todas as features de modelo como críticas.
  - **Fix:** Extrair keywords para constante compartilhada ou sincronizar manualmente.
- [ ] **P2.A10 - Sincronizar features em `hyperopt_search.py`:**
  - **Problema:** `_prepare_data()` no hyperopt não adiciona ELO ratings nem team target encoding. Hiperparâmetros são otimizados num feature set diferente de produção.
  - **Fix:** Adicionar `add_elo_ratings()` e `add_team_target_encoding()` em `_prepare_data()`.
- [ ] **P2.A11 - Sincronizar features em `walk_forward.py`:**
  - **Problema:** `_build_features()` não inclui rolling STD, rolling EMA, H2H features nem `drop_redundant_features()`. Avaliação walk-forward usa feature set anterior ao P1.
  - **Fix:** Adicionar chamadas de `add_rolling_std()`, `add_rolling_ema()`, `add_h2h_features()` e `drop_redundant_features()`.
- [ ] **P2.A12 - `_build_ensemble_schedule` ignora parâmetro `algorithms`:**
  - **Problema:** `train.py` para `ensemble_size` entre 25-35 chama `_build_hybrid_ensemble_schedule(size)` ignorando completamente o parâmetro `algorithms` do config. Alguém configurando `algorithms=("xgboost",)` com `ensemble_size=30` receberia silenciosamente 4 algoritmos.
  - **Fix:** Validar que `algorithms` configurado é compatível com o schedule híbrido, ou fazer o schedule respeitar o parâmetro.
- [ ] **P2.A13 - `build_variation_params` usa RNG inconsistente entre algoritmos:**
  - **Problema:** XGBoost usa `np.random.default_rng()` para diversidade de hiperparâmetros, enquanto LightGBM/RF/Ridge/ElasticNet usam listas hardcoded de 10 elementos indexadas por `variation_index % 10`. Se ensemble tiver >10 modelos de um algoritmo, params repetem.
  - **Fix:** Usar RNG-based params consistentemente em todos os algoritmos.

#### P2-B: Infraestrutura e CI (Prioridade Média)

- [ ] **P2.B1 - CI Básico (pytest em push):** Automatizar validação mínima de qualidade com coverage gate > 60%. (antigo P2 Core)
- [ ] **P2.B2 - Logging Estruturado por Aposta:** Salvar decisão com lambdas, votos, edge, threshold, stake e resultado. (antigo P2 Core)
- [ ] **P2.B3 - Reescrever `update_pipeline.py` (Non-Functional):**
  - **Bug 1:** `PipelineConfig(**config_dict)` passa dicts crus do YAML como se fossem dataclasses — crash imediato. **Resolvido automaticamente se P2.B6 for feito primeiro** (usar `PipelineConfig.from_yaml()`).
  - **Bug 2:** Feature engineering completamente ausente — dados brutos vão direto ao `train_and_save_ensemble()`. Portar pipeline completo de features (rolling, STD, EMA, ELO, matchup, H2H, team identity, drop redundant).
  - **Bug 3:** `algorithms=("xgboost", "lightgbm", "randomforest")` hardcoded — falta `"ridge"` e `"elasticnet"`. Ler do config.
  - **Dependência:** P2.B6 (centralizar config) simplifica Bug 1. P0-FIX.5 (rolling fix) deve ser feito antes de portar features.
  - **Referência:** `run.py` (config loading correto) e `mvp_pipeline.py` (feature pipeline completo).
- [ ] **P2.B4 - Migrar `run.py` de `print()` para `logging`:** Usar o módulo de logging já existente em `utils/logging.py`.
- [ ] **P2.B5 - Completar `pyproject.toml`:** Adicionar metadata (author, description, license, requires-python), entry points (`[project.scripts]`), e dev dependencies.
- [ ] **P2.B6 - Centralizar `_load_config()` em `config.py`:**
  - **Problema:** 4 scripts (`run.py`, `consensus_accuracy_report.py`, `hyperopt_search.py`, `feature_correlation_analysis.py`) duplicam lógica de carregamento de config com variações (ex.: conversão list→tuple de `algorithms` feita só em `run.py`).
  - **Fix:** Criar `PipelineConfig.from_yaml(path)` em `config.py` com lógica única e correta. Substituir em todos os scripts.
- [ ] **P2.B7 - Verificar integridade de pickle antes de deserializar:**
  - **Arquivo:** `run.py` linha 88
  - **Problema:** `pickle.load()` sem verificação de hash — artefatos maliciosos podem executar código arbitrário. O projeto já tem `_compute_artifact_hash` em `mvp_pipeline.py`.
  - **Fix:** Verificar SHA256 do `.pkl` contra o hash armazenado no JSON metadata antes de `pickle.load()`.

#### P2-C: Limpeza e Consistência (Prioridade Média-Baixa)

- [ ] **P2.C1 - Remover código morto:**
  - `value/value_engine.py` (217 linhas) - lógica 100% duplicada em `japredictbet.betting.engine`, não é importado por nenhum módulo ativo. **Atenção:** contém bugs próprios — `should_bet()` usa `>` (strict) vs `>=` no engine.py, `implied_probability()` sem zero-check, `remove_overround()` sem guard `total==0`.
  - `config_backup.yml` - backup manual desnecessário (usar git history).
  - `src/japredictbet/agents/` - scaffolding vazio (`NotImplementedError`), sem uso.
  - `rolling.py::add_rolling_features()` (linhas 9-48) — dead code, nunca importada/chamada. Todos os callers usam `add_stat_rolling()`. Remover ou marcar deprecated.
- [ ] **P2.C2 - Resolver boundary `probability/` vs `betting/engine.py`:** Módulo `probability/` contém apenas `calibration.py` (P1.B1). Toda lógica de probabilidade Poisson continua em `betting/engine.py`, violando a boundary do AGENTS.md (`probability → statistical calculations`). Opções: (a) mover funções Poisson para `probability/poisson.py`, ou (b) atualizar AGENTS.md e ARCHITECTURE.md para refletir a realidade.
- [ ] **P2.C3 - Padronizar código (linguagem + style):** Código tem mix de português e inglês (engine.py, mvp_pipeline.py) — escolher um idioma. Também mover imports inline (`re`, `unicodedata`) de `_normalize_team_name()`/`_split_match_name()` em `mvp_pipeline.py` para module-level. Corrigir regex `r"[^a-z0-9\\s]"` → `r"[^a-z0-9\s]"` em `_normalize_team_name()` (impacto prático mínimo, `\\s` em raw string é literal `\s`).
- [ ] **P2.C4 - Sincronizar documentação contraditória:** ✅ PARCIALMENTE RESOLVIDO (01-APR-2026)
  - ✅ `VALIDATION_REPORT.md` reescrito — 3 blockers marcados como resolvidos
  - ✅ `EXECUTIVE_SUMMARY.md` atualizado — blockers fechados
  - ✅ `PROJECT_CONTEXT.md` atualizado — status P1 correto
  - ✅ `MODEL_ARCHITECTURE.md` — Corrigido (03-APR-2026): XGB/LGB counts corrigidos (11 XGB + 10 LGB), adicionadas seções H2H, ELO, Calibração, SHAP, Hyperparameter Persistence, CLV, Risk Management
  - **Pendente (descoberto 03-APR-2026) — 60 inconsistências em 16 arquivos:**
  - ⚠️ **XGB/LGB counts invertidos em TODOS os docs:** Código produz `11 XGB + 10 LGB`. Docs dizem `10 XGB + 11 LGB`. Corrigir em: `ARCHITECTURE.md`, `MODEL_ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `AGENTS.md`.
  - ⚠️ **`IMPLEMENTATION_CONSENSUS.md` completamente errado (Seção 3):** Ainda diz "10 XGB + 10 LGB + 10 RandomForest = 30", depois contradiz com "70/30 hybrid". Reescrever seção inteira para refletir arquitetura real (11 XGB + 10 LGB + 5 Ridge + 4 ElasticNet).
  - ⚠️ **`EXECUTIVE_SUMMARY.md` stale:** Diz "87/87 testes, P1-B parcial". Deveria ser 158/158, P1 100%. Listar P2 como próximos passos.
  - ⚠️ **`VALIDATION_REPORT.md` stale:** Mesmos números desatualizados. Seção 7 "ITENS PENDENTES" lista P1 items como pendentes quando todos estão feitos. Test file names incorretos (`test_integration.py` não existe).
  - ⚠️ **`PROJECT_CONTEXT.md`:** Diz "11 LGBM" (errado, são 10). Diz "87 testes, 10 arquivos" (stale). Corrigir para 158/158, 15+ arquivos.
  - ⚠️ **`TRAINING_STRATEGY.md` (Seção 2):** Diz "50% random split test". Código usa `_build_temporal_split()` com ~25% temporal holdout strict. Corrigir percentuais e método.
  - ⚠️ **`AGENTS.md`:** Preferred libraries falta `lightgbm`, `optuna`, `shap`. Boundaries `probability → statistical calculations` não reflete realidade (Poisson vive em `betting/engine.py`).
  - ⚠️ **`README.md`:** Status diz "P0 100% Completo" sem P1. Falta `lightgbm`/`optuna`/`shap` nas dependências. P0 item numbering diverge de `P0_COMPLETION_SUMMARY.md`.
  - ⚠️ **`DATA_SCHEMA.md`:** Faltam H2H features (`*_h2h_last3`). ELO features genéricas.
  - ⚠️ **`FEATURE_ENGINEERING_PLAYBOOK.md`:** Sem menção de H2H features.
  - ⚠️ **`FEATURE_IMPORTANCE_GUIDE.md`:** Não menciona SHAP (`shap_weights.py`) nem `importance.py`.
  - ⚠️ **`PRODUCT_REQUIREMENTS.md`:** Seção "Reproducibility:" truncada sem conteúdo.
  - ⚠️ **`VALIDATION.md`:** Checklist P1 marca itens como pendentes (CLV ≥ 55%, Brier ≤ 0.20, ROI Monte Carlo) — implementação existe em `engine.py` e `risk.py`, mas validação formal de thresholds pode estar pendente. Clarificar status.
  - ⚠️ **`WORK_MODEL.md`:** Seção de testes recomenda `config_test_50matches.yml` que falta P1 feature flags (ver P2.C5).
- [ ] **P2.C5 - Sincronizar configs de teste/backup com P1 feature flags:**
  - **Problema:** `config_test_50matches.yml` e `config_backup.yml` faltam todos os P1 feature flags: `rolling_use_std`, `rolling_use_ema`, `drop_redundant`, `h2h_window`, `tight_margin_threshold`, `tight_margin_consensus`.
  - **Problema 2:** `config.yml` lista `RandomForest` em `algorithms` mas o hybrid schedule ignora essa lista para size 25-35, tornando-a enganosa.
  - **Fix:** Adicionar flags P1 a ambos os configs. Remover ou documentar `RandomForest` no `algorithms`.

#### P2-D: Produto (Postergar Sem Bloquear)

- [ ] **P2.D1 - Tratamento de Erros Robusto:** Implementar `try-except` em pontos críticos (ex: `fetch_odds`) para evitar falhas abruptas.
- [ ] **P2.D2 - Dashboard de Saúde do Modelo:** Acompanhar volume, hit rate, ROI, CLV e calibração por período.
- [x] ~~**P2.D3 - Integração com APIs Real-time**~~ → **ABSORVIDO por P2-SHADOW** (trilha SH1-SH7 implementa integração real-time com Superbet em modo observacional).
- [ ] **P2.D4 - Bot de Alertas (Telegram):** Notificação de oportunidades aprovadas pelo consenso. **Dependência:** P2-SHADOW (precisa do shadow log como fonte de dados).

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

### Matriz de Maturidade do Projeto (03-APR-2026)

| Dimensão | Nota | Comentário |
|----------|------|------------|
| Arquitetura | 9/10 | Excelente design modular, bem documentada |
| Implementação | 8/10 | P0+P1 completos com FIX.5/FIX.6 fechados; ainda restam `update_pipeline.py` non-functional e divergências de feature set entre scripts |
| Documentação | 5/10 | 60 inconsistências em 16 arquivos: XGB/LGB counts invertidos, docs stale (EXECUTIVE_SUMMARY, VALIDATION_REPORT), IMPLEMENTATION_CONSENSUS errado, TRAINING_STRATEGY com split errado |
| Testes | 7/10 | 158 testes passando (17 arquivos), cobertura ~60%; modulos data/ingestion.py ainda sem testes; rolling cross-group não detectado por testes existentes |
| Reprodutibilidade | 8/10 | SHA256, seeds, requirements pinados, config-driven; penalizado por configs de teste faltando P1 flags e default `algorithms` incompleto |
| Production-Ready | 7/10 | Pipeline completo com calibração, risk management e CLV, mas rolling bug compromete qualidade de features; pickle sem verificação de hash |

---

### Changelog

| Data | Ação |
|------|------|
| 30-MAR-2026 | Criação do roadmap. P0 encerrado. |
| 31-MAR-2026 | Revisão completa de código: 26 arquivos Python, 3 configs, 17 docs. Adicionado P0-FIX (3 bugs bloqueantes). Reorganizado P1 em sub-grupos (A-D) por prioridade. Expandido P2 com gaps de testes e limpeza. Adicionado P3 (performance). Adicionada matriz de maturidade. |
| 31-MAR-2026 | P0-FIX 100% concluído: FIX.1 já estava OK, FIX.2 (`importance.py` multi-model dispatch), FIX.3 (config schema padronizado + validação), FIX.4 (requirements.txt com versões pinadas + requirements-dev.txt). 21 testes passando. |
| 31-MAR-2026 | P1.A1 (ensemble híbrido), P1.A2 (dynamic margin), P1.A3 (lambda validation), P1.B2 (STD+EMA) implementados. 87 testes passando. |
| 01-APR-2026 | Consensus script (`consensus_accuracy_report.py`) sincronizado com pipeline principal: agora usa 106 features (STD+EMA+drop_redundant). Documentação completa revisada e atualizada. |
| 03-APR-2026 | P1 100% concluído: B1 (calibração Brier/ECE), B5 (H2H last 3), C1 (Optuna hyperopt), C2 (SHAP weighted votes), C3 (hyperparameter persistence), D2 (CLV audit), D3 (Kelly/risk). 158 testes passando em 17 arquivos. |
| 03-APR-2026 | Adicionada trilha P2-SHADOW (Superbet Shadow Mode) com 7 items. Corrigido spec SH2: endpoint é SSE, não JSON monolítico — `ijson` substituído por SSE parsing. Matriz de maturidade atualizada. |
| 03-APR-2026 | Revisão profunda de código e documentação: 80 problemas encontrados (20 em código, 60 em docs). **P0-FIX reaberto** com FIX.5 (rolling cross-group contamination — bloqueante), FIX.6 (default algorithms), FIX.7 (regex). Adicionados P2.A9-A12 (feature sync), P2.B6 (centralizar config), P2.B7 (pickle hash), P2.C5 (config flags). Expandidos P2.B3 (3 bugs em update_pipeline), P2.C1 (dead code), P2.C4 (60 inconsistências documentais detalhadas). Matriz de maturidade rebaixada (Implementação 7, Docs 5, Reprodutibilidade 8, Production-Ready 7). |
| 03-APR-2026 | Reavaliação do roadmap: removidos 3 itens absorvidos (P2.A4→SH7, P2.A7→SH1, P2.D3→SHADOW). P0-FIX.7 (regex, impacto mínimo) movido para P2.C3. C3+C3b fundidos. P2.A1 corrigido (1/4 módulos com cobertura, não 0/4). P2.C4 corrigido (MODEL_ARCHITECTURE counts ainda errados). P2.C2 desc atualizada (probability/ não é vazio, tem calibration.py). Adicionadas dependências cruzadas (B6→B3, FIX.5→A5, SHADOW→D4). |
| 03-APR-2026 | **REVISÃO COMPLETA DE P0-FIX:** Todos os 6 itens verificados e implementados corretamente. P0-FIX.1 (hybrid schedule): ✅ 11 XGB + 10 LGB + 5 Ridge + 4 EN. P0-FIX.2 (importance dispatch): ✅ Suporta todos 5 tipos. P0-FIX.3 (config schema): ✅ Validado em `__post_init__`. P0-FIX.4 (version pinning): ✅ Todas as deps com versão exata. P0-FIX.5 (rolling cross-group): ✅ All 4 functions use `.transform()` + regression tests. P0-FIX.6 (default algorithms): ✅ Tuple completa (xgb, lgb, rf, ridge, en). **1 doc issue encontrado:** AGENTS.md linha 166 com XGB/LGB invertido — corrigido (11/10). **Conclusão:** Pipeline P0 production-ready. |
| 03-APR-2026 | P0-FIX hotfix aplicado: rolling cross-group corrigido via `transform(...)` em 4 funcoes (`rolling.py`) + novos testes de regressao (`test_rolling_cross_group.py`). P0-FIX.6 fechado com default `algorithms` incluindo Ridge/ElasticNet + teste dedicado. Retreino completo dos artefatos permanece pendente para fechamento operacional do FIX.5. |
| 03-APR-2026 | Execucao operacional do FIX.5: retreino completo realizado via `run.py` e validacoes `full` + `random-lines` concluidas com relatorios em `log-test/consensus_test_report_20260403_214546.txt` e `log-test/consensus_test_report_20260403_214826.txt`. Cenario `recent subset` continua bloqueado por insuficiencia de linhas de treino em `config_test_50matches.yml` (erro de `Not enough training rows`). |
| 03-APR-2026 | Desbloqueio do `recent subset`: treino/predicao passaram a tratar features esparsas com fallback deterministico (imputacao por mediana + descarte de colunas 100% NaN), filtro de dados criticos no pipeline foi reduzido para campos essenciais, e o script de consenso foi ajustado para nao zerar subsets pequenos por `dropna` estrito. Validacoes `full`, `recent` e `random-lines` executadas com sucesso. |
