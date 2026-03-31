# P1 Development Plan — P1-A e P1-B

**Data de Criação:** 31 de Março, 2026  
**Status:** Planejamento Concluído  
**Baseline:** P0-FIX 100% completo, 21 testes passando  
**Duração Estimada:** 3-4 semanas (80-120 horas)

---

## 📋 Resumo Executivo

### Visão Geral

**P1-A (Integridade do Pipeline)** — 3 tarefas de consolidação  
Objetivo: Fazer o pipeline core (`run.py` → `train.py`) ter paridade funcional com o script experimental  

**P1-B (Evolução de Features)** — 4 tarefas de engenharia de features  
Objetivo: Melhorar acurácia com rolling windows curtas, EMA, record/momentum, e H2H  

### Roadmap de Sequenciamento

```
Semana 1: P1-A (consolidação)
├── P1.A1: Portar 70/30 ensemble para core
├── P1.A2: Parametrizar dynamic margin rule
└── P1.A3: Validar lambda values (defensivo)

Semana 2-3: P1-B (features)
├── P1.B1: Calibração de probabilidades
├── P1.B2: Rolling + EMA features
├── P1.B3: Record e game state
└── P1.B4: H2H e cross-features
```

### Status Crítico

✅ **Desbloqueado:** Nenhum bloqueador. P0-FIX completado.  
⚠️ **Dependências:** P1.B depende de P1.A1 completado.  
🔴 **Risco:** Multicolinearidade em P1.B, data leakage em features.

---

## P1-A: Integridade do Pipeline

### 🎯 P1.A1 — Portar lógica 70/30 para train.py

**Objetivo:** Fazer ensemble core usar híbrido 70/30 (21 boosters + 9 linear)

#### Status Atual

| Item | Status | Nota |
|------|--------|------|
| `_build_hybrid_ensemble_schedule()` | ✅ Existe | Implementado em train.py:415 |
| Scheduling corr. | ✅ OK | Retorna [xgb, lgb, ..., ridge, elasticnet, ...] |
| `train_and_save_ensemble()` | ❌ Não usa | Ignora algorithms param |
| `run.py` | ❌ Hardcode | Sem parametrização ensemble |
| Testes | ⚠️ Parcial | 21 testes passam, mas sem ensemble validation |

#### Análise Técnica

```python
# train.py linha 120-150
train_ensemble_models(
    algorithms=("xgboost", "lightgbm", "randomforest"),  # ← PROBLEMA: só boosters
    ensemble_size=30
)

# train.py linha 182-200
def train_and_save_ensemble(...):
    models, specs = train_ensemble_models(...)  # ← não passa algorithms!
    
# run.py
run_mvp_pipeline(config)  # ← tudo hardcoded, sem CLI options
```

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 1.1 | Adicionar `algorithms` param a `train_and_save_ensemble()` | train.py:182 | 30min |
| 1.2 | Implementar default `algorithms=("xgboost", "lightgbm", "ridge", "elasticnet")` | train.py:120 | 20min |
| 1.3 | Validar `build_variation_params()` suporta ridge/elasticnet | train.py:475+ | 30min |
| 1.4 | Adicionar testes: ensemble size 30 → 21+9 split | tests/models/ | 1h |
| 1.5 | Validar todos 30 modelos treinam sem erro | Manual test | 30min |
| 1.6 | Verificar que importância funciona com Ridge/ElasticNet | importance.py + test | 30min |

**Total:** ~3.5h

#### Critério de Sucesso

- [ ] `ensemble_size=30` com hybrid gera exatamente 21 boosters + 9 linear
- [ ] Nenhum erro de treinamento com Ridge/ElasticNet
- [ ] `importance.py` computável para todos os tipos
- [ ] 21/21 testes continuam passando

#### Notas de Implementação

- Lógica blueprint já existe em `scripts/consensus_accuracy_report.py` L228-257
- `build_variation_params()` já suporta ridge/elasticnet (adicionar hyperparâmetros)
- Considerar adicionar CLI param `--algorithms` para flexibilidade futura

---

### 🎯 P1.A2 — Centralizar dynamic margin rule

**Objetivo:** Parametrizar regra que aumenta consenso quando λ ≈ line

#### Status Atual

| Componente | Status | Local |
|------------|--------|-------|
| Lógica script | ✅ Implementada | consensus_accuracy_report.py:545-548 |
| ConsensusEngine | ❌ Hardcoded | betting/engine.py (tight_margin=0.5) |
| Config | ❌ Ausente | config.yml |
| Documentação | ⚠️ Incompleta | Mencionado mas sem spec clara |

#### Regra de Lógica

