# P1 Development — Checklist de Tarefas

**Atualizado:** 31-MAR-2026  
**Status Global:** 🟡 PLANEJADO (pronto para iniciar)

---

## P1-A: Integridade do Pipeline

### P1.A1 — Portar lógica 70/30 para train.py

**Duração estimada:** 3.5h  
**Status:** ✅ COMPLETO  
**Data:** 31-MAR-2026  
**Prioridade:** 🔴 MÁXIMA (prerequisito de P1-B)  
**Dependência:** P0-FIX ✅

#### Subtarefas

- [x] **1.1** Adicionar `algorithms` param a `train_and_save_ensemble()`  
  - Arquivo: `src/japredictbet/models/train.py` linha 182  
  - Tarefa: accept `algorithms: tuple[str, ...] = ("xgboost", "lightgbm", "randomforest", "ridge", "elasticnet")`  
  - ✅ COMPLETO: Default atualizado para incluir Ridge + ElasticNet
  - Esforço: 30min ✅

- [x] **1.2** Validar `build_variation_params()` cobre ridge/elasticnet  
  - Arquivo: `src/japredictbet/models/train.py` linha 475+  
  - Tarefa: Ridge (alpha variation) + ElasticNet (alpha + l1_ratio combo)  
  - ✅ COMPLETO: Ridge (10 alphas), ElasticNet (10 alpha + l1_ratio combos)
  - Esforço: 20min ✅

- [x] **1.3** Testar ensemble com size=30 → 21+9 split  
  - Arquivo: `tests/models/test_train.py` (nova seção)  
  - Tarefa: `_build_hybrid_ensemble_schedule(30)` → 21 boosters + 9 linear
  - ✅ COMPLETO: 4 testes em TestHybridEnsembleSchedule, all passing
  - Esforço: 45min ✅

- [x] **1.4** Treinar ensemble completo, validar sem erro  
  - Arquivo: Manual test + end-to-end validation
  - Tarefa: `python run.py --config config_test_50matches.yml` → 30 models trained
  - ✅ COMPLETO: Ensemble treinado e executado com sucesso
  - Esforço: 30min ✅

- [x] **1.5** Validar `importance.py` funciona com Ridge/ElasticNet  
  - Arquivo: `src/japredictbet/models/importance.py` (P0-FIX.2)
  - Tarefa: Ridge/ElasticNet use `abs(coef_)` para importância
  - ✅ COMPLETO: Already implemented in P0-FIX.2, 34/34 tests passing
  - Esforço: 30min ✅

- [x] **1.6** Update `run.py` para ser mais explícito (output logs)  
  - Arquivo: `run.py` função de logging  
  - Tarefa: print "Ensemble composition: 21 boosters + 9 linear"
  - ✅ COMPLETO: Logging adicionado com detalhamento do ensemble
  - Esforço: 20min ✅

**Acceptance Criteria:**
- ✅ ensemble_size=30 → exatamente 21+9
- ✅ Todos os 30 modelos treinam sem erro (validado)
- ✅ Importância computável para Ridge/ElasticNet (validado em P0-FIX.2)
- ✅ Tests: 34/34 passing (13 novos + 21 existentes)

**PR Checklist:**
- [x] Configuration: Updated config.yml, config_test_50matches.yml, config_backup.yml
- [x] Train.py: Updated algorithms defaults + Ridge/ElasticNet params + filenames
- [x] Run.py: Updated artifact discovery + added ensemble logging
- [x] Tests: 13 new tests in tests/models/test_train.py
- [x] Docs: ARCHITECTURE.md updated
- [x] End-to-end: Pipeline trained successfully with 30 models

---

### P1.A2 — Centralizar dynamic margin rule

**Duração estimada:** 4h  
**Prioridade:** 🔴 MÁXIMA  
**Dependência:** P1.A1 ✅

#### Subtarefas

- [ ] **2.1** Adicionar `tight_margin_threshold: float = 0.5` a `ValueConfig`  
  - Arquivo: `src/japredictbet/config.py` linha ~50  
  - Tarefa: adicionar field  
  - Esforço: 15min

