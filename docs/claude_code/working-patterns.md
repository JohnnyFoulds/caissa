# Claude Working Patterns

Cross-project, evidence-backed patterns distilled from 3,786 prompts across 31
project paths, 89 session transcripts (116,608 JSONL records, 1,029 genuine human
turns), and 18 plan documents.

Every claim carries a frequency or a sanitised quote. Claims corroborated by two
independent analysis passes are marked **[×2]**. Short control words are quoted
verbatim — they contain no sensitive content. Longer quotes are abstracted with
`<placeholder>` tokens.

> **Tool:** `tools/claude_mine.py` recomputes all frequency figures.
> Run `python3 tools/claude_mine.py --verify` to confirm the counts hold.

---

## 1. Control Vocabulary

The most frequent short directives (≤40 chars), from the session corpus:

| Directive | ~n | Category |
|---|---|---|
| `continue` | 49 | drive — resume after context limit or pause |
| `what's next?` | 39 | status pull — what does the plan say to do now |
| `commit and push` | 21 | git close-out |
| `open` | 14 | show me the artifact / open PR |
| `go` | 27 | drive — bare resume, often after a plan approval |
| `yes` | 13 | approval |
| `do it` | 8 | approval |
| `merged` | 7 | merge handoff — resume token after manual merge |
| `begin` | 7 | drive |

From `history.jsonl` (wider, across all projects):

| Directive | ~n | Notes |
|---|---|---|
| `yes` | 46 | most common single-word approval |
| `continue` | 19 | |
| `done` | 18 | |
| `what's next?` | 17 | |
| `do it` | 16 | |
| `go` | 13 | |
| `push` | 11 | |

**What this means for Claude:** These prompts are the control loop, not new
instructions. When `continue`, `go`, or `what's next?` arrives, the correct
response is to re-read the plan/tracker and proceed — not to ask for clarification.
When `merged` arrives, it is the resume token after a manual merge; acknowledge and
continue.

---

## 2. Plan Feedback Moves

**[×2]** Headline numbers: **164 `ExitPlanMode` presentations** across 89 sessions.
Approximately **~65% are approved silently** (no text reply). **Any prose reply to a
plan is a correction or an amendment.**

Mean **4.7 presentations per approval**; longest arc 18 rounds. All review cost
is paid up front — none of the 35 post-approval messages contained a plan
correction. Once approved, the plan is final.

### 2.1 Silent approval (≈65%)

No text reply; the user accepts via the UI and sends `go` / `continue` / `do it`.

> *Implication:* Do not treat silence as absence of engagement. It is the highest
> expression of confidence. If the user replies with words, something is wrong.

### 2.2 Approve-with-amendment (≈23% of text replies)

Opens with a token of acceptance, pivots immediately to a delta. Never re-litigates
the whole plan; always scoped to one addition or correction.

Template:
```
Yes — but also <delta>.
<Existing capability> must stay as-is; <new capability> is additive only.
Update <doc/spec> to match, including what must NOT be changed.
```

Common delta shapes:
- *"also make sure there is <additional verification>"*
- *"<existing behaviour> stays, but we will now also have <new behaviour>"*
- *"update <doc>, and with clear guidelines of what we should not mess with"*

### 2.3 Refuse a "blocked / impossible" conclusion **[×2]**

When a plan concludes an approach is closed, the user does **not** accept the
constraint or pivot to a fallback. They push.

Template:
```
Do not fall back to <plan B> yet. <Plan A> produced <the one thing that worked>.
Push harder on that: try <technique 1>, <technique 2>, and generate new approaches.
Tell me what you actually tried and what the observed result was — not what you expect.
```

Observed phrasings: *"push as hard as you can"* · *"we are not moving to approach b,
you got something right in approach a, dig further"* · *"I believe in you, try harder,
think of new ideas"*.

### 2.4 Challenge / skepticism **[×2]**

Two flavours. **(a) Confidence probe** (short, interrogative, targets one claim):
*"are you 100% sure that is exactly what <system> does?"* · *"are you very sure?"*

