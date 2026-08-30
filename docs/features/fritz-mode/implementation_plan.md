# Fritz Mode Behaviour — Implementation Plan

**Status:** Active  
**Spec reference:** [feature_spec.md](feature_spec.md)  
**Steps reference:** [feature_steps.md](feature_steps.md)

---

## Overview

Seven phases (0–6), each on its own branch, closed with its own PR to `JohnnyFoulds/caissa`.

| Phase | Branch | Scope summary | Blocker |
|---|---|---|---|
| 0 | `feat/fritz-mode-phase0` | Red tests + doc drift + SDD artefacts | Gate A |
| 1 | `feat/fritz-mode-phase1` | Boot state — kill landing screen, ManagerSolo, pane wiring | Phase 0 |
| 2 | `feat/fritz-mode-phase2` | Dropdown + toggle infrastructure | Phase 1 |
| 3 | `feat/fritz-mode-phase3` | Home + Board tab button behaviour | Phase 2 |
| 4 | `feat/fritz-mode-phase4` | Analysis + Engine tab button behaviour | Phase 3 |
| 5 | `feat/fritz-mode-phase5` | View tab + layouts | Phase 4 |
| 6 | `feat/fritz-mode-phase6` | Icons + ribbon geometry + widget moves | Phase 5 |

---

## Phase 0 — Stop the Bleeding

**Goal:** Green test suite, all docs honest, this SDD on a branch.

**Session 0.1 — Branch + fix red tests**

1. `git checkout main && git pull`
2. `git checkout -b feat/fritz-mode-phase0`
3. Open `Resources/Ribbons/modern-fritz.json`:
   - Fix T-RMAP-03: QAT/tab key overlap is valid for backstage-facing keys — update `test_no_duplicate_slot_keys_within_tab` to permit QAT ∩ tab overlap as intentional; OR move the overlapping keys so they only appear in one place. The preferred fix is to update the test's docstring and logic to match the Office design intention (backstage keys are always in QAT).
   - Fix T-RMAP-06: `TB_QUIT` now lives in the File backstage. Either add it back to `quick_access`, or relax the test so `NEVER_FILTER_TOOLBAR ⊆ quick_access ∪ backstage`.
   - Fix dead `overflow.group`: rename from `home.more` to an existing group id, or delete the `overflow` key if overflowing is unneeded.
4. Run `QT_QPA_PLATFORM=offscreen /Users/johannes/code/lucaschess/.venv/bin/python3 -m pytest tests/test_ribbon_map.py -v` — must be green.

**Session 0.2 — Doc citations**

Replace every `manual p.NN` in `docs/fritz/ribbon.md` and `docs/fritz/ribbon-design.md` with the live URL:

| Old citation | Live URL |
|---|---|
| manual p.31 (Board tab) | `https://help.chessbase.com/Fritz/18/Eng/000031.htm` |
| manual p.34–35 (Levels dropdown) | `https://help.chessbase.com/Fritz/18/Eng/000058.htm` |
| manual p.35–36 (Standard Layouts) | `https://help.chessbase.com/Fritz/18/Eng/000078.htm` |
| manual p.63 (Hint/Suggestion) | `https://help.chessbase.com/Fritz/18/Eng/000018.htm` and `https://help.chessbase.com/Fritz/18/Eng/000070.htm` |
| manual p.73 (Panes) | `https://help.chessbase.com/Fritz/18/Eng/000104.htm` |

**Session 0.3 — SDD artefacts + stub docs**

- Create `docs/features/fritz-mode/` with the four artefacts (this session — already done).
- Create stubs `docs/fritz/theming.md`, `docs/fritz/testing.md`, `docs/fritz/troubleshooting.md`.
- Update `docs/fritz/README.md` to index `ribbon-design.md` and `assets/`.
- Append D18, D19, D20 to `docs/fritz/decisions.md`.
- Run `make docs` — zero warnings.

**Session 0.4 — Commit and PR**

```bash
git add docs/ Resources/Ribbons/modern-fritz.json tests/test_ribbon_map.py
git commit -m "docs(fritz): fritz-mode SDD, fix red tests, live manual citations"
gh pr create --repo JohnnyFoulds/caissa --title "docs(fritz): fritz-mode SDD phase 0 — stop the bleeding"
```

---

## Phase 1 — Boot State

**Goal:** Fritz mode opens on a live board, no landing screen, engine analysing silently.

**Session 1.1 — Delete WFritzHome + refactor right column builder**

1. Delete `bin/Code/UIModes/WFritzHome.py`.
2. In `modern_fritz_ui.py`:
   - Remove import (`:290`), creation (`:302-306`), show (`:320-322`), attribute assign (`:339`), signal wiring (`:347`).
   - Delete `_swap_home_to_analysis` (`:354-495`).
   - Write `_build_fritz_right_col(mw)` — builds the right `QSplitter` with `_PANE_SPECS` order.
