# SDD/TDD Workflow — Caissa

**Status:** Normative  
**Scope:** All non-trivial Caissa features  
**Relationship to standards:** This document is the operational *how*. The
`docs/standards/spec-driven-development.md` is the normative *what* (artefact structure, spec
format, the §7 completeness checklist). When the two conflict, the standard wins; bring this
document into alignment.

---

## The Pipeline

```
Problem Statement
      ↓
initial_idea.md   (FROZEN at scope-lock — business requirements, open questions)
      ↓
feature_spec.md   (R/I/P/Q/N — GATE A before any code)
      ↓
feature_steps.md  (phase + test plan — all test names written here first)
      ↓
implementation_plan.md  (session breakdown — generated from prompts)
      ↓
Sessions (red → implement → Gate C → green → commit)
      ↓
PR per phase — GATES F, G (if errors), H (docs)
      ↓
Final phase → GATE E (production readiness)
```

**Cardinal rule: implementation MUST NOT begin before Gate A passes.**
When spec and code conflict, the spec governs. Spec wrong → stop, update spec, resume.
Undocumented divergence is a defect, not a shortcut.

---

## Artefact Roles

| Artefact | Frozen? | Who reads it |
|---|---|---|
| `initial_idea.md` | **FROZEN** at scope-lock | Auditors, PRs back-referencing scope decisions |
| `feature_spec.md` | LIVING | Everyone; the single source of truth for the feature |
| `feature_steps.md` | LIVING | Implementors; updated as phases complete |
| `implementation_plan.md` | LIVING | The session-level guide; archived on completion |
| `docs/rpa/<pages>` | LIVING | Product documentation; lives as long as the code |

Dependency chain: `CLAUDE.md → feature_spec → feature_steps → implementation_plan → prompts`.
Each document depends on the ones above it being correct.

**On completion:** move `docs/features/<name>/` to `docs/features/_archive/<name>/` (git mv,
so history follows). Set `**Status:** Completed YYYY-MM-DD` in each file's front matter.
The archive is never deleted — it is the audit trail.

---

## Per-Session Loop

For every session in `implementation_plan.md`:

1. **Run `make test`** — confirm the session's target tests are **red** (failing or `xfail`).
   If they are already green, the session is already done; skip to step 7.
2. **Write the production code** described in the session scope.
3. **Human diff review (Gate C)** — read every line of every changed file before committing.
   Skipping is abdication, not a shortcut.
4. **Run `make test`** — all tests **green**; no regressions.
5. **Run `make lint`** — zero issues.
6. **Update living docs** if the implementation revealed any corrections (spec wrong → update
   spec; tracker wrong → update tracker; new decision → add to `decisions.md`).
7. **Commit** with the session's suggested commit message (conventional format, `rpa` scope).
8. More sessions in this phase? GOTO 1. Else open PR.

**One branch = one phase = one PR.** Never stack phases on a single branch — the PR diff
becomes unreviewable. Never branch a phase off the previous phase's branch — the PR diff
inherits all prior work.

**Abandoned work → `wip/<topic>` branch**, preserved but never merged.

---

## Test Management

- All planned test names are written into `feature_steps.md` in Phase 0 *as documentation*.
  Test files are created by the phase that owns them.
- Deferred tests use `@pytest.mark.xfail(strict=True, reason="Requires Phase N …")`.
  `strict=True` is non-negotiable — it makes a secretly-passing test a hard failure.
  Never use `skip` for deferred work.
- Bug fixes add `@pytest.mark.regression` in the same commit as the fix.
- Phase 9 asserts that every test name in `feature_steps.md` exists in the suite.

---

## Gate Table

Gates are tickable checklists. Every item must be checked before the gate passes.

### Gate A — Spec Completeness
*Checked before any code.*

- [ ] Functional requirements stated in MUST/SHOULD/MAY language (RFC 2119)
- [ ] Interface defined (function signatures, config keys, JSON schemas)
- [ ] Preconditions enumerated
- [ ] Postconditions and invariants enumerated
- [ ] Classical invariant impact stated
- [ ] Non-functional constraints stated (startup cost, UI responsiveness, memory)
- [ ] `initial_idea.md` frozen (open questions noted, not assumed resolved)

### Gate B — Spec Conformance (Fagan-style, per session)
*Checked after each implementation session.*

- [ ] Each new interface has a precondition, postcondition, and error semantics stated
- [ ] Any implementation surprise captured in the living spec
- [ ] No undocumented divergence between code and spec

### Gate C — Human Diff Review
*Checked before every commit.*