- [ ] **2.2** Adicionar `tight_margin_consensus: float = 0.50` a `ValueConfig`  
  - Arquivo: `src/japredictbet/config.py`  
  - Tarefa: adicionar field  
  - Esforço: 15min

- [ ] **2.3** Atualizar `config.yml` com novos fields  
  - Arquivo: `config.yml`, `config_test_50matches.yml`, `config_backup.yml`  
  - Tarefa:  
    ```yaml
    value:
      threshold: 0.05
      consensus_threshold: 0.45
      tight_margin_threshold: 0.5
      tight_margin_consensus: 0.50
      ...
    ```  
  - Esforço: 20min

- [ ] **2.4** Refatorar `ConsensusEngine` para usar config  
  - Arquivo: `src/japredictbet/betting/engine.py`  
  - Tarefa: procurar `tight_margin`, passar config em vez de hardcode  
  - Esforço: 1h (exploração + refator)

- [ ] **2.5** Implementar método `apply_tight_margin_rule()`  
  - Arquivo: `src/japredictbet/betting/engine.py`  
  - Tarefa:  
    ```python
    def apply_tight_margin_rule(
        lambda_total: float, 
        line: float, 
        consensus: float,
        threshold: float,
        tight_consensus: float
    ) -> float:
        if abs(lambda_total - line) < threshold:
            return max(consensus, tight_consensus)
        return consensus
    ```  
  - Esforço: 45min

- [ ] **2.6** Testes: tight margin ativa quando λ perto de line  
  - Arquivo: `tests/betting/test_engine.py`  
  - Tarefa:  
    - `apply_tight_margin_rule(5.0, 5.5, 0.45, 0.5, 0.50)` → 0.50 ✓  
    - `apply_tight_margin_rule(3.0, 5.5, 0.45, 0.5, 0.50)` → 0.45 ✓  
  - Esforço: 1h

- [ ] **2.7** Validação manual: script vs core comportamento idêntico  
  - Arquivo: Notebook ou script de diff  
  - Tarefa: rodar 100 matches com ambos, comparar consensos  
  - Esforço: 30min

**Acceptance Criteria:**
- ✅ tight_margin_threshold, tight_margin_consensus em config
- ✅ ConsensusEngine aplica dinamicamente
- ✅ Consenso sobe para 50% quando |λ - line| < 0.5
- ✅ Comportamento 100% idêntico ao script

**PR Checklist:**
- [ ] Branch: `feature/p1a-dynamic-margin`
- [ ] Commit: `feat(P1.A2): parametrize dynamic margin rule via config`
- [ ] Rebase on P1.A1: `git rebase feature/p1a-ensemble`
- [ ] Tests: `pytest tests/betting/ -v`

---

### P1.A3 — Validar lambda values

**Duração estimada:** 2.5h  
**Prioridade:** 🟡 ALTA (defensivo)  
**Dependência:** P0-FIX ✅

#### Subtarefas

- [ ] **3.1** Criar `is_valid_lambda(lambda_: float) -> bool`  
  - Arquivo: `src/japredictbet/betting/engine.py`  
  - Tarefa:  
    ```python
    def is_valid_lambda(lambda_: float) -> bool:
        """Check if lambda is valid for Poisson calculations."""
        return np.isfinite(lambda_) and lambda_ >= 0
    ```  
  - Esforço: 15min

- [ ] **3.2** Adicionar validação em `poisson_over_prob()`  
  - Arquivo: `src/japredictbet/betting/engine.py` linha ~15  
  - Tarefa:  
    ```python
    if not is_valid_lambda(lambda_):
        raise ValueError(f"Invalid lambda: {lambda_}")
    ```  
  - Esforço: 10min

- [ ] **3.3** Adicionar validação em `poisson_under_prob()`  
  - Arquivo: `src/japredictbet/betting/engine.py` linha ~25  
  - Tarefa: similar a 3.2  
  - Esforço: 10min

- [ ] **3.4** Guard em `evaluate_bet()` antes de Poisson cálculos  
  - Arquivo: `src/japredictbet/betting/engine.py` linha ~90  
  - Tarefa: check antes de `poisson_over_prob()` ou `poisson_under_prob()`  
  - Esforço: 15min

