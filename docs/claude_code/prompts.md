# Claude Code Prompts — Caissa (SDD/TDD Library)

<!-- Caissa-specific SDD/TDD prompts for the living-document workflow.
     For general-purpose prompts that work in any project, see prompt-library.md.
     For the patterns behind these prompts, see working-patterns.md. -->

---

## Usage Patterns

These patterns emerged from RPA layer development and apply to any Caissa feature.
Read this section first — the prompts below only work well in the right sequence.

> **See also:** `docs/claude_code/working-patterns.md` — cross-project patterns,
> plan feedback moves, and the full recurring-corrections list.
> `docs/claude_code/prompt-library.md` — project-agnostic templates.

### 1. The SDD Pipeline Sequence

Never jump to code. The order is:

```
1. New feature kickoff (prompt §1)      → initial_idea.md + feature dir
2. Steps document (prompt §3)           → feature_steps.md
3. Piece plan (prompt §4)               → implementation_plan.md
4. Per-session: "go" or Next Piece      → one session at a time
5. Per-session: Verify (prompt §6)      → before commit
6. Per-phase: open PR
7. At feature completion: Gate E, archive (prompt §10)
```

### 2. The "go" Continuation Pattern

When a session runs out of context mid-implementation, start the next session with a bare:

```
go
```

or

```
continue
```

This works reliably because `implementation_plan.md` contains the Session Summary Table.
Claude reads it on the way in and picks up the next undone session automatically.

Use the bare "go" when you want to continue without changing direction. Use the full
**Next Piece** prompt (§5) when you want to confirm which session is next before committing
to it. Use the full **Verify** prompt (§6) when something felt uncertain in the last session
and you want an explicit sign-off before opening the PR.

### 3. Exploration → Document

When reaching a milestone (feature done, phase done, or a natural pause), explore
interactively first, then ask Claude to formalise the findings:

1. Ask open questions conversationally: *"have we built anything others would actually want?"*,
   *"what best describes this repo?"*, *"what's still missing?"*
2. Discuss and refine in a few turns.
3. Only then say: *"document this as [future work / a decision / an ADR]"*.

This avoids premature documentation. The conversational turn surfaces the real insight;
the documentation prompt commits only what survived scrutiny.

### 4. Domain Analogy for Requirements

When explaining a complex technical requirement, anchor it in a domain you know:

> *"When I was in RPA at UIPath, we used this process: 1. Before action, check state.
> 2. If not right, restore state. 3. Perform action. 4. Verify. I want to formalise this."*

Claude uses the analogy to ask fewer clarifying questions and write more accurate specs.
This is faster than writing the requirement from scratch. After the spec is written, the
analogy can be dropped — the spec is the authority.

### 5. Sessions Are Sized for Human Diff Review

Gate C (human diff review) is non-negotiable: every changed line read by a human before
commit. Sessions are deliberately granular so the diff fits a single review sitting.
If a session feels too large to review comfortably, split it — do not skip the review.
This is the main quality gate; the automated tests catch regressions, but only the diff
review catches design drift, sneaky reformats of upstream code, and bad abstractions.

### 6. Housekeeping at Natural Boundaries

At the end of a feature or before starting the next: run the **Housekeeping Check**
prompt (§11). Common items: merged branches not deleted, leftover `wip/` branches,
stale `[Unreleased]` sections in CHANGELOG, feature docs not archived.

### 7. One Branch = One Phase = One PR

Strictly enforced. Stacking phases on one branch makes the diff unreviewable and defeats
Gate C. Branch from latest `main`, not from the previous phase's branch. The implementation
plan enforces this via the "Suggested commit" and "Branch" fields in each session.

---

## Configuration

Fill this table when adapting these prompts for a new feature. Replace placeholders in
all prompt blocks with the actual paths before pasting.

| Placeholder | Actual path |
| --- | --- |
| `<feature-spec-doc>` | _(fill in: e.g. `docs/features/my-feature/feature_spec.md`)_ |
| `<feature-steps-doc>` | _(fill in: e.g. `docs/features/my-feature/feature_steps.md`)_ |
| `<piece-plan-doc>` | _(fill in: e.g. `docs/features/my-feature/implementation_plan.md`)_ |
| `<coding-standards-doc>` | `docs/standards/coding-standards.md` |
| `<docstring-standards-doc>` | `docs/standards/docstring-standards.md` |
| `<templates-dir>` | `docs/templates` |
| `<feature-dir>` | _(fill in: e.g. `docs/features/my-feature/`)_ |
| `<product-docs-dir>` | _(fill in: e.g. `docs/rpa/` for the RPA layer)_ |

