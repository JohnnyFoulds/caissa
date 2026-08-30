# CLAUDE.md — Caissa (Lucas Chess R6 fork)

## Repository Purpose

Caissa is a fork of Lucas Chess R6 that adds a Mode system (Coach, Analyse, Train, Compete, Just Play) and a Theme overlay system on top of the upstream desktop chess application. Built with Python 3.13 + PySide6.

**CRITICAL SECURITY RULE:** Never push to `lukasmonk/lucaschessR6`. All pushes go to `JohnnyFoulds/caissa` only.

---

## Repository Structure

```text
bin/Code/
├─ Main/WBase.py          # Toolbar injection point (pon_toolbar, ~line 503)
├─ Main/LogSetup.py       # App logging configuration (entry point only)
├─ Config/WindowConfig.py # General Configuration dialog
├─ UIModes/
│  ├─ UIModes.py          # Mode loader: active_mode(), toolbar_inject()
│  └─ actions/            # Per-mode action registrations + hooks
│     ├─ coach_home.py    # Coach landing screen (2×2 card grid)
│     └─ <mode>_ui.py     # Optional mode UI hook (patch_config_form, etc.)
├─ Rpa/                   # RPA layer (closed-loop automation engine)
│  ├─ Errors.py           # CaissaError + RpaError hierarchy
│  ├─ Types.py            # Rect, ElementRef, Snapshot (zero third-party imports)
│  ├─ Driver.py           # Driver base + QtDriver (only Qt-touching class in Rpa/)
│  ├─ Runner.py           # Step-pumped state machine
│  └─ ...                 # See docs/rpa/ for the full architecture
└─ Fritz/                 # Fritz visual layer (fixed window, panes, LCD clocks, ribbon)
   ├─ Types.py            # Frozen dataclasses (zero third-party imports)
   ├─ Errors.py           # FritzError(CaissaError) hierarchy
   ├─ QssRules.py         # scan_qss / template_gaps / qproperties — pure
   └─ ...                 # See docs/fritz/ for the full architecture

Resources/
├─ Modes/                 # Mode JSON files (classical, Coach, Analyse, Train, Compete, Just Play)
├─ Styles/                # QSS themes + optional <name>.ui.json overlays
├─ Ribbons/               # Ribbon content maps (<name>.json, one per Fritz mode)
└─ Rpa/                   # RPA assets: Templates/, Reference/, Fixtures/

docs/
├─ theme-mode-system.md   # SDD: Theme/Mode overlay architecture
├─ standards/             # Engineering standards (see below)
├─ engines.md
├─ process/
│  └─ sdd-workflow.md     # SDD/TDD workflow — THE ROUTINE + 8 gates
├─ features/              # Per-feature SDD artefacts
│  ├─ rpa-layer/          # RPA layer spec, steps, implementation plan
│  └─ fritz-polish/       # Fritz Polish spec, steps, implementation plan
├─ fritz/                 # Fritz layer product documentation
├─ rpa/                   # RPA layer product documentation
└─ templates/             # SDD artefact templates
```

---

## Key Architecture Concepts

### The Classical Invariant
`classical` mode + no theme overlay = upstream Lucas Chess R6 exactly. This is the regression safety net. The only permitted addition in classical mode: the `UI mode` combobox so users can switch to a Caissa mode.

### Mode System
- Mode JSON files: `Resources/Modes/<name>.json` — define `toolbar` allowlist, `menu_keys` allowlist, `toolbar_inject` list
- Active mode stored in config as `x_ui_mode`
- `UIModes.active_mode()` returns the current mode dict
- `WBase.pon_toolbar` calls `UIModes.toolbar_inject()` and prepends injected actions

### Theme Overlay System
- `Resources/Styles/<name>.ui.json` — renames/hides fields in Configuration dialog
- Applied at dialog-open time via `OverlayForm` proxy (`bin/Code/Config/FormOverlay.py`)
- Absence of `.ui.json` = upstream behaviour, zero changes
- Mode-owned config section: `config_section` key in mode JSON appends a mode-owned tab
- Mode UI hooks: `bin/Code/UIModes/actions/<mode>_ui.py` with optional `patch_config_form`
- See `docs/theme-mode-system.md` for the full spec

### Purity Tiers

New Caissa code lives in a flat feature package under `bin/Code/` (e.g. `bin/Code/Fritz/`, `bin/Code/Rpa/`). Every module declares a purity tier:

