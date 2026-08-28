# Fritz Polish — Implementation Steps

<!-- PURPOSE: Phase-by-phase TDD implementation tracker.
     Mark phases complete (✅) as they finish. Update test lists if scope changes.
     Keep in sync with feature_spec.md.

     Caissa adaptation: no ABC stubs. Phase 1 delivers working, tested code for the
     first logical group. There is no "all methods as NotImplementedError stubs" phase. -->

Living implementation tracker for the Fritz Polish feature.
Updated after each phase is completed.

**Spec reference:** [feature_spec.md](feature_spec.md)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Complete |

---

## Phase D — Documentation & Process ✅

**Branch:** `docs/fritz-polish`

**Files:**

- `docs/features/fritz-polish/initial_idea.md` (create — FROZEN)
- `docs/features/fritz-polish/feature_spec.md` (create — Gate A before any code)
- `docs/features/fritz-polish/feature_steps.md` (create — this file)
- `docs/features/fritz-polish/implementation_plan.md` (create)
- `docs/fritz/README.md` (create — design-time)
- `docs/fritz/concepts.md` (create — design-time)
- `docs/fritz/glossary.md` (create — design-time)
- `docs/fritz/decisions.md` (create — design-time)
- `docs/fritz/design-approval.md` (create — filled at the gate, stub now)
- `docs/standards/ui-design-process.md` (create)
- `docs/standards/architecture.md` (create)
- `docs/modern-fritz.md` (supersede via `git mv` content into `docs/fritz/`)
- `CLAUDE.md` (edit — repo tree, Key Architecture Concepts, Standards, Development Commands)
- `CHANGELOG.md` (edit — `[Unreleased]` entry)

**What we deliver:**

- Problem statement frozen at scope-lock
- Full spec with all eleven sections, purity-tier table, Classical Invariant argument, all N-FRITZ constraints
- This steps document with all test names for all phases (later phases as xfail stubs)
- Design-time product docs: README, concepts, glossary, ADR log
- Two new standards that every future mode inherits: `ui-design-process.md`, `architecture.md`
- Gate A checklist complete: spec present, Classical Invariant impact stated, `initial_idea.md` frozen, no open decision

**TDD test cases:**

All planned test names are recorded below with `@pytest.mark.xfail(strict=True)` markers until the
owning phase lands. The parity test in `tests/unit/fritz/test_completeness.py` asserts these names
exist in source.

**Spec refs:** BR-1 through BR-5, §1, §8 (Classical Invariant)

**Docs shipped (Gate H):** `docs/fritz/README.md`, `docs/fritz/concepts.md`,
`docs/fritz/glossary.md`, `docs/fritz/decisions.md`, `docs/standards/ui-design-process.md`,
`docs/standards/architecture.md`

---

## Phase 0 — Fritz package skeleton, QSS contract, design harness ✅

**Branch:** `chore/fritz-foundations`

**Files:**