**(b) Anti-generosity probe** — recurs across projects:
```
I think you are being too generous. Re-check every <item> against the actual
<source of truth: code / live system / primary document>.
Something sounding like a <problem> does not make it one.
For each item state: verdict, the evidence you observed, and the file/line or
command that proves it.
```

### 2.5 Evidence demand **[×2]** (~22 occurrences)

Does not accept narrative. Asks for the raw artifact.

Template:
```
Don't tell me it works — show me. Run <the thing>, paste the output, and confirm
the output matches the spec and the intent, not just that it exited 0.
If you cannot observe it, add the instrumentation that would let you observe it first.
```

Observed phrasings: *"show me the <logs> to prove that is what happened"* · *"run it,
and see if the output matches the plan, the expectations, and is usable as the intent
was"* · *"be empirical, and make sure you are factually correct"*.

### 2.6 Reframe / wrong-target (~12 occurrences)

Three sub-types:
- **Wrong branch:** *"I suspect the scan was done against the wrong branch — a very
  outdated default branch instead of <the real trunk>"*
- **Plan identity drift:** *"the plan was <named-plan-A> and now you have some new
  <named-plan-B> — sort this out"*
- **Own framing revised:** the user corrects their own prior phrasing mid-session and
  expects the model to re-scope

Template:
```
Stop. Confirm first: which branch, which plan document, which spec are you working against?
If it is not <named trunk> / <named plan file>, that is the bug — fix that before
anything else.
```

### 2.7 Self-verify-to-exhaustion **[×2]** (~10 occurrences)

The user refuses to be the sensor. They expect the agent to observe what the user
would observe before asking for human testing.

Template:
```
Your first priority is programmatic control and observability of <the thing>, before
any fixes. You must be able to see what I see: navigate, act, read state, capture output.
Exhaust your own verification first. Escalate to me only when nothing is left that you
can self-check.
```

Observed phrasings: *"you take the screenshot"* · *"don't ask me to tell you what is
wrong — instrument everything so you can drive it yourself"* · **"when things look
correct to you and there is nothing more you can self-check and test, then it is time
for human testing"**.

### 2.8 Scope reduction / optionality mandate (~15 occurrences)

Rarely "do less"; usually "**make that a switch, not a requirement**".

Template:
```
Make <dependency/feature> optional and configurable — assume it may be unavailable.
Support pointing at an existing <instance> rather than deploying a new one.
Do not gate the work on <policy/licence/approval concern>; that is my decision, note
it and move on.
```

### 2.9 Inline quoted-comment amendment (~15 occurrences, highest info density)

Annotates specific plan sentences by pasting them back:

Template:
```
[Re: "<verbatim quote from the plan>"] <correction | verdict | instruction>
[Re: "<second quote>"] <…>
```

This is the highest-signal feedback move — each `[Re: ...]` block targets exactly
one claim. Expect every claim in a plan to be audited literally.

### 2.10 Adversarial-persona review (~8 occurrences)

Re-read the artifact wearing a hostile expert hat. Issued repeatedly until a pass
returns no findings — treat repeated identical review requests as "converge to zero".

Template:
```
Re-read <artifact> as an adversarial <hostile expert role> whose job is to discredit it.
List every claim you could not defend, then fix them in place.
```

---

## 3. What a Good Plan Looks Like

Features of the 19/19 accepted plan docs on disk:

1. **`## Context` first, always.** The facts the plan rests on, with `file:line` or
   command evidence.
2. **`## Verification` last, always — runnable commands.** Each command annotated
   with what it proves. Not prose; copy-pasteable.
3. **Step 0: commit the plan itself to the repo.** Before any code. Named path.
   *"Before any implementation starts, I also want the plan itself to be written to
   `<docs path>`."* — 8 explicit instances.
4. **Named trunk and target.** Which branch is source, which environment is target.
5. **One phase = one branch = one PR.** Stated with the branch name in the heading.
6. **Explicit `## Out of scope`.** Deferred items listed with reasons, never dropped
   silently. Silent omission triggers "also…" feedback.
7. **Reuse — do not reinvent.** What existing code the plan uses instead of writing new.
8. **Landmine register.** Known traps in the code the plan must touch.
9. **RED tests written first.**  `xfail` stubs for deferred tests.
10. **Documentation deliverables as first-class items.** Methodology, design decisions,
    architecture, quickstart, user guide, API docs.
