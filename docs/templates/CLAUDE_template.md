# CLAUDE.md — TODO: Feature Name

<!-- PURPOSE: Feature-level context supplement for Claude Code.
     The repo-wide CLAUDE.md at the root covers all Caissa conventions.
     This file covers only what is specific to THIS feature.
     Delete sections that just repeat what the repo CLAUDE.md already says. -->

## Feature Purpose

TODO: One paragraph — what this feature does and why it exists.

---

## Feature Directory

```text
bin/Code/TODO/
├─ __init__.py      0 bytes (as all 62 existing packages)
├─ Module1.py
└─ Module2.py

docs/features/TODO/
├─ initial_idea.md       FROZEN
├─ feature_spec.md       LIVING
├─ feature_steps.md      LIVING
└─ implementation_plan.md LIVING

docs/TODO/               product documentation
tests/unit/TODO/         no-Qt unit tests
```

---

## Key Design Decisions

<!-- List only decisions that are non-obvious or that contradict intuition.
     Each bullet: what was decided + why. -->

- TODO: Decision 1 and rationale.
- TODO: Decision 2 and rationale.

---

## Living Documents

| Document | Path | Status |
|---|---|---|
| Specification (SDD) | `docs/features/TODO/feature_spec.md` | LIVING |
| Phase tracker | `docs/features/TODO/feature_steps.md` | LIVING |
| Session plan | `docs/features/TODO/implementation_plan.md` | LIVING |
| Prompt library | `docs/claude_code/prompts.md` | LIVING |

---

## Classical Invariant

TODO: One sentence confirming how this feature preserves the classical invariant,
or an explicit statement that it does not affect it.

---

## References

- `docs/process/sdd-workflow.md` — the full SDD routine and 8 gates
- `docs/standards/` — coding, docstring, error-handling, logging standards