3. In `_PANE_SPECS` add the `eval_bar` entry.
4. Delete dead QSS rules: `#WFritzHome*` blocks in `Fritz.qss`, `Modern Fritz.qss`, `fritz-widgets.qss`.

**Session 1.2 — Boot ManagerSolo, fix pane_api timing**

1. In `on_mode_enter`:
   - Terminate `presentacion` manager (`proc.manager.terminate()` if `ManagerChallenge101`).
   - Call `_build_fritz_right_col(mw)`.
   - Set `mw.base.analysis_bar.force_hidden = True` before `activate_analysis_bar(True)`.
   - Add one-shot guard: `if getattr(mw, '_fritz_booted', False): return` (guard skips on game-end re-entry; cleared on real mode switch).
   - Launch `ManagerSolo.ManagerSolo(procesador).start({"PLAY_AGAINST_ENGINE": False, "ANALYSIS_BAR": True})`.
   - Call `GeometryStore.load_splitters(mw)`.

2. In `Ribbon.py:57-70`: defer `pane_api` capture to after `main_window` is assigned.
   Fix: use a lazy lambda or wire via a post-`start` callback instead of capturing at toolbar-creation time.
   Also fix `load_mode_hook` to pass `hook` from mode JSON.

3. Widen `Resources/Modes/modern-fritz.json` `toolbar` allowlist: add `TB_FILE`, `TB_PGN_LABELS`, `TB_REPLAY`.

4. In `on_mode_exit`: call `GeometryStore.save_splitters(mw)` before teardown.

**Session 1.3 — WFritzPlayerHeader analysis-mode display**

In `WFritzPlayerHeader`: detect whether a real `TimeControl` is running (i.e. whether a real game is active). In Infinite Analysis mode, display side-to-move + eval string. Switch to clock display when a game starts.

**Session 1.4 — Tests + real-execution**

Write/update `tests/ui/test_fritz_layout.py`:
- `test_fritz_no_landing_screen_on_boot`
- `test_fritz_panes_visible_on_boot`
- `test_fritz_engine_silent_after_human_move`
- `test_fritz_analysis_bar_active_on_boot`
- `test_fritz_pane_checkboxes_wired`
- `test_fritz_dark_mode_pane_api_not_none`
- `test_fritz_eval_bar_pane_spec_exists`
- `test_fritz_layout_persists_across_restart`

Real-execution: launch Fritz mode, confirm no landing screen, eval moving, moves accepted for both sides, engine silent.

---

## Phase 2 — Dropdown + Toggle Infrastructure

**Goal:** Every ▼ button opens a real panel; toggle buttons are checkable and synced.

**Session 2.1 — WDropdownPanel**

Create `bin/Code/Fritz/WDropdownPanel.py`:
- `__init__(self, parent, title: str, items: list[tuple[str, Callable]])`
- `popup(self, button: QWidget) → None` — position below button, `Qt.Popup` window flag, dismiss on outside click
- `set_checked(self, label: str) → None`
- Blue header bar (`#005b99`), white body, `#cce4ff` hover row, `#b0b0b8` border, drop shadow

**Session 2.2 — Toggle support in WRibbon**

In `WRibbon.py`:
- `_build_slots_group`: when `slot.get("toggle")`, call `btn.setCheckable(True)`.
- `sync(li_acciones)`: for each checkable button, read app state to set `btn.setChecked(...)`.
  Initial state sources: `board.is_white_bottom` for Flip Board, `mw.is_fullscreen()` for Full Screen, `manager.play_against_engine` for Analyse.

Replace the string-literal `▼` append (`:762-768`) with a real mechanism: a small `▼` indicator widget or CSS `::after`-equivalent, and wire the button's `clicked` to `WDropdownPanel.popup(btn)`.

**Session 2.3 — RibbonModel validation**

In `RibbonModel._validate()`:
- Resolve all `TB_*` keys via `getattr(Constantes, key)` — raise `FritzError` on `AttributeError`.
- Check for duplicate slot keys *within a tab* (QAT/tab overlap is permitted, same-tab duplication is not).
- Validate `size` in `{"large", "small"}`.
- Validate `kind` in `{"slots", "panes", "checkboxes", "backstage"}`.
- Validate `default_tab` names an existing tab id.
- Actually call `_validate()` from `__init__`.
- Actually call `compact()` where it is needed.
- Reference and use `_CAISSA_KEY_RE` for `caissa:` key format.

Flip `tests/ui/test_fritz_ribbon.py` T-RIB-01..11 from `xfail` to real assertions.

---

## Phase 3 — Home + Board Tab Behaviour