11. **Prior decisions this plan overturns — explicitly**, not silently.
12. **Standing-requirements table at the top** once a plan exceeds ~40k chars, mapping
    each requirement to the section that closes it.
13. **No "this is impossible"** without exhausting the search.

---

## 4. Session Lifecycle

### The four-token control loop

```
/plan  →  (silent approve)  →  go/continue  →  commit and push
  →  [user merges manually]  →  "merged, what's next?"
```

~140 turns in the corpus are pure loop mechanics. This only works because
`implementation_plan.md` contains the Session Summary Table — Claude re-reads it and
picks up the next session automatically.

### Three session openings

1. **Liveness probe** (12 sessions): `hello`, then nothing. Smoke-tests a new
   config or model. These are not real work sessions.
2. **Orientation**: point at a durable artifact — *"what are we currently working on,
   look in `<dir>`"* · *"where are we on our plan?"* · *"SITREP + next actions"*.
3. **Cold evidence drop**: paste a symptom or log, no framing. Expected response is
   to go find the context, diagnose, and not guess.

### Git-hygiene close-out **[×2]**

Sessions end on `commit and push`, `is everything checked in, pushed, merged and
ready?`, or `commit push pr and auto merge, then continue`. **Merging is reserved for
the human.** The user approves and then reports `merged`. Auto-merge was granted once
as an explicit temporary measure and later revoked.

---

## 5. Context-Exhaustion Playbook

**[×2]** 336 compactions across 89 sessions (~3.8 per session). Context exhaustion is
the primary environmental constraint.

Countermeasures (all observed explicitly):

1. **Tracking document.** *"The context keeps getting full and compacting — you have
   to start making a tracking document."*
2. **Session-resumability.** *"Is everything in `<feature dir>` correct and up to
   date, so if I start a new session the full context will be there?"*
3. **Fan-out is a context-budget strategy**, not just a speed strategy. *"It concerns
   me that you had to compact during your initial investigation. You have to fan out
   aggressively and investigate each finding with a subagent."*
4. **Commits as anti-amnesia checkpoints.** *"You seem to be losing content now —
   commit and push."* Long-document edits lose content; commit after each phase.

---

## 6. Post-Failure Five-Step Sequence

Observed consistently across projects:

1. Paste the raw symptom — no diagnosis, just the observation.
2. Refuse to diagnose: *"I am not asking for advice, diagnose then code."*
3. Reject the point fix; demand **observability**: *"Is the code instrumented for
   debugging?"* · *"Do you have sufficient logging to see what happened?"*
4. Demand a **regression test of the right kind**: *"The lesson here is that UI also
   needs TDD."*
5. Escalate to causal reproach: *"Would this sort of thing happen if you wrote proper
   tests?"*

---

## 7. Habits Worth Knowing

**The idea escalation ladder.** Small trigger → investigate → generalise → full feature
with SDD/TDD. The user never wants the small version; expect scope to expand upward
deliberately. The signal to formalise is *"Now plan this out properly and in detail,
and you know SDD, TDD and all the standards you have to follow."*

**The taste-dispute → measurable-spec → test ladder.** When something subjective
(visual consistency, layout quality) is wrong: screenshot it → name it → define a
measurement → write a unit test that encodes the measurement. Highly transferable.

**The exploration-then-document pattern.** Open questions are asked conversationally
(*"have we built anything others would actually want?"*, *"what best describes this?"*),
discussed for a few turns, then — and only then — *"document this as <future work /
a decision / an ADR>"*. Never the other way around.

**Artifact harvesting.** Explicit requests to mine past sessions for reusable prompts
and patterns; to find a prior session by plan name; to check what a previous session
concluded. Session transcripts and plan files are treated as a knowledge base, not
exhaust.

**Delegation policy.** Fan-out to subagents for *"verify N independent claims"* or
*"research a wide surface"*. Delegates to background / remote machines for heavy jobs.
Keeps for himself: merge approval, real human UI testing, credential handling, and
final judgement calls.