- [ ] Every changed line read by a human
- [ ] No accidental reformat of upstream Lucas Chess R6 code
- [ ] No banner-style comment dividers (use `#region`/`#endregion`)
- [ ] No comments that only restate what the code does
- [ ] No disallowed imports for the module's purity tier
- [ ] RST docstrings present for all new and modified public and non-public members
- [ ] `make lint` clean

### Gate D — Session Definition of Done
*Checked at the end of each session.*

- [ ] All session target tests green
- [ ] No other tests broken
- [ ] Living docs updated with any corrections
- [ ] Commit pushed; PR open (or on the queue)

### Gate E — Production Readiness
*Checked after the final phase, before the final PR.*

- [ ] All phases complete (all ✅ in `feature_steps.md`)
- [ ] `make test` all green
- [ ] `make cov` ≥ 90 % (scoped, omit list per plan)
- [ ] `make lint` zero issues
- [ ] `make docs` zero warnings
- [ ] Findings from the review are labelled and tracked to resolution
- [ ] `quickstart.md` executed verbatim as its own acceptance test
- [ ] No regression in existing test suites (`test_remote_control.py`, `test_classical_invariant.py`)
- [ ] Classical Invariant confirmed by `workflows/classical_invariant.py` run

### Gate F — PR Sign-Off
*Checked per PR.*

- [ ] PR title ≤ 70 chars; body summarises what and why (not just what)
- [ ] Test evidence included (make test output or link to run)
- [ ] Compatibility notes (does this break any existing behaviour?)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` in the same commit (user-visible changes only)
- [ ] Branch targets `JohnnyFoulds/caissa`, not `lukasmonk/lucaschessR6`

### Gate G — Error-Handling Checklist
*Checked per PR that introduces or modifies error handling.*

- [ ] Domain exceptions inherit from `CaissaError` via `RpaError` (shallow: base + one level)
- [ ] Every raised exception includes what failed, which value, and why if not obvious
- [ ] `raise … from exc` when wrapping lower-level exceptions
- [ ] Every `logger.error()` at a catch site includes `exc_info=True`
- [ ] No `except Exception: pass` in new code
- [ ] `except BaseException` not used (swallows `KeyboardInterrupt` and `SystemExit`)
- [ ] Non-critical catches include a comment explaining why the swallow is acceptable

### Gate H — Docs Completeness
*Checked per phase, before the phase's PR is opened.*

- [ ] Every `docs/rpa/` page listed for this phase in the phase table exists and is current
- [ ] Any earlier `docs/rpa/` page invalidated by this phase's implementation is amended in
  this PR (Gate H allows "amended in a later phase" only when explicitly noted)
- [ ] Every new public callable in `bin/Code/Rpa/` has an RST/Sphinx docstring
- [ ] `make docs` builds with zero warnings
- [ ] New terms are in `docs/rpa/glossary.md`
- [ ] New decisions are appended to `docs/rpa/decisions.md`

---

## Traceability

- Requirement IDs: `BR-n`, `FR-n`, `NFR-n` from `feature_spec.md`
- Every phase and session in the tracker has a `**Spec refs:**` line
- Every test is traceable to a spec element (FR or §)
- Findings are labelled (`D1`, `A-3`) and tracked to resolution in `decisions.md`
- Doc wrong → fix doc; code wrong → fix code; both wrong → agree behaviour, update doc first

---

## Handling Spec Errors

If the implementation reveals that the spec is wrong:

1. **Stop.** Do not commit code that conforms to a wrong spec.
2. **Update the spec first.** Get the spec correct and reviewed before continuing.
3. **Then implement.** The corrected spec is the new target; backtrack only to the last
   session whose tests still pass against it.

If the spec and code both seem wrong, the spec is still updated first — it is easier to
reason about correctness from a written contract than from reading implementation.

---

## Deferred Decisions

Open decisions noted in `initial_idea.md` must be resolved or explicitly carried as open
questions in `feature_spec.md` with a `D-n` label. They are appended to `decisions.md`
when resolved, with the date and the rationale that closed them.

---

## References

- `docs/standards/spec-driven-development.md` — normative *what* (spec format, §7 completeness checklist)
- `docs/templates/` — template files for all four artefacts
- `docs/claude_code/prompts.md` — Caissa/SDD-specific session prompts
- `docs/claude_code/prompt-library.md` — general-purpose prompt templates
- `docs/claude_code/working-patterns.md` — cross-project patterns and plan feedback moves
- `docs/rpa/decisions.md` — ADR log for the RPA layer