- `bin/Code/Fritz/__init__.py` (create — 0 bytes)
- `bin/Code/Fritz/Types.py` (create — frozen dataclasses, zero third-party imports)
- `bin/Code/Fritz/Errors.py` (create — `FritzError(CaissaError)` + subclasses)
- `bin/Code/Fritz/QssRules.py` (create — pure: `scan_qss`, `template_gaps`, `qproperties`)
- `bin/Code/Fritz/ModeGateway.py` (create — adapter: cached mode-JSON reader, `invalidate()`)
- `tests/unit/fritz/__init__.py` (create)
- `tests/unit/fritz/test_completeness.py` (create — purity + allowlist + feature_steps parity)
- `tests/unit/fritz/test_qss_rules.py` (create — T-QSS-01..07)
- `tests/unit/fritz/test_qss_parser_snapshot.py` (create — T-QPS-01..02, §0.2b characterisation)
- `tests/unit/fritz/test_mode_gateway.py` (create — cache-hit-count, `invalidate`)
- `tests/test_qproperty_contract.py` (create — T-QPR-01..05, offscreen)
- `tools/design/__init__.py` (create — `CAISSA_DESIGN_OUT` path, `get_design_out()`)
- `tools/design/fritz_mock.py` (create — `--scene` offscreen renderer)
- `tools/design/compare.py` (create — `images_mean_diff`, `crop_button` lifted from test)
- `tools/design/review.py` (create — builds `review.html`, opens via `webbrowser.open`)
- `tools/design/README.md` (create — usage only, links `docs/standards/ui-design-process.md`)
- `bin/Code/UIModes/UIModes.py` (edit — delegate `load_modes` to `ModeGateway`)
- `bin/Code/Main/InitApp.py` (edit — §0.2b: `split(":", 1)` + `rstrip(" {")`, optional)
- `bin/Code/QT/WColors.py` (edit — §0.2b: same two plus `dic_original.get(key, …)`, optional)
- `tests/test_sidebar_icon_consistency.py` (edit — import helpers from `tools/design/compare.py`)
- `ruff.toml` (edit — add `bin/Code/Fritz/**`, `tests/unit/fritz/**`, `tools/design/**`)
- `.coveragerc` (edit — second config `fritz.coveragerc` + `make cov-fritz`)
- `Makefile` (edit — `cov-fritz`, `docs-fritz` targets, `## ` comments)
- `docs/conf.py` (edit — `docs/fritz/api/` autodoc target)
- `.gitignore` (edit — `docs/fritz/api/`)
- `docs/fritz/qss-contract.md` (create — E1-E4 contract + per-widget property tables — Gate H)

**What we implement:**

- `bin/Code/Fritz/` package with its dependency-free foundations
- The three QSS authoring rules as executable code: `QssRules.scan_qss`, `template_gaps`, `qproperties`
- `ModeGateway` caching `Resources/Modes/` so Phase 7's ~486 parses per screen change become 1
- Design harness: offscreen rendering → PNG → diff score → review HTML sheet
- E1-E4 QSS extension contract documented in `docs/fritz/qss-contract.md`
- Optional §0.2b pre-parser hardening behind an additions-only snapshot test

**TDD test cases (tests/unit/fritz/test_qss_rules.py + tests/test_qproperty_contract.py):**

- `test_qss_scan_finds_q1_violation`
- `test_qss_scan_finds_q3_violation`
- `test_qss_scan_clean_on_all_shipped_stylesheets`
- `test_template_gaps_empty_for_all_shipped_colors`
- `test_qproperties_parses_multivalue_correctly`
- `test_qproperties_returns_empty_for_no_qproperty_lines`
- `test_qproperties_raises_on_unbalanced_brace`
- `test_load_modes_parses_once_across_100_calls`
- `test_invalidate_forces_exactly_one_reparse`
- `test_qproperty_names_resolve_to_declared_properties` (T-QPR-01)
- `test_property_defaults_are_valid_colors_or_positive_ints` (T-QPR-02)
- `test_fritz_and_dark_yield_different_resolved_values` (T-QPR-03)
- `test_widget_renders_with_no_stylesheet_using_defaults` (T-QPR-04)
- `test_wa_styled_background_set_on_all_custom_painted_widgets` (T-QPR-05)
- `test_qss_parser_snapshot_matches_baseline` (T-QPS-01)
- `test_qss_parser_snapshot_diff_is_additions_only` (T-QPS-02)

**Spec refs:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, NFR-4, NFR-5, §4, §5.2, N-FRITZ-1 through N-FRITZ-12

**Docs shipped (Gate H):** `docs/fritz/qss-contract.md`

---

## Phase 1 — De-hardcode the five WFritz* widgets ✅

**Branch:** `refactor/fritz-widget-qss`

**Files:**