| Tier | May import | Examples |
|---|---|---|
| Dependency-free | stdlib only | `Types.py`, `Errors.py` |
| Pure | stdlib + dependency-free + Qt-free upstream | `BoardFit.py`, `QssRules.py` |
| Adapter | upstream `Code.*` + pure + stdlib | `ThemeGateway.py`, `ModeGateway.py` |
| Qt allowlist | Qt + everything above | `WFritzPane.py`, `WRibbon.py` |

Enforced by `tests/unit/<feature>/test_completeness.py` using transitive AST import resolution. See `docs/standards/architecture.md` for the full rules.

### Config Keys
- `x_ui_mode` — active Mode (feature-set filter)
- `x_style_mode` — active Theme (visual appearance)
- `x_style` — Qt widget renderer (`Fusion`, `macOS`, etc.)

---

## Non-Negotiable: Real Execution Before Done

**A feature is not done until it has been run for real and the output verified.**

Mock/fake tests (FakeCpu, FakeDriver, StringIO, synthetic fixtures) prove internal code
consistency only. They do not prove the feature works. Before any feature with a
real-execution tier is declared complete:

1. **Run it** — actually execute the feature against real inputs (real binary, real process,
   real hardware).
2. **Observe the output** — a real move, a real response, a real file written. Not
   "it should work" or "the unit tests pass."
3. **Verify correctness** — the output matches expectations, not just "non-null."

For any opt-in test tier (`retro_rom`, `rpa_ui`, `rpa_cv`, etc.):
- Real assertions only — `pytest.skip()` is for environment capability checks,
  never a permanent placeholder for unwritten tests.
- The tier must actually run and pass before the feature closes.
- Evidence of the run goes in the PR body.

This applies to work done by fork agents too: agents must execute the end-to-end path
and report observed output — green unit-test-with-fakes is not sufficient evidence.

**Retro Engine smoke test** (run this before calling it done):
```bash
printf 'uci\nisready\nposition startpos\ngo\nquit\n' | tools/caissa-retro
# Must produce:  bestmove <real-move>  (NOT bestmove 0000)
```

Full rule: `docs/process/sdd-workflow.md` §Test Management, Gate D, Gate E.

---

## Standards

Full standards documents are in `docs/standards/`. Summary of key rules:

### Branching and PRs

**Never commit directly to `main`.** All work goes on a branch and merges via a PR.

```bash
git checkout -b feat/<topic>   # branch from latest main
# ... commits ...
gh pr create --repo JohnnyFoulds/caissa   # open PR
gh pr merge --repo JohnnyFoulds/caissa <N> --squash --delete-branch
git checkout main && git pull
```

**Auto-merge policy (current):** Claude Code approves and merges PRs automatically when a feature
is done and work is moving to the next task. This will switch to manual review later.

Branch naming: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, `chore/<topic>`

See `docs/standards/coding-standards.md`.

### Commit Messages
Conventional Commits format: `type(scope): subject`

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`  
Scopes: `modes`, `toolbar`, `config`, `coach`, `ui`, `engine`, `theme`, `rpa`

Non-trivial commits need a body with bullet points. See `docs/standards/coding-standards.md`.

### Specification-Driven Development
Write an SDD before implementing any non-trivial feature. Use the feature-directory
convention: `docs/features/<name>/` with `initial_idea.md`, `feature_spec.md`,
`feature_steps.md`, and `implementation_plan.md`. See `docs/standards/spec-driven-development.md`.

The full SDD/TDD routine and 8-gate checklist: `docs/process/sdd-workflow.md`.  
Templates: `docs/templates/`.  
Prompt library (SDD/Caissa): `docs/claude_code/prompts.md`.  
Prompt library (general): `docs/claude_code/prompt-library.md`.  
Working patterns: `docs/claude_code/working-patterns.md`.  
Session archaeology runbook: `docs/claude_code/session-archaeology.md`.  
Portable CLAUDE.md snippet: `docs/claude_code/claude-md-snippet.md`.

Existing flat specs (grandfathered): `docs/theme-mode-system.md`, `docs/ui-testing.md`.

### UI Design Process
Design in the shipping medium (PySide6 + real `.qss`), never in a design tool. A two-round mockup
approval gate must pass before any visual phase begins. Custom-painted widgets take their design
values from the `.qss` via the E1-E4 `qproperty-` contract. See `docs/standards/ui-design-process.md`.

### Architecture
New Caissa code goes in a flat feature package under `bin/Code/`, pure by default, with Qt confined
to a named allowlist and purity enforced by an AST test. Seams are plain base classes; no `abc.ABC`
and no `typing.Protocol`. See `docs/standards/architecture.md`.

### Docstrings
RST/Sphinx style for all new public modules, classes, and functions.
See `docs/standards/docstring-standards.md`.

### Error Handling
- New Caissa modules define domain exceptions inheriting from `CaissaError`
- Always `raise ... from exc` when wrapping lower-level exceptions
- Every `logger.error()` at a catch site must include `exc_info=True`
- See `docs/standards/error-handling.md`

### Logging
- `logging.getLogger(__name__)` at module level
- `%s`-style lazy formatting, not f-strings
- See `docs/standards/logging-standard.md`

### Changelog

**`CHANGELOG.md` must be kept up to date.** Every PR that adds, changes, or fixes
something user-visible or architecturally significant must include a `CHANGELOG.md`
update in the same commit.

Rules:
- New entries go under `## [Unreleased]` → appropriate sub-heading
  (`### Added`, `### Changed`, `### Fixed`, `### Removed`)