```python
# Quando |λ_total - line| < threshold:
#   consenso_mínimo = 50% (em vez de 45% padrão)
# Racional: Incerteza aumenta perto da linha, subirBar

# Exemplo: line=5.5
λ_total_low = 5.0   → |5.0 - 5.5| = 0.5 ✓ TIGHT → consenso=50%
λ_total_high = 5.9  → |5.9 - 5.5| = 0.4 ✓ TIGHT → consenso=50%
λ_total_safe = 3.0  → |3.0 - 5.5| = 2.5 ✗ LOOSE → consenso=45%
```

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 2.1 | Adicionar `tight_margin_threshold` a ValueConfig | config.py | 20min |
| 2.2 | Adicionar `tight_margin_consensus` a ValueConfig | config.py | 20min |
| 2.3 | Atualizar config.yml com defaults | config*.yml | 20min |
| 2.4 | Refatorar ConsensusEngine para usar config | betting/engine.py | 1h |
| 2.5 | Adicionar método `apply_tight_margin_rule()` | betting/engine.py | 45min |
| 2.6 | Testes: tight margin ativa quando λ perto | tests/betting/ | 1h |
| 2.7 | Validar comportamento idêntico ao script | Manual validation | 30min |

**Total:** ~4h

#### Critério de Sucesso

- [ ] Parâmetros `tight_margin_threshold` e `tight_margin_consensus` em config.yml
- [ ] ConsensusEngine aplica dinâmicamente (sem hardcode)
- [ ] Consenso sobe para 50% quando dentro do threshold
- [ ] Comportamento 100% idêntico ao script

#### Notas Técnicas

- Localizar onde ConsensusEngine usa tight_margin valores (procurar em engine.py)
- Precisar fazer consenso_sweep respeitar dynamic threshold
- Testar com múltiplas linhas (5.5, 8.5, 10.5) e lambdas

---

### 🎯 P1.A3 — Validar lambda values

**Objetivo:** Prevenir NaN/Inf em lambdas que quebram cálculos Poisson

#### Status Atual

| Ponto | Status | Risco |
|-------|--------|-------|
| Validação lambda | ❌ Nenhuma | **ALTO** — silent failure em poisson.cdf(NaN) |
| Modelos regressores | ⚠️ Possível NaN | Possível com outliers ou bad features |
| Error handling | ❌ Mínimo | Nenhum try-except em probs Poisson |

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 3.1 | Criar `is_valid_lambda(lambda_: float) -> bool` | engine.py | 20min |
| 3.2 | Validar em `poisson_over_prob()` | engine.py:15 | 15min |
| 3.3 | Validar em `poisson_under_prob()` | engine.py:23 | 15min |
| 3.4 | Adicionar validação/guard em `evaluate_bet()` | engine.py:85 | 20min |
| 3.5 | Testes edge case: lambda=-1, NaN, Inf | tests/betting/ | 45min |
| 3.6 | Documentar expected behavior | engine.py docstring | 15min |

**Total:** ~2.5h

#### Critério de Sucesso

- [ ] Função `is_valid_lambda()` detecta NaN, Inf, negativo
- [ ] ValueError apropriado em vez de silent crash
- [ ] 100% cobertura de testes para lambdas inválidas
- [ ] Documentação clara do comportamento

---

## P1-B: Evolução de Features

### 🎯 P1.B1 — Calibração de Probabilidades

**Objetivo:** Validar aderência entre probabilidade prevista e realidade real

#### Status Atual

| Métrica | Status | Referência |
|---------|--------|-----------|
| Brier Score | ❌ Não existe | docs/VALIDATION.md menciona |
| ECE | ❌ Não existe | docs/VALIDATION.md menciona |
| Teste temporal | ❌ Não existe | Precisa série temporal |
| Calibration plots | ❌ Não existe | Visual validation |

#### Definições

**Brier Score:** `BS = mean((prob_predicted - outcome)²)`  
- Objetivo: < 0.25 (boa)  
- Interpretação: penaliza probabilidades longe da verdade

**ECE (Expected Calibration Error):** Agrupar predições em bins + comparar  
- Objetivo: < 0.10 (boa)  
- Interpretação: "quando modelo diz 70%, acaba acontecendo ~70%?"

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 1.1 | Criar `models/calibration.py` com Brier, ECE | models/calibration.py | 1h |
| 1.2 | Implementar calibration curves (bins by prob) | models/calibration.py | 1h |
| 1.3 | Rotina pós-treino: computa calibração em test split | pipeline/ | 1.5h |
| 1.4 | Análise temporal: calibração por período (4-week) | models/calibration.py | 1.5h |
| 1.5 | Integrar em `run.py` output | run.py | 30min |
| 1.6 | Documentar métricas em VALIDATION.md | docs/ | 45min |
| 1.7 | Testes calibração | tests/ | 1h |