- `bin/Code/UIModes/WFritzPlayerHeader.py` (edit — E1/E2/E3, remove constants)
- `bin/Code/UIModes/WFritzHome.py` (edit — inline `setStyleSheet` → `#WFritzHome*` selectors)
- `bin/Code/UIModes/WFritzEvalGraph.py` (edit — E1/E2, remove constants)
- `bin/Code/UIModes/WFritzAnalysisTable.py` (edit — mostly QSS, `qproperty-` for custom paints)
- `bin/Code/UIModes/WFritzNewGame.py` (edit — QSS + E4 dynamic properties)
- `bin/Code/Fritz/ThemeGateway.py` (create — adapter: `color`, `is_dark`, `nag_color`, `invalidate`)
- `bin/Code/Fritz/ConfigGateway.py` (create — adapter: `pgn_width`, `with_figurines`, `width_piece`, `ui_mode`, `set_width_piece`)
- `Resources/Styles/Modern Fritz.qss` (edit — add `WFritz*` selector blocks with `qproperty-` lines)
- `Resources/Styles/Modern Fritz.colors` (edit — add 6 `NAG_*` keys)
- `Resources/Styles/colors.template` (edit — add 6 `NAG_*` keys)
- `Resources/Styles/*.colors` (edit — add `NAG_*` to all 9 other files so `template_gaps` stays empty)
- `tests/unit/fritz/test_theme_gateway.py` (create)
- `tests/unit/fritz/test_config_gateway.py` (create)
- `tests/test_fritz_qproperties.py` (create — T-FQP-01..09, offscreen)

**What we implement:**

- Every `WFritz*` widget takes its design values from `qproperty-` (E1), box model from E2, fonts from E3, state from E4
- Every colour arrives via `qproperty-` or `ThemeGateway`; no widget reads `Code.dic_colors` directly
- Six `NAG_*` colour keys added to `colors.template` and all 10 existing `.colors` files
- Three latent defects fixed: `WFritzPlayerHeader` one-pixel height clip, dead CSS in `WFritzHome`, monkey-patched NAG colours moved to data

**TDD test cases (tests/test_fritz_qproperties.py):**

- `test_no_hardcoded_hex_outside_property_defaults` (T-FQP-01)
- `test_every_python_property_has_qss_line_in_both_themes` (T-FQP-02)
- `test_every_qss_qproperty_has_python_property` (T-FQP-03)
- `test_different_themes_yield_different_resolved_values` (T-FQP-04)
- `test_no_stylesheet_renders_with_documented_defaults` (T-FQP-05)
- `test_player_header_height_not_less_than_content` (T-FQP-06)
- `test_player_header_font_family_not_menlo_under_qss` (T-FQP-07)
- `test_nag_keys_in_template_and_all_colors_files` (T-FQP-08)
- `test_no_widget_reads_dic_colors_directly` (T-FQP-09)

**Spec refs:** FR-7 through FR-15, NFR-2, NFR-3, §5.4 (ThemeGateway, ConfigGateway)

**Docs shipped (Gate H):** `docs/fritz/qss-contract.md` per-widget property tables updated

---

## Phase 2 — Fixed window, board fits the available space ✅

**Branch:** `feat/fritz-fixed-window`

**Files:**

