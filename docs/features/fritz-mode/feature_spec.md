# Fritz Mode Behaviour — Software Design Document

**Status:** Specified — implementation pending  
**Branch:** `docs/fritz-mode` (this document), then one branch per phase — see `feature_steps.md`

<!-- Living document. Update alongside every design decision, constraint change, or
     interface change. Decisions logged in docs/fritz/decisions.md starting at D18
     and summarised in §2.4. -->

---

## 1. Problem Statement

Caissa's Fritz mode has an approved ribbon design and a working ribbon widget layer, but
no specification of what the mode actually *does*. Two concrete problems follow:

1. Fritz mode opens on a landing screen ("Modern Fritz" sidebar with New Game / Load Game
   cards) that has no equivalent in real Fritz 18. Real Fritz boots directly into a live
   board with panes open and the engine analysing.

2. Most approved ribbon buttons are undefined, unwired, or broken — the `▼` chevron is
   cosmetic, `"toggle": true` is never read, `caissa:std_layout` is a `pass` stub, pane
   checkboxes are permanently inert because `pane_api` is captured before
   `Procesador.main_window` is assigned.

This document specifies Fritz mode behaviour end to end: boot state, every ribbon button,
the pane model, the reuse map, and the new components required. The Fritz 18 online manual
(`https://help.chessbase.com/Fritz/18/Eng/`) is the authoritative behavioural north star.

See `initial_idea.md` for the frozen scope decisions.

---

## 2. Requirements

### 2.1 Business / Product Requirements

| ID | Requirement |
|---|---|
| BR-1 | Fritz mode **MUST** boot directly into a live board with panes open and the engine analysing — no landing screen — because real Fritz 18 works this way and the approved ribbon already provides all the entry points the landing screen offered. |
| BR-2 | Every button in the approved ribbon design (`docs/fritz/ribbon-design.md`) **MUST** have defined, implemented behaviour or be explicitly deferred to a named phase. A visible button that silently does nothing is a product defect. |
| BR-3 | Fritz mode **MUST** restore the user's last layout on startup, because that is the documented Fritz 18 behaviour (`https://help.chessbase.com/Fritz/18/Eng/000078.htm`) and because losing pane sizes on every restart is the single most intrusive friction in daily use. |
| BR-4 | The `▼` dropdown chevron on New Game, Levels, Piece style, Square colour, Depth, Lines, Select Engine, and Standard Layouts **MUST** open a floating selection panel matching the Fritz 18 pattern (blue header, white body, hover highlight), because all eight appear in the approved raster mockup and their current no-op behaviour is misleading. |

### 2.2 Functional Requirements

#### Boot state

| ID | Requirement |
|---|---|
| FR-1 | On entering Fritz mode, the system **MUST** launch `ManagerSolo` headlessly (`ManagerSolo.ManagerSolo(procesador).start()`), placing the board in the initial position with both sides enterable by the human. |
| FR-2 | On entering Fritz mode, the system **MUST** terminate any `presentacion` manager (`ManagerChallenge101`) that `Procesador.start()` created before the mode hook runs (`Procesador.py:291-294`). |
| FR-3 | On entering Fritz mode, `AnalysisBar` **MUST** be activated (`mw.activate_analysis_bar(True)`) before `manager.start()` is called. The force-hidden flag **MUST** be set before activation to prevent the macOS Qt6/Metal `QGraphicsDropShadowEffect` crash (`modern_fritz_ui.py:330-334`). |
| FR-4 | In the boot state the engine **MUST NOT** reply to moves. `ManagerSolo.play_against_engine` **MUST** be `False` at startup. The engine analyses the position continuously but does not play. |
| FR-5 | The system **MUST** restore the user's last Fritz layout from `GeometryStore.load_splitters()` on boot and save it on exit via `GeometryStore.save_splitters()`. |
| FR-6 | The system **MUST** present all default panes (Players, Engine analysis, Eval profile, Notation) on first boot. The Eval bar pane defaults to hidden. |
| FR-7 | On `on_mode_enter`, the system **MUST** build the right column directly — `_build_fritz_right_col()` — without creating `WFritzHome`. The file `bin/Code/UIModes/WFritzHome.py` **MUST** be deleted. |
| FR-8 | A one-shot guard **MUST** prevent `on_mode_enter` from re-launching a new game when it is called after a finished game (game end → `procesador.start()` → `reset()` → `on_mode_enter()`). The guard MUST allow re-entering Fritz mode from another mode to start fresh. |
| FR-9 | On mode exit, `GeometryStore.save_splitters()` **MUST** be called before the pane widgets are destroyed. |