**Total:** ~7.5h

#### Critério de Sucesso

- [ ] Brier Score computável e < 0.25
- [ ] ECE computável e < 0.10
- [ ] Calibração temporal detecta shifts em qualidade
- [ ] Output visual (histogramas, curvas)

---

### 🎯 P1.B2 — Rolling Features (EMA + Volatilidade)

**Objetivo:** Adicionar historicais curtos (3 jogos), desvio padrão (volatilidade), EMA

#### Status Atual

| Feature | Status | Windows |
|---------|--------|---------|
| Rolling mean | ✅ Existe | [10, 5] |
| Window=3 | ❌ Falta | Curto prazo |
| STD (volatilidade) | ❌ Falta | - |
| EMA | ❌ Falta | Time-decay |

#### Novas Features

```
Corners (rolling):
  - home_corners_for_last3 (mean)
  - home_corners_for_last3_std (volatility)
  - home_ema_3 (exponential, alpha=0.33)
  
Goals:
  - Similar para goals_for, goals_against
  
Result/momentum:
  - Wins last 3, last 5, last 10
```

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 2.1 | Estender `add_rolling_features()` para window=3 | features/rolling.py | 30min |
| 2.2 | Criar `add_rolling_std()` para STD | features/rolling.py | 45min |
| 2.3 | Criar `add_ema_features()` com Time-Decay | features/rolling.py | 1.5h |
| 2.4 | Testar sem data leakage (.shift(1)) | tests/features/ | 1h |
| 2.5 | Validar correlação com target | Notebook analysis | 1h |
| 2.6 | Documentar em FEATURE_ENGINEERING_PLAYBOOK.md | docs/ | 45min |
| 2.7 | Integrar em mvp_pipeline.py | pipeline/mvp_pipeline.py | 1h |

**Total:** ~6.5h

#### Critério de Sucesso

- [ ] Pipeline gera 6 distinct windows: [3, 5, 10] × [mean, std] + EMA
- [ ] Sem NaN forward leakage (todos os features usam .shift(1))
- [ ] Novos features correlação com target > 0.05
- [ ] Feature importance top-20 inclui novos com score > 0.01

#### Notas Técnicas

```python
# EMA usando pandas
df['ema_3'] = df.groupby('team')['corners_for'].shift(1).ewm(span=3, adjust=False).mean()
# span=3 → alpha = 2/(3+1) = 0.5

# Testar: compare vanilla rolling vs EMA em mesmo período
```

---

### 🎯 P1.B3 — Record e Game State

**Objetivo:** Adicionar contexto tático (V-E-D record) e momentum recente

#### Status Atual

| Feature | Status | Implementação |
|---------|--------|----------------|
| V-E-D record | ⚠️ Parcial | `add_result_rolling()` existe mas tem TODO |
| Momentum | ❌ Falta | Razão (wins + 0.5*draws) / games |
| Form/Hot streak | ❌ Falta | "Ganhou recentemente?" |

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 3.1 | Testar/corrigir `add_result_rolling()` | features/rolling.py:96+ | 1h |
| 3.2 | Criar `add_momentum_features()` (W+0.5D)/G | features/rolling.py | 45min |
| 3.3 | Criar `add_form_features()` (hot streak indicator) | features/rolling.py | 45min |
| 3.4 | Adicionar "team confidence" (underdog vs favorite) | features/rolling.py | 1h |
| 3.5 | Testes data leakage | tests/features/ | 1h |
| 3.6 | Validar NaN handling primeiros 10 jogos | Manual test | 30min |
| 3.7 | Documentar significado tático | docs/ | 45min |

**Total:** ~5.5h

#### Critério de Sucesso

- [ ] Record features correlação > 0.1 com cantos
- [ ] Momentum reduz overfitting (melhor val score)
- [ ] Sem missing values exceto primeiros 10 jogos/season
- [ ] Tático claro e interpretável

---

### 🎯 P1.B4 — H2H e Cross-Features

**Objetivo:** Adicionar head-to-head histórico e features cruzadas ataque×defesa

#### Status Atual

| Feature | Status | Nota |
|---------|--------|------|
| H2H dados | ❌ Não existe | Precisa agregar histórico direto |
| Cross-features | ❌ Não existe | Precisa ataque_home vs defesa_away |
| matchup.py | ✅ Base existe | Mas é simples, sem cross |

#### Novas Features

```
H2H (últimos 3 confrontos):
  - home_h2h_corners_avg_last3
  - away_h2h_corners_avg_last3
  
Cross-features:
  - home_attack × away_defense
  - home_defense × away_attack
  - Interação home_form × away_form
```

#### Subtarefas Detalhadas