- One bullet per logical change; reference the PR number `(#N)` or commit where useful
- When a release is tagged, rename `[Unreleased]` to `[x.y.z] — YYYY-MM-DD` and open
  a fresh `[Unreleased]` section above it
- Do **not** document internal refactors, test-only changes, or doc-only commits unless
  they change observable behaviour or the public API surface

### Code Style
- Do not reformat existing Lucas Chess R6 code
- No banner-style comment dividers — use `#region` / `#endregion`
- No default comments — only add when the WHY is non-obvious
- See `docs/standards/coding-standards.md`

---

## Development Commands

Run from the repo root so `from tests.helpers import …` resolves.

```bash
make lint        # ruff check --config ruff.toml  (mandatory --config, never bare ruff)
make test        # -m "unit or rpa"               default suite, no Qt
make test-all    # by path                         cross-checks markers vs filesystem
make cov         # branch coverage, --cov-fail-under=90
make docs        # sphinx -W --keep-going          zero warnings required at Gates H and E
make test-ui     # -m "ui or rpa_ui"               launches the real app out-of-process
```

Order to run: `make test` (seconds, no Qt) → `make test-all` → `make test-ui` (minutes, real app).

**Pytest markers** — every collected test declares exactly one as a module-level `pytestmark`:

| Marker | What it covers |
|---|---|
| `unit` | fast, no Qt, no I/O |
| `ui` | in-process Qt, `QT_QPA_PLATFORM=offscreen` |
| `rpa` | out-of-process, bare remote-control verbs |
| `rpa_ui` | out-of-process, widget-level verbs |
| `rpa_cv` | out-of-process, CV template assertions; auto-skips when `cv2` missing |

Config files: `ruff.toml` (lint), `requirements-dev.txt` (dev deps), `.coveragerc` (coverage omit list + 90% gate).

---

## Running the App

```bash
tools/caissa               # foreground
nohup tools/caissa > /tmp/caissa.log 2>&1 &   # background
```

---

## Development Notes

- The config pickle is at `UserData/__Config__/lk.pk2`. To force a mode for testing:
  ```bash
  python3 -c "import pickle; p='UserData/__Config__/lk.pk2'; cfg=pickle.load(open(p,'rb')); cfg['x_ui_mode']='Coach'; pickle.dump(cfg, open(p,'wb'))"
  ```
- Stockfish engines use NNUE files — ensure they are not LFS stubs (see NNUE bug fix in memory)
- When adding a new mode JSON, include `TB_OPTIONS` in the `toolbar` allowlist so users can always reach Configuration

---

## RPA Pattern for Automation — Non-Negotiable

Any time you need to interact with a running application (FS-UAE, DOSBox, any external
program), you **MUST** implement the interaction as `Activity` subclasses in
`bin/Code/<Target>/Activities.py`, following the pattern in `bin/Code/Dos/Activities.py`.

**NEVER write a `/tmp` script for automation.** `/tmp` scripts have no precondition, no
postcondition, no settle/verify loop, and no unit tests. They cannot be reproduced,
retried, or tested in isolation.

The UiPath analogy: every UI interaction is a named Activity in a Sequence. You test
the activity in isolation, verify it passes, then chain it. You do not write VBA to
click a button outside the workflow.

### Mandatory steps for any new automation target

1. `bin/Code/<Target>/Driver.py` — screenshot + input events for that app (see `Dos/Driver.py`)
2. `bin/Code/<Target>/Activities.py` — `Activity` subclasses with precondition/execute/postcondition
3. `tests/unit/<target>/test_activities.py` — unit tests using a `FakeDriver` with pre-captured images
4. Test each Activity in isolation before chaining
5. Only then run Activities in a runner loop

### What each Activity must declare