**Goal:** All Home and Board tab buttons do their specified thing.

**Session 3.1 — TB_LEVEL, Hints, Suggestion, Threat, Coach**

1. `ManagerPlayAgainstEngine.run_action`: add `elif key == TB_LEVEL: self._open_levels_panel()`.
2. `WFritzNewGame`: remove the `"HINTS": 0` hard-set.
3. Register `caissa:suggestion`, `caissa:threat`, `caissa:coach_watching` actions.
4. `caissa:suggestion` → draw the engine top-move as a board arrow (`Board.set_arrow_...`).
5. `caissa:threat` → draw opponent's best reply as a red board arrow.
6. `caissa:coach_watching` → toggle Fritz coach (existing Lucas `TB_HELP`-adjacent mechanism or new).

**Session 3.2 — Flip Board, Display checkboxes, Piece/Square panels**

1. `caissa:flip_board` → `Board.rotate_board()`.
2. Wire Board ▸ Display checkboxes: add `key` values, implement handlers for Coordinates, Always Queen, Show eval bar, Show arrow, Replay slider.
3. Build Piece style ▼ and Square colour ▼ panels backed by existing piece-style and board-colour config keys.

**Session 3.3 — New Game ▼ and Levels ▼ panels**

1. New Game ▼ panel items: "Play vs computer", "Play vs human (local)", "Set up position".
   "Set up position" → `Voyager.voyager_position()`.
2. Levels ▼ panel items: Blitz / Rapid / Classical / Custom… → `WFritzNewGame`.

---

## Phase 4 — Analysis + Engine Tab Behaviour

**Goal:** Infinite Analysis toggle, Depth/Lines panels, engine selection, kibitzers.

**Session 4.1 — caissa:infinite_analysis toggle**

1. Register `caissa:infinite_analysis` action.
2. On activation: toggle `procesador.manager.play_against_engine`; if turning on, call `change_rival()` to build the engine; if turning off, terminate rival.
3. Remove the dead `voyager2` route from `_dispatch_non_game_action`.
4. Depth ▼ and Lines ▼ panels: set `MultiPV` via engine config; disable both panels when `play_against_engine == True`.

**Session 4.2 — Engine selection + kibitzers**

1. `caissa:select_engine` → `WDropdownPanel` listing `procesador.configuration.engines_list()`.
2. Right-click on `WFritzAnalysisTable` header → engine switch.
3. Kibitzer: cap at 6; add Remove all.

---

## Phase 5 — View Tab

**Goal:** Named layouts, last-layout-on-startup, fullscreen, arrange shortcuts.

**Session 5.1 — Layouts.py + Standard Layouts panel**

1. Create `bin/Code/Fritz/Layouts.py` with `NAMED_LAYOUTS` dict and `apply_layout(mw, preset)`.
2. Wire `caissa:std_layout` → `WDropdownPanel` backed by `NAMED_LAYOUTS` + Save / Load / Factory Settings.
3. Factory Settings → `GeometryStore` reset to Standard preset.

**Session 5.2 — Full Screen + Arrange**

1. `caissa:fullscreen` toggle → `mw.showFullScreen()` / `mw.showNormal()`.
2. Arrange shortcuts → `QApplication.topLevelWidgets()` layout logic.

---

## Phase 6 — Polish

**Goal:** Icons, ribbon geometry, widget moves to Fritz package.

**Session 6.1 — Move WFritz* to bin/Code/Fritz/**

`git mv` the five widget files; update all import sites; confirm `test_completeness.py` passes.

**Session 6.2 — Ribbon geometry**

Close the 30 px gap identified by `ribbon_report.py --variant light`:
- QAT height: 12 → 29 px
- Content area: 73 → 91 px
- `selected_tab_breaks_rule`: implement the rule-gap under the selected tab

**Session 6.3 — Icons**

Implement icon factories for all buttons in `docs/fritz/ribbon-design.md` §§ "Icons" tables.
Use `QPainterPath` or `QPixmap` per D11 for custom icons; fall back to `Iconos.*` for those that exist.

---

## Gate E Checklist (Final Phase)

- [ ] All phases ✅ in `feature_steps.md`
- [ ] `make test` all green
- [ ] `make cov-fritz` ≥ 90%
- [ ] `make lint` zero issues
- [ ] `make docs` zero warnings
- [ ] `ribbon_report.py --variant light` reports 143 px total, QAT 29, content 91, `selected_tab_breaks_rule` True
- [ ] Real-execution evidence in Phase 1, 4 PRs
- [ ] No regression in `test_classical_invariant.py`
- [ ] `CHANGELOG.md` updated
- [ ] All PRs target `JohnnyFoulds/caissa` (never `lukasmonk/lucaschessR6`)
