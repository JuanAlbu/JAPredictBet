# P1 Development Plan — Índice Master

**Criado:** 31-MAR-2026 por GitHub Copilot  
**Status:** 🟡 PLANEJADO — Pronto para iniciar  
**Duração:** 3-4 semanas (80-120 horas)  
**Responsável:** Você (80%) + Code Review (20%)

---

## 📚 Documentação Disponível

### 1. **[P1_DEVELOPMENT_PLAN.md](P1_DEVELOPMENT_PLAN.md)** — Plano Detalhado
   - Resumo executivo
   - P1-A (3 tarefas) e P1-B (4 tarefas) completas
   - Status atual, análise técnica, subtarefas
   - Critérios de sucesso, esforço estimado
   - **Use para:** Entender "o quê" e "por quê"

### 2. **[P1_TIMELINE_DEPENDENCIES.md](P1_TIMELINE_DEPENDENCIES.md)** — Cronograma Visual
   - Timeline de execução (Gantt chart)
   - Dependency graph (fluxo de bloqueadores)
   - Sprint breakdown (semana por semana)
   - Checkpoints e validações
   - Riscos e contingências
   - **Use para:** Planejar "quando" e "em que ordem"

### 3. **[P1_CHECKLIST.md](P1_CHECKLIST.md)** — Checklist de Tarefas
   - Checklist detalhado por subtarefa
   - Arquivo, esforço, acceptance criteria por item
   - PR checklist
   - Commit message template
   - **Use para:** Acompanhamento dia-a-dia

### 4. **[next_pass.md](next_pass.md)** — Roadmap Geral (Referência)
   - P0-FIX (100% ✅ completo)
   - P1-A e P1-B specs
   - P2, P3, R&D roadmap futuro
   - Matriz de maturidade do projeto
   - **Use para:** Contexto do projeto como um todo

---

## 🚀 Como Começar

### Hoje (31-MAR-2026)

1. ✅ **Leia:** `P1_DEVELOPMENT_PLAN.md` (30min)
   - Entenda P1-A (consolidação) e P1-B (features)

2. ✅ **Visualize:** `P1_TIMELINE_DEPENDENCIES.md` (20min)
   - Veja Gantt chart: 4 semanas, 7 tarefas

3. ✅ **Prepare:** Branch de feature
   ```bash
   git checkout -b feature/p1a-ensemble
   ```

### Amanhã (1-APR-2026)

4. **Comece P1.A1** (Portar 70/30)
   - Use `P1_CHECKLIST.md` seção P1.A1
   - Acompanhe cada subtarefa: 1.1, 1.2, 1.3, ...
   - Esforço: 3.5h

---

## 📊 Visão Geral do Escopo

### P1-A: Integridade do Pipeline (16h)

```
P1.A1: Portar 70/30 ensemble (3.5h)
├─ Adicionar algorithms param
├─ Validar build_variation_params
├─ Testes 21+9 split
└─ Integração & validação

P1.A2: Dynamic margin rule (4h)
├─ Config fields: tight_margin_threshold, tight_margin_consensus
├─ Refatorar ConsensusEngine
├─ Testes de ativação
└─ Validação vs script

P1.A3: Lambda validation (2.5h)
├─ Função is_valid_lambda()
├─ Guards em poisson_over/under_prob()
├─ Testes NaN/Inf
└─ Documentação

Total P1.A: 14.5h + 2h testes/review = 16.5h
```

### P1-B: Evolução de Features (31h)

```
P1.B1: Calibração (7.5h)
├─ Brier score
├─ ECE (Expected Calibration Error)
├─ Análise temporal
└─ Documentação

P1.B2: Rolling + EMA (6.5h) ← prerequisito para B3+B4
├─ Window=3, STD features
├─ EMA com time-decay
├─ Validação leakage
└─ Feature importance

P1.B3: Record + Momentum (5.5h)
├─ V-E-D record (wins/draws/losses)
├─ Momentum = (W + 0.5*D) / games
├─ Form features ("hot streak")
└─ Confidence indicator

P1.B4: H2H + Cross (8h)
├─ H2H últimos 3 confrontos
├─ Cross-features: ataque×defesa
├─ VIF validation
└─ Feature importance

Total P1.B: 27.5h + 3.5h testes/review = 31h
```

