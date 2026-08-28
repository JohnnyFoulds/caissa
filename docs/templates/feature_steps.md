# TODO: Feature Name — Implementation Steps

<!-- PURPOSE: Phase-by-phase TDD implementation tracker.
     Mark phases complete (✅) as they finish. Update test lists if scope changes.
     Keep in sync with feature_spec.md.

     Caissa adaptation: no ABC stubs. Phase 1 delivers working, tested code for the
     first logical group. There is no "all methods as NotImplementedError stubs" phase. -->

Living implementation tracker for the TODO: Feature Name feature.
Updated after each phase is completed.

**Spec reference:** [feature_spec.md](feature_spec.md)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Complete |

---

## Phase 0 — Documentation & Process ⬜

**Branch:** `docs/<topic>`

**Files:**

- `docs/features/<name>/initial_idea.md` (create — FROZEN)
- `docs/features/<name>/feature_spec.md` (create — Gate A before any code)
- `docs/features/<name>/feature_steps.md` (create — this file)
- `docs/features/<name>/implementation_plan.md` (create)
- `docs/rpa/<relevant-pages>.md` (create — design-time subset)

**What we deliver:**

- Problem statement and frozen business requirements
- Full R/I/P/Q/N spec (Gate A checklist complete)
- This steps document with all test names for all phases
- Design-time product docs (those whose content is design output, not implementation output)

**TDD test cases (tests/unit/rpa/test_placeholder.py):**

- All planned test names are recorded in this document with `xfail(strict=True)` markers
  until the owning phase lands.

**Spec refs:** BR-1, §1, §8 (Classical Invariant)

---

## Phase 1 — TODO: Phase Name ⬜

**Branch:** `TODO: feat/<topic>`

**Files:**

- `bin/Code/TODO/<Module>.py` (create)
- `tests/unit/TODO/test_<module>.py` (create)
- `docs/TODO/<page>.md` (create — Gate H)

**What we implement:**

- TODO: Class/function list with exact signatures, parameter names, defaults, return types.

**TDD test cases (tests/unit/TODO/test_<module>.py):**

- `test_TODO_basic_behaviour`
- `test_TODO_error_case`

**Spec refs:** FR-1, NFR-2, §5.1

---

<!-- Add more Phase blocks above the Verification section. -->

## Verification

After each phase completes, mark it ✅ in the phase heading of this document.

After all phases are complete:

```bash
make lint        # zero issues
make test        # all green
make cov         # ≥ 90 % Code.Rpa coverage
make docs        # zero warnings
```