- `bin/Code/Fritz/BoardFit.py` (create — pure: `ancho_for_width_piece`, `width_piece_for_ancho`, `fit`)
- `bin/Code/Fritz/GeometryStore.py` (create — adapter: `save_window`, `load_window`, `save_splitters`, `load_splitters`, `clamp_to_screens`)
- `bin/Code/Main/MainWindow.py` (edit — `_fit_board`, `adjust_size` guard, `_fit_board_now`, `changeEvent` Fritz branch, `schedule_fit_board`, `save_video`/`restore_video` via GeometryStore)
- `bin/Code/Main/WBase.py` (edit — `key` at `:291` uses `x_tb_orientation_horizontal`)
- `bin/Code/Main/WInformation.py` (edit — `_fit_board` guard at `:308`)
- `bin/Code/ManagerBase/ManagerResistance.py` (edit — `_fit_board` guard at `:295`)
- `bin/Code/QT/LCDialog.py` (edit — `register_splitter` replace-by-name, `unregister_splitter`, `len(li_sp) == sp.count()`)
- `bin/Code/Board/Board.py` (edit — `fit_to`, `fit_to_width_piece`)
- `bin/Code/Rpa/Driver.py` (edit — `QtDriver`: `window_info`, `board_info`, `resize_window`, `set_window_state`, `set_splitter_sizes`, `click_tabbar`)
- `bin/Code/Debug/RemoteControl.py` (edit — two-line delegation per new verb)
- `Resources/Modes/modern-fritz.json` (edit — `layout` block with `fit_board_to_window`, `default_size`, `right_col_width`)
- `tests/ui/rc_contract.json` (edit — success-path probes for `window_info`, `board_info`; probes for new verbs)
- `tests/unit/fritz/test_board_fit.py` (create — T-BFIT-01..08, no Qt)
- `tests/unit/fritz/test_geometry_store.py` (create — round-trip, maximized encoding, offscreen clamp)
- `tests/ui/test_fixed_window.py` (create — T-FIX-01..15)

**What we implement:**

- `_fit_board` flag gates the whole fixed-window path; absent key and `null` both read as false
- `adjust_size` and `_adjust_tamh` inert in Fritz via two-line early returns
- Board fit arithmetic in `BoardFit` (pure); `Board` only applies it
- Four anti-loop guards: `SetNoConstraint`, reentrancy flag, `_last_applied_ap`, owned `QTimer(60ms)`
- `changeEvent` Fritz branch: board zoom disabled, F11 handled without `maximize_size`
- Splitter persistence: three latent bugs fixed (deleted objects, hardcoded `len==2`, stale sizes)
- Six new `QtDriver` verbs including `click_tabbar` (bare `QTabBar` click, needed by Phases 5 + 7)
- `WBase.py:291` board-config key decoupled from `key_video`
- `test_fritz_layout.py` T-FRITZ-01/02/03 `KeyError` fix (twelve lines, `w`/`h` not `width`/`height`)

**TDD test cases (tests/unit/fritz/test_board_fit.py):**

- `test_ancho_for_width_piece_matches_characterisation_table` (T-BFIT-01)
- `test_width_piece_for_ancho_is_monotonic` (T-BFIT-02)
- `test_round_trip_is_identity` (T-BFIT-03)
- `test_fit_clamps_to_min_ancho_on_zero_pane` (T-BFIT-04)
- `test_fit_is_idempotent` (T-BFIT-05)
- `test_negative_pane_returns_min_ap` (T-BFIT-06)
- `test_tam_frontera_shifts_ancho_by_double` (T-BFIT-07)
- `test_fit_result_clamped_flag` (T-BFIT-08)

**TDD test cases (tests/ui/test_fixed_window.py):**

- `test_resize_window_reports_correct_size` (T-FIX-01)
- `test_window_unchanged_after_game_start` (T-FIX-02)
- `test_window_unchanged_after_return_home` (T-FIX-03)
- `test_board_grows_with_window` (T-FIX-04)
- `test_min_size_small` (T-FIX-05)
- `test_maximize_restore_returns_original_size` (T-FIX-06)
- `test_fullscreen_round_trip` (T-FIX-07)
- `test_width_piece_never_persisted_by_fit` (T-FIX-08)
- `test_splitter_sizes_survive_restart` (T-FIX-09)
- `test_no_runtime_error_on_repeated_mode_enter` (T-FIX-10)
- `test_classical_adjust_size_still_runs` (T-FIX-11)
- `test_board_zoom_disabled_in_fritz_enabled_in_classical` (T-FIX-12)
- `test_show_variations_does_not_change_window_size` (T-FIX-13)
- `test_no_basev_entry_created_by_fritz_mode` (T-FIX-14)
- `test_dispatch_size_path_guarded` (T-FIX-15)

**Spec refs:** FR-16 through FR-24, FR-46 through FR-49, NFR-1, §5.3 (BoardFit), §5.4 (GeometryStore)

