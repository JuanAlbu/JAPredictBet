# P1 Development Plan — Quick Reference (1-Page)

**Status:** 🟡 READY TO START | **Duration:** 3-4 weeks | **Effort:** 80-120h

---

## The Plan in 30 Seconds

| Phase | Tasks | Duration | Goal |
|-------|-------|----------|------|
| **P1-A** | Ensemble, Margin, Lambda | 1 week | Core pipeline = Script |
| **P1-B** | Calibration, Rolling, Record, H2H | 2-3 weeks | Accuracy +2-3% |
| **Final** | Tests, Docs, Merge | 1 week | Production ready |

---

## P1-A: Consolidate (1 Week)

### P1.A1: Ensemble 70/30 (3.5h)
- **Do:** Make core use 21 boosters + 9 linear (like script does)
- **Files:** `src/japredictbet/models/train.py`
- **Before:** `python run.py` fails or uses wrong ensemble
- **After:** ✅ 30-model ensemble [21+9] trains correctly

### P1.A2: Dynamic Margin (4h)
- **Do:** Parametrize `tight_margin` rule (Consensus ↑ when λ ≈ line)
- **Files:** `config.py`, `config.yml`, `betting/engine.py`
- **Before:** Hardcoded 0.5 threshold, not configurable
- **After:** ✅ `config.yml` controls threshold & consensus

### P1.A3: Lambda Validation (2.5h)
- **Do:** Prevent NaN/Inf in Poisson calculations
- **Files:** `betting/engine.py`
- **Before:** Silent crashes on invalid lambdas
- **After:** ✅ ValueError if lambda invalid

**P1-A Success Criteria:**
- ✅ `python run.py` runs without error
- ✅ Ensemble confirmed 21+9 split
- ✅ 21/21 tests pass
- ✅ Code approved

---

## P1-B: Features (2-3 Weeks)

### P1.B1: Calibration (7.5h)
- **Do:** Compute Brier & ECE scores (validate probability quality)
- **Files:** NEW: `models/calibration.py`
- **Target:** Brier < 0.25, ECE < 0.10
- **Impact:** Know if probabilities are trustworthy

### P1.B2: Rolling + EMA (6.5h) ← prerequisite for B3+B4
- **Do:** Add window=3, STD, EMA features
- **Files:** `features/rolling.py`, `pipeline/mvp_pipeline.py`
- **Total Features:** 6 rolling + EMA = ~15-20 new features
- **Validate:** No data leakage (use .shift(1))

### P1.B3: Record + Momentum (5.5h)
- **Do:** Add V-E-D record, momentum, form indicators
- **Files:** `features/rolling.py`
- **Features:** Wins/Draws/Losses, momentum = (W+0.5*D)/games
- **Result:** Contextual features for team performance

### P1.B4: H2H + Cross (8h)
- **Do:** Head-to-head history, cross-features (atk×def)
- **Files:** NEW: `features/h2h.py`, `features/cross.py`
- **Target:** H2H 80%+ coverage, cross VIF < 5
- **Result:** Advanced derived features

**P1.B Success Criteria:**
- ✅ Brier < 0.25, ECE < 0.10
- ✅ 15-20 new features, no leakage
- ✅ Feature importance > 0.01 for new features
- ✅ 60+ tests pass

---

## Execution Timeline (Gantt)

```
Week 1:  A1 (3.5h) → A2 (4h) → A3 (2.5h) [+ tests]  → MERGE P1-A ✅
Week 2:  B1 (7.5h) + B2 (6.5h) [parallel] → tests → MERGE P1.B1+B2 ✅
Week 3:  B3 (5.5h) → B4 (8h) → tests → MERGE P1.B3+B4 ✅
Week 4:  Final review, docs, release
```

---

## Pre-Start Checklist

- [ ] Read `P1_DEVELOPMENT_PLAN.md` (30min context)
- [ ] Scan `P1_CHECKLIST.md` (task list for today)
- [ ] Create branch: `git checkout -b feature/p1a-ensemble`
- [ ] Verify tests: `pytest tests/ -q` → should be 21/21 ✅
- [ ] Run baseline: `python run.py --config config_test_50matches.yml`

---

## Key Success Metrics

| Metric | Target | How to Verify |
|--------|--------|--------------|
| Accuracy | Brier < 0.25, ECE < 0.10 | After P1.B1 |
| Ensemble | [21+9] mix | `log` output confirms |
| Features | +15-20 new | `df.columns` count |
| Leakage | None | Temporal split test |
| Coverage | 60+ tests pass | `pytest` green |
| Config | Extensible | Edit `.yml`, no code change |
| Runtime | < 5min | Time `python run.py` |

---

## Doc Map (Use As Needed)

| Doc | Purpose | When to Read |
|-----|---------|------|
| **P1_MASTER_INDEX.md** | Overview + links | Start here |
| **P1_DEVELOPMENT_PLAN.md** | Detailed specs | Deep dive on any task |
| **P1_TIMELINE_DEPENDENCIES.md** | When & order | Planning sprints |
| **P1_CHECKLIST.md** | Daily tasks | Day-to-day work |
| **next_pass.md** | Context | Project roadmap |

---

## Quick Commands

```bash
# Start task
git checkout -b feature/p1a-<task>
# e.g., git checkout -b feature/p1a-ensemble

# Run tests
pytest tests/ -v --tb=short

# Style check
black --check src/

# Build & validate
python run.py --config config_test_50matches.yml

# Final PR
git push origin feature/p1a-<task>
# Create PR on GitHub, request review
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Multicolinearity | Check VIF < 5, drop if needed |
| Data leakage | Audit `.shift(1)`, split validation |
| Performance | Profile `cProfile`, optimize hot loops |
| EMA instability | Test multiple spans (3, 5, 10) |

---

## Final Checklist: Ready to Code?

✅ Understand what P1 does (consolidate pipeline + improve features)  
✅ Know the order: P1-A first, then P1.B1+B2, then B3, then B4  
✅ Have all 4 docs, know where to look  
✅ Branch created  
✅ Tests running (baseline 21/21)  
✅ Ready to start P1.A1  

**→ Open `P1_CHECKLIST.md`, go to P1.A1, start subtask 1.1 → Proceed!**

---

*Questions? Read the detailed docs or grep code for references.*