**TOTAL: ~80 horas = 2-3 weeks 50% allocation, ou 3-4 weeks 30% allocation**

---

## 🎯 Quick Reference: Key Stats

| Métrica | Target | Status |
|---------|--------|--------|
| **Ensemble** | 21 boosters + 9 linear | ✅ Spec, pronto |
| **Dynamic Margin** | Consenso 45% → 50% se \|λ-line\|<0.5 | ✅ Spec, pronto |
| **Brier Score** | < 0.25 | 🎯 Target |
| **ECE** | < 0.10 | 🎯 Target |
| **Rolling Windows** | [3,5,10] + STD + EMA | 🎯 Target |
| **H2H Coverage** | 80%+ matches | 🎯 Target |
| **Feature Importance** | Top-20 inclui novos (score>0.01) | 🎯 Target |
| **Tests** | 21/21 continue passing | ✅ Baseline |
| **Code Style** | PEP8 + Black | ✅ Requirement |
| **Runtime** | < 5min end-to-end | 📊 Monitor |

---

## 🔗 Fluxo de Dependências

```
P0-FIX (✅ DONE)
    ↓
P1.A1 (ensemble)
    ↓
P1.A2 (dynamic margin) — paralelo com A3
    ↓
P1.A3 (lambda validation) — paralelo com A2
    ↓
✅ P1-A DONE (pipeline ready)
    ↓
P1.B1 (calibração) ← paralelo
P1.B2 (rolling) ← prerequisito para B3+B4
    ↓
P1.B3 (record) ← depende de B2
P1.B4 (H2H) ← depende de B3
    ↓
✅ P1 COMPLETE
```

---

## 📋 Estado Atual de Cada Tarefa