#### Ribbon wiring

| ID | Requirement |
|---|---|
| FR-10 | `pane_api` **MUST** be wired after `Procesador.main_window` is assigned. `Ribbon.py:57-70` **MUST** be refactored so `pane_api` is not captured at `WBase.create_toolbar` time. |
| FR-11 | `load_mode_hook` **MUST** honour the `hook` key in the mode JSON so that `modern-fritz-dark.json` (which sets `"hook": "modern_fritz"`) gets the same `pane_api` as `modern-fritz.json`. |
| FR-12 | The `eval_bar` pane **MUST** have a `PaneSpec` entry in `_PANE_SPECS`. The ribbon JSON entries for `eval_bar` (lines 72 and 191 in `modern-fritz.json`) **MUST** connect to a real pane. |
| FR-13 | `TB_LEVEL` **MUST** be handled in `ManagerPlayAgainstEngine.run_action()`, opening the Levels ▼ panel. |
| FR-14 | `WFritzNewGame` **MUST NOT** set `"HINTS": 0`. Hint and Suggestion buttons **MUST** be enabled when the game state allows them (FR-26 below). |
| FR-15 | `caissa:flip_board` **MUST** call `Board.rotate_board()` (`Board.py:2503`) instead of poking `is_white_bottom` + `redraw()`. |
| FR-16 | The `▼` chevron **MUST** be implemented as a real dropdown trigger. The string-literal approach in `WRibbon.py:762-768` **MUST** be replaced by `WDropdownPanel`. |
| FR-17 | `"toggle": true` in a ribbon slot spec **MUST** result in `setCheckable(True)` on the button, with checked state synced in `WRibbon.sync()`. |
| FR-18 | `RibbonModel._validate()` **MUST** enforce: all `TB_*` keys resolve via `getattr(Constantes, key)`; no duplicate slot keys within a tab (QAT/tab overlap excepted for backstage); all `size` values in `{"large", "small"}`; all `kind` values in `{"slots", "panes", "checkboxes", "backstage"}`; `default_tab` names an existing tab id. |
| FR-19 | The `overflow` group (`home.more`) **MUST** either exist as a real group or the `overflow` spec key **MUST** be removed. |
| FR-20 | Board ▸ Display checkboxes (Coordinates, Show arrows, Show hints) **MUST** have `key` values and be wired to their respective `Board` settings. |
| FR-21 | The `caissa:std_layout` and `caissa:play_now` stubs **MUST** be implemented or removed from the ribbon JSON. |
| FR-22 | `caissa:select_engine` **MUST NOT** reference `Procesador.motores` (which does not exist); it **MUST** open the Select Engine ▼ panel from the installed engines list. |

#### Home tab — per-button behaviour