- [ ] **3.5** Testes edge cases: lambda=-1, NaN, Inf  
  - Arquivo: `tests/betting/test_engine.py`  
  - Tarefa:  
    - `poisson_over_prob(-1, 5.5)` → ValueError  
    - `poisson_over_prob(np.nan, 5.5)` → ValueError  
    - `poisson_over_prob(np.inf, 5.5)` → ValueError  
  - Esforço: 45min

- [ ] **3.6** Testes que valid lambdas (0, 1.5, 10) funcionam  
  - Arquivo: `tests/betting/test_engine.py`  
  - Tarefa: cobertura de casos válidos  
  - Esforço: 20min

**Acceptance Criteria:**
- ✅ `is_valid_lambda()` detecta NaN, Inf, negativo
- ✅ ValueError em vez de silent failure
- ✅ 100% cobertura edge cases
- ✅ Documentação clara

**PR Checklist:**
- [ ] Branch: `feature/p1a-lambda-validation`
- [ ] Commit: `feat(P1.A3): lambda value validation in Poisson calculations`
- [ ] Tests: `pytest tests/betting/test_engine.py::test_lambda_validation -v`

---

## P1-B: Evolução de Features

### P1.B1 — Calibração de Probabilidades

**Duração estimada:** 7.5h  
**Prioridade:** 🟠 ALTA  
**Dependência:** P1.A1 ✅

#### Subtarefas

- [ ] **1.1** Criar `src/japredictbet/models/calibration.py`  
  - Arquivo: novo módulo  
  - Tarefa: estrutura básica com imports  
  - Esforço: 15min

- [ ] **1.2** Implementar `brier_score(y_true, y_pred) -> float`  
  - Arquivo: `models/calibration.py`  
  - Tarefa: `mean((y_pred - y_true)^2)`  
  - Esforço: 20min

- [ ] **1.3** Implementar `expected_calibration_error(y_true, y_pred, n_bins=10) -> float`  
  - Arquivo: `models/calibration.py`  
  - Tarefa: bin predictions, compare avg_prob vs freq per bin  
  - Esforço: 45min

- [ ] **1.4** Implementar `calibration_curve(y_true, y_pred, n_bins=10) -> (prob_true, prob_pred)`  
  - Arquivo: `models/calibration.py`  
  - Tarefa: return array of (prob_predicted, prop_positive) per bin para plot  
  - Esforço: 30min

- [ ] **1.5** Rotina pós-treino em pipeline  
  - Arquivo: `src/japredictbet/pipeline/mvp_pipeline.py` ou novo `calibration_reporter.py`  
  - Tarefa: após final predictions, compute Brier/ECE no test split  
  - Esforço: 1h

- [ ] **1.6** Análise temporal (4-week rolling calibração)  
  - Arquivo: `models/calibration.py`  
  - Tarefa: função que slices test set por período, computa Brier por período  
  - Esforço: 1.5h

- [ ] **1.7** Integrar em `run.py` output  
  - Arquivo: `run.py`  
  - Tarefa: print Brier, ECE após treino  
  - Esforço: 30min

- [ ] **1.8** Documentar em `docs/VALIDATION.md`  
  - Arquivo: `docs/VALIDATION.md`  
  - Tarefa: adicionar seção Calibration com definições, target scores (Brier < 0.25, ECE < 0.10)  
  - Esforço: 45min

- [ ] **1.9** Testes  
  - Arquivo: `tests/models/test_calibration.py`  
  - Tarefa: testes Brier, ECE com dados sintéticos  
  - Esforço: 1h

**Acceptance Criteria:**
- ✅ Brier score < 0.25 (test set)
- ✅ ECE < 0.10 (test set)
- ✅ Calibração temporal gera insight (ex: degradation over time)
- ✅ Documentado

**PR Checklist:**
- [ ] Branch: `feature/p1b-calibration`
- [ ] Tests: `pytest tests/models/test_calibration.py -v`
- [ ] Commit: `feat(P1.B1): calibration metrics (Brier, ECE)`

---

### P1.B2 — Rolling Features (EMA + Volatilidade)

**Duração estimada:** 6.5h  
**Prioridade:** 🟠 MÁXIMA (prerequisito P1.B3+B4)  
**Dependência:** P1.A1 ✅

