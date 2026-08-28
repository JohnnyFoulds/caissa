# Portable CLAUDE.md Snippet

Copy this block into any project's `CLAUDE.md` to carry the distilled working
rules forward without Caissa-specific content.

Derived from `docs/claude_code/working-patterns.md` §8–9: the standing preferences
and recurring corrections that generalise across unrelated projects.

---

```markdown
## Working Rules

### Plans
- Write the plan itself to `docs/features/<name>/implementation_plan.md` as step 0,
  before any code.
- Plans must have a `## Context` section (evidence-backed facts the plan rests on)
  and a `## Verification` section (runnable commands, each annotated with what it proves).
- Name the trunk branch and target environment explicitly; never assume the repo default.
- One phase = one branch = one PR.
- List deferred items in `## Out of scope` with reasons; do not drop them silently.
- No "this approach is closed" without exhausting the search first.

### Doing work
- Confirm which branch and plan document you are working against before starting.
  Performing work against a stale default branch invalidates everything downstream.
- Never claim completion without observed evidence — output, logs, or a screenshot.
- Exhaust your own verification before escalating; human testing is the last resort.
- If you cannot observe the system, add instrumentation before attempting a fix.
- Every fix ships with a test that would have caught it. UI and user journeys included.
- Stand up real dependencies for tests, and tear everything down afterwards.
- Make dependencies optional and configurable; support existing infrastructure.

### Quality and honesty
- Research or read the source. Never handwave, never guess, never grade yourself generously.
- Do not display a metric you cannot actually compute.
- No fabricated placeholder content.

### Docs and commits
- Documentation, changelog, and specs are updated in the same unit of work as the code.
- If a process step is not explicitly recorded in the feature directory, it MUST be.
- No AI attribution (Co-Authored-By, "Generated with", etc.) in any VCS artefact.
- Keep a durable tracking document so a fresh session can resume without the conversation.

### Session flow
- On `continue` / `go` / `what's next?`: re-read the tracking document and proceed.
  Do not ask for clarification.
- On `merged`: the user has merged manually; acknowledge and continue to the next session.
- Do not ask permission mid-flow. Do not stall between steps.
```
