# Claude Code Prompts — Caissa Feature Template

<!-- PURPOSE: Ready-to-paste Claude Code prompts for the SDD/TDD living-document workflow.

     HOW TO USE:
     1. Fill in the Configuration table below.
     2. Do a find-and-replace across all prompt blocks to substitute the actual paths.
        Verify: no angle-bracket placeholders remain except __SESSION__.
     3. Paste the relevant prompt into a Claude Code session.
     4. For the Verify prompt, replace __SESSION__ each time (e.g. "2-A").

     The filled-in version for the RPA layer is at docs/claude_code/prompts.md. -->

## Configuration

| Placeholder | Actual path | Filled? |
| --- | --- | --- |
| `<feature-spec-doc>` | TODO: e.g. `docs/features/rpa-layer/feature_spec.md` | ☐ |
| `<feature-steps-doc>` | TODO: e.g. `docs/features/rpa-layer/feature_steps.md` | ☐ |
| `<piece-plan-doc>` | TODO: e.g. `docs/features/rpa-layer/implementation_plan.md` | ☐ |
| `<coding-standards-doc>` | `docs/standards/coding-standards.md` | ☐ |
| `<docstring-standards-doc>` | `docs/standards/docstring-standards.md` | ☐ |
| `<templates-dir>` | `docs/templates` | ☐ |

**Per-use placeholder** (replace each time you paste the Verify prompt):

| Placeholder | Replace with | Example |
| --- | --- | --- |
| `__SESSION__` | The session ID you are verifying | `2-A`, `5-B` |

---

## Code Standards

```text
Please confirm that the coding standards defined in `<coding-standards-doc>`
and `<docstring-standards-doc>` are followed. Make sure to include RST/Sphinx
docstrings for all public and non-public functions and classes, and ensure the
code is well-structured and readable. No ABCs or typing.Protocol — use plain
base classes raising NotImplementedError where an interface is needed.
```

---

## Planning

### Steps Document

```text
Please read the feature specification at `<feature-spec-doc>`. Based on the spec,
create a phase-by-phase TDD implementation tracker following the structure defined
in the template at `<templates-dir>/feature_steps.md`.

For each phase:
- List the files to create or edit (use "create" for the first appearance; descriptive
  "edit — …" annotation for all later touches)
- List every class, method, property, and private helper to implement, with exact
  constructor signatures, parameter names, default values, and return types
- For every method include: exception type and triggering condition for each documented
  error path; whether bulk-getter return values are copies or live references; for
  dict-returning methods, the exact top-level key names
- List every TDD test case name for that phase
- Add a Spec refs line citing the relevant FR/NFR IDs and section numbers from the spec

Note: Caissa uses no ABCs or typing.Protocol. Plain base classes raising NotImplementedError
are the interface pattern. Match the style of bin/Code/ManagerBase/Manager.py.

Store the document as `<feature-steps-doc>`.
```

---

### Piece Plan

```text
Please review what has currently been implemented. Then review the specification
`<feature-spec-doc>` and the implementation plan `<feature-steps-doc>`. Based on
this, for each phase, break it into smaller pieces implementable in a single coding
session that I can manually code review.

The output document must contain in order:
1. A "Current State" table showing which files exist and their status
2. A "How to use this plan" section describing the TDD session loop:
   red → implement → human diff review (Gate C) → green → lint → docs update → commit → PR
3. A "Files to Create / Modify" overview table
4. One section per phase, each with one or more named sessions. Every session must include:
   - Files to create or edit
   - Scope: what the session accomplishes
   - Precise implementation notes (signatures, helpers, constructor attributes, key names,
     error paths)
   - Tests this session makes green
   - Spec refs line
   - Definition-of-done checklist
   - Suggested conventional commit message with the rpa scope
5. A "Final Verification" section
6. A "Session Summary Table"

Follow the template at `<templates-dir>/piece_implementation_plan.md`.
Store as `<piece-plan-doc>`.
```

---

### Next Piece

```text
Please review the current project status, then look at the piece implementation plan at
`<piece-plan-doc>`, the specification at `<feature-spec-doc>`, and the phase tracker at
`<feature-steps-doc>`. Identify the next session that should be implemented and provide
a brief summary (2-4 sentences): which session it is, what it implements, which files to
edit, and the TDD starting point (which tests to write first).
```

---

## Verify Implementation

```text
Please confirm that session __SESSION__ described in `<piece-plan-doc>` is implemented
correctly. Verify it against:
- The implementation plan at `<piece-plan-doc>` (scope, definition of done, tests listed)
- The specification at `<feature-spec-doc>` (the Spec refs listed in the session)
- The phase tracker at `<feature-steps-doc>`

Run `make test` and `make lint` and report the output. If any tests are failing or lint
issues exist, list them explicitly.

Report any gaps, deviations, or missing items. Ensure all living documents are up to
date with the implementation status. If everything is correct, confirm that the session
can be marked complete and the PR can be opened.
```

---

## Design Changes

```text
We have made design choice changes and updated our documents accordingly.
First, check if our documentation is logical and consistent between the different documents.

Then use these documents to verify all code implementation and make sure existing
implemented phases match what the documents require.

If code and documents are inconsistent, do not change code to match stale documents.
Instead, report each discrepancy with: (a) what the document says, (b) what the code
does, and (c) a recommended resolution. Only update living documents once the correct
behaviour has been agreed. Spec wrong → stop, update spec, resume.

The main documents are:
- The implementation plan at `<piece-plan-doc>`
- The specification at `<feature-spec-doc>`
- The phase tracker at `<feature-steps-doc>`
```

---

## Milestone Review

_Explore what has been built honestly before deciding what is next. Follow with the
Exploration → Document pattern: discuss first, then ask Claude to formalise findings._

```text
We have just completed <milestone description>. Please review the full repository and:

1. Summarise what has been built that is new (did not exist before this work).
2. Identify which additions are genuinely novel or differentiated.
3. Point out any architectural or technical debt worth addressing.
4. Suggest the highest-value next feature, with a one-sentence rationale.

Be direct. If something is ordinary, say so.
```

---

## Housekeeping Check

_Use at natural boundaries: before starting a new feature, or when the repo feels cluttered._

```text
Please do a housekeeping pass on the repository:

1. Branches: list any branches not `main` and not a current active branch. For each,
   confirm whether merged or abandoned, and recommend deletion or archiving.
2. CHANGELOG: confirm `[Unreleased]` section is accurate and complete.
3. Feature docs: any `docs/features/` directories complete but not yet archived?
4. Open PRs: any PRs open against the wrong base or stale?

Report each item with a recommended action. Do not take any action yet.
```

---

## Feature Archive

_Use when a feature is fully merged and implementation docs should move to the archive._

```text
The <feature name> feature is complete. All phases are merged to main.

Please:
1. `git mv docs/features/<name>/ docs/features/_archive/<name>/`
2. Add `**Status:** Completed <today's date>` to the front matter of each archived file.
3. Update any cross-references pointing to the old path.
4. Confirm the archive exists and the original path is gone.

Do not delete — the archive is the audit trail.
```
