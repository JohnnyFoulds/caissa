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

### Activity development protocol (one activity at a time)

For EACH activity, follow this cycle before moving to the next:

1. **Code it** — write the activity class (precondition / execute / postcondition)
2. **Unit test it** — add `FakeDriver` tests in `tests/unit/<target>/test_activities.py`; run `make test`
3. **UI test it** — run the single activity against the real running process and observe the result
4. **Iterate** — if UI test fails, go back to step 1 and fix the activity; do not move on
5. **Document** — once it works, commit constants to `bin/Code/<Target>/BattleChess.py` and CLAUDE.md
6. **Then and only then** — add the next activity to the chain

**Never chain two untested activities.** If activity N is known-good and activity N+1 fails, you know
exactly where the bug is. If you chain 5 untested activities and something breaks, you don't know which one.

This is the UiPath Test Sequence button analogy: run each activity in isolation before wiring it in.

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

### Exception taxonomy — non-negotiable

Two exception types govern how a broken automation step is handled.

**SystemException** — the Activity or driver is broken.
- Signal: an Activity fails **every** attempt across all retries (postcondition never True).
- Rule: **STOP immediately.** Do not continue the workflow. Fix the Activity in isolation.
- Protocol: (1) run the single Activity against the live app; (2) take a screenshot immediately
  after execute; (3) fix the root cause (code, calibration, or driver); (4) verify the Activity
  passes alone before re-chaining the workflow.
- Adding more retries to a SystemException is WRONG. Retries are for transient environmental
  flakiness only, not for fundamentally broken steps.

**BusinessRuleException** — the automation ran correctly but the outcome is unexpected.
- Signal: postcondition returned True but a later step found an unexpected state.
- Rule: log full context (screenshot + ctx), decide if recovery is possible, compensate or halt.

**Practical rule:** If a core Activity has NEVER succeeded in the current session, treat it
as a SystemException — stop, diagnose, fix, verify, then re-run. Never move on.

---

## Retro Engine Emulator (`bin/Code/Retro/Think.py`) — Investigation 2026-08-31

The Battle Chess Amiga binary runs under Unicorn M68K emulator. The goal is for the AI to write a valid best-move to `AI_BEST_MOVE_ADDR` so `caissa-retro` can return a real move instead of falling back to python-chess.

### Key addresses (confirmed from disassembly + hooks)

