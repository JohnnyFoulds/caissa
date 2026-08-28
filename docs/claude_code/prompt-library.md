# General-Purpose Prompt Library

Project-agnostic prompt templates with `<placeholder>` tokens. Each prompt was
used multiple times across unrelated projects before being recorded here.

These complement `prompts.md` (which is Caissa/SDD-specific). Copy, fill in
the placeholders, and paste into any session.

---

## 1. Document Integrity Review

**The most frequently retyped prompt in the corpus (~17 wording variants, hundreds
of uses). Written down here for the first time.**

Use when any artifact — plan, spec, report, architecture doc, analysis — needs
a completeness and consistency pass before acting on it.

```
Review <artifact: the plan / the spec / the document / the report> in detail.
Make sure it is logical, correct, rigorous, empirical, and internally consistent,
and that it will meet the stated objectives and goals.
Identify any gaps and ambiguities and <close / resolve / save> them.
```

Slot-fill options:
- **Object:** `the plan` · `the entire plan` · `all repo documentation` · `the report`
- **Predicates:** `logical` · `correct` · `internally consistent` · `complete` ·
  `implementable` · `empirical` · `will produce the desired outcome` ·
  `will meet the objectives and goals` · `matches code implementation`
- **Disposition:** `close them` · `resolve them` · `fix them` · **`save them`**
  (strongest — gaps that cannot be closed must be *recorded*, not hidden)
- **Intensifiers:** `in detail` · `carefully` · `systematically` · `Verify everything`

Maximal form (used verbatim):
```
Please check that the plan is logical, correct, and internally consistent.
Verify everything, and identify any gaps or ambiguities and save them.
```

**When:** before implementation starts, before a plan approval, after a large
context-window accumulation, or whenever you suspect drift between the plan and the
current state of the code.

---

## 2. Claim-by-Claim Verification Against Ground Truth

Use when an artifact was produced by a tool, a vendor, or an earlier session
that may have used a stale branch or wrong version.

```
Check every <finding / claim / spec item / audit result> individually and
systematically against <the actual code on branch <trunk> / the live environment>.
Some items may be wrong because they were produced against <the wrong branch /
a stale snapshot>. Fan out with subagents and verify all claims.
For each item state: verdict, the evidence you observed, and the file/line or
command that proves it.
```

**When:** after any automated scan, security audit, or analysis that ran against a
default branch you did not choose; whenever a finding smells implausible.

---

## 3. Adversarial Persona Review

Use after any substantive artifact to stress-test it before showing it to others
or acting on it. Issue repeatedly until a pass returns no findings.

```
Re-read <artifact> as an adversarial <hostile expert role: security researcher /
senior architect / domain specialist / hostile reviewer> whose job is to discredit it.
List every claim you could not defend under scrutiny, with a specific objection for
each. Then fix them in place.
```

Variants observed:
```
Do an adversarial review of <artifact> and make corrections if applicable.
```
```
Read <report> critically as a <senior exec / domain expert / attacker>.
```

**When:** before publishing a report, before sending a design for external review,
before treating a security finding as confirmed.

---

## 4. Deep Research with Rigour

Use when you need academic or technical depth rather than a surface-level overview.

```
Do formal, rigorous research on <question / topic>. Don't handwave — find the
literature and report what it actually says. Full rigour with <APA / IEEE / Chicago>
citations.
Include a side-by-side comparison of <approach A> vs <approach B> where relevant.
Create a directory for the research outputs.
Fan out aggressively; every subagent must record its findings.
```

**When:** literature surveys, technology comparisons, methodology selection,
competitive analysis. Never accept plausible prose when primary sources exist.

---

## 5. Repo State Close-Out Audit

Use at natural milestones: feature complete, before starting a new feature, or
when the repo feels cluttered.

```
Is everything committed, pushed, merged, and MR'd?
Are all documents updated, all necessary tests written, and all tests run?
Any leftover branches, open PRs against the wrong base, or stale worktrees to
clean up?
Report each item with a recommended action. Do not take action yet.
```

