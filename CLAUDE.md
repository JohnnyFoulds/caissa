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