#### Subtarefas

- [ ] **2.1** Estender `add_rolling_features()` para window=3  
  - Arquivo: `src/japredictbet/features/rolling.py` linha 10+  
  - Tarefa: adicionar calls com window=3  
  - Esforço: 20min

- [ ] **2.2** Implementar `add_rolling_std()`  
  - Arquivo: `src/japredictbet/features/rolling.py`  
  - Tarefa:  
    ```python
    def add_rolling_std(df, team_col, for_col, against_col, window, prefix):
        group = df.groupby(team_col, sort=False)
        df[f"{prefix}_corners_for_std_last{window}"] = 
            group[for_col].shift(1).rolling(window).std()
        df[f"{prefix}_corners_against_std_last{window}"] = 
            group[against_col].shift(1).rolling(window).std()
        return df
    ```  
  - Esforço: 45min

- [ ] **2.3** Implementar `add_ema_features()`  
  - Arquivo: `src/japredictbet/features/rolling.py`  
  - Tarefa:  
    ```python
    def add_ema_features(df, team_col, for_col, against_col, spans=[3,5,10], prefix=""):
        group = df.groupby(team_col, sort=False)
        for span in spans:
            df[f"{prefix}_ema_corners_for_span{span}"] = 
                group[for_col].shift(1).ewm(span=span, adjust=False).mean()
            df[f"{prefix}_ema_corners_against_span{span}"] = 
                group[against_col].shift(1).ewm(span=span, adjust=False).mean()
        return df
    ```  
  - Esforço: 1.5h

- [ ] **2.4** Integrar em `mvp_pipeline.py`  
  - Arquivo: `src/japredictbet/pipeline/mvp_pipeline.py` linha ~100+  
  - Tarefa: chamar `add_rolling_std()` para windows [3,5,10], `add_ema_features()`  
  - Esforço: 45min

- [ ] **2.5** Testes data leakage  
  - Arquivo: `tests/features/test_rolling.py`  
  - Tarefa: assert primeira linha por team tem NaN no rolling_3 (não temos 3 games de history)  
  - Esforço: 45min

- [ ] **2.6** Validar sem NaN forward leakage  
  - Arquivo: Manual notebook ou test  
  - Tarefa: EMA/rolling para match em data T só usa histórico <= T-1  
  - Esforço: 45min

- [ ] **2.7** Feature importance análise  
  - Arquivo: Notebook (ad-hoc)  
  - Tarefa: train completo, compar feature importance novos vs antigos  
  - Esforço: 1h

- [ ] **2.8** Documentar em FEATURE_ENGINEERING_PLAYBOOK.md  
  - Arquivo: `docs/FEATURE_ENGINEERING_PLAYBOOK.md`  
  - Tarefa: adicionar seção sobre rollin/std/EMA, spans utilizados, racional  
  - Esforço: 45min

**Acceptance Criteria:**
- ✅ 6 distinct features: [3,5,10] × [mean, std] + EMA
- ✅ Sem NaN forward leakage (.shift(1) obrigatório)
- ✅ Correlação com target > 0.05 para novos features
- ✅ Feature importance top-20 inclui pontos adicionais con score > 0.01

**PR Checklist:**
- [ ] Branch: `feature/p1b-rolling-ema`
- [ ] Tests: `pytest tests/features/ -v`
- [ ] Docs: FEATURE_ENGINEERING_PLAYBOOK.md atualizado
- [ ] Commit: `feat(P1.B2): rolling features (window=3, std, EMA)`

---

### P1.B3 — Record e Game State

**Duração estimada:** 5.5h  
**Prioridade:** 🟠 ALTA  
**Dependência:** P1.B2 ✅

#### Subtarefas

- [ ] **3.1** Testar/Corrigir `add_result_rolling()` existente  
  - Arquivo: `src/japredictbet/features/rolling.py` linha ~96  
  - Tarefa: confirma que gera W/D/L para últimos 5, 10  
  - Esforço: 1h

