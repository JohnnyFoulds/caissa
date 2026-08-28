# Cross-Project Claude Working Patterns & Session Archaeology

## Context

`docs/claude_code/prompts.md` was expanded in PR #23, but it was mined from **one feature in
one repo** (the Caissa RPA layer). The patterns are real, the sample is narrow, and the doc
conflates Caissa-specific SDD prompts with general ways of working.

Mining the wider corpus — 3,786 prompts across 31 project paths, 89 session files
(116,608 records, 1,029 genuine human turns), 18 plan documents — produced findings that
justify separate, durable artifacts:

| Finding | Evidence |
|---|---|
| **A signature review macro is used hundreds of times in ~17 wording variants and is saved nowhere** | *"review the plan, make sure it is logical, correct, and internally consistent; identify any gaps and ambiguities and close them"* — retyped from memory every time |
| Plans are presented **164** times; **~21%** approved. Mean **4.7** presentations per approval, longest arc 18 rounds | `ExitPlanMode` call analysis |
| **~65% of plans are approved silently.** Any prose reply to a plan is therefore a correction | 55 of 164 answered with text |
| **100%** of surviving plan docs have `## Context` **and** `## Verification` | 19/19 on disk |
| Review cost is paid **up front**: none of the 35 post-approval messages corrects plan content | first message after each approval |
| **336 compactions across 89 sessions** (~3.8/session) — context exhaustion is the dominant constraint | fan-out is the stated countermeasure |
| Standing requirement, repeatedly given: **write the plan itself to the repo before any code** | 8 explicit instances |
| Shell-first operator | Bash 10,983 vs Read 3,651 tool calls |

Two independent analysis passes corroborated the same core moves (evidence demands,
self-verify-to-exhaustion, adversarial-persona review, fan-out as context budget, git-hygiene
close-out, the no-AI-attribution rule), so the headline findings are cross-validated rather
than single-sourced.

### Urgent incidental finding — ongoing data loss

Session pruning is **not** a backup defect: `~/.claude/.last-cleanup` is dated today and the
oldest local session is exactly 29 days old. Claude Code's own ~30-day `cleanupPeriodDays`
retention is running **on its default** (the key is absent from both `settings.json` and
`settings.local.json`) and deletes sessions daily. Six projects have already been erased
locally with no directory left at all. Raising `cleanupPeriodDays` would stop the bleeding —
flagged here as a **decision for the user**, not something this work changes unilaterally.

### Hard constraint — sanitisation

This repo is public; the corpus is not. Sensitive paths include an employer group, a private
media project, several personal projects, a doctoral proposal, and a security tool. **Only
generic material lands here:** patterns, `<placeholder>`-abstracted templates, ways of working.
Never a company/client name, codename, hostname, URL, repo name, credential, person name, or
ticket ID. Short control words (`go`, `continue`, `merged`) are safe to quote verbatim.

### Method (reusing the user's own)

`extract-style-profile.py` — already copied into four of the user's projects — implements
HyPoGenic-style extraction (Garbacea & Tan, arXiv:2505.00038): *propositional hypotheses backed
by direct evidence quotes*. The patterns doc adopts that shape — every claim carries a
sanitised quote or a frequency. This is the user's existing methodology turned on his own
working style, not a new invention.

### Confirmed decisions

1. **Repo docs + a portable snippet.** Do **not** create or modify `~/CLAUDE.md`.
2. **Recover from GDrive and keep a permanent de-duplicated local corpus**, outside the repo.
3. **Build a reusable mining tool** in `tools/`.
4. **Stop the retention deletion**: set `cleanupPeriodDays: 3650` in `~/.claude/settings.json`.
5. **Recover everything** — all 69 archives, not a boundary subset.

Corpus path: **`~/claude-corpus/`** — outside `~/.claude` for two independent reasons:
`claude-backup.sh` tars `~/.claude` wholesale with **no excludes** (a corpus inside would
compound into every future daily archive), and tar restores original mtimes, so anything
restored under `~/.claude/projects/` would be **deleted again** by the next cleanup run.

### Out of scope

- Editing `~/CLAUDE.md` or any global rules file.
- claude.ai web conversations (a separate extractor already exists for those).
- Changing the backup script's retention — 69 archives and growing is **reported**, not fixed.
- Re-mining after each future session; the tool makes that a re-run, not a project.

## Implementation

Branch `docs/claude-working-patterns` off latest `main`, one PR to `JohnnyFoulds/caissa`.
No `Co-Authored-By` trailer, no AI footer — the global hook rejects them.

### Step 0 — persist this plan

Honouring the standing requirement, commit this plan into the repo before the rest of the work,
as `docs/features/claude-working-patterns/implementation_plan.md`.

### 1. Stop the ongoing deletion (do this first — it is the only time-sensitive step)

