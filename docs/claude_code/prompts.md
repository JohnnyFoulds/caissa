# Claude Code Prompts — Caissa RPA Layer

<!-- Filled-in version of docs/templates/claude_code_prompts.md for the RPA layer feature. -->

## Configuration

| Placeholder | Actual path |
| --- | --- |
| `<feature-spec-doc>` | `docs/features/rpa-layer/feature_spec.md` |
| `<feature-steps-doc>` | `docs/features/rpa-layer/feature_steps.md` |
| `<piece-plan-doc>` | `docs/features/rpa-layer/implementation_plan.md` |
| `<coding-standards-doc>` | `docs/standards/coding-standards.md` |
| `<docstring-standards-doc>` | `docs/standards/docstring-standards.md` |
| `<templates-dir>` | `docs/templates` |

**Per-use placeholder** (replace each time you paste the Verify prompt):

| Placeholder | Replace with | Example |
| --- | --- | --- |
| `__SESSION__` | The session ID you are verifying | `2-A`, `5-B` |

---

## Caissa-Specific Reminders

When generating or reviewing any RPA layer code:

- No ABCs or `typing.Protocol` — plain base classes raising `NotImplementedError`.
- Only three modules may `import PySide6`: `Driver.py`, `Vision/Capture.py`, `Service.py`.
- `Types.py` must have zero third-party imports.
- `time.sleep` raises in tests — all waiting is deadline polling via `driver.now()`.
- `ElementRef` carries a selector, never a Qt pointer.
- Use `Code.path_resource(...)` for all resource paths — never relative paths.
- New code must not reformat existing Lucas Chess R6 files.
- `#region`/`#endregion` for grouping — no banner comment dividers.
- Commits go to `JohnnyFoulds/caissa`, never `lukasmonk/lucaschessR6`.

---

## 1. Code Standards

```text
Please confirm that the coding standards defined in `docs/standards/coding-standards.md`
and `docs/standards/docstring-standards.md` are followed. Make sure to include RST/Sphinx
docstrings for all public and non-public functions, classes, and modules. No ABCs or
typing.Protocol — plain base classes raising NotImplementedError. No PySide6 imports
outside Driver.py, Vision/Capture.py, and Service.py. No time.sleep(). All new code
scoped to bin/Code/Rpa/ and tests/unit/rpa/.
```

---

## 2. Steps Document

```text
Please read the feature specification at `docs/features/rpa-layer/feature_spec.md`.
Based on the spec, create a phase-by-phase TDD implementation tracker following the
structure defined in `docs/templates/feature_steps.md`.

For each phase:
- List the files to create or edit (use "create" for the first appearance; descriptive
  "edit — …" annotation for all later touches)
- List every class, method, property, and private helper to implement, with exact
  constructor signatures, parameter names, default values, and return types
- For every method include: exception type and triggering condition for each documented
  error path; for dict-returning methods, the exact top-level key names
- List every TDD test case name for that phase
- Add a Spec refs line citing the relevant FR/NFR IDs and section numbers

Caissa-specific: no ABC stubs. Phase 1 delivers working, tested code. No typing.Protocol.
Store as `docs/features/rpa-layer/feature_steps.md`.
```

---

## 3. Piece Plan

```text
Please review what has currently been implemented. Then review the specification
`docs/features/rpa-layer/feature_spec.md` and the implementation plan
`docs/features/rpa-layer/feature_steps.md`. Based on this, for each phase, break it
into smaller pieces implementable in a single coding session.

The output document must contain in order:
1. A "Current State" table
2. A "How to use this plan" section describing: red → implement → human diff review
   (Gate C from docs/process/sdd-workflow.md) → green → lint → docs update → commit
3. A "Files to Create / Modify" overview table
4. One section per phase, each with one or more named sessions including:
   - Files to create or edit
   - Scope, implementation notes, tests, spec refs, definition-of-done, suggested commit
5. A "Final Verification" section
6. A "Session Summary Table"

Follow the template at `docs/templates/piece_implementation_plan.md`.
Store as `docs/features/rpa-layer/implementation_plan.md`.
```

---

## 4. Next Piece

```text
Please review the current project status, then look at `docs/features/rpa-layer/implementation_plan.md`,
`docs/features/rpa-layer/feature_spec.md`, and `docs/features/rpa-layer/feature_steps.md`.
Identify the next session and provide a brief summary (2–4 sentences): which session it is,
what it implements, which files to edit, and which tests to write first (TDD red).
```