**Docs shipped (Gate H):** `docs/fritz/concepts.md` fixed-window section

---

## Phase 3 — Pane title bars and Fritz density ✅

**Branch:** `feat/fritz-panes`

**Files:**

- `bin/Code/Fritz/WFritzPane.py` (create — title bar + content, `qproperty-` contract)
- `bin/Code/Fritz/PaneRegistry.py` (create — pure: `register`, `names`, `spec`, `restore_px`)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` (edit — wrap panes in `WFritzPane`, `pane_api()`, fixed splitter pixel literals)
- `Resources/Styles/Modern Fritz.qss` (edit — add `QSplitter::handle`, `#WFritzPane*` blocks; fix `QTableView` and `QProgressBar` conflicts)
- `tests/unit/fritz/test_pane_registry.py` (create — T-PREG-01..04, no Qt)
- `tests/ui/test_fritz_panes.py` (create — T-PANE-01..07)

**What we implement:**

- `WFritzPane(spec, content)` with title bar: name left, `▾ ✕` right
- `✕` shares the same hide path as the ribbon Panes group (FR-26)
- `▾` menu: Hide, Reset size, sibling submenu — no floating, no docking
- Title bar is a `paintEvent` gradient with colours from `qproperty-titleTop`/`titleBottom` (E1)
- `PaneRegistry`: pure sizing decisions; Qt half stays in the mode hook closures
- Pixel literals in `modern_fritz_ui.py` replaced with `qproperty-` values or `layout` JSON keys

**TDD test cases (tests/unit/fritz/test_pane_registry.py):**

- `test_restore_px_returns_default_from_zero` (T-PREG-01)
- `test_restore_px_returns_current_when_nonzero` (T-PREG-02)
- `test_restore_px_floors_at_min_px` (T-PREG-03)
- `test_unknown_key_raises_pane_not_registered_error` (T-PREG-04)
- `test_names_preserves_registration_order` (T-PREG-05)
- `test_register_same_key_twice_replaces_not_duplicates` (T-PREG-06)

**TDD test cases (tests/ui/test_fritz_panes.py):**

- `test_pane_title_bars_present_with_correct_labels` (T-PANE-01)
- `test_title_bar_height_matches_qss_property` (T-PANE-02)
- `test_close_button_hides_pane_siblings_intact` (T-PANE-03)
- `test_reshown_pane_returns_above_min_px` (T-PANE-04)
- `test_chevron_menu_has_three_items_and_sibling_submenu` (T-PANE-05)
- `test_mode_exit_restores_layout_to_baseline` (T-PANE-06)
- `test_no_fritz_widget_has_zero_dimension` (T-PANE-07)

**Spec refs:** FR-25 through FR-28, §5.5 (WFritzPane), §5.1 (PaneRegistry)

**Docs shipped (Gate H):** `docs/fritz/qss-contract.md` `WFritzPane` property table

---

## Phase 4 — LCD clocks and the dense eval line ⬜

**Branch:** `feat/fritz-clocks-eval`

**Files:**

