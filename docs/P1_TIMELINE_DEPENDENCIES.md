# P1 Development — Cronograma e Dependências Visuais (Atualizado 31-MAR-2026)

## Timeline de Execução (Sprint Board)

### EXECUÇÃO COMPLETA (P1-A1 ✅ | P1-A2/A3 Ready 🟢)

```
SEMANA 1 (P1-A) - INICIADO                             SEMANA 2-3 (P1-B) - PRONTO              
┌─────────────────────┐                                ┌──────────────────────┐
│ Mon-Tue: P1.A1 ✅   │    ┌─ COMPLETO ─┐            │ Mon-Tue: P1.B1+B2    │
│ Portar 70/30        │    │             ├──────────> │ Calibração + EMA     │
│ 3.5h (ON TIME)      │    │ 31-MAR-2026 │            │ 6.5h (DESBLOQUEADO)  │
└─────────────────────┘    └─────────────┘            └──────────────────────┘
       ✅ COMPLETO
       - 30 modelos treinam
       - 13 novos testes
       - Pipeline merged
                                                       ┌──────────────────────┐
┌─────────────────────┐                                │ Wed-Thu: P1.B2cont   │
│ Wed: P1.A2 🟢       │    ┌─ READY 🟢 ─┐            │ + Colinearidade      │
│ Dynamic Margin      │    │             ├──────────> │ + Testing            │
│ 3h est. (PRONTO)    │    │ NEXT PHASE  │            │ 4h                   │
└─────────────────────┘    └─────────────┘            └──────────────────────┘

┌─────────────────────┐                                ┌──────────────────────┐
│ Thu: P1.A3 🟢       │                                │ Fri: Testes Integ.   │
│ Lambda Validation   │    ┌─ READY 🟢 ─┐            │ & PR Review          │
│ 1.5h est. (PRONTO)  │    │             ├──────────> │ (Validação)          │
└─────────────────────┘    └─────────────┘            └──────────────────────┘

COMPLETADO: 3.5h       PRONTO: 4.5h       TOTAL RESTANTE: ~13.5h
```

---

## Dependency Graph (Updated Status)

```
                           ┌─────────────────┐
                           │    P0-FIX       │
                           │  ✅ COMPLETO    │
                           │  (31-MAR)       │
                           └────────┬────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
               ┌────▼────┐      ┌───▼───┐      ┌───▼────┐
               │ P1.A1   │      │ P1.A2 │      │ P1.A3  │
               │ Ensemble│      │ Margin│      │ Lambda │
               │ ✅ DONE │      │ 🟢 RDY│      │ 🟢 RDY │
               └────┬────┘      └───┬───┘      └────┬───┘
                    │               │              (parallel)
                    └───────────────┼───────────────┘
                                    │
                             ┌──────▼──────────┐
                             │  P1-B DESBLOQ   │
                             │ 🟢 6 TASKS RDY  │
                             │   P1-A      │
                             │  COMPLETE   │
                             │ (Now test   │
                             │  run.py)    │
                             └──────┬──────┘
                                    │
      ┌─────────────────────────────┼─────────────────────────────┐
      │                             │                             │
      │                             │                    ┌────────▼────────┐
      │                             │                    │  P1.B1: Calib   │
  ┌───▼──────┐  ┌─────────────┐   ┌▼────────┐           │  (independent)  │
  │ P1.B2:   │  │ P1.B3: Rec  │   │ P1.B4:  │           │  4-5h parallel  │
  │ Rolling  │◄─┤ +Momentum   │   │ H2H     │           └─────────────────┘
  │ EMA      │  └─────────────┘   │ Cross   │
  │ 5-6h     │                    │ 8h      │
  └──────────┘                    └─────────┘
       │
  ┌────▼──────────────────────────────┐
  │  P1.B3, B4 dependem de B2 features│
  │  Ordem: B1 (parallel) → B2 → B3→B4│
  └───────────────────────────────────┘
```

### Legenda
- ✅ Completo
- 🟢 Pronto/Desbloqueado
- 🟡 Em progresso
- 🔴 Bloqueado
- ▼ Depende de

