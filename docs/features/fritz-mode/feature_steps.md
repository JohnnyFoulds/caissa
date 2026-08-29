# Fritz Mode Behaviour — Implementation Steps

<!-- Living implementation tracker. Mark phases complete (✅) as they finish.
     Update test lists if scope changes. Keep in sync with feature_spec.md.

     All planned test names are declared here. Test files are created by the phase
     that owns them. Deferred phases use @pytest.mark.xfail(strict=True). -->

Living implementation tracker for the Fritz Mode Behaviour feature.  
**Spec reference:** [feature_spec.md](feature_spec.md)

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Complete |

---

## Phase 0 — Stop the Bleeding (Docs + Red Tests) ⬜

**Branch:** `feat/fritz-mode-phase0`

**Files modified:**

- `docs/features/fritz-mode/initial_idea.md` (this commit — FROZEN)
- `docs/features/fritz-mode/feature_spec.md` (this commit — Gate A)
- `docs/features/fritz-mode/feature_steps.md` (this commit)
- `docs/features/fritz-mode/implementation_plan.md` (this commit)
- `docs/fritz/decisions.md` — append D18, D19, D20
- `docs/fritz/ribbon.md` — replace `manual p.NN` citations with live ChessBase URLs
- `docs/fritz/ribbon-design.md` — same citation fix; fix `ribbon-design.md:2` references
- `docs/fritz/README.md` — index `ribbon-design.md` + `assets/`
- `docs/fritz/theming.md` (create — Gate H stub)
- `docs/fritz/testing.md` (create — Gate H stub)
- `docs/fritz/troubleshooting.md` (create — Gate H stub)
- `Resources/Ribbons/modern-fritz.json` — get uncommitted edits onto this branch; fix dead `overflow` group (`home.more` → remove or create the group); fix T-RMAP-03 (duplicate QAT/tab keys); fix T-RMAP-06 (TB_QUIT back in QAT or test relaxed)
- `tests/test_ribbon_map.py` — relax T-RMAP-03 and T-RMAP-06 where over-strict per the backstage design

**What we deliver:**

- All four SDD artefacts complete → Gate A passes
- `make test` green (T-RMAP-03 and T-RMAP-06 no longer fail)
- `make docs` zero warnings
- `modern-fritz.json` on a real branch, not sitting on `main`
- Live ChessBase URLs replacing unverifiable PDF page citations everywhere in `docs/fritz/`

**TDD test cases:**

