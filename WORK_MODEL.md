# Work Model for AI Agents

**Version:** 1.0 (31-MAR-2026)  
**Purpose:** Define how agents should work on this codebase  
**Scope:** Code changes, testing, documentation

---

## Core Principles

### 1. Single Source of Truth
- **docs/next_pass.md** is the ONLY planning document
- All task specs, timelines, dependencies go there
- NO side files (P1_*.md, P2_*.md, etc.)

### 2. Git Management (User-Controlled)
- ❌ Agent does NOT create branches
- ❌ Agent does NOT commit
- ❌ Agent does NOT push
- ✅ User manages all git operations

### 3. Local Changes Only
- Agent modifies files locally
- User reviews all changes
- User decides on commits

### 4. No Auxiliary Planning Files
- ❌ Do NOT create README files for specific tasks
- ❌ Do NOT create checklist files
- ❌ Do NOT create timeline documents
- ✅ Put everything in next_pass.md

---

## Task Workflow

### When Given a Task

```
1. Read next_pass.md to understand context
2. Check dependencies (what blocks this?)
3. Make code changes locally
4. Run tests locally
5. Report status back to user
6. Wait for user instructions (commit, continue, etc.)
```

### Example: "Implement P1.A2 (Dynamic Margin Rule)"

**DO:**
```
1. Open next_pass.md → find P1.A2 details
2. Edit: config.py, config.yml, betting/engine.py
3. Run: pytest tests/
4. Answer: "Changes ready for review at:"
   - config.py (lines X-Y)
   - config.yml (lines X-Y)
   - betting/engine.py (lines X-Y)
5. Wait: User says "looks good, commit it"
```

**DON'T:**
```
✗ Create P1.A2_IMPLEMENTATION.md
✗ Create git branch feature/p1a2-margin
✗ Auto-commit with message
✗ Generate separate checklist or spec
```

---

## Documentation Rules

### Code Changes Must Go In

**Option A: Existing sections in next_pass.md**
```
### P1.A2 — Centralizar dynamic margin rule
- [ ] Task 1: Update config.py
  - Files: src/japredictbet/config.py L50-80
  - Status: DONE ✅
  - Changes: Added tight_margin_threshold field
```

**Option B: Update existing task status**
```
- [x] **2.1** Add tight_margin_threshold to ValueConfig ✅
  - Changed from: [ ] to [x]
  - Last updated: 31-MAR-2026
  - Implementation: Added field with default 0.5
```

### What NOT to Do
- ❌ Create separate implementation doc
- ❌ Generate completion report
- ❌ Add new markdown sections for "task planning"

---

## Testing & Validation

### Before Reporting "Done"

```
✅ All unit tests pass: pytest tests/ -q
✅ Integration test passes: python run.py --config config_test_50matches.yml
✅ Code follows: PEP8 (black --check src/)
✅ DocStrings present where needed
✅ No new warnings/errors in output
```

**Nota:** `config_test_50matches.yml` deve incluir todos os P1 feature flags (`rolling_use_std`, `rolling_use_ema`, `drop_redundant`, `h2h_window`, `tight_margin_threshold`, `tight_margin_consensus`) para reproduzir fielmente o pipeline de produção.

### Report Format

```
**P1.A2 Implementation Complete:**

Changes:
- config.py: Added ValueConfig.tight_margin_threshold (L52)
- config.py: Added ValueConfig.tight_margin_consensus (L53)
- config.yml: Added value.tight_margin_threshold: 0.5
- config.yml: Added value.tight_margin_consensus: 0.50
- betting/engine.py: Updated ConsensusEngine.__init__ to use config

Tests: ✅ 34/34 passing
Type check: ✅ No errors
Static check: ✅ PEP8 compliant

Ready for: User review → commit
```

---

## Bad Practices to Avoid

| ❌ Don't | ✅ Do |
|---------|------|
| Create new markdown files for planning | Update sections in next_pass.md |
| Auto-commit after changes | Wait for user to review & commit |
| Make git branch automatically | Let user manage branches |
| Generate "implementation plan" doc | Edit code directly based on next_pass |
| Create task-specific checklists | Use next_pass checklist items |
| Multiple versions of task specs | Single source: next_pass.md only |

---

## Communication Template

### When Starting Work
```
Starting P1.A2 (Dynamic Margin Rule)
- Estimated time: 3h
- Files to modify: 3 (config.py, config.yml, engine.py)
- Tests affected: betting/test_engine.py
- Proceeding...
```

### On Completion
```
✅ P1.A2 COMPLETE

Modified files (ready for review):
- src/japredictbet/config.py (2 changes)
- config.yml (2 parameters added)
- src/japredictbet/betting/engine.py (4 changes)

Status: All tests passing (34/34)

Next: Awaiting user approval to commit
```

### On Blockers
```
⚠️ BLOCKED: P1.A2 requires changes to ValueConfig

Issue: ValueConfig dataclass is frozen (frozen=True)
Solution needed: Revert frozen or modify initialization order

User decision needed: How to proceed?
```

---

## File Structure Expectations

### Current Valid Structure
```
codebase/
├── docs/
│   ├── next_pass.md ✅ (primary planning doc)
│   ├── ARCHITECTURE.md
│   ├── PROJECT_CONTEXT.md
│   └── ... (other docs)
├── src/
├── tests/
└── WORK_MODEL.md (this file)
```

### Invalid Structure (DO NOT CREATE)
```
❌ P1_DEVELOPMENT_PLAN.md
❌ P1_CHECKLIST.md
❌ P1_TIMELINE_DEPENDENCIES.md
❌ AGENT_INSTRUCTIONS.md (duplicate of WORK_MODEL.md)
❌ TASK_001_PLAN.md
```

---

## Escalation Points

### When to Ask User for Direction

1. **Task ambiguity**
   - "P1.A2 references 'dynamic margin' but script has 3 different implementations"
   - Ask: "Which behavior should I implement?"

2. **Architectural decisions**
   - "Config parameter vs hardcoded vs environment variable?"
   - Ask: "preference for tight_margin_threshold storage?"

3. **Blocked by dependencies**
   - "P1.A3 (Lambda validation) needs ValueConfig change from P1.A2"
   - Report: "Blocked waiting for P1.A2 review"

4. **Test failures**
   - "New test_dynamic_margin fails with 'tight_margin not in config'"
   - Ask: "Should I update test fixture or config?"

---

## Version History

| Date | Change | Status |
|------|--------|--------|
| 31-MAR-2026 | Created WORK_MODEL.md | Active |

---

**Last Updated:** 31-MAR-2026  
**Next Review:** After P1.A2 completion