**Per-use placeholder** (replace each time you paste the Verify prompt):

| Placeholder | Replace with | Example |
| --- | --- | --- |
| `__SESSION__` | The session ID you are verifying | `2-A`, `5-B` |
| `__PHASE__` | The phase number you are checking | `3`, `7` |

---

## Caissa-Specific Reminders

Include these in any implementation session for Caissa code:

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

## 1. New Feature Kickoff

_Use at the start of a new non-trivial feature. Creates the feature directory and all
SDD artefacts. Do not implement any code in this session._

```text
We are starting a new feature: <feature name>.

Please create the feature directory at <feature-dir> and populate the four SDD artefacts:

1. `initial_idea.md` — capture the problem statement and open questions as I have
   described them. Mark it FROZEN immediately after creation.
2. `feature_spec.md` — full spec following the template at `<templates-dir>/feature_spec.md`.
   Gate A checklist (from `docs/process/sdd-workflow.md`) must be satisfied before
   we proceed to any code.
3. `feature_steps.md` — phase-by-phase TDD tracker with all test names written up front.
   Follow the template at `<templates-dir>/feature_steps.md`.
4. `implementation_plan.md` — session breakdown following `<templates-dir>/piece_implementation_plan.md`.

Work through these in order. After writing `feature_spec.md`, pause and confirm
Gate A before continuing to the steps and plan documents.

Caissa-specific: classical mode + no theme overlay must remain unchanged (Classical
Invariant). State the impact in the spec.
```

---

## 2. Code Standards

_Paste into any implementation session as a reminder. Usually not needed as a standalone
prompt — include it in the session prompt instead._

```text
Please confirm that the coding standards defined in `docs/standards/coding-standards.md`
and `docs/standards/docstring-standards.md` are followed. Make sure to include RST/Sphinx
docstrings for all public and non-public functions, classes, and modules. No ABCs or
typing.Protocol — plain base classes raising NotImplementedError. No PySide6 imports
outside Driver.py, Vision/Capture.py, and Service.py. No time.sleep(). All new code
scoped to bin/Code/Rpa/ and tests/unit/rpa/.
```

---

## 3. Steps Document

_Use after the feature spec has passed Gate A. Creates `feature_steps.md`._

```text
Please read the feature specification at `<feature-spec-doc>`. Based on the spec,
create a phase-by-phase TDD implementation tracker following the structure defined
in `<templates-dir>/feature_steps.md`.

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
Store as `<feature-steps-doc>`.
```

---

## 4. Piece Plan

_Use after `feature_steps.md` is written. Creates `implementation_plan.md`._

```text
Please review what has currently been implemented. Then review the specification
`<feature-spec-doc>` and the implementation plan `<feature-steps-doc>`. Based on this,
for each phase, break it into smaller pieces implementable in a single coding session.

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

Follow the template at `<templates-dir>/piece_implementation_plan.md`.
Store as `<piece-plan-doc>`.
```

---

## 5. Next Piece

_Use at the start of a session to confirm which session is up next before implementing.
Alternatively, just type "go" — see Usage Patterns §2._

```text
Please review the current project status, then look at `<piece-plan-doc>`,
`<feature-spec-doc>`, and `<feature-steps-doc>`.
Identify the next session and provide a brief summary (2–4 sentences): which session it is,
what it implements, which files to edit, and which tests to write first (TDD red).
```

---

## 6. Verify Implementation

_Use after implementing a session, before committing. Replace `__SESSION__` each time._

```text
Please confirm that session __SESSION__ described in `<piece-plan-doc>` is implemented
correctly. Verify against:
- The implementation plan (scope, definition of done, tests listed)
- The specification at `<feature-spec-doc>` (Spec refs for the session)
- The phase tracker at `<feature-steps-doc>`

Run `make test` and `make lint` and report the output. List any failures explicitly.

Report any gaps, deviations, or missing items. Check that:
- No PySide6 import outside the three-module allowlist
- RST docstrings present for all new and modified callables
- No time.sleep() in any new code
- CHANGELOG.md updated if user-visible

If everything is correct, confirm the session can be marked complete and the PR opened.
```