- `precondition(img, ctx) → bool` — is the app in the right state?
- `execute(driver, ctx) → None` — issue **one** driver action; never loop or sleep here
- `postcondition(img, ctx) → bool` — did the action take effect? (polled by the runner)
- `settle_ms` — wait after execute before first postcondition poll
- `verify_ms` — max time for postcondition to become True before DECIDE_RECOVERY

### Where calibrated constants go

Board coordinates, colour thresholds, window sizes: **immediately** into
`bin/Code/<Target>/BattleChess.py` AND into this CLAUDE.md. Not in `/tmp`. Not
discovered-and-discarded. Every constant must survive context compaction.

See `docs/rpa/new-target-guide.md` for the full step-by-step guide.
See `docs/rpa/uipath-mapping.md` for the UiPath ↔ Caissa vocabulary map.

---

## Context Compaction — Preventing Knowledge Loss Across Sessions

Context compaction is automatic and lossy. When it fires, tool output, /tmp
contents, calibrated constants, and mid-analysis decisions are dropped. This
has caused repeated rediscovery of binary offsets, DOS calibration constants,
and engine phase work.

### Six non-negotiable rules

**1. CLAUDE.md is the only safe persistent store.**
Everything a future session *must know* goes into CLAUDE.md **immediately when
discovered** — not at the end, not after confirmation. Compaction re-reads
CLAUDE.md every turn; it does not preserve conversation history.
`/tmp` is invisible after compaction. Never use it for knowledge.

**2. Compact at 60%, not 95%.**
Run `/compact focus on <task>. Key decisions: <X>. Next step: <Y>. Preserve: <constants>.`
proactively at a natural boundary — after merging a PR, before a long binary
analysis run, when pivoting from investigation to implementation.
Never wait for autocompact to fire mid-analysis; the model is least capable at 95%.

**3. End every session with a git commit + a progress note.**
Before `/clear` or end-of-session, write `docs/features/<name>/progress.md` with:
- What was accomplished this session
- What is next
- Any constants, offsets, or invariants not yet in CLAUDE.md

Then commit everything. The git log + `progress.md` = the session handoff.

**4. Break long tasks into phases; one PR per phase.**
Each phase must be small enough to complete in one session, end with a merged PR,
and have all findings committed to code + CLAUDE.md before closing.
"Phase complete" = code committed + tests pass + CLAUDE.md updated.

**5. Use fork/subagents for investigation work.**
Binary analysis, calibration runs, and long debugging sessions generate enormous
tool output that pollutes the parent context. Use `Agent(subagent_type: "fork")`
for any research task where only the conclusion matters; the fork keeps its
tool noise out of the parent context.

**6. Session start ritual — always do these three steps before writing code.**
```bash
git log --oneline -10                          # what was last committed?
cat docs/features/<name>/progress.md           # what's next?
grep -n "<topic>" CLAUDE.md                    # what constants do I need?
```
This prevents the "guess at what happened" failure mode at a cost of 3 tool calls.

---

## DOS/Battle Chess Automation Layer (`bin/Code/Dos/`)

### Python interpreter
All DOS-layer code and automation scripts **must run under `/opt/homebrew/bin/python3.14`**.
That is the only Python on this machine that has `Quartz`, `AppKit`, `Pillow`, and `numpy`.
The conda Python 3.13 at `/opt/homebrew/Caskroom/miniconda/base/bin/python3` lacks Quartz
and will silently fail (window detection returns None, all activities timeout).

### Game directory
Battle Chess DOS files live at `/Users/johannes/Documents/dosbox/oldgames/bc/`.
The `DosBoxProcess` constructor takes `(_GAME_DIR, _LAUNCH_CMD)` from `BattleChess.py`.

### 2D mode detection (calibrated, do not change without re-measuring)
Board-coloured pixel fraction over `_BOARD_REGION=(100,38,443,379)`:
- **2D flat board**: fraction ≈ 0.40 → `_is_2d_mode` returns True if fraction ≥ 0.25
- **3D perspective board**: fraction ≈ 0.14 → _is_2d_mode returns False
- **Title screen / loading**: fraction can be 0.05–0.14 (decorative chess elements)
- `_board_visible` uses threshold 0.10 to confirm ANY game content is on screen

The bot/top ratio heuristic (ratio < 1.15 → 2D) was an incorrect approach; use absolute
fraction threshold 0.25 instead.

### Menu navigation to '2D Board' (calibrated)
Only works when DOSBox is on a **secondary display** (x < 0 or x > 2559 on this machine).
On the primary display the menu bar appears but the Settings dropdown does not open.