| Task | Status | Owner | Docs |
|------|--------|-------|------|
| **P1.A1** | ✅ COMPLETE | You | [Development](P1_DEVELOPMENT_PLAN.md#p1a1), [Checklist](P1_CHECKLIST.md#p1a1) |
| **P1.A2** | 🟢 READY | You | [Development](P1_DEVELOPMENT_PLAN.md#p1a2), [Checklist](P1_CHECKLIST.md#p1a2) |
| **P1.A3** | 🟢 READY | You | [Development](P1_DEVELOPMENT_PLAN.md#p1a3), [Checklist](P1_CHECKLIST.md#p1a3) |
| **P1.B1** | 🟢 READY (P1.A1 ✅) | You | [Development](P1_DEVELOPMENT_PLAN.md#p1b1), [Checklist](P1_CHECKLIST.md#p1b1) |
| **P1.B2** | 🟢 READY (P1.A1 ✅) | You | [Development](P1_DEVELOPMENT_PLAN.md#p1b2), [Checklist](P1_CHECKLIST.md#p1b2) |
| **P1.B3** | 🟡 BLOCKED (awaits P1.B2) | You | [Development](P1_DEVELOPMENT_PLAN.md#p1b3), [Checklist](P1_CHECKLIST.md#p1b3) |
| **P1.B4** | 🟡 BLOCKED (awaits P1.B3) | You | [Development](P1_DEVELOPMENT_PLAN.md#p1b4), [Checklist](P1_CHECKLIST.md#p1b4) |

---

## ✅ Acceptance Criteria Summary

### P1-A Success
```
✅ python run.py completes without error
✅ Ensemble: 21 boosters + 9 linear (verified)
✅ Dynamic margin: config-driven (não hardcode)
✅ Lambda validation: NaN/Inf prevented
✅ 21/21 tests pass
✅ Code review approved
```

### P1-B Success
```
✅ Brier score < 0.25, ECE < 0.10
✅ Rolling features: 6 windows [3,5,10] × [mean,std] + EMA
✅ Record: V-E-D, momentum, forma
✅ H2H: 80%+ coverage
✅ Cross-features: VIF < 5, importance > 0.01
✅ No data leakage (temporal validation)
✅ Feature importance: top-20 include new (score>0.01)
✅ 60+ tests pass
✅ Code review approved
```

### Integration Success
```
✅ Core pipeline (run.py) ≡ Script (consensus_accuracy_report.py)
✅ Accuracy gain: +2-3% (temporal validation)
✅ All docs updated
✅ PR merged to main
```

---

## 🚨 Key Risks & Mitigations

| Risk | Plan B |
|------|--------|
| **Multicolinearrity (P1.B)** | VIF filter, remove high-correlation pairs |
| **Data leakage in features** | Audit .shift(1), temporal split validation |
| **Performance degradation** | Profile hot loops, feature selection (P1.C1) |
| **EMA instability** | Multiple spans, ensemble approach |
| **H2H sparse data** | Zero-fill, conditional masking |

---

## 📞 Questions & Support

### Common Issues

**Q: Como iniciar P1.A1?**  
A: Veja [P1_CHECKLIST.md#p1a1](P1_CHECKLIST.md#p1a1) — começa por subtarefa 1.1

**Q: Por que P1.B depende de P1.A?**  
A: P1.A1 treina ensemble correto; P1.B valida que funciona bem. Ver [P1_TIMELINE_DEPENDENCIES.md](#fluxo-de-dependências)

**Q: Como rodar testes durante desenvolvimento?**  
A: `pytest tests/ -v --tb=short` ou teste específico `pytest tests/models/test_train.py::test_ensemble_hybrid -v`

**Q: Documentação exausted, preciso mais?**  
A: Releia [next_pass.md](next_pass.md) para context completo, ou code comments em train.py

---

## 📅 Sprint Start Checklist

Before starting implementation:

- [ ] Read all 3+ docs above (90min total)
- [ ] Review `scripts/consensus_accuracy_report.py` para blueprint 70/30 (30min)
- [ ] Setup branches: `git checkout -b feature/p1a-ensemble`
- [ ] Ensure tests run: `pytest tests/ -q` (should be 21/21 ✅)
- [ ] Verify `python run.py --config config_test_50matches.yml` runs (baseline)
- [ ] Pull latest main: `git pull origin main`
- [ ] Schedule 30min daily standup with progress check

---

## 📈 Progress Tracking Template

Use this to track as you work:

```markdown
## P1 Development Progress

### Week 1 (P1-A)
- [ ] P1.A1: [X]% (1.1 ✅, 1.2 ✅, 1.3 🔄, 1.4, 1.5, 1.6)
- [ ] P1.A2: Starting Mon
- [ ] P1.A3: After A2
- [ ] P1-A Merge: Friday EOD
- **Blockers:** None currently

### Week 2-3 (P1-B)
- [ ] P1.B1: Starting
- [ ] P1.B2: 
- [ ] P1.B3: (depends on B2)
- [ ] P1.B4: (depends on B3)
- **Blockers:** TBD

### Overall
- **Actual vs Plan:** On track / Behind / Ahead
- **Key learnings:** (fill as you go)
- **PRs submitted:** X/7
```

---

## 🎓 Learning Resources

**Internal:**
- `src/japredictbet/models/train.py` — ensemble logic
- `scripts/consensus_accuracy_report.py` — script blueprint
- `docs/ARCHITECTURE.md` — design reference
- `tests/` — test examples

**External:**
- [Scikit-learn Calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [Poisson Regression](https://en.wikipedia.org/wiki/Poisson_regression)
- [VIF (Variance Inflation Factor)](https://en.wikipedia.org/wiki/Variance_inflation_factor)

---

## 🎉 Celebratory Milestones

- ✅ P1.A1 PR merged: "*Hybrid ensemble in core!*"
- ✅ P1-A complete: "*Pipeline consolidation done!*"
- ✅ P1.B2 PR merged: "*EMA features live!*"
- ✅ P1 complete: "*Feature engineering phase wrapped!*"

---

## Next: After P1 Complete

Once P1 is done:
1. Merge all PRs to main
2. Tag release: `v1.1-p1-complete`
3. Plan P1.C (hyperparameter optimization) or P2 (tests)
4. See [next_pass.md](next_pass.md) for full roadmap

---

**Created by:** GitHub Copilot  
**Last Updated:** 31-MAR-2026  
**Questions?** Review docs or re-read this master index.