- [ ] **3.2** Implementar `add_momentum_features()`  
  - Arquivo: `src/japredictbet/features/rolling.py`  
  - Tarefa:  
    ```python
    def add_momentum_features(df, team_col, goals_for_col, goals_against_col, windows=[5,10]):
        for window in windows:
            # momentum = (wins + 0.5*draws) / games_played
            # Usar V,E,D já computados por add_result_rolling()
            df[f"momentum_last{window}"] = ...
        return df
    ```  
  - Esforço: 1h

- [ ] **3.3** Implementar `add_form_features()`  
  - Arquivo: `src/japredictbet/features/rolling.py`  
  - Tarefa:  
    ```python
    def add_form_features(df, team_col, goals_for_col, goals_against_col):
        # hot_form = 1 se última vitória < 2 jogos, 0 otherwise
        group = df.groupby(team_col, sort=False)
        df["hot_form"] = group["_win"].shift(1).rolling(2).sum() > 0
        return df
    ```  
  - Esforço: 45min

- [ ] **3.4** Adicionar "team confidence" (fav vs underdog)  
  - Arquivo: `src/japredictbet/features/rolling.py`  
  - Tarefa: feature indicando se time é historicamente strong (Poisson cornes > median)  
  - Esforço: 1h

- [ ] **3.5** Testes data leakage em record features  
  - Arquivo: `tests/features/test_rolling.py`  
  - Tarefa: assert W/D/L uses only past games, não contém current game  
  - Esforço: 1h

- [ ] **3.6** Validar NaN handling primeiros 10 jogos  
  - Arquivo: Manual test  
  - Tarefa: após feature engineering, primeiros 10-15 rows OK ter NaN  
  - Esforço: 30min

- [ ] **3.7** Documentar tático  
  - Arquivo: `docs/FEATURE_ENGINEERING_PLAYBOOK.md`  
  - Tarefa: adicionar seção Record/Momentum com interpretações  
  - Esforço: 45min

**Acceptance Criteria:**
- ✅ Record features correlação > 0.1 com cantos
- ✅ Momentum reduz overfitting (melhor val score)
- ✅ Sem missing values exceto primeiros 10 jogos/season
- ✅ Tático claro e interpretável

**PR Checklist:**
- [ ] Branch: `feature/p1b-record-momentum`
- [ ] Base: rebase on P1.B2
- [ ] Tests: `pytest tests/features/test_rolling.py -v`
- [ ] Commit: `feat(P1.B3): record and momentum features`

---

### P1.B4 — H2H e Cross-Features

**Duração estimada:** 8h  
**Prioridade:** 🟡 MÉDIA (nice-to-have, pode postergar)  
**Dependência:** P1.B3 ✅ (ou paralelo se precisa)

#### Subtarefas

- [ ] **4.1** Criar `src/japredictbet/features/h2h.py` (novo arquivo)  
  - Arquivo: novo módulo  
  - Tarefa: estrutura básica  
  - Esforço: 15min

- [ ] **4.2** Implementar `add_h2h_features()`  
  - Arquivo: `features/h2h.py`  
  - Tarefa:  
    ```python
    def add_h2h_features(df, home_col, away_col, corners_col, window=3):
        # Aggregate últimos 3 H2H quando home jogou contra away (vice-versa)
        # Retornar avg_corners, count matches
        return df_with_h2h
    ```  
  - Esforço: 1.5h

- [ ] **4.3** Join H2H com dataset principal  
  - Arquivo: `features/h2h.py`  
  - Tarefa: merge on (home_team, away_team), fill NAs com 0 ou média  
  - Esforço: 45min

- [ ] **4.4** Implementar `add_cross_features()`  
  - Arquivo: `src/japredictbet/features/cross.py` (novo)  
  - Tarefa:  
    ```python
    def add_cross_features(df):
        # home_attack_strength × away_defense_weakness
        # home_defense_strength × away_attack_strength
        df["home_atk_vs_away_def"] = df["home_corners_for_last10"] * 
                                      (1 / (df["away_corners_against_last10"] + 1))
        # etc...
        return df
    ```  
  - Esforço: 1.5h

- [ ] **4.5** Testes H2H sem data leakage  
  - Arquivo: `tests/features/test_h2h.py`  
  - Tarefa: H2H em data T só inclui matches antes de T  
  - Esforço: 1.5h