### Fluxo de Bloqueio
```
Sem bloqueadores críticos! ✅

P1.A1 libera ensembles para treino
    ↓
P1.B1-B4 podem rodar em paralelo (exceto B3◄─B2)
```

---

## Gantt Chart (Semanas)

```
Tarefa              Week1  Week2  Week3  Week4
─────────────────────────────────────────────
P1.A1 (3.5h)        ███
P1.A2 (4h)             ███
P1.A3 (2.5h)              ██
Testes P1.A              ██
─────────────────────────────────────────────
P1.B1 (7.5h)             ████████
P1.B2 (6.5h)             ████████
P1.B3 (5.5h)                       ██████
P1.B4 (8h)                            ████
Testes Integração                           ██
PR Review+Merge                             ██
─────────────────────────────────────────────
TOTAL:  80-90 hours        3-4 weeks sprint
```

---

## Distribuição de Esforço por Sprint

### Sprint 1 (Semana 1 — P1-A)

| Day | Task | Duration | Deliverable |
|-----|------|----------|------------|
| Mon-Tue | **P1.A1:** Portar 70/30 para core | 3.5h | ✅ Ensemble híbrido funcional |
| Wed | **P1.A2:** Dynamic margin rule | 4h | ✅ Parametrizado via config |
| Thu | **P1.A3:** Lambda validation | 2.5h | ✅ Guard contra NaN/Inf |
| Fri | Tests, PR, Review, Merge | 2.5h | ✅ **P1-A DONE** |
| **Total** | | **14.5h** | — |

**Sucesso:** `python run.py` executa com ensemble 30, 21+9 split, no errors

---

### Sprint 2 (Semanas 2-3 — P1-B)

| Period | Task | Duration | Deliverable |
|--------|------|----------|------------|
| W2 Mon-Tue | **P1.B1:** Calibração (Brier, ECE) | 7.5h | ✅ Métricas pós-treino |
| W2 Wed-Thu | **P1.B2:** Rolling + EMA | 6.5h | ✅ 6 windows + EMA features |
| W2 Fri | Tests + PR Review | 2h | ✅ **P1.B1+B2 DONE** |
| W3 Mon-Tue | **P1.B3:** Record + Momentum | 5.5h | ✅ V-E-D, form, confidence |
| W3 Wed-Thu | **P1.B4:** H2H + Cross | 8h | ✅ H2H 80%, cross VIF<5 |
| W3 Fri | Tests + PR Review | 2h | ✅ **P1.B DONE** |
| **Total** | | **31h** | — |

**Sucesso:** Feature engineering phase completa, Brier<0.25, novo features em top-20

---

### Sprint 3 (Fine-tuning + Merge)

| Activity | Duration | Output |
|----------|----------|--------|
| Code review (PRs P1-A, P1-B1, P1-B2) | 2h | Approved |
| Fix comments + squash | 2h | Clean commits |
| Final validation (pipeline, tests) | 2h | Green light |
| Docs update + README | 1h | Documented |
| **Subtotal** | **7h** | **Ready to merge** |

---

## Recursos e Alocação

### Pessoas (estimado)
- **Lead Dev:** 80% (você) — 64-72h
- **Code Review:** 20% (opcional) — 16-20h
- **QA:** 10% — testes automatizados

### Ferramentas/Ambientes
- Python 3.9+ (✅ em uso)
- Jupyter para análise ad-hoc (calibração, VIF)
- Git branches: `feature/p1a-ensemble`, `feature/p1b-calibration`, etc.
- CI/CD: pytest local + eventual CI

---

## Checkpoints e Validações

### P1-A Checkpoint (End of Week 1)

```
✅ Checks:
  - python run.py completes without error
  - ensemble_size=30 → 21+9 (verified via logs)
  - All 21 tests pass
  - importance works for Ridge/ElasticNet
  - Config has tight_margin_threshold, tight_margin_consensus
  - Lambda validation catches NaN

⚠️ Review:
  - Code style (PEP8)
  - Docstrings complete
  - No hardcodes remaining
```

