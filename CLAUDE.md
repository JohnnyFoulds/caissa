# CLAUDE.md — Caissa (Lucas Chess R6 fork)

## Repository Purpose

Caissa is a fork of Lucas Chess R6 that adds a Mode system (Coach, Analyse, Train, Compete, Just Play) and a Theme overlay system on top of the upstream desktop chess application. Built with Python 3.13 + PySide6.

**CRITICAL SECURITY RULE:** Never push to `lukasmonk/lucaschessR6`. All pushes go to `JohnnyFoulds/caissa` only.

---

## Repository Structure

```text
bin/Code/
├─ Main/WBase.py          # Toolbar injection point (pon_toolbar, ~line 503)
├─ Config/WindowConfig.py # General Configuration dialog
├─ UIModes/
│  ├─ UIModes.py          # Mode loader: active_mode(), toolbar_inject()
│  └─ actions/            # Per-mode action registrations + hooks
│     ├─ coach_home.py    # Coach landing screen (2×2 card grid)
│     └─ <mode>_ui.py     # Optional mode UI hook (patch_config_form, etc.)

Resources/
├─ Modes/                 # Mode JSON files (classical, Coach, Analyse, Train, Compete, Just Play)
└─ Styles/                # QSS themes + optional <name>.ui.json overlays

docs/
├─ theme-mode-system.md   # SDD: Theme/Mode overlay architecture
├─ standards/             # Engineering standards (see below)
└─ engines.md
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

### Theme Overlay System (not yet implemented — see SDD)
- `Resources/Styles/<name>.ui.json` — renames/hides fields in Configuration dialog
- Applied at dialog-open time via `OverlayForm` proxy
- Absence of `.ui.json` = upstream behaviour, zero changes
- See `docs/theme-mode-system.md` for the full spec

### Config Keys
- `x_ui_mode` — active Mode (feature-set filter)
- `x_style_mode` — active Theme (visual appearance)
- `x_style` — Qt widget renderer (`Fusion`, `macOS`, etc.)

---

## Standards

Full standards documents are in `docs/standards/`. Summary of key rules:

### Commit Messages
Conventional Commits format: `type(scope): subject`

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`  
Scopes: `modes`, `toolbar`, `config`, `coach`, `ui`, `engine`, `theme`

Non-trivial commits need a body with bullet points. See `docs/standards/coding-standards.md`.

### Specification-Driven Development
Write an SDD before implementing any non-trivial feature. Store in `docs/<feature>.md`.
The Theme/Mode overlay system spec (`docs/theme-mode-system.md`) is the reference example.
See `docs/standards/spec-driven-development.md`.

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

### Code Style
- Do not reformat existing Lucas Chess R6 code
- No banner-style comment dividers — use `#region` / `#endregion`
- No default comments — only add when the WHY is non-obvious
- See `docs/standards/coding-standards.md`

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