- [ ] **4.6** Validar VIF < 5 para cross-features  
  - Arquivo: Notebook (ad-hoc)  
  - Tarefa: calcular VIF, remover se > 5  
  - Esforço: 1.5h

- [ ] **4.7** Testar feature importance > 0.01 para novos features  
  - Arquivo: Notebook (ad-hoc)  
  - Tarefa: treinar completo, validar cross-features em top-30 features  
  - Esforço: 1h

- [ ] **4.8** Documentar features derivadas  
  - Arquivo: `docs/FEATURE_ENGINEERING_PLAYBOOK.md`  
  - Tarefa: adicionar seção H2H + Cross com definitions, rationals  
  - Esforço: 1h

**Acceptance Criteria:**
- ✅ H2H disponível para 80%+ matches
- ✅ Cross-features VIF < 5
- ✅ Feature importance > 0.01 para novos features
- ✅ Sem silent failures

**PR Checklist:**
- [ ] Branch: `feature/p1b-h2h-cross`
- [ ] Base: rebase on P1.B3 (ou P1.B2 se paralelo)
- [ ] Tests: `pytest tests/features/ -v`
- [ ] Commit: `feat(P1.B4): H2H and cross-features`

---

## Global Completion Checklist

### P1-A Final

- [ ] All 3 sub-items (A1, A2, A3) have PRs merged to main
- [ ] Tests: 21/21 continue passing
- [ ] `python run.py` executes without error
- [ ] Ensemble: 21 boosters + 9 linear verified
- [ ] Dynamic margin: config-driven, not hardcoded
- [ ] Lambda validation: NaN/Inf prevented
- [ ] Code review approved
- [ ] Docs updated

### P1-B Final

- [ ] All 4 sub-items (B1, B2, B3, B4) have PRs merged to main
- [ ] Calibration: Brier < 0.25, ECE < 0.10 on test
- [ ] Rolling: 6 windows generated, no leakage
- [ ] Record: W-E-D for windows [5,10], momentum computed
- [ ] H2H: 80%+ coverage, 0-filled fallback
- [ ] Cross-features: VIF < 5, importance > 0.01
- [ ] Feature count: +15-20 new features added
- [ ] Pipeline runtime: < 5min end-to-end
- [ ] Code review approved
- [ ] Docs updated

### Integration & Validation

- [ ] Temporal validation: last 10% accuracy ≥ baseline
- [ ] Overfitting test: (train Brier - test Brier) < 0.05
- [ ] All 60+ tests pass: `pytest tests/ -v`
- [ ] CI/CD green: GitHub actions ✅
- [ ] Code style: `black --check src/`
- [ ] Coverage: > 40% (target for next phase)

---

## Notes for Daily Use

### Starting Each Small Task

1. Create feature branch: `git checkout -b feature/p1-<letter>-<name>`
2. Make corresponding TODO item in this checklist
3. Update as you progress
4. Before PR: ensure all sub-task checks ✅

### Before Each PR

```bash
# Run tests
pytest tests/ -v

# Check style
black --check src/

# Build/validate
python run.py --config config_test_50matches.yml

# View coverage (if available)
pytest --cov=src/japredictbet tests/ --cov-report=term-missing
```

### Resolving Blockers

- **Multicolineariry in cross-features?** → Use VIF, remove high-correlation pair
- **Data shows leakage?** → Trace .shift(1), check groupby logic
- **Performance too slow?** → Profile with cProfile, optimize hot loops
- **Tests fail unexpectedly?** → Run single test, check data semantics

---

## Commit Message Template

```
feat(P1.A1): <short description>

<detailed explanation>
- What changed
- Why it was needed
- How it works

Fixes: <issue ref if applicable>
Related: P1.A1
```

Example:
```
feat(P1.A1): hybrid 70/30 ensemble scheduling in core

Ported logic from consensus_accuracy_report.py to train.py.
Now train_and_save_ensemble() accepts algorithms parameter.
Default: 70% boosters (xgboost/lightgbm) + 30% linear (ridge/elasticnet).

- Added algorithms=tuple parameter to train_and_save_ensemble()
- Updated _build_hybrid_ensemble_schedule() to correctly split 21+9
- Added tests for ensemble composition validation

Related: docs/next_pass.md P1.A1
```