| ID | Requirement |
|---|---|
| FR-23 | **New Game ▼** (large) — **MUST** open a `WDropdownPanel` with items: "Play vs computer", "Play vs human (local)", "Set up position". "Set up position" **MUST** call `Voyager.voyager_position()`. "Play vs computer" and "Play vs human" **MUST** open `WFritzNewGame` pre-selecting the appropriate mode. |
| FR-24 | **Levels ▼** (large) — **MUST** open a `WDropdownPanel` with time-control items (Blitz 5 min, Rapid 15 min, Classical 90 min, Custom…) wired to `WFritzNewGame`. Reachable from `TB_LEVEL` dispatch **and** by right-clicking `WFritzPlayerHeader` (per `https://help.chessbase.com/Fritz/18/Eng/000031.htm`). |
| FR-25 | **Resign / Offer Draw / Abort / Takeback** — MUST map to the existing `ManagerPlayAgainstEngine` actions (`TB_RESIGN`, `TB_DRAW`, `TB_REINIT`, `TB_TAKEBACK`) and be **disabled** in Infinite Analysis boot state and enabled only when a real game is in progress. |
| FR-26 | **Hint** — MUST call `TB_ADVICE` (Lucas's help/advice action, `ManagerPlayAgainstEngine:1186`). Per `https://help.chessbase.com/Fritz/18/Eng/000018.htm`, Hint opens an advice window. Enabled only when a real game is in progress and hints > 0. |
| FR-27 | **Suggestion** — MUST be a new `caissa:suggestion` action that draws a move arrow on the board. `TB_HELP` (Lucas's *Help* action, which opens a help dialog) **MUST NOT** be used for Suggestion. Per `https://help.chessbase.com/Fritz/18/Eng/000070.htm`, Suggestion shows the engine's recommended move as a board arrow. |
| FR-28 | **Threat** (new, not in current JSON) — MUST be a new `caissa:threat` action that draws the opponent's best reply as a red arrow. Per `https://help.chessbase.com/Fritz/18/Eng/000099.htm`. Add to Home ▸ Coaching group alongside Hint and Suggestion. |
| FR-29 | **"Coach is watching"** (new, not in current JSON) — MUST be a `caissa:coach_watching` toggle that enables Fritz's chess coach (`https://help.chessbase.com/Fritz/18/Eng/000082.htm`). Add to Home ▸ Coaching group. |
| FR-30 | **Panes checkboxes** (Players, Engine analysis, Eval profile, Notation, Eval bar) — MUST toggle actual pane visibility via `pane_api["set"]`. The `eval_bar` checkbox MUST be wired (FR-12). |
| FR-30a | In Infinite Analysis boot state (no real game in progress), `WFritzPlayerHeader` **MUST** display the side-to-move indicator and the current eval rather than LCD clock values, because `ManagerSolo` never starts `tc_white`/`tc_black`. When a real game starts, it MUST switch to the standard clock display. |

#### Board tab — per-button behaviour

| ID | Requirement |
|---|---|
| FR-31 | **Flip Board** (large, toggle) — MUST call `Board.rotate_board()` (FR-15). Toggle state MUST reflect board orientation. |
| FR-32 | **Coordinates** (checkbox) — MUST show/hide rank/file labels. |
| FR-33 | **Always Queen** (checkbox) — MUST suppress the promotion dialog and always promote to queen. |
| FR-34 | **Piece style ▼** (large) — MUST open a `WDropdownPanel` listing installed piece sets, switching style on selection. |
| FR-35 | **Square colour ▼** (large) — MUST open a `WDropdownPanel` listing colour themes, switching on selection. |
| FR-36 | **Show eval bar** (checkbox) — MUST show/hide the side-of-board evaluation bar widget. |
| FR-37 | **Show arrow** (checkbox) — MUST show/hide the last-move arrow overlay on the board. |
| FR-38 | **Replay slider** (checkbox) — MUST show/hide the move-navigation slider below the board. |

#### Analysis tab — per-button behaviour

| ID | Requirement |
|---|---|
| FR-39 | **Analyse** (large, toggle) — MUST toggle `ManagerSolo.play_against_engine` via a new `caissa:infinite_analysis` action. When off (analysis mode), the engine analyses but does not reply. When on (play mode), the engine replies. This is Fritz's Alt-F2 toggle (`https://help.chessbase.com/Fritz/18/Eng/000128.htm`). |
| FR-40 | **Stop** (large, `TB_STOP`, "Play Now") — MUST force the engine to play immediately during a real game. Disabled in Infinite Analysis mode. |
| FR-41 | **Pause / Continue** (`TB_PAUSE`, `TB_CONTINUE`) — existing behaviour preserved. |
| FR-42 | **Depth ▼** — MUST open a `WDropdownPanel` with depth options (5 ply, 10 ply, 20 ply, Infinite). MUST be **disabled** when not in analysis mode (per `https://help.chessbase.com/Fritz/18/Eng/000105.htm`: "+/- lines only in analysis mode"). |
| FR-43 | **Lines ▼** — MUST open a `WDropdownPanel` with multi-PV options (1, 2, 3, 4 lines). Same enable/disable rule as FR-42. |
| FR-44 | **Copy to notation** — MUST insert the current engine variation into the game PGN notation. |
| FR-45 | **Clear** — MUST clear the analysis output in `WFritzAnalysisTable`. |
| FR-46 | Previous / Next (`TB_PREVIOUS`, `TB_NEXT`) — existing behaviour preserved. |
| FR-47 | Variations / Tools / Utilities (`TB_VARIATIONS`, `TB_TOOLS`, `TB_UTILITIES`) — existing behaviour preserved. |

#### Engine tab — per-button behaviour

| ID | Requirement |
|---|---|
| FR-48 | **Select Engine ▼** (large) — MUST open a `WDropdownPanel` listing installed engines with a checkmark on the active engine. MUST NOT reference `Procesador.motores`. MUST also be triggerable by right-clicking the engine pane name in `WFritzAnalysisTable` (per `https://help.chessbase.com/Fritz/18/Eng/000105.htm`). |
| FR-49 | **Engine Properties** — MUST open the engine's native parameter dialog. |
| FR-50 | **UCI Options** — MUST open the Caissa UCI options panel (hash size, threads, etc.). |
| FR-51 | **Add Kibitzer** — MUST add a second engine window running in parallel. Capped at 6 kibitzers (per `https://help.chessbase.com/Fritz/18/Eng/000098.htm`). Ctrl-K shortcut. |
| FR-52 | **Remove Kibitzer** — MUST remove the most-recently-added kibitzer. |
| FR-53 | A **Remove all kibitzers** action MUST be available (per `000098`). |

#### View tab — per-button behaviour

| ID | Requirement |
|---|---|
| FR-54 | **Standard Layouts ▼** — MUST open a `WDropdownPanel` with: Standard, Big Board, Big Notation, Big Engine, Board Only, All Windows, ─── (separator), Save layout, Load layout, Factory settings. Per `https://help.chessbase.com/Fritz/18/Eng/000078.htm`. |
| FR-55 | **Full Screen** (large, toggle) — MUST toggle fullscreen mode. Toggle state MUST be reflected in button checked state. |
| FR-56 | **Layout presets** MUST be implemented by `bin/Code/Fritz/Layouts.py` as pure splitter-size data with no Qt imports. |
| FR-57 | **Save / Load layout** in the Standard Layouts panel MUST call `GeometryStore.save_splitters()` / `GeometryStore.load_splitters()`. |
| FR-58 | **Factory settings** MUST restore the default splitter sizes and pane visibility without touching any other config. |
| FR-59 | View ▸ Panes checkboxes MUST be in sync with Home ▸ Panes checkboxes (both are `pane_api["set"]` calls; no duplication in the ribbon JSON). |

### 2.3 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Fritz mode boot to first rendered frame (board + panes + eval number) **MUST** complete in under 3 seconds on the reference machine (M-series Mac, SSD). |
| NFR-2 | All new public and non-public callables **MUST** have RST/Sphinx docstrings per `docs/standards/docstring-standards.md`. |
| NFR-3 | All new signatures **MUST** carry complete type annotations. |
| NFR-4 | All new modules in `bin/Code/Fritz/` **MUST** declare a purity tier and be covered by the AST walk in `tests/unit/fritz/test_completeness.py`. |
| NFR-5 | The five existing `WFritz*` widget files in `bin/Code/UIModes/` **MUST** be moved to `bin/Code/Fritz/` (Phase 6) so the purity AST walk covers them. |
| NFR-6 | `make lint` (ruff check `--config ruff.toml`) **MUST** produce zero issues after every phase. |
| NFR-7 | `make test` **MUST** pass (no regressions in any existing suite) after every phase. |
| NFR-8 | Fritz mode MUST continue to work identically in both `modern-fritz.json` (light) and `modern-fritz-dark.json` (dark) — both share `"hook": "modern_fritz"`. |

### 2.4 Constraints & Assumptions

- Module locations: `bin/Code/Fritz/` (pure/adapter/Qt), `bin/Code/UIModes/actions/modern_fritz_ui.py` (hook).
- Python 3.13; PySide6.
- No `abc.ABC`, no `typing.Protocol` — plain base classes raising `NotImplementedError` (D7).
- Errors inherit from `CaissaError` via `FritzError` (`bin/Code/Fritz/Errors.py`).
- `WDropdownPanel` is new; it must be a `Qt allowlist` tier module.
- `Layouts.py` is new; it must be `Pure` tier (no Qt imports, no `Code.*` imports).
- Pane persistence via `GeometryStore` already exists and is unit-tested; this feature adds the production callers, not a new mechanism.
- **D18 — `_swap_home_to_analysis` is deleted, not patched.** The function early-returns when `_fritz_home is None` and mutates `right_col` positionally. Its only remaining job after the landing screen is removed is identical to `_build_fritz_right_col()`. Delete it; write `_build_fritz_right_col()` directly.
- **D19 — `WFritzHome.py` is deleted in Phase 1, not archived.** It has no callers after the boot-state change and its 33 associated QSS rules become dead code.
- **D20 — `voyager2` route in `_dispatch_non_game_action` is dead and must be removed.** `play_menu().run_exec("voyager2")` is only handled in `Openings/WindowOpeningLine.py`, not in analysis mode. The correct call for "Set up position" is `Voyager.voyager_position()`.
- The `classical` mode must not be touched. The Classical Invariant is preserved by design (§8).
- "One branch = one phase = one PR" is non-negotiable per `docs/process/sdd-workflow.md`.

---

## 3. Terminology & Existing Infrastructure

| Term | Definition |
|---|---|
| **Infinite Analysis** | Fritz's default startup mode: engine analyses the position continuously, both sides can enter moves, engine does not reply. Alt-F2 toggles into play mode. Source: `https://help.chessbase.com/Fritz/18/Eng/000128.htm` |
| **Boot state** | The manager and UI state immediately after `on_mode_enter` completes. In this feature: `ManagerSolo` running, `play_against_engine = False`, `AnalysisBar` active, all default panes visible. |
| **Landing screen** | The `WFritzHome` widget that currently occupies the right column on mode entry. Deleted in Phase 1. |
| **Pane** | A `QSplitter` child panel in the Fritz right column. Not a `QDockWidget`. |
| **`pane_api`** | Dict returned by `modern_fritz_ui.pane_api(mw)` with keys `names`, `get`, `set`. Used by the ribbon to wire pane checkboxes. |
| **`WDropdownPanel`** | New widget: a floating panel with a blue header bar and a list of selectable items. Implements the Fritz dropdown visual pattern. |
| **`Layouts.py`** | New Pure-tier module: named layout presets as pure splitter-size data. No Qt imports. |
| **`GeometryStore`** | Existing module in `bin/Code/Fritz/` with `save_splitters()` / `load_splitters()`. Written, unit-tested, zero production callers before this feature. |
| **`ManagerSolo`** | `bin/Code/Z/ManagerSolo.py` — Lucas Chess's "create your own game" manager. `GT_ALONE`, free two-sided move entry, `play_against_engine` defaults `False`. The Infinite Analysis manager. |
| **`AnalysisBar`** | `bin/Code/Main/WAnalysisBar.py:14` — the always-on continuous engine. Already running in Fritz mode; widget force-hidden. Single data source for `WFritzAnalysisTable` and `WFritzEvalGraph`. |
| **Context-visibility matrix** | The table in `docs/fritz/ribbon-design.md:374-391` mapping button enable/disable state to game states. Must gain an "Infinite analysis" column. |

---

## 4. Architecture

The Fritz mode hook (`modern_fritz_ui.py`) owns the lifecycle. On entry it terminates the
`presentacion` manager, builds the right column via `_build_fritz_right_col()`, starts
`ManagerSolo` in Infinite Analysis mode, activates `AnalysisBar`, and restores the saved
layout. On exit it saves the layout and tears down the Fritz-specific panes.

The ribbon is wired *after* `Procesador.main_window` is assigned (fixing the `pane_api`
timing defect), giving the ribbon's pane checkboxes a live reference to the pane dict.

```text
on_mode_enter(procesador)
  │
  ├── terminate presentacion manager (if any)
  ├── _build_fritz_right_col(mw)     ← panes + right QSplitter
  ├── activate_analysis_bar(True)    ← before manager.start() [crash guard]
  ├── ManagerSolo.start()            ← Infinite Analysis boot state
  ├── GeometryStore.load_splitters() ← restore last layout
  └── ribbon.rewire_pane_api(mw)     ← fix timing: pane_api after main_window assigned

ManagerSolo.play_against_engine = False  (default — engine silent)
caissa:infinite_analysis toggle   ↕ flip play_against_engine

WDropdownPanel ← New Game ▼, Levels ▼, Depth ▼, Lines ▼,
                  Piece style ▼, Square colour ▼, Select Engine ▼,
                  Standard Layouts ▼

Layouts.py (Pure) ← splitter-size data for each named layout preset

GeometryStore ← save_splitters / load_splitters  (existing, now wired)
```

---

## 5. Interface Contract

### 5.1 `_build_fritz_right_col(mw: MainWindow) → None`

Replaces the current `_swap_home_to_analysis`. Called once on boot (replacing the landing
screen path) and once when a real game starts (replacing the `_swap_home_to_analysis`
game-start path). Idempotent — safe to call twice.

| Member | Kind | Description |
|---|---|---|
| `_build_fritz_right_col(mw)` | module-level function → `None` | Builds / rebuilds the right QSplitter with all panes in their spec-defined order. Raises `FritzError` if `mw.base` is None. |

### 5.2 `WDropdownPanel`

| Member | Kind | Description |
|---|---|---|
| `WDropdownPanel(parent, title, items)` | constructor | `parent`: the button that owns it. `title`: str for the blue header. `items`: list of `(label: str, callback: Callable[[], None])`. |
| `popup(button)` | method → `None` | Shows the panel positioned directly below `button`. Dismisses on selection or outside click. |
| `set_checked(label)` | method → `None` | Shows a checkmark on the row matching `label`. |

### 5.3 `bin/Code/Fritz/Layouts.py`

| Member | Kind | Description |
|---|---|---|
| `NAMED_LAYOUTS` | `dict[str, LayoutPreset]` | Maps layout name → `LayoutPreset` frozen dataclass with splitter ratios. |
| `LayoutPreset` | frozen dataclass | `name: str`, `right_ratios: list[int]`, `main_ratios: list[int]`. |
| `apply_layout(mw, preset)` | function → `None` | Applies `preset` to `mw`'s splitters via `GeometryStore`. |

### 5.4 `caissa:` action registry additions

| Action key | Trigger | Precondition | Effect |
|---|---|---|---|
| `caissa:infinite_analysis` | toggle button | `ManagerSolo` active | Flips `manager.play_against_engine`; updates button checked state |
| `caissa:suggestion` | button | Game in progress | Draws the engine's top move as a board arrow (clears after next move) |
| `caissa:threat` | button | Game in progress | Draws opponent's best reply as a red board arrow (clears after next move) |
| `caissa:coach_watching` | toggle | Always | Enables/disables Fritz chess coach monitoring |
| `caissa:select_engine` | `▼` button | Always | Opens Select Engine `WDropdownPanel` |
| `caissa:std_layout` | `▼` button | Always | Opens Standard Layouts `WDropdownPanel` |

---

## 6. Error Semantics

| Condition | Behaviour |
|---|---|
| `_build_fritz_right_col` called before `mw.base` assigned | Raises `FritzError("right_col: base not ready")` |
| `WDropdownPanel` shown with empty item list | Raises `FritzError("WDropdownPanel: items must not be empty")` |
| `Layouts.apply_layout` called with unknown preset name | Raises `FritzError(f"unknown layout: {name!r}")` |
| `GeometryStore.load_splitters` — file missing on first run | Returns silently; caller uses default sizes |
| `on_mode_enter` called when `main_window` is `None` | Raises `FritzError("on_mode_enter: main_window not yet assigned")` |

---

## 7. Non-Functional Constraints (N)

| ID | Constraint |
|---|---|
| N-FRITZMODE-1 | `WDropdownPanel` **MUST** dismiss on any outside click (standard popup semantics). |
| N-FRITZMODE-2 | `Layouts.py` **MUST** be importable with zero Qt/PySide6 on `PYTHONPATH` (Pure tier). |
| N-FRITZMODE-3 | `pane_api` rewiring **MUST** happen after `Procesador.main_window` is assigned (`Procesador.py:187`) so the ribbon captures a live pane dict, not `{}`. |
| N-FRITZMODE-4 | The one-shot boot guard **MUST** distinguish mode re-entry (switch mode → Fritz → back → Fritz) from game-end re-entry (`procesador.start()` loop). |
| N-FRITZMODE-5 | All five `WFritz*` widget files currently in `bin/Code/UIModes/` **MUST** be moved to `bin/Code/Fritz/` before Phase 6 is closed, so `tests/unit/fritz/test_completeness.py` covers them. |

---

## 8. Classical Invariant Impact

This feature adds no widget, toolbar entry, menu entry, mode JSON, QSS rule, overlay, or
render-time config key to the `classical` mode. All new code is gated behind
`x_ui_mode == "Modern Fritz"`. The mode JSON files (`modern-fritz.json`,
`modern-fritz-dark.json`) are not touched in classical mode. `test_classical_invariant.py`
must pass after every phase.

---

## 9. Implementation Sequence

See `feature_steps.md` for the full phase-by-phase breakdown.

---

## 10. Out of Scope

- Fritz features with no Lucas Chess implementation: ChessBase Live, LiveBook, online
  play, database browser, media player, DGT board, tournament arbiter mode.
- Classic Lucas Chess features absent from Fritz mode by design: training puzzles,
  competition ladder, resistance mode, tactics trainer, leagues, databases.
- Converting `MainWindow` from `QDialog` to `QMainWindow`.
- Any work in `classical` mode.
- The four RPA object-tier defects (D8 — deferred to the RPA feature).
- Gate H docs beyond what each phase specifies (`docs/fritz/theming.md`,
  `docs/fritz/testing.md`, `docs/fritz/troubleshooting.md` are Phase 0 deliverables).

---

## 11. Changelog

| Date | Author | Change |
|---|---|---|
| 2026-08-29 | JF | Initial spec — all 11 sections, Gate A ready |

---

## References

- Fritz 18 manual: `https://help.chessbase.com/Fritz/18/Eng/`
- Approved ribbon design: `docs/fritz/ribbon-design.md`
- Ribbon schema: `docs/fritz/ribbon.md`
- Architecture decisions: `docs/fritz/decisions.md` D1–D17 (new decisions start at D18)
- SDD workflow: `docs/process/sdd-workflow.md`
- Architecture standard: `docs/standards/architecture.md`
- Spec-driven development: `docs/standards/spec-driven-development.md`