---

## 7. Design Changes

_Use when a design decision was changed mid-implementation and documents need reconciling._

```text
We have made design choice changes and updated our documents accordingly. First, check
if our documentation is logical and consistent between the different documents.

Then verify all code implementation against the documents. If code and documents are
inconsistent: report each discrepancy as (a) what the document says, (b) what the code
does, (c) recommended resolution. Only update living documents once the correct behaviour
is agreed. Spec wrong → stop, update spec, resume.

The main documents:
- `<piece-plan-doc>`
- `<feature-spec-doc>`
- `<feature-steps-doc>`
```

---

## 8. Classical Invariant Check

_Use before merging any PR that touches the UI, modes, toolbar, menus, or imports._

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

## 9. Milestone Review

_Use at natural milestones: feature complete, phase done, or before starting a new
feature. Explores conversationally what has been built, what is unique, and what is
worth doing next. Follow with the Exploration → Document pattern (Usage Patterns §3)._

```text
We have just completed <milestone description>. Please review the full repository and:

1. Summarise what has been built that did not exist in upstream Lucas Chess R6.
2. Identify which of these additions are genuinely novel — not available in other
   openly available chess tools.
3. Identify anything the upstream project might want to adopt.
4. Point out any architectural or technical debt that should be addressed before
   the next major feature.
5. Suggest the highest-value next feature or direction, with a one-sentence rationale.

Be direct. If something is ordinary, say so. The goal is an honest assessment, not a summary.
```

---

## 10. Feature Archive

_Use when a feature is fully merged and the implementation docs should move to the archive._

```text
The <feature name> feature is complete. All phases are merged to main.

Please:
1. `git mv docs/features/<name>/ docs/features/_archive/<name>/`
2. Add `**Status:** Completed <today's date>` to the front matter of each archived file.
3. Update any cross-references in `docs/process/sdd-workflow.md` or `CLAUDE.md` that
   still point to the old path.
4. Confirm `docs/features/_archive/<name>/` exists and the original path is gone.

Do not delete — the archive is the audit trail.
```

---

## 11. Housekeeping Check

_Use at natural boundaries: before starting a new feature, after a milestone, or when
the repo feels cluttered. Covers branches, CHANGELOG, and stale docs._

```text
Please do a housekeeping pass on the repository:

1. Branches: list any branches (local and remote) that are not `main` and not
   a current active branch. For each, confirm whether it is merged or abandoned, and
   recommend deletion or archiving.
2. CHANGELOG: confirm `[Unreleased]` section is accurate and complete. Any merged
   PRs whose user-visible changes are missing?
3. Feature docs: any `docs/features/` directories that are complete but not yet archived?
4. Open PRs: any PRs open against the wrong base or stale?
5. Worktrees: any leftover git worktrees from previous sessions?

Report each item with a recommended action. Do not take any action yet — present the
list for review first.
```

---

## 12. Gate H Docs Check

_Use per phase, before the phase's PR is opened. Replace `__PHASE__`._

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

## 13. Coverage Gate Check

_Use after `make cov` to confirm the coverage gate. Adjust omit list per feature._

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

---

## 14. State Machine Consistency Check _(RPA-specific example)_

_Use when the runner or state machine is changed. Adapt the constants and state count
for other state-machine modules._

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

## 15. RemoteControl Contract Check _(RPA-specific example)_

_Use after any refactor of RemoteControl or the RPA verb dispatcher._

```text
Please verify that the RemoteControl refactor in Phase 2 preserved the wire contract:
- Run the 25 parametrised tests against tests/ui/rc_contract.json
- Confirm tests/test_remote_control.py (44 tests) all green
- Confirm the only change to test_remote_control.py is the Phase 1 pytestmark line
- Confirm CAISSA_RPA=0 makes all rpa_* verbs return clean "disabled" errors and leaves
  all 25 original verbs working

Report any regression with the exact test name and failure message.
```