- `bin/Code/Fritz/WFritzLCD.py` (create — `QPainterPath` seven-segment widget)
- `bin/Code/Fritz/ClockModel.py` (create — pure: `parse`, `format`, `digits`)
- `bin/Code/Fritz/EvalModel.py` (create — pure: `describe`, `describe_values`)
- `bin/Code/Fritz/EngineGateway.py` (create — adapter: `latest_analysis()`)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` (edit — substitute `WFritzLCD` for `WBase` clock labels)
- `tests/unit/fritz/test_clock_model.py` (create — T-CLK-01..N, no Qt)
- `tests/unit/fritz/test_eval_model.py` (create — T-EVAL-01..N, no Qt)
- `tests/ui/test_fritz_clocks.py` (create — T-LCD-01..06)

**What we implement:**

- `WFritzLCD`: `QPainterPath` polygons for the seven segments; lit/dim/box/thickness from `qproperty-` (E1); box model from E2; accepts `H:MM:SS`, `MM:SS` or HTML two-line form
- `ClockModel.parse` handles all three input forms; used at all three reachable clock sites
- Dense eval summary above the PV rows: *`Side is <assessment>: <nag> (<cp>) Depth: <d>/<sd> <time> <nodes>`*
- `EngineGateway.latest_analysis()` is the only impure part; `EvalModel.describe` is pure

**TDD test cases (tests/unit/fritz/test_clock_model.py):**

- `test_parse_hmmss_form`
- `test_parse_mmss_form`
- `test_parse_html_two_line_form`
- `test_parse_returns_none_for_garbage`
- `test_format_tenths_below_threshold`
- `test_format_no_tenths_above_threshold`
- `test_negative_seconds_clamp_to_zero`

**TDD test cases (tests/unit/fritz/test_eval_model.py):**

- `test_assessment_ladder_slightly_better`
- `test_assessment_ladder_winning`
- `test_mate_score_produces_correct_nag`
- `test_none_cp_is_handled`
- `test_sign_is_side_to_move_relative`
- `test_describe_values_produces_correct_summary`

**TDD test cases (tests/ui/test_fritz_clocks.py):**

- `test_lcd_widgets_present_and_visible` (T-LCD-01)
- `test_lcd_renders_nonbackground_pixels` (T-LCD-02)
- `test_lcd_parses_both_input_forms` (T-LCD-03)
- `test_classical_shows_qlabel_not_lcd` (T-LCD-04)
- `test_eval_summary_line_format` (T-LCD-05)
- `test_three_reachable_clocks_agree` (T-LCD-06)

**Spec refs:** FR-29 through FR-32, §5.1 (EvalSummary), §5.3 (ClockModel, EvalModel)

**Docs shipped (Gate H):** `docs/fritz/qss-contract.md` `WFritzLCD` property table

---

## Phase 5 — Notation tab strip and NAG palette ⬜

**Branch:** `feat/fritz-notation`

**Files:**

- `bin/Code/Fritz/NotationRowModel.py` (create — pure: `row(move) -> NotationRow`)
- `bin/Code/Fritz/Delegates.py` (create — `FritzEtiquetaPGN(Delegados.EtiquetaPGN)`)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` (edit — add `QTabBar`, NAG buttons, attach delegate)
- `tests/unit/fritz/test_notation_row_model.py` (create — uses Qt-stubbing bootstrap)
- `tests/ui/test_fritz_notation.py` (create — T-NOT-01..08)

**What we implement:**

- Bare `QTabBar` above the notation grid: Notation / Training / Score sheet / LiveBook / Openings Book / My Moves
- Tab list declared in `layout.notation_tabs`; only Notation has content initially
- `FritzEtiquetaPGN` subclass overrides `paint` only; inherits figurine glyphs and `ChessMerida.ttf`
- Two rows of NAG symbol buttons wired to existing NAG plumbing
- `modern_fritz_ui.py` monkey-patch of `grid_color_fondo` replaced by delegate

**TDD test cases (tests/unit/fritz/test_notation_row_model.py):**

- `test_row_returns_correct_figurine_glyph`
- `test_row_returns_correct_nag_nums`
- `test_row_indent_level_for_variation`
- `test_row_is_current_flag`

**TDD test cases (tests/ui/test_fritz_notation.py):**

- `test_tab_labels_in_order` (T-NOT-01)
- `test_tab_switch_no_error` (T-NOT-02)
- `test_current_move_highlighted` (T-NOT-03)
- `test_nag_rows_present_with_correct_count` (T-NOT-04)
- `test_nag_button_applies_to_move` (T-NOT-05)
- `test_fritz_delegate_attached_in_fritz` (T-NOT-06)
- `test_nag_annotated_cell_differs_from_unannotated` (T-NOT-07)
- `test_classical_has_no_tab_strip` (T-NOT-08)

**Spec refs:** FR-33 through FR-35, §5.1 (NotationRow), §5.5 (Delegates.FritzEtiquetaPGN)