```
# All coordinates are window-relative
MENU_TRIGGER = (320, 33)     # right-click-hold here opens Settings menu
ITEM_2D_BOARD = (410, 180)   # drag to here while holding right button, then release
```

Sequence: `MOUSEMOVED → (320,33)` → wait 0.35s → `RDOWN (320,33)` → wait 0.6s →
`RDRAG (410,180)` → wait 0.3s → `RUP (410,180)`.

The cursor MUST be moved to the trigger position with MOUSEMOVED before RDOWN,
otherwise SDL does not register a cursor-enter event.

### Two-click move (confirmed working)
Battle Chess 2D uses **two-click** move mechanics, NOT drag-to-move.

```python
_COL_X = {"a":127,"b":183,"c":238,"d":293,"e":349,"f":404,"g":459,"h":515}
_RANK_Y = {"1":393,"2":345,"3":298,"4":251,"5":203,"6":156,"7":109,"8":61}
```

Required event sequence for each click:
1. `MOUSEMOVED → square` (SDL needs cursor-enter before click; without this, click is ignored)
2. wait 0.2s
3. `MOUSEDOWN → square`
4. wait 0.08s
5. `MOUSEUP → square`

Full move = SourceClick (click source) + settle 400ms + DestClick (click dest) + settle 300ms.
Activities: `SourceClick("e2")` then `DestClick("e4", "e2")`.
`DragToDest`, `DragRelease`, `SourceDragDown` are legacy aliases — do not use for new code.

### Move postcondition (compare BOTH squares vs baseline)
`has_piece_at` gives false positives on light board squares and cursor artefacts.
Use `inner_square_changed(baseline, img, sq)` with the pre-drag baseline instead:
- `inner_square_changed(baseline, img, from_sq)` → source changed = piece left
- `inner_square_changed(baseline, img, to_sq)` → dest changed = piece arrived

Both must be True. Baseline is captured in SourceDragDown.precondition before any cursor movement.
This is implemented in `DragRelease.postcondition`.

### WaitCpuReply timing and baseline
Battle Chess CPU think time varies by difficulty level. On hard settings it can
exceed 60 seconds. `verify_ms=90000` (90s) is the current setting.
`settle_ms=3000` — mandatory, to let selection-highlight artefacts from our own
click decay before polling starts. Without this, adjacent-square artefacts fire
within 1-2 seconds as false CPU replies.

Use `ctx["after_our_move"]` as the comparison baseline when available (set by
`DestClick.postcondition`). This is a stable post-move screenshot where click
artefacts at adjacent squares (e.g. e3 adjacent to clicked e4) are already
"baked in" — they won't fire as false CPU-move detections.
Fall back to pre-move baseline + exclusion of our from_sq/to_sq only if
`after_our_move` is not yet set.

After `_infer_from_candidates` infers `cpu_from`/`cpu_to`, add a double-check:
`inner_square_changed(ref, img, cpu_from) and inner_square_changed(ref, img, cpu_to)`
must both be True. This mirrors the DestClick postcondition and rejects noisy candidates.

### CPU move direction rule — brightness DELTA
**NEVER use `brightness(before)` alone to infer from/to.** The old "brighter before = FROM"
heuristic fails for black pieces: dark pieces are darker than empty squares, so the
direction is inverted (c7c5 is reported as c5c7).

Correct rule in `_infer_from_candidates` and `infer_move`:
```python
delta = brightness(after, sq) - brightness(before, sq)
# more-positive delta = square got brighter = piece LEFT = FROM
# more-negative delta = square got darker = piece ARRIVED = TO
```
Empirically verified: 1.e4 → c7c5 (Sicilian), consistent across two runs.

### Quartz keyboard events — focus BEFORE keypress
`CGEventPost(kCGHIDEventTap, key_event)` fires at whatever has OS focus. If the user is
typing elsewhere, ENTER goes to their window, not DOSBox. Always:
1. Call `driver.focus()` first
2. `time.sleep(0.3)` — let the OS commit focus
3. Then send the key event

### Quartz mouse events
`CGEventPost(kCGHIDEventTap, ev)` routes events globally to whatever window is
frontmost. Call `driver.focus()` before any input sequence. The user moving the
mouse or typing during automation will disrupt the sequence — there is no reliable
way to prevent this with HID-level events on macOS without Accessibility permission
to inject directly into a process.

### Screenshot capture
`screencapture -x -o -l <wid>` captures by Quartz window number. `-o` removes
the macOS drop shadow so the image is exactly 640×428 with coordinate (0,0) at
window top-left. Using `-R x,y,w,h` is unreliable when the window moves displays.