### P1-B1+B2 Checkpoint (End of Week 2)

```
✅ Checks:
  - Brier score < 0.25 (test set)
  - ECE < 0.10 (test set)
  - Rolling windows: 3, 5, 10 all generated
  - EMA present in feature set
  - No data leakage (features use .shift(1))
  
📊 Metrics:
  - Feature importance top-20 includes new features
  - Correlation with target for new features > 0.05
  - Pipeline runtime < 2min (< 3x slower acceptable)
```

### P1-B3+B4 Checkpoint (End of Week 3)

```
✅ Checks:
  - V-E-D record generated (W=wins, D=draws, L=losses last 5,10)
  - Momentum = (W + 0.5*D) / games
  - H2H available for 80%+ matches
  - Cross-features: home_atk × away_def, etc.
  
📊 Metrics:
  - Record feature correlation > 0.1
  - H2H missingness < 20%
  - VIF for cross-features < 5
  - Feature importance > 0.01 for new features

🎯 Validation:
  - Temporal (last 10%) accuracy ≥ baseline
  - Overfitting test (train vs test Brier) ≤ 0.05 gap
```

---

## Success Criteria Summary

| Dimension | Target | Acceptance |
|-----------|--------|-----------|
| **Functionality** | P1-A + P1-B complete | All tasks done |
| **Quality** | No data leakage | Leakage tests pass |
| **Performance** | Pipeline runtime | < 5min (end-to-end) |
| **Accuracy** | Brier/ECE metrics | Brier < 0.25, ECE < 0.10 |
| **Code** | Tests, docs, style | 100% pass, PEP8, docstrings |
| **Integration** | PR merged to main | GitHub CI ✅, code review ✅ |

---

## Risks & Contingencies

| Risk | Impact | Plan B |
|------|--------|--------|
| **Multicolineariy breaks models** | 🔴 HIGH | Feature selection (P1.C1 moves up), remove high-VIF features |
| **EMA causes instability** | 🟡 MEDIUM | Use multiple spans, ensemble approach, fallback to vanilla rolling |
| **H2H data sparse** | 🟡 MEDIUM | Fallback to zeros, mask detection, conditional features |
| **Calendar drift (season change)** | 🟡 MEDIUM | Season-aware rolling, separate L-1 season lookback |
| **Performance degradation** | 🟡 MEDIUM | Feature profiling, lazy computation, caching (P3 work) |

---

## Communication Plan

### Daily
- 10min standup: blockers, progress

### Weekly (Friday)
- Sprint recap: metrics, tests, PRs
- Sprint planning: next week tasks

### Biweekly (Wednesday)
- Stakeholder sync: business impact, accuracy gains

---

## Reference Docs

📄 **Main Roadmap:** [next_pass.md](next_pass.md)  
📄 **P0-FIX Completion:** [P0_COMPLETION_SUMMARY.md](#)  
📄 **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)  
📖 **Features Guide:** [FEATURE_ENGINEERING_PLAYBOOK.md](FEATURE_ENGINEERING_PLAYBOOK.md)  
📊 **Validation Strategy:** [VALIDATION.md](VALIDATION.md)  

---

## Notes & Observations

### P1-A Prerequisites Met ✅
- P0-FIX complete: no blocking bugs
- Hybrid schedule already coded: just needs integration
- Dynamic margin rule: fully specified in script, needs parametrization
- Lambda validation: straightforward guard clauses

### P1-B Feature Strategy
- **Order:** B1 (indep.) → B2 → B3 ← B4 cross
- **Risk focus:** Data leakage (B2, B3, B4 all temporal)
- **Wins:** Correlation analysis, feature importance tracking
- **Measurement:** Brier/ECE reliable for corner models (Poisson)

### Timeline Realistic?
- ✅ Yes, assuming no major blockers
- ✅ Buffer: 1-2h per sprint for emergencies
- ⚠️ Could compress to 2 weeks with parallel work
- ⚠️ Could extend to 5 weeks with deep analysis