**Docs shipped (Gate H):** none (visual phase — uses design approval gate for sign-off)

---

## Phase 6 — Fritz light theme as the default ⬜

**Branch:** `feat/fritz-light-theme`

**Files:**

- `Resources/Styles/Fritz.qss` (create — light palette variant, block-for-block from `Modern Fritz.qss`)
- `Resources/Styles/Fritz.colors` (create — 92 keys: 85 template + `IS_DARK` + 6 `NAG_*`)
- `Resources/Modes/modern-fritz-dark.json` (create — `"style": "Modern Fritz"`, `"hook": "modern_fritz"`)
- `Resources/Modes/modern-fritz.json` (edit — `"style": "Fritz"`)
- `bin/Code/UIModes/UIModes.py` (edit — `load_mode_hook` reads optional `"hook"` key)
- `tests/test_fritz_light_theme.py` (create — T-LIT-01..08)

**What we implement:**

- `Fritz.qss` light blue-grey palette; `Modern Fritz.qss` kept as dark sibling
- Both files declare the same set of `qproperty-` names and are geometrically identical once colour lines are stripped
- `BOARD_STATIC` stays dark in both themes (text drawn on the board)
- `modern-fritz-dark.json` shares the same hook as `modern-fritz.json` via optional `"hook"` key
- `Fritz.colors` carries all 92 keys so `template_gaps` stays empty for all 11 files

**TDD test cases (tests/test_fritz_light_theme.py):**

- `test_template_gaps_empty_for_all_eleven_colors_files` (T-LIT-01)
- `test_no_q1_or_q3_violation_in_fritz_qss` (T-LIT-02)
- `test_geometry_parity_between_themes` (T-LIT-03)
- `test_same_qproperty_names_different_values` (T-LIT-04)
- `test_board_static_dark_in_both_themes` (T-LIT-05)
- `test_is_dark_differs_between_themes` (T-LIT-06)
- `test_both_modes_resolve_to_modern_fritz_ui_hook` (T-LIT-07)
- `test_every_wfritz_selector_present_in_both_themes` (T-LIT-08)

**Spec refs:** FR-12 through FR-15, §5.6 (mode-JSON schema additions)

**Docs shipped (Gate H):** `docs/fritz/theming.md` (create)

---

## Phase 7 — The Office-style ribbon ⬜

**Branch:** `feat/fritz-ribbon`

**Files:**

- `bin/Code/Fritz/RibbonModel.py` (create — pure: `load`, `state`, `overflow`, `best_tab`, `compact`)
- `bin/Code/Fritz/Ribbon.py` (create — `install`, `sync`)
- `bin/Code/Fritz/WRibbon.py` (create — `WRibbon`, `WRibbonPage`, `WRibbonGroup`, `WRibbonPanesGroup`)
- `bin/Code/UIModes/actions/modern_fritz_ui.py` (edit — `pane_api()` capability)
- `bin/Code/Main/WBase.py` (edit — the three `create_toolbar`/`pon_toolbar` edits, ~14 net lines)
- `bin/Code/Rpa/Driver.py` (edit — `ribbon_info`, `select_ribbon_tab`, `click_ribbon`, `toggle_pane`; extend toolbar enumeration/click for ribbon)
- `bin/Code/Debug/RemoteControl.py` (edit — two-line delegation per new verb)
- `Resources/Modes/modern-fritz.json` (edit — add `"ribbon": "modern-fritz"`)
- `Resources/Ribbons/modern-fritz.json` (create — the ribbon content map)
- `Resources/Styles/Modern Fritz.qss` (edit — add `#WRibbon*` selector blocks)
- `Resources/Styles/Fritz.qss` (edit — same `#WRibbon*` blocks, light values)
- `tests/ui/rc_contract.json` (edit — probes for `ribbon_info`, `select_ribbon_tab`, `click_ribbon`, `toggle_pane`)
- `tests/test_ribbon_map.py` (create — T-RMAP-01..08, no Qt)
- `tests/ui/test_fritz_ribbon.py` (create — T-RIB-01..11)
- `docs/fritz/ribbon.md` (create — Gate H)
- `docs/fritz/testing.md` (create — Gate H)
- `docs/fritz/troubleshooting.md` (create — Gate H)