| Symbol | Address | Notes |
|---|---|---|
| `AI_OUTER_DRIVER_ADDR` | `0x81DC` | Entry point; emulation starts here |
| `AI_BEST_MOVE_ADDR` | `0x3662` | Where search writes best move (to_sq @ +0, from_sq @ +2) |
| `_AI_BEST_MOVE_FINAL_ADDR` | `0x365A` | Phase-2 final result slot (from_sq @ +0, to_sq @ +2) |
| `_ABORT_FLAG_ADDR` | `0x4A4A` | Non-zero → inner search exits; ROM init = 0xFFFC, zero before search |
| `_LOOP_FLAG_ADDR` | `0x4A5A` | Must be 2 for outer driver to loop; BSS = 0x0278 (exits immediately) |
| `_WAIT_FLAG_ADDR` | `0x4A92` | Timer wait loop; zero before search |
| `_SEARCH_COMPLETE_FLAG_ADDR` | `0x8270` | ROM code bytes = 0x0003; zero before search or inner loop exits immediately |
| `_AI_INIT_PATH_FLAG_ADDR` | `0x07D2` | ROM bytes; zero so AI_INIT takes clean depth-1 path |
| `_DE7A_ADDR` | `0xDE7A` | Search-iteration handler; each call = one alpha-beta tree walk |
| `_TC_ADDR` | `0x008A` | ElapsedTime stub; NOOP'd by `_hook_tc` |
| `_ABORT_CHECK_ADDR` | `0x0C2CE` | `tst.w [0x4A4A]` — node counter hook fires here |
| `PLAYER_TYPE_BASE` | `0x07D4` | ROM opcodes, NOT player data. `[0x07D4+color*2]` must be written to 1 (Human) before search |
| `BOARD_ARRAY_ADDR` | `0x30F4` | 128×4 bytes; `[sq*4]=piece_type, [sq*4+1]=color` |
| BSS range | `0x3000..0x5FFE` | Pre-init to `0x0278` before each search (game's own 0x8820 routine bypassed) |

### What currently works (as of 2026-08-31)

```
loop=2 820c=2 tc=1 de7a=30 nodes=31 81f2=1 c198=1
```
- Outer driver loops twice ✓, DE7A fires 30 times ✓, 31 search nodes ✓, phase 0 returns ✓
- `_hook_de7a` sets `[0x4A4A]=1` after 30 calls → inner search exits cleanly
- `_hook_diag_81f2` stops emulation at phase-0 return if a valid move is found

### What is still broken

`best=94620002` → `to_sq=0x9462` (garbage), `from_sq=0x0002` (c1 Bishop = White piece).
Engine falls back to python-chess g8h6.

**Two confirmed write sites at `AI_BEST_MOVE_ADDR` (from `_mem_write` hook):**

- **PC=0xD490** — writes `to_sq=0x0002` or `0x0000`, D1=2 or 0, nodes=0 at write time
- **PC=0xD8FE** — writes `to_sq=0x9462`, D1=0x9462, nodes=0 at write time

Both fire with `nodes=0` — before any alpha-beta nodes are counted. This is initialisation code, NOT the search. The actual search (31 nodes) may write valid moves but they get overwritten.

**ROM bytes at those addresses** (for next session to decode):
```bash
xxd -s $((0xD490 + 0x28)) -l 32 Resources/Retro/BattleChess.amiga
xxd -s $((0xD8FE + 0x28)) -l 32 Resources/Retro/BattleChess.amiga
```

### Next step

Determine whether the valid best-move is ever written to `AI_BEST_MOVE_ADDR` DURING the 31-node search, before the init code at 0xD8FE overwrites it. Add snapshot logic in `_hook_abort_check` that captures the value at each of the 31 nodes and logs it. If any of the 31 snapshots are a valid Black pawn move, the fix is to stop at the right moment.

If no node produces a valid move, the search itself has a bug (wrong piece iteration, wrong color filtering, wrong board state) and needs deeper diagnosis.

### BYPASS_NOOP set (current)

`{0x000C, 0x013E, 0x0036, 0x0084, 0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}`

### Dragon-crack region

The ROM file has non-standard trailing bytes (Dragon Inc crack) loaded as `DRAGON_CRACK` region at the load address immediately after the code hunk. `_scan_cmpiw` scans both `HUNK_CODE` and `DRAGON_CRACK`.

---

## Amiga/FS-UAE Automation Layer (`bin/Code/Amiga/`) — Calibrated 2026-08-30

### SDL2 relative-mouse-mode physics (macOS, this machine)

- **Per-event X cap**: each `kCGEventMouseMoved` moves the Amiga cursor at most **89px**
  regardless of the delta value, once the send value ≥ 150.
- **Small-delta scale**: send ≤ 100 → scale ≈ **0.74 amiga-px / send-unit**
  (e.g. send=100 → 74px, send=50 → 37px).
- **Y behaves identically to X** (same cap and scale).
- **Home position**: after `home_cursor()`, cursor is reliably at amiga content
  **(86, 13)** — screenshot **(86, 45)**.
- **SDL2 wake on fresh launch**: on a brand-new FS-UAE process, delta events are
  silently ignored until SDL2 mouse capture is activated. `home_cursor()` handles
  this by clicking the macOS **title bar** (y = win_y + 15 in screen coords) before
  sending negative steps.  The title-bar click does **not** interact with Amiga UI.

### One-shot positioning algorithm (implemented in `_move_to_amiga`)

```
home_cursor()  →  cursor at (HOME_X=86, HOME_Y=13)
dx = target_x - 86
dy = target_y - 13
full_steps = dx // 89           # send _X_FULL_SEND=150 per step → 89px each
rem_x = dx - full_steps * 89    # 0 ≤ rem_x < 89

for _ in range(full_steps):
    send event (150, 0)    # X only; Y sent in final event
send event (rem_x / 0.74, dy / 0.74)   # final: remaining X + all Y
```

Example: icon at amiga (516, 56) → dx=430, dy=43 → 4 full steps + final (100, 58) → lands at (515, 56), 1px error.

### BattleChess disk icon on Workbench

- Icon centre in Amiga content pixels (screenshot Y − 32px title bar):
  `WORKBENCH_ICON_X = 516`, `WORKBENCH_ICON_Y = 56`
- Confirmed by `double_click(516, 56)` → screen brightness 7.72 → 12.33 (game loading)

### FS-UAE window geometry

- Config: `window_width=640`, `window_height=400` (Amiga content)
- Actual window size including macOS title bar: 640×432
- Window position on secondary display: typically X=640 (varies by monitor layout)

### Battle Chess Amiga menu bar — calibrated 2026-08-30

Menu bar is at Amiga content y=8.  Four headers (left to right):

| Header | Amiga content X | What it opens |
|---|---|---|
| Disk | ~175 | Load/Save/New Game/Setup Board/Quit |
| (Sound/Board/Player) | ~255 | Sound, 3D/2D Board, Human/Amiga/Modem Plays Red |
| Settings | ~335 | TBD |
| Level | ~415 | TBD |

**Second menu items** (x=255, Amiga content Y):

| Item | Amiga Y | Notes |
|---|---|---|
| Sound On | ~51 | + = currently on |
| Sound Off | ~67 | |
| 3D Board | ~83 | |
| 2D Board | ~99 | + = currently 2D |
| Human Plays Red | ~115 | + = default (human plays White/bottom) |
| Amiga Plays Red | ~131 | Makes AI play White/bottom side |
| Modem Plays Red | ~147 | |

**To make AI play White**: navigate to second menu header (x=255), select "Amiga Plays Red" (y=131).
Use `SetAmigaPlaysRed` activity. Restore with `SetHumanPlaysRed` (y=115) after corpus recording.

**StartNewGame settle_ms = 4000** — Battle Chess needs ~4s after "New Game" before accepting move input.
Confirmed: 2s was too short, 8s definitely works, 4s used as a safe value.

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