Add `"cleanupPeriodDays": 3650` to `~/.claude/settings.json`, preserving all existing keys.
Cleanup runs at startup, so until this lands every day costs more sessions. Verify by
re-reading the file and confirming the JSON still parses.

### 2. Recover the full corpus into `~/claude-corpus/`

Verified environment: **bsdtar 3.5.3 only**, no GNU tar. `--include=<glob>` works; **`--wildcards`
does not exist on bsdtar** — do not copy GNU recipes. `*` crosses `/`, which is convenient here
because it also captures subagent transcripts.

Verified working form, one archive at a time:

```
rclone cat gdrive:claude-backups/claude-backup-<DATE>.tar.gz \
  | tar -xzf - -C ~/claude-corpus/raw/<DATE> --include='*/projects/*.jsonl'
```

**All 69 archives**, 18.6 GiB, at a measured **~372 KB/s** → **~14 h wall clock**. gzip must be
decompressed sequentially, so listing an archive costs the same as extracting it; there is no
cheaper survey pass. Therefore:

- Run as a **resumable background job** — a loop that skips any date whose marker file already
  exists, so it can be interrupted and restarted without re-streaming.
- Process **newest-first**, then the known-high-yield dates (2026-08-12, 2026-08-03, 2026-06-18),
  then the remainder. Useful data lands in the first hour; the long tail is completeness.
- Write a per-archive manifest (session IDs + sizes) so progress is inspectable mid-run and the
  final coverage report is a cheap read rather than a re-scan.
- Three dates have **no archive** (the machine was asleep at 02:00): 2026-06-28, 2026-08-17,
  2026-08-21. Skip without treating as failure.
- **Available accelerator, not applied by default:** runs of consecutive archives share a byte
  size (e.g. five dates at 420.2 MB) and almost certainly share a session set, so one
  representative per run would cut hours. It is a heuristic, so full recovery ignores it —
  noted in the runbook as an opt-in.

Then de-duplicate into `~/claude-corpus/sessions/` by session UUID, keeping the largest copy
(sessions grow as they run). Because the backup script tolerates `tar` exit 1, a session being
appended at 02:00 can be **truncated mid-line**; parse line-by-line, tolerate a bad final line,
and prefer a longer copy from an adjacent date. Archives cannot be de-duplicated by hash — all
69 have distinct MD5s despite identical byte sizes.

Do not pipe a stream into `head`: it kills the transfer and wastes it. Capture output once.

Expect the OAuth access token to refresh mid-run (it expires within the hour); a refresh token
is present and rclone handles this, but a 14 h job will cross several refreshes.

### 3. `tools/claude_mine.py` (new)

Stdlib-only miner, RST docstrings per `docs/standards/docstring-standards.md`.

- Sources: `history.jsonl` (`display`, `timestamp`, `project`, `sessionId`), session `*.jsonl`
  (`message.role == "user"`; content str or `[{type:"text"}]`), and the recovered corpus.
- Drop harness noise: leading `<`, `This session is being continued`, `Caveat:`, tool_result
  blocks. Tally `/slash` commands separately — UI usage, not prompts.
- Bucket short control directives vs substantive prompts; classify into archetypes.
- Detect `ExitPlanMode` calls and the following user turn, so the approve/amend/reject ratio is
  **recomputable** rather than a one-off number.
- Tolerate truncated final lines (see above) instead of aborting on a `JSONDecodeError`.
- **Sanitiser** (safety-critical): redact absolute paths, emails, URLs, IPs, AWS ARNs and
  account IDs, long tokens, and a configurable project-name denylist. Redacted by default; raw
  output requires an explicit `--unsafe` flag.

Ground truth for verification: `commit and push`≈21, `continue`≈49, `what's next?`≈39,
`yes`≈13, `open`≈14, `go`≈27 from the session corpus; `yes`≈46, `continue`≈19, `done`≈18,
`what's next?`≈17, `do it`≈16, `go`≈13, `push`≈11 from `history.jsonl`.

### 4. `docs/claude_code/working-patterns.md` (new) — primary deliverable

- **Control vocabulary** — the short-directive lexicon with counts; verbatim, safe.
- **Plan feedback moves** — headline section. Per move: trigger, abstracted phrasing,
  frequency, and what Claude should do differently. Lead with the two structural facts:
  silence means approval, and prose means something is wrong.
- **What a good plan looks like here** — the acceptance checklist (Context; Verification as
  runnable commands annotated with what each proves; named trunk/branch; one phase = one branch
  = one PR; explicit out-of-scope; reuse-don't-reinvent; landmine register; standing-requirements
  table once a plan exceeds ~40k chars).
- **Session lifecycle** — the four-token control loop
  (`plan → silent approve → go/continue → commit and push → user merges → "merged, what's next?"`),
  the three distinct session openings, and the git-hygiene close-out.