**What we implement:**

- `RibbonModel`: pure load/validate + state/overflow/best_tab/compact — no Qt
- `Ribbon.install` returns `None` + logs on any failure (never a dead app)
- `WRibbon` wired by `setDefaultAction(dic_toolbar[key])` only — no new dispatch code
- Ribbon hosted in `QToolBar` as one `QWidgetAction`; height pinned before first board fit
- Contextual tab switching respects user manual selections
- `WRibbonPanesGroup` drives `pane_api` from the mode hook
- Four new `QtDriver` verbs; toolbar enumeration extended without breaking existing key set

**TDD test cases (tests/test_ribbon_map.py):**

- `test_all_ribbon_jsons_valid_schema` (T-RMAP-01)
- `test_unique_tab_and_group_ids` (T-RMAP-02)
- `test_no_duplicate_slot_keys` (T-RMAP-03)
- `test_all_keys_resolve_in_constantes` (T-RMAP-04)
- `test_all_fritz_toolbar_keys_in_slot_or_quick_access` (T-RMAP-05)
- `test_never_filter_keys_in_quick_access` (T-RMAP-06)
- `test_no_non_fritz_mode_has_ribbon_key` (T-RMAP-07)
- `test_no_ribbon_json_in_modes_directory` (T-RMAP-08)

**TDD test cases (tests/ui/test_fritz_ribbon.py):**

- `test_ribbon_present_correct_height` (T-RIB-01)
- `test_tab_labels_in_order_each_tab_has_groups` (T-RIB-02)
- `test_group_captions_below_controls` (T-RIB-03)
- `test_resign_disabled_at_home_geometry_stable` (T-RIB-04)
- `test_overflow_empty_across_screen_states` (T-RIB-05)
- `test_close_keys_in_quick_access` (T-RIB-06)
- `test_click_ribbon_new_game_opens_dialog` (T-RIB-07)
- `test_toggle_pane_hides_and_restores` (T-RIB-08)
- `test_user_tab_pin_respected` (T-RIB-09)
- `test_classical_mode_no_ribbon` (T-RIB-10)
- `test_resize_with_ribbon_board_fits` (T-RIB-11)

**Spec refs:** FR-36 through FR-45, §5.3 (RibbonModel), §5.5 (WRibbon, Ribbon)

**Docs shipped (Gate H):** `docs/fritz/ribbon.md`, `docs/fritz/testing.md`, `docs/fritz/troubleshooting.md`

---

## Phase 9 — Production Readiness ⬜

**Branch:** `chore/fritz-production-readiness`

**Files:**

- `docs/features/fritz-polish/production_readiness.md` (create)
- `docs/features/fritz-polish/feature_steps.md` (edit — mark all phases ✅)

**What we deliver:**

- `production_readiness.md` with 8 numbered headings + `## Findings` (each `F-n` labelled `(RESOLVED — Phase N)`) + `## Archive` note
- Branch coverage ≥ 90 % for `Code.Fritz` per `fritz.coveragerc`
- `make docs` clean — zero Sphinx warnings
- Every test name in this `feature_steps.md` asserted to exist in source by `test_completeness.py`
- Classical Invariant workflow green against the live app
- `git mv docs/features/fritz-polish/ docs/features/_archive/fritz-polish/`

**Spec refs:** §9, Gate E in `docs/process/sdd-workflow.md`

---

## Verification

After each phase completes, mark it ✅ in the phase heading of this document.

After all phases are complete:

```bash
make lint        # zero issues
make test        # all green
make cov-fritz   # ≥ 90 % Code.Fritz branch coverage
make docs        # zero warnings
make test-ui     # out-of-process, launches the real app
```
