# Living Document Templates — Caissa

This directory contains reusable templates for the SDD/TDD living-document workflow used in
Caissa. These are Caissa-adapted versions of the AIBooster+ GenAI templates.

**Key adaptation from the upstream templates:** Caissa does not use ABCs or `typing.Protocol`
(see `docs/standards/coding-standards.md` §3.2). The "NON-ABC" variants are the *default* here.
The ABC-specific sections in the originals have been removed or replaced with plain-class guidance.

---

## The templates

| Template | Use it for |
|---|---|
| [CLAUDE_template.md](CLAUDE_template.md) | Project-level context for Claude Code — purpose, architecture, living document references, dependency policy, dev setup, TDD workflow, coding standards, branching strategy, and PR requirements. Copy into a new feature directory as needed; the main `CLAUDE.md` at repo root covers Caissa-wide conventions. |
| [feature_spec.md](feature_spec.md) | Authoritative specification for a single feature — R/I/P/Q/N requirements, interface contract, error behaviour, usage examples, and technical spec. Must stay in sync with every design decision. |
| [feature_steps.md](feature_steps.md) | Phase-by-phase TDD implementation tracker. One section per phase, each listing files to touch, what to implement, and which test cases to write. Updated after each phase completes. |
| [piece_implementation_plan.md](piece_implementation_plan.md) | Session-level breakdown of all phases. Each session is small enough to implement and review in one sitting. Includes scope, implementation notes, test list, definition-of-done checklist, and a suggested commit message per session. |
| [claude_code_prompts.md](claude_code_prompts.md) | Ready-to-paste Claude Code prompts for the four recurring workflow moments: generating the steps document, generating the piece plan, identifying the next piece, and verifying a completed session. |

---

## How the documents relate

```text
CLAUDE.md                         ← repo-wide context (read automatically)
    │
    └─► docs/features/<name>/
            ├─ initial_idea.md    ← FROZEN at scope-lock — business requirements + open questions
            ├─ feature_spec.md    ← LIVING spec (R/I/P/Q/N — write first; keep current always)
            ├─ feature_steps.md   ← LIVING phase tracker (links back to spec; updated as phases complete)
            └─ implementation_plan.md  ← LIVING session breakdown
                    │
                    └─► docs/claude_code/prompts.md      ← SDD/Caissa prompt library
                    └─► docs/claude_code/prompt-library.md  ← general-purpose templates
                    └─► docs/claude_code/working-patterns.md ← cross-project patterns
```

The typical sequence for a new feature:

1. Create `docs/features/<name>/initial_idea.md` — state the problem and freeze scope.
2. Write `feature_spec.md` — R/I/P/Q/N before any code. Gate A must pass.
3. Write `feature_steps.md` — break the spec into TDD phases.
4. Run the **Piece Plan** prompt to generate `implementation_plan.md`.
5. Work through sessions one at a time, using the **Next Piece** and **Verify** prompts.
6. After any design change, run the **Design Changes** prompt to keep all docs consistent.

See `docs/process/sdd-workflow.md` for the full routine and the 8 gates.

---

## How to use a template

1. Copy the template file(s) into `docs/features/<name>/`.
2. Replace every `TODO:` marker and `<placeholder>` token with project-specific content.
3. Delete template comment blocks (`<!-- … -->`) once guidance is no longer needed.
4. Follow the SDD workflow gates before implementation begins.

---

## Living document rules

- **`feature_spec.md` is always current.** Update it alongside every design decision,
  constraint change, or interface change — never let it lag behind the code.
- **`feature_steps.md` reflects actual status.** Mark phases complete (✅) as they finish.
- **`implementation_plan.md` reflects actual progress.** Update the Current State table
  and session status as sessions complete.
- Never merge a design change without updating all three living documents in the same commit.
- On feature completion, move the directory to `docs/features/_archive/<name>/` (git mv).