| # | Tarefa | Arquivo | Esforço |
|---|--------|---------|---------|
| 4.1 | Criar `add_h2h_features()` | features/h2h.py (NEW) | 1.5h |
| 4.2 | Join H2H com main dataset | features/h2h.py | 45min |
| 4.3 | Criar `add_cross_features()` | features/cross.py (NEW) | 1.5h |
| 4.4 | Validar H2H sem data leakage | tests/features/ | 1h |
| 4.5 | Verificar VIF < 5 (multicolinearidade) | Notebook analysis | 1.5h |
| 4.6 | Testar feature importance > 0.01 | Notebook analysis | 1h |
| 4.7 | Documentar features derivadas | docs/ | 1h |

**Total:** ~8h

#### Critério de Sucesso

- [ ] H2H disponível para 80%+ matches
- [ ] Cross-features VIF < 5
- [ ] Feature importance > 0.01 para novos features
- [ ] Sem silent failures em matches com H2H faltando

---

## 📅 Roadmap de Execução (3-4 semanas)

### **Semana 1: P1-A Consolidação** (16-17 horas)

| Dia | P1.A1 | P1.A2 | P1.A3 | Outros |
|-----|-------|-------|-------|--------|
| Mon-Tue | 3.5h | — | — | Setup branch |
| Wed | — | 4h | — | — |
| Thu | — | — | 2.5h | Testes integração |
| Fri | — | — | — | **PR Review** |

**Objetivo:** P1-A 100% completo e merged

---

### **Semana 2: P1-B Foundation** (13.5 horas)

| Dia | P1.B1 | P1.B2 | Outros |
|-----|-------|-------|--------|
| Mon-Tue | 4h | 2.5h | Setup new branch |
| Wed | 3.5h | 4h | — |
| Thu | — | — | Testes integração |
| Fri | — | — | **PR Review** |

**Objetivo:** P1.B1 + P1.B2 completados

---

### **Semana 3-4: P1-B Advanced** (13.5 horas)

| Dia | P1.B3 | P1.B4 | Outros |
|-----|-------|-------|--------|
| Mon-Tue | 2.5h | 4h | Setup features |
| Wed-Thu | 3h | 4h | VIF analysis |
| Fri | — | — | **PR Review + Merge** |

**Objetivo:** P1-B 100% completo, todos merged

---

## ✅ Critérios de Sucesso Global

### P1-A: Integridade

- [ ] `python run.py` treina ensemble 21 boosters + 9 linear sem erro
- [ ] Dynamic margin rule ativa quando `|λ - line| < threshold`
- [ ] Lambda validation previne crashes com NaN/Inf
- [ ] Todos 21 testes continuam passando

### P1-B: Features

- [ ] Brier Score < 0.25, ECE < 0.10
- [ ] 6 rolling windows (3,5,10 × mean,std) + EMA gerados
- [ ] V-E-D record + momentum sem data leakage
- [ ] H2H para 80%+, cross-features VIF < 5
- [ ] Feature importance top-20 inclui novos features (score > 0.01)

### Integração

- [ ] Pipeline core paridade com script
- [ ] Accuracy melhora 2-3% vs baseline (validação temporal)
- [ ] Documentação completa e atualizada
- [ ] Code review aprovado, todos testes verde

---

## 🚨 Riscos e Mitigações

| Risco | Severidade | Mitigação |
|-------|-----------|----------|
| Multicolinearidade P1.B | 🟠 ALTO | Usar VIF, feature selection, regularização existe |
| Data leakage novos features | 🟠 ALTO | Revisar .shift(1) obrigatório, testes leakage |
| Performance pipeline (mais features) | 🟡 MÉDIO | Profile, possível feature selection P1.C1 |
| EMA instabilidade | 🟡 MÉDIO | Usar múltiplos spans (3,5,10), averaging |
| H2H dados incompletos | 🟢 BAIXO | Fallback para zeros, mask NAs |

---

## 📚 Referências e Links

- **P0-FIX (Concluído):** Documento acima
- **Código Blueprint:** `scripts/consensus_accuracy_report.py` L228-257 (ensemble), L545-548 (margin)
- **Docs:** `docs/FEATURE_ENGINEERING_PLAYBOOK.md`, `docs/VALIDATION.md`, `docs/ARCHITECTURE.md`
- **Testes:** `tests/pipeline/`, `tests/betting/`, `tests/features/`

---

## 📝 Próximos Passos

1. ✅ **Agora:** Revisar e aprovar plano
2. 🎯 **Amanhã:** Criar branch `feature/p1a-ensemble` e iniciar P1.A1
3. 🔄 **Durante:** Daily standups, code review em paralelo
4. 📊 **Fim de semana:** Validação temporal, análise de acurácia