Tests for red-test fixes live in `tests/test_ribbon_map.py` (already exists — modify, don't create):

- `test_no_duplicate_slot_keys_within_tab` — T-RMAP-03 (relax: backstage panel entries are allowed to duplicate QAT; tab-to-tab duplication is prohibited)
- `test_quick_access_never_filter_toolbar` — T-RMAP-06 (update: TB_QUIT is in File backstage, not QAT; NEVER_FILTER_TOOLBAR definition is consistent with that)
- `test_overflow_group_exists` (new) — the `overflow.group` value names a real group id within the specified `overflow.tab`

**Spec refs:** BR-1, §1 (problem 1), §10 (out of scope)

---

## Phase 1 — Boot State ⬜

**Branch:** `feat/fritz-mode-phase1`

**Files modified:**

- `bin/Code/UIModes/WFritzHome.py` — **delete**
- `bin/Code/UIModes/actions/modern_fritz_ui.py` — major refactor:
  - Delete `WFritzHome` import and creation (`:290, :302-306, :320-322, :339, :347`)
  - Delete `_swap_home_to_analysis` (`:354-495`)
  - Add `_build_fritz_right_col(mw)`
  - Add one-shot boot guard (FR-8)
  - Boot `ManagerSolo` headlessly (FR-1)
  - Terminate `presentacion` manager (FR-2)
  - Fix analysis-bar activation ordering (FR-3)
  - Wire `GeometryStore.save_splitters` / `load_splitters` (FR-5, FR-9)
  - Add `eval_bar` PaneSpec to `_PANE_SPECS` (FR-12)
- `bin/Code/Fritz/Ribbon.py:57-70` — fix `pane_api` timing (FR-10)
- `bin/Code/Fritz/Ribbon.py` — fix `load_mode_hook` hook override (FR-11)
- `Resources/Modes/modern-fritz.json` — widen `toolbar` allowlist (`TB_FILE`, `TB_PGN_LABELS`, `TB_REPLAY`); rewrite description
- `Resources/Modes/modern-fritz-dark.json` — same description rewrite
- `Resources/Styles/Fritz.qss` — delete 11 dead `#WFritzHome*` rules (`:836-905`)
- `Resources/Styles/Modern Fritz.qss` — delete 11 dead `#WFritzHome*` rules (`:836-905`)
- `Resources/Styles/fritz-widgets.qss` — delete 33 dead `#WFritzHome*` rules (`:111-186`)
- `docs/fritz/ribbon-design.md` — add "Infinite analysis" column to context-visibility matrix (`:374-391`)
- `tests/ui/test_fritz_layout.py` — rewrite T-FRITZ-01, T-FRITZ-05, `_start_fritz_game`

**What we implement:**

- Fritz mode boots to live board with panes open, engine analysing, no landing screen
- `ManagerSolo` running with `play_against_engine = False`
- Pane checkboxes live (pane_api timing fixed)
- Splitter sizes restored and saved
- `WFritzPlayerHeader` shows side-to-move + eval during Infinite Analysis (FR-30a)

**TDD test cases (`tests/ui/test_fritz_layout.py` — modify existing):**

- `test_fritz_no_landing_screen_on_boot` — on mode enter, no `WFritzHome` instance in widget tree
- `test_fritz_panes_visible_on_boot` — Players, Engine analysis, Eval profile, Notation all visible
- `test_fritz_engine_silent_after_human_move` — after a human move, `manager.play_against_engine == False` and no engine reply observed
- `test_fritz_analysis_bar_active_on_boot` — `mw.with_analysis_bar == True` after mode enter
- `test_fritz_pane_checkboxes_wired` — ribbon pane checkboxes toggle actual pane visibility
- `test_fritz_dark_mode_pane_api_not_none` — modern-fritz-dark mode hook gets valid `pane_api`
- `test_fritz_eval_bar_pane_spec_exists` — `eval_bar` key in `_PANE_SPECS`
- `test_fritz_layout_persists_across_restart` — splitter sizes saved and restored (unit, using `GeometryStore` directly)

**Real-execution evidence (Gate D requirement):**  
Launch `tools/caissa` in Fritz mode. Confirm by observation:
- No landing screen — board and panes appear immediately
- Eval numbers move in the analysis table
- A human move for White is entered — engine does not reply
- A human move for Black is entered — engine does not reply

**Spec refs:** FR-1..FR-12, FR-30a, §3 (ManagerSolo), §5.1 (interface), §8 (classical invariant)

---

## Phase 2 — Dropdown + Toggle Infrastructure ⬜

**Branch:** `feat/fritz-mode-phase2`

**Files created:**

- `bin/Code/Fritz/WDropdownPanel.py` (FR-16; Qt allowlist tier)

**Files modified:**

- `bin/Code/Fritz/WRibbon.py` — implement `"toggle": true` → `setCheckable`, sync in `sync()` (FR-17)
- `bin/Code/Fritz/WRibbon.py` — replace string-literal `▼` with `WDropdownPanel` trigger (FR-16)
- `bin/Code/Fritz/RibbonModel.py` — implement `_validate()` key-resolution, duplicate, size, kind, default_tab checks (FR-18); call `_validate()` from `__init__`

**What we implement:**

- Eight ▼ buttons open real `WDropdownPanel` floating panels
- Toggle buttons (`"toggle": true`) are checkable and stay in sync with app state
- `RibbonModel` validates the ribbon JSON on load — bad JSON raises `FritzError`

**TDD test cases (`tests/ui/test_fritz_ribbon.py` — flip `xfail` → passing):**

All T-RIB-01..11 are currently `@pytest.mark.xfail(strict=True)` stubs. This phase flips them:

- `test_dropdown_panel_opens_below_button` — T-RIB-01
- `test_dropdown_panel_dismisses_on_outside_click` — T-RIB-02
- `test_dropdown_panel_checkmark_on_active_item` — T-RIB-03
- `test_toggle_button_is_checkable` — T-RIB-04 (`"toggle": true` → `setCheckable(True)`)
- `test_toggle_button_sync_with_app_state` — T-RIB-05 (`ribbon.sync()` updates checked state)
- `test_ribbon_model_rejects_unknown_tb_key` — T-RIB-06
- `test_ribbon_model_rejects_duplicate_slot_keys_within_tab` — T-RIB-07
- `test_ribbon_model_rejects_invalid_size` — T-RIB-08
- `test_ribbon_model_rejects_invalid_kind` — T-RIB-09
- `test_ribbon_model_rejects_unknown_default_tab` — T-RIB-10
- `test_ribbon_model_accepts_qat_tab_overlap` — T-RIB-11 (Office-correct: backstage keys may overlap QAT)

**Spec refs:** FR-16, FR-17, FR-18, §5.2 (WDropdownPanel interface)

---

## Phase 3 — Home + Board Tabs ⬜

**Branch:** `feat/fritz-mode-phase3`

**Files created:**

- `bin/Code/UIModes/actions/caissa_actions.py` — or extend existing caissa action registry:
  `caissa:suggestion`, `caissa:threat`, `caissa:coach_watching`

**Files modified:**

- `bin/Code/PlayAgainstEngine/ManagerPlayAgainstEngine.py` — handle `TB_LEVEL` in `run_action()` (FR-13)
- `bin/Code/UIModes/WFritzNewGame.py` — remove `"HINTS": 0` (FR-14)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` — wire `caissa:flip_board` → `Board.rotate_board()` (FR-15)
- `Resources/Ribbons/modern-fritz.json` — add `caissa:threat`, `caissa:coach_watching` to `home.coaching`; wire Display checkboxes with real keys (FR-20); fix `caissa:suggestion` key
- Context-visibility matrix in `docs/fritz/ribbon-design.md` — add Infinite analysis column

**What we implement:**

- New Game ▼, Levels ▼ panels open with real items
- Resign / Draw / Abort / Takeback enabled only in real game (context-visibility correct)
- Hint (TB_ADVICE) works; Suggestion draws a move arrow; Threat draws red arrow
- Coach-is-watching toggle wired
- Flip Board calls `Board.rotate_board()` correctly
- Display checkboxes (Coordinates, Always Queen, Show eval bar, Show arrow, Replay slider) wired
- Piece style ▼ and Square colour ▼ panels open

**TDD test cases (`tests/unit/fritz/` or `tests/ui/`):**

- `test_tb_level_handled_in_run_action` — `TB_LEVEL` does not fall through to `routine_default`
- `test_hints_not_zeroed_by_wfritznewgame` — `WFritzNewGame` default dic has `HINTS` > 0 or absent
- `test_flip_board_calls_rotate_board` (unit, mock Board) — `caissa:flip_board` calls `Board.rotate_board()` not `redraw()`
- `test_suggestion_draws_arrow_not_help_dialog` — `caissa:suggestion` sets a board arrow, does not open a help dialog
- `test_threat_draws_red_arrow` — `caissa:threat` sets a red board arrow
- `test_game_controls_disabled_in_infinite_analysis` — Resign, Draw, Abort, Takeback all disabled when `ManagerSolo.play_against_engine == False`
- `test_hint_enabled_when_hints_available` — TB_ADVICE is in `li_acciones` when game in progress and hints > 0

**Spec refs:** FR-13..FR-15, FR-20, FR-23..FR-30, §5.4 (caissa: action registry)

---

## Phase 4 — Analysis + Engine Tabs ⬜

**Branch:** `feat/fritz-mode-phase4`

**Files created:**

- `bin/Code/UIModes/actions/caissa_actions.py` — add `caissa:infinite_analysis` (FR-39)

**Files modified:**

- `bin/Code/UIModes/actions/modern_fritz_ui.py` — wire `caissa:infinite_analysis`; delete dead `voyager2` route from `_dispatch_non_game_action` (D20)
- `bin/Code/UIModes/WFritzAnalysisTable.py` — add right-click context menu for engine switch (FR-48), "Copy to notation" (FR-44), "Clear" (FR-45)
- Engine tab ribbon actions: implement `caissa:select_engine` panel (FR-48), FR-49, FR-50
- Kibitzer actions: cap at 6 (FR-51), add Remove all (FR-53)

**What we implement:**

- `caissa:infinite_analysis` toggle flips `ManagerSolo.play_against_engine`
- Depth ▼ / Lines ▼ panels open; both disabled when not in analysis mode
- Copy to notation and Clear wired
- Select Engine ▼ panel lists installed engines
- Engine-pane right-click opens engine switch
- Kibitzers capped at 6; Remove all available

**TDD test cases:**

- `test_infinite_analysis_toggle_flips_play_against_engine` — unit test
- `test_depth_panel_disabled_when_play_mode` — `caissa:depth_panel` disabled when `play_against_engine == True`
- `test_lines_panel_disabled_when_play_mode` — same for lines
- `test_select_engine_panel_lists_installed_engines` — panel items match engine installation
- `test_kibitzer_cap_at_six` — adding a 7th kibitzer is silently ignored or shows an error
- `test_remove_all_kibitzers` — after Remove all, kibitzer count is 0

**Real-execution evidence (Gate D requirement):**  
Launch `tools/caissa` in Fritz mode. Confirm:
- Engine eval numbers visible in analysis table (Infinite Analysis)
- Click caissa:infinite_analysis toggle → engine starts replying to moves
- Click toggle again → engine stops replying; analysis resumes

**Spec refs:** FR-39..FR-53, D20

---

## Phase 5 — View Tab ⬜

**Branch:** `feat/fritz-mode-phase5`

**Files created:**

- `bin/Code/Fritz/Layouts.py` (FR-56; Pure tier)

**Files modified:**

- `bin/Code/UIModes/actions/modern_fritz_ui.py` — implement `caissa:std_layout` → `WDropdownPanel` backed by `Layouts.py` (FR-21, FR-54)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` — implement `caissa:fullscreen` toggle (FR-55)
- `bin/Code/Fritz/WRibbon.py` or action registry — implement Arrange shortcuts (FR-55)
- View ▸ Panes checkboxes confirmed in sync with Home ▸ Panes (FR-59)

**What we implement:**

- Standard Layouts ▼ panel with six named presets + Save / Load / Factory Settings
- Last layout restored at startup (wire `GeometryStore` call in Phase 1 already done; this phase verifies it via a restart test)
- Full Screen toggle
- Top 2 Vertical / Horizontal / Maximize All arrange shortcuts

**TDD test cases:**

- `test_named_layouts_apply_splitter_sizes` — unit test against `Layouts.NAMED_LAYOUTS`
- `test_layouts_pure_tier` — `Layouts.py` importable with no Qt on PYTHONPATH
- `test_save_load_layout_round_trip` — save current splitter sizes; change; load; sizes match saved
- `test_factory_settings_restores_defaults` — factory settings produces the Standard preset sizes
- `test_last_layout_restored_on_reentry` — enter Fritz mode twice; second entry restores layout from first

**Spec refs:** FR-54..FR-59, §5.3 (Layouts interface)

---

## Phase 6 — Polish ⬜

**Branch:** `feat/fritz-mode-phase6`

**Files moved (git mv):**

- `bin/Code/UIModes/WFritzAnalysisTable.py` → `bin/Code/Fritz/WFritzAnalysisTable.py`
- `bin/Code/UIModes/WFritzEvalGraph.py` → `bin/Code/Fritz/WFritzEvalGraph.py`
- `bin/Code/UIModes/WFritzPlayerHeader.py` → `bin/Code/Fritz/WFritzPlayerHeader.py`
- `bin/Code/UIModes/WFritzEvalBar.py` → `bin/Code/Fritz/WFritzEvalBar.py` (if exists)
- Any remaining `WFritz*` in `bin/Code/UIModes/` → `bin/Code/Fritz/`

**Files modified:**

- `tests/unit/fritz/test_completeness.py` — confirm all moved widgets are covered by purity AST walk (NFR-4, NFR-5)
- `Resources/Styles/Fritz.qss`, `Modern Fritz.qss` — close the 30 px ribbon-height gap:
  QAT height 12 → 29 px, content area 73 → 91 px, `selected_tab_breaks_rule` = True
- Icons per the tables in `docs/fritz/ribbon-design.md` §§ "Icons"

**What we implement:**

- All `WFritz*` widgets inside `bin/Code/Fritz/` and covered by purity enforcement
- Ribbon geometry matches the measured Fritz 18 reference
- Icons in place for all ribbon buttons per the approved design

**TDD test cases:**

- `test_wfritz_widgets_in_fritz_package` — no `WFritz*` in `bin/Code/UIModes/` (AST scan)
- `test_purity_all_fritz_widgets_covered` — `test_completeness.py` covers the moved widgets
- `test_ribbon_height_matches_reference` — `ribbon_report.py --variant light` reports total height 143 px, QAT 29, content 91, `selected_tab_breaks_rule` True

**Spec refs:** NFR-4, NFR-5; `docs/fritz/ribbon.md` § "Measured reference"

---

## Verification

After all phases complete:

```bash
cd /Users/johannes/code/lucaschess

make lint       # ruff check --config ruff.toml — zero issues
make test       # unit + rpa, no Qt (use background / longer timeout)
make test-all   # cross-checks markers vs filesystem
make test-ui    # in-process Qt, offscreen
make docs       # sphinx -W, zero warnings
make cov-fritz  # ≥ 90 % Code.Fritz coverage

# ribbon geometry check
PYTHONPATH=. .venv/bin/python3 tools/design/ribbon_report.py --variant light

# direct pytest (requires venv interpreter):
QT_QPA_PLATFORM=offscreen /Users/johannes/code/lucaschess/.venv/bin/python3 \
    -m pytest tests/ui/test_fritz_layout.py tests/ui/test_fritz_ribbon.py -v
```

**Real-execution sign-off** (CLAUDE.md § "Non-Negotiable" — required before any phase is declared done):  
Launch `tools/caissa`, switch to Fritz mode, and confirm by observation:
1. No landing screen — board and panes appear immediately
2. Eval numbers moving in the engine analysis pane, engine not replying
3. Home ▸ Levels → game starts, engine replies
4. Every ▼ button opens a dropdown panel
5. Toggle buttons (Flip Board, Analyse, Full Screen) show correct checked state
6. Layout is restored after exiting and re-entering Fritz mode