- **Context-exhaustion playbook** — tracking documents, session-resumability, fan-out as a
  context-budget strategy, commits as anti-amnesia checkpoints.
- **Habits worth knowing** — the post-failure five-step sequence, the taste-dispute →
  measurable-spec → test ladder, the idea escalation ladder, artifact harvesting.
- **Standing preferences** — the `always`/`never` rules, abstracted.
- **Recurring corrections** — the 19 anti-patterns, ranked; source for the portable snippet.

### 5. `docs/claude_code/prompt-library.md` (new)

Project-agnostic templates with `<placeholder>` tokens. Anchored by the signature review macro
written down properly for the first time, with its slot-fills (object / predicates /
disposition — including *save* the gaps that cannot be closed / intensifiers). Then the other
recurring archetypes: claim-by-claim verification against ground truth, adversarial-persona
review, deep research with rigour, repo-state close-out audit, process-conformance audit,
make-it-self-verifying, reproducibility harness, viability interrogation, standards import,
orientation/SITREP. Each: purpose, when to use, template, notes.

### 6. `docs/claude_code/session-archaeology.md` (new)

Runbook for mining one's own history: backup architecture (`~/bin/claude-backup.sh` + launchd
`com.johnnyfoulds.claude-backup`, daily 02:00 → `gdrive:claude-backups`, logs in
`/tmp/claude-backup.*.log`); data layout of `history.jsonl`, session files, subagent
transcripts, and `plans/`; the **verified** bsdtar streaming commands with the flag gotchas;
how to pick boundary archives from the size series; `claude_mine.py` usage and the sanitisation
workflow. Records the operational findings: the `cleanupPeriodDays` root cause, the
restore-into-`~/.claude` trap, no retention policy on the backup, no excludes, three missed
backup dates where the machine was asleep at 02:00, and distinct-MD5s-despite-equal-sizes.

### 7. `docs/claude_code/claude-md-snippet.md` (new)

The distilled rules as one copy-paste block for any project's `CLAUDE.md`, drawn from the
recurring-correction and standing-preference sections — short, imperative, no Caissa specifics.

### 8. Edits to existing files

- `docs/claude_code/prompts.md` — retitle as the Caissa/SDD-specific library; move the generic
  half of its Usage Patterns into `working-patterns.md` and cross-link, keeping the
  SDD-pipeline-specific patterns in place.
- Add the new docs to the four existing index points: `CLAUDE.md:113`,
  `docs/process/sdd-workflow.md:216`, `docs/standards/spec-driven-development.md:97`,
  `docs/templates/README.md`.
- `CHANGELOG.md` — one bullet under `[Unreleased] → Added`.

## Verification

1. **Sanitisation gate (blocking).** Grep the staged diff for the denylist: every one of the 31
   project directory names, plus `arn:`, `aws`, `@`, `http`, `/Users/`. Zero hits outside
   placeholder tables. Then read the full rendered diff — this is Gate C and the one gate that
   matters, because a leak is unrecoverable once pushed to a public repo.
2. **Retention fix.** `~/.claude/settings.json` parses and contains `cleanupPeriodDays: 3650`
   with every pre-existing key intact (diff against a copy taken before the edit).
3. **Tool correctness.** `python3 tools/claude_mine.py` reproduces the ground-truth counts in §3
   from both sources, and recomputes the plan approve/amend/reject ratio. Run the sanitiser over
   a fixture seeded with a fake ARN, email, URL, and absolute path; confirm all redacted. Feed
   it a deliberately truncated jsonl and confirm it does not abort.
4. **Recovery correctness.** Report unique session IDs recovered versus the 89 currently local —
   the boundary archives alone are known to hold ~131 absent sessions and ~1,065 subagent
   transcripts, so a full run must meet or exceed that. Confirm the 66 expected archives were
   streamed and the 3 missing dates were skipped as expected. Confirm nothing was written inside
   `~/.claude`, so neither tomorrow's 02:00 archive grows nor the cleanup run deletes the
   recovered files. Spot-check that de-duplication kept the largest copy of a session present in
   several archives.
5. **Evidence discipline.** Every claim in `working-patterns.md` carries a frequency or a quote;
   no claim rests on a single observation. Claims corroborated by both analysis passes are
   marked as such.
6. **Docs build.** `make docs` with zero new warnings; all cross-links resolve.
7. **No regression.** `tests/test_classical_invariant.py` green. Untouched by construction —
   docs plus one new `tools/` script, nothing under `bin/`.

### Sequencing

The retention fix and the docs are not blocked on the 14 h recovery. Order of work: retention
fix → start the background recovery job → build `claude_mine.py` → write the four docs from the
analysis already completed → refresh the numbers from the recovered corpus once the job lands →
edits to existing files → PR. Only step 4's frequency figures depend on the recovery finishing,
so the PR can be prepared while it runs and the counts confirmed before merge.