**When:** end of a feature, end of a sprint, before starting something new.

---

## 6. Process Conformance Audit

Use when you suspect the process has been followed in name but not in substance.

```
Are you still following our process — branches, MRs, doc updates, standards,
definition-of-done, and a briefing at the start of each session?
Go through <feature dir / commit history / reports> and tell me in detail exactly
what process steps have been completed. If a step is not explicitly recorded in
<feature dir>, it MUST be.
```

**When:** mid-feature health check; after a long break; when commits landed without
corresponding spec updates.

---

## 7. Make-It-Self-Verifying

Use when the agent keeps asking the user to observe something that the agent should
be able to observe itself.

```
Your first priority is programmatic control and observability of <the thing>, before
any fixes. You must be able to see what I see: navigate, act, read state, capture output.
Stand up whatever instrumentation or scaffolding you need.
Exhaust your own verification first. Only escalate to human testing when nothing is left
that you can self-check.
```

**When:** UI automation, integration tests, any task where "can you check if it works"
keeps coming back to the user.

---

## 8. Reproducibility Harness

Use after a one-off analysis to turn it into a repeatable process.

```
To produce this you had to gather data from several places. I want the process
reproducible: first write a <script / notebook> that gathers all the data and evidence
in one pass, then have the <report / output> consume that script's output.
We will have to do this regularly.
```

**When:** any dashboard, report, or analysis you will run again — cost reports,
test-coverage summaries, session-usage reports.

---

## 9. Viability / Stakeholder Interrogation

Use at milestones to get an honest external-perspective assessment.

```
Would <a stakeholder archetype: enterprise buyer / open-source contributor /
new user / hostile reviewer> actually want to use and deploy this? Why or why not?
What can we do technically and in documentation to satisfy them?
What would have to be made true for this to be a massive success?
```

Also the honest nihilistic form for a gut-check:
```
Have we built anything others would actually want and that is not available somewhere
else? Be direct. If something is ordinary, say so.
```

**When:** after completing a feature or project phase; before writing marketing copy
or a README; when deciding whether to continue a workstream.

---

## 10. Standards Import

Use to bring existing standards into a new project so they are followed automatically.

```
Read the standards at <path> and make sure they are followed in this repo.
Adapt them to be repo-specific, keep the adapted copy in this repo, and reference
them from CLAUDE.md and wherever else makes sense so they keep being followed.
```

**When:** starting a new project that should inherit engineering norms from another;
onboarding a codebase that has no standards yet.

---

## 11. Orientation / SITREP

Use at the start of a session when you don't remember exactly where you left off.

```
What are we currently working on — look in <feature dir / plan dir / README>.
Give me a SITREP and the recommended next actions.
Also check whether the README's recommended actions still hold.
```

**When:** resuming after a break; after context exhaustion and compaction; when
`what's next?` is too vague because multiple tracks are open.

---

## 12. Plan Self-Audit (before requesting approval)

Use *before* presenting a plan, to catch the issues that most often cause rejection.

```
Before I present this plan for approval, review it against this checklist:
1. Does it commit the plan itself to the repo as step 0?
2. Does it name the trunk branch and target environment?
3. Does it have an explicit "Out of scope" section with reasons?
4. Does each phase have RED tests and documentation deliverables?
5. Does it have a Verification section with runnable commands?
6. Does it note any prior decisions it overturns?
7. Is there a reuse-don't-reinvent section?
If any item is missing, add it before presenting.
```

**When:** before every `ExitPlanMode` call on a plan that matters.

---

## 13. Summary Digest for Long Plans

Use when a plan has grown past ~100k chars and needs a navigable overview.

```
This plan is very long now — give me a human-readable summary so I can confirm all
the decisions are correct. Do not change the plan itself; give me only the summary.
```

**When:** plans that have been through many rounds of amendment and have grown
unwieldy; before asking for final approval on a large plan.