---

## 5. Verify Implementation

```text
Please confirm that session __SESSION__ described in `docs/features/rpa-layer/implementation_plan.md`
is implemented correctly. Verify against:
- The implementation plan (scope, definition of done, tests listed)
- The specification at `docs/features/rpa-layer/feature_spec.md` (Spec refs for the session)
- The phase tracker at `docs/features/rpa-layer/feature_steps.md`

Run `make test` and `make lint` and report the output. List any failures explicitly.

Report any gaps, deviations, or missing items. Check that:
- No PySide6 import outside the three-module allowlist
- RST docstrings present for all new and modified callables
- No time.sleep() in any new code
- CHANGELOG.md updated if user-visible

If everything is correct, confirm the session can be marked complete and the PR opened.
```

---

## 6. Design Changes

```text
We have made design choice changes and updated our documents accordingly. First, check
if our documentation is logical and consistent between the different documents.

Then verify all code implementation against the documents. If code and documents are
inconsistent: report each discrepancy as (a) what the document says, (b) what the code
does, (c) recommended resolution. Only update living documents once the correct behaviour
is agreed. Spec wrong → stop, update spec, resume.

The main documents:
- `docs/features/rpa-layer/implementation_plan.md`
- `docs/features/rpa-layer/feature_spec.md`
- `docs/features/rpa-layer/feature_steps.md`
- `docs/rpa/state-machine.md` (for any runner-related changes)
```

---

## 7. Classical Invariant Check

```text
Please verify that the Classical Invariant is preserved by all changes in this PR:
`classical` mode + no theme overlay = upstream Lucas Chess R6 exactly.

Check:
- No widget, toolbar entry, menu entry, mode JSON, QSS rule, overlay, or render-time
  config key added that activates in classical mode
- `bin/Code/Rpa/` is not imported until an rpa_* verb arrives (lazy import)
- `CAISSA_RPA=0` kill switch is functional (test this)
- `tests/test_classical_invariant.py` still green
- `test_importing_runner_does_not_import_cv2` still green

Report any violation with the exact file and line.
```

---

## 8. Gate H Docs Check

```text
Please verify Gate H (Docs Completeness) for Phase __PHASE__:
- Every docs/rpa/ page listed for this phase in the phase table exists and is current
- Every new public callable in bin/Code/Rpa/ has an RST docstring
- Run `make docs` and confirm zero warnings
- New terms are in docs/rpa/glossary.md
- New decisions are in docs/rpa/decisions.md
- Any earlier docs/rpa/ page this phase invalidated is amended in this PR

Report any missing item with the file it should be in.
```

---

## 9. State Machine Consistency Check

```text
Please verify that the runner implementation in bin/Code/Rpa/Runner.py is consistent
with the formal spec in docs/rpa/state-machine.md. Check:
- The sub-state enum in Runner.py lists exactly 14 sub-states matching the spec
- Every outgoing edge in the spec exists in the runner's pump() method
- The three deadlines (run: 90_000 ms, step-verify: 5_000 ms, converge: 12 transitions)
  are present as named constants
- No time.sleep() anywhere in Runner.py
- One pump = at most one sub-state transition and at most one driver actuation

Report any discrepancy with line numbers.
```

---

## 10. RemoteControl Contract Check

```text
Please verify that the RemoteControl refactor in Phase 2 preserved the wire contract:
- Run the 25 parametrised tests against tests/ui/rc_contract.json
- Confirm tests/test_remote_control.py (44 tests) all green
- Confirm the only change to test_remote_control.py is the Phase 1 pytestmark line
- Confirm CAISSA_RPA=0 makes all rpa_* verbs return clean "disabled" errors and leaves
  all 25 original verbs working

Report any regression with the exact test name and failure message.
```

---

## 11. Coverage Gate Check

```text
Please run `make cov` and verify:
- Overall coverage for Code.Rpa is ≥ 90 %
- The omit list matches exactly: Driver.py, Service.py, Vision/Capture.py,
  Vision/Template.py, Vision/Ocr.py, Fakes.py
- No module outside this omit list has zero coverage (that would mean the omit list
  is wrong, not that coverage is good)
- Fakes.py has docstrings and passes lint even though it is omitted from the gate

Report the per-module coverage numbers alongside any gate failure.
```