**The `remember…` signal.** 23 instances of `remember…` re-asserting a standing rule.
Each instance means that rule should have been written into `CLAUDE.md` so it never
needs re-stating.

---

## 8. Standing Preferences

**Attribution and authorship**
- Never include AI/Claude co-authorship attribution in commit messages, tags, MR/PR
  bodies, or issue comments. Codified in standards *and* enforced by a global hook —
  the strongest rule in the corpus.

**Branch and MR discipline**
- Work against the **named integration/trunk branch**, not the repository default;
  confirm before starting.
- Every change gets an MR; the human approves merges.
- Clean up leftover branches after a feature lands.
- Don't touch local branches when only remote ops were asked for.

**Testing**
- Unit **and** e2e **and** user-journey tests — never just one tier.
- *"UI also needs TDD."*
- Test against the real deployment target; cover the full matrix of deployment modes.
- Stand up real dependencies for tests, and **tear them down afterwards**.
- Red/green TDD by name.

**Cost and cleanup**
- Always tear down infrastructure spun up for tests.
- Use empirical cost tooling; don't estimate when real figures exist.
- Report before **and** after for any cleanup/remediation task.

**Dependencies and deployment**
- Make dependencies optional and configurable.
- Support pointing at existing infrastructure rather than deploying new instances.
- Don't gate work on licence/approval concerns — flag them and continue.

**Honesty and rigour**
- *"Don't handwave / don't guess / go find the research."* Research or read the source.
- Never claim done without showing it.
- Do not be generous when grading your own or a vendor's output.
- Don't display a metric you cannot actually compute.
- No fabricated placeholders.

**Interaction style**
- Don't ask permission mid-flow.
- Don't ask the user to be the sensor.
- Exhaust self-verification before escalating to human testing.
- Use structured question dialogs with options and recommendations, not open prose questions.

---

## 9. Recurring Corrections (Anti-Patterns)

Ranked by frequency × cost. Each is a strong candidate for a standing rule in
any project's `CLAUDE.md`.

| # | Anti-pattern | ~n | Signature correction |
|---|---|---|---|
| 1 | **Claiming done without observing the result** | ~15 | *"show me how it looks before telling me it's done"* |
| 2 | **Asking the user to be the sensor** | ~10 | *"You take the screenshot — instrument everything so you can drive it yourself"* |
| 3 | **Working against the wrong branch** | ~6 | *"we work with `<trunk>` as our trunk — did you get this wrong again?"* |
| 4 | **Losing plan identity across compaction** | ~4 | *"the plan was `<A>` and now you have some new `<B>` plan"* |
| 5 | **Skipping a test because the dependency isn't up** | ~4 | *"spin up `<the deployment>`, test, then tear it down"* |
| 6 | **Not cleaning up after yourself** | ~4 | *"you have not cleaned up — tear down `<the deployment>`"* |
| 7 | **Handwaving / unsourced assertions** | ~8 | *"don't handwave, go find the research"* |
| 8 | **Over-generous self/vendor assessment** | ~6 | *"you might be too generous"* |
| 9 | **Fixing the symptom instead of adding observability + test** | ~6 | *"is the code instrumented for debugging?"* |
| 10 | **Asking permission / stalling mid-flow** | ~5 | *"just continue, stop asking me this"* |
| 11 | **Docs/changelog drifting from code** | ~10 | *"is all the documentation up to date and correct?"* |
| 12 | **Adding hard dependencies where optional was asked for** | ~5 | *"I want `<X>` optional and I do not want to deploy `<Y>`"* |
| 13 | **Silent content loss during long-document edits** | 2 | *"where did our executive summary go? You seem to be losing content — commit"* |
| 14 | **Abandoning a hard problem too early** | ~8 | *"we are not moving to approach b, dig further in approach a"* |
| 15 | **Ignoring resource realism in plans** | 2 | *"don't plan to simulate `<N>` users from my laptop — it will fail before the system under test"* |
| 16 | **Breaking the user's environment while automating** | ~6 | *"make it usable again — always have an undo path"* |
| 17 | **Over-refusal on legitimate work** | 2 | Hard boundary: do not editorialise about safety on work the user has authorised on their own systems. |
