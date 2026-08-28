# TODO: Feature Name — Implementation Plan

<!-- PURPOSE: Breaks every phase of the implementation tracker into concrete,
     independently-reviewable coding sessions. Each session is small enough to
     complete and review in one sitting.

     Caissa adaptation: the TDD session loop is read-green-refactor with mandatory
     human diff review (Gate C) before every commit. -->

**Spec reference:** [feature_spec.md](feature_spec.md)
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## Current State (as of TODO: YYYY-MM-DD)

| What exists | Status |
|---|---|
| `TODO: tests/unit/...` | TODO: e.g. Phase 0 complete; Phase 1 tests red |
| `TODO: bin/Code/Rpa/...` | TODO: e.g. Not yet started |

Work continues at **Session TODO: N-X** (`TODO: description`): write tests first (TDD red),
then implement, then human diff review, then green.

---

## How to use this plan

Each session maps to a small, coherent set of changes. The workflow for every session:

1. Run `make test` — confirm the session's target tests are **red** (failing or `xfail`).
2. Write the production code.
3. **Human diff review** — Gate C; skipping is abdication.
4. Run `make test` — confirm all tests are **green**, no regressions.
5. Run `make lint` — confirm zero lint issues.
6. Update living docs if the implementation revealed any corrections.
7. Commit with the suggested commit message.
8. More work in this phase? GOTO 1. Else open PR.

---

## Files to Create / Modify

| File | Action |
| --- | --- |
| `TODO: bin/Code/TODO.py` | **Create** — TODO |
| `TODO: tests/unit/test_todo.py` | **Create** — TODO |

---

## Phase 1 — TODO: Phase Name

### Session 1-A — TODO: Session Name

**Files to create/edit:**

- `bin/Code/TODO.py` (create)
- `tests/unit/TODO/test_todo.py` (create — write tests first, then implement)

**Scope:**

TODO: One sentence describing what this session delivers.

**What to implement:**

1. Module-level docstring.
2. `TODO: ClassName(param1: str, param2: int)` — brief purpose.
   - `param1` — describe.
   - `param2` — describe.

**Tests this session makes green (write in `tests/unit/TODO/test_todo.py` first):**

- `test_TODO_basic`
- `test_TODO_error_case`

**Spec refs:** FR-1, §5.1

**Definition of done:**

- [ ] TODO: Primary deliverable exists
- [ ] RST docstrings for all new public and non-public members
- [ ] All target tests green; no other tests broken
- [ ] `make lint` passes
- [ ] Tracker updated: Phase 1 marked ✅

**Suggested commit:** `feat(rpa): TODO: commit subject`

---

## Final Verification

```bash
make lint        # zero issues
make test        # all green
make cov         # ≥ 90 % Code.Rpa coverage
make docs        # zero warnings
```

Update `feature_steps.md`: mark all phases ✅.

---

## Session Summary Table

| Session | Phase | What it delivers | New tests made green |
|---------|-------|-----------------|----------------------|
| 1-A | Phase 1 — TODO | TODO | 0 |

**Total: TODO: N sessions, ~TODO: N tests.**
