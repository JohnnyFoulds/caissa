# Modern Fritz Skin — Specification

## Overview

Modern Fritz is a Caissa UI mode that replicates the look and feel of Fritz 15–18
(the ChessBase GUI). It combines three things:

1. A near-black Fritz color scheme (distinct from Midnight's blue-slate)
2. Layout changes that activate only in this mode via `on_mode_enter`/`on_mode_exit` hooks
3. A Fritz-specific engine panel (`WFritzEnginePanel`) that shows depth, score and
   best line in Fritz style above the move list

The classical invariant is preserved: selecting any other mode restores the
previous layout exactly.

---

## Fritz 15–18 Layout Reference

Researched from ChessBase documentation and Fritz 17/18:

```
┌──────────────────────────────────────────────┬────────────────────────────┐
│  Toolbar  (dark, minimal)                    │                            │
├──┬───────────────────────────────────────────┤  ┌──────────────────────┐  │
│  │                                           │  │ Stockfish 18  d:24   │  │
│  │                                           │  │ ████████████░░ +0.42 │  │
│E │          BOARD                            │  │ 1.e4 e5 2.Nf3 Nc6…  │  │
│V │                                           │  └──────────────────────┘  │
│A │                                           │  ┌──────────────────────┐  │
│L │                                           │  │ 1.  e4     e5        │  │
│  │                                           │  │ 2.  Nf3    Nc6       │  │
│B │                                           │  │ 3.  Bb5    a6        │  │
│A │                                           │  └──────────────────────┘  │
│R │                                           │                            │
│  ├───────────────────────────────────────────┤                            │
│  │  White player   ●   Black player          │                            │
└──┴───────────────────────────────────────────┴────────────────────────────┘
```

Key observations from Fritz:
- **Eval bar** — vertical, thin (≈20px), runs the full height of the board on the
  left side. Light fill = White advantage, dark fill = Black advantage. Numerical
  score shown at top and bottom. Lucas Chess already has this (`WAnalysisBar`).
- **Engine panel** — sits at the top of the right column. Shows: engine name,
  search depth, numerical eval, and the current best line. This is the component
  NOT present in the standard Lucas Chess layout.
- **Move list** — below the engine panel in the right column. Standard PGN display.
- **Toolbar** — minimal, dark. Fritz uses a thin top toolbar.
- **Background** — near-black (`#161616`), NOT blue. Fritz's dark theme is achromatic
  dark grey with a signature blue (`#0078d4`) as the only accent.

---

## Color Scheme

| Role | Value | Notes |
|---|---|---|
| Background | `#161616` | Near-black, achromatic Fritz dark |
| Surface | `#1f1f1f` | Panel surfaces |
| Surface-2 (hover/zebra) | `#2d2d2d` | |
| Border | `#3a3a3a` | Hairline separators |
| Text | `#e8e8e8` | Cool white |
| Text-dim | `#8a8a8a` | Secondary info |
| **Accent (Fritz Blue)** | `#0078d4` | Windows/ChessBase signature blue |
| Accent hover | `#1890e8` | |
| Success | `#107c10` | Win color |
| Danger | `#c42b1c` | Loss / danger |
| Mistake / warning | `#ca5010` | Orange-red |
| Eval bar white | `#d4d4d4` | White side of analysis bar |
| Eval bar black | `#1a1a1a` | Black side of analysis bar |

---

## Files

| File | Role | Status |
|---|---|---|
| `Resources/Styles/Modern Fritz.qss` | Near-black Fritz QSS | UPDATE (fix colors) |
| `Resources/Styles/Modern Fritz.colors` | Color values (88 keys) | UPDATE |
| `Resources/Modes/modern-fritz.json` | Mode definition | MINOR UPDATE |
| `bin/Code/Procesador.py` | Wire on_mode_enter/on_mode_exit hooks | MODIFY |
| `bin/Code/UIModes/WFritzEnginePanel.py` | Fritz-specific engine info widget | NEW |
| `bin/Code/UIModes/actions/modern_fritz_ui.py` | Mode hook | NEW |
| `bin/Code/Main/WAnalysisBar.py` | Add set_update_callback() | MINOR MODIFY |

---

## `WFritzEnginePanel` Component

A `QWidget` that sits as the top section of the right column (inserted into the
main `QSplitter` at index 1, shifting `pgn_information` to index 2).

### Layout

```
┌──────────────────────────────────────────────────┐
│  Stockfish 18                     depth: 24       │  ← header row (LB)
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░  +0.42                │  ← horizontal QProgressBar
│  1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6…         │  ← best line (QLabel, wrap)
└──────────────────────────────────────────────────┘
```

Height: ≈ 90px. Width: inherits from splitter pane.

### Data source

Reads from `analysis_bar.mrm` (the `MultiRM` from the running analyzer engine)
via a 250ms `QTimer`. No second engine is started — the Fritz panel reuses the
same analyzer engine that powers the side eval bar.

The following fields are read from `mrm.rm_best()`:
- `rm.abbrev_text_base1()` — score text ("+0.42", "M5", etc.)
- `rm.depth` — search depth
- `rm.pv` + `Game.pv_pgn(fen, pv)` — best line in algebraic notation
- `engine_manager.name` — engine name (from `analysis_bar.engine_manager`)

### Injection / removal

`on_mode_enter(procesador)`:
1. `mw.activate_analysis_bar(True)` — start side eval bar + analyzer engine
2. `mw.active_information_pgn(True)` — show move list panel
3. Create `WFritzEnginePanel(mw, mw.base.analysis_bar)`
4. `mw.splitter.insertWidget(1, panel)` — inserts before pgn_information
5. Store `mw._fritz_panel = panel` for cleanup

`on_mode_exit(procesador)`:
1. Stop panel timer: `mw._fritz_panel.stop()`
2. Remove from splitter: `mw._fritz_panel.setParent(None)`
3. Delete reference

`on_mode_exit` is called from `Procesador.reset()` before it deactivates panels,
so the panel has time to clean up before the engine is stopped.

---

## Hook wiring in `Procesador.py`

**`reset()` — call exit hook at the START** (before `activate_analysis_bar(False)`):

```python
def reset(self):
    from Code.UIModes.UIModes import active_mode as _active_mode, load_mode_hook as _load_mode_hook
    _hook = _load_mode_hook(_active_mode().get("name", ""))
    if _hook and hasattr(_hook, "on_mode_exit"):
        _hook.on_mode_exit(self)

    self.main_window.activate_analysis_bar(False)
    ...  # rest of existing reset
```

**`start()` — call enter hook at the END** (after `self.kibitzers_manager.stop()`):

```python
def start(self):
    ...
    self.kibitzers_manager.stop()

    from Code.UIModes.UIModes import active_mode as _active_mode, load_mode_hook as _load_mode_hook
    _hook = _load_mode_hook(_active_mode().get("name", ""))
    if _hook and hasattr(_hook, "on_mode_enter"):
        _hook.on_mode_enter(self)
```

---

## QSS authoring rules compliance

- **Q1**: No `#RRGGBB` on a line with more than one colon
- **Q2**: Same 88-key set as all other `.colors` files (no new keys)
- **Q3**: All selectors on own line, `{` on next line
- **Geometry parity**: byte-identical geometry lines vs Midnight

---

## `on_mode_enter` / `on_mode_exit` general contract

These are now a first-class lifecycle convention for all modes with UI side effects.
The pattern:
- Hooks are loaded dynamically from `bin/Code/UIModes/actions/<mode_lower>_ui.py`
- Both functions receive `procesador` as their sole argument
- Hooks must be idempotent (safe to call if previous call failed partway)
- Hooks must not assume any particular manager is active — only `main_window` and
  `configuration` are guaranteed to be in a known state at hook time
