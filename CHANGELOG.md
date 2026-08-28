# Changelog

All notable changes to **Caissa** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Caissa uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Upstream base: **Lucas Chess R6.0.4** by Lucas Monge (GPL-3.0).

---

## [Unreleased]

### Added
- **Modern Fritz — one-screen layout fix** (`feat/modern-fritz-layout`, PR #6)
  - `WFritzPlayerHeader`: Fritz-style player info strip (black player top, white bottom)
    polling `WBase.lb_player_*` / `lb_clock_*` at 500 ms; fixed 60 px height; Fritz blue
    clock colour; shown as the topmost pane of the Fritz right column during play
  - `modern_fritz_ui._swap_home_to_analysis`: complete rewrite — reparents `mw.base.pgn`
    (the actual game move list) into Fritz right column as the bottom pane; collapses
    WBase's internal right-panel widgets (player labels, clocks, rotulos, captures) to
    zero size so the board fills WBase; stores (layout, index) for full restoration on
    exit; Fritz right column becomes [WFritzPlayerHeader, WFritzAnalysisTable,
    WFritzEvalGraph, pgn] — a genuine Fritz-like one-screen arrangement
  - `modern_fritz_ui.on_mode_exit`: restores `mw.base.pgn` to its exact layout position
    in WBase, restores all widget size constraints, calls `show_replay()` — Classical
    mode renders identically to upstream after switching back
  - `_find_widget_in_layout(top_layout, target)`: recursive layout-tree search helper
    returning (layout, index) for a widget's direct container
  - `tests/ui/test_fritz_layout.py`: five Fritz-specific e2e tests (T-FRITZ-01–05)
    covering home panel width, in-game panel sizes, player header visibility, toolbar
    Fritz-style assertion, and mode-exit restoration

- **Modern Fritz — Stage 1: visual overhaul** (`feat/modern-fritz-layout`, PR #6)
  - `WFritzAnalysisTable`: proper multi-PV engine analysis table — up to 5 lines,
    each showing rank, score (Fritz blue/red), depth, and principal variation;
    `+`/`−` buttons control the number of visible PV lines; polls `analysis_bar.mrm`
    at 250 ms; replaces the old single-line `WFritzEnginePanel`
  - `WFritzHome`: Fritz-style home/landing panel shown on mode entry — three
    action buttons (New Game, Load Game, Enter & Analyze); swaps itself out for
    the analysis table when an action is chosen, giving the "one-screen" Fritz feel
    without requiring a popup dialog to start playing
  - `modern_fritz_ui.on_mode_enter`: shows `WFritzHome` first; connects
    `action_chosen` signal to swap in `WFritzAnalysisTable` then dispatch the
    action through the existing menu handlers (no new game-start logic)
  - `caissa:fritz_level` action (`fritz_level.py`): toolbar "Level" button that
    opens the Fritz level/time-control picker and restarts the game with new
    settings — no menu navigation required
  - `modern-fritz.json` toolbar allowlist: restricted to Fritz-relevant keys
    (resign, draw, takeback, new game, pause, config, utilities + home-screen
    keys); `TB_ADJOURN` removed; both `caissa:fritz_level` and
    `caissa:switch_mode` injected at toolbar start
  - `WFritzEvalGraph`: 80 px fixed-height evaluation profile graph — QPainter bar
    chart, Fritz-blue bars for white advantage, red for black, ±600 cp scale; polls
    `AnalysisBar.mrm` at 250 ms and accumulates one centipawn value per half-move;
    trims on backward navigation; inserted between analysis table and move list
  - `WFritzNewGame`: Fritz-style simplified game-start dialog — three toggle-button
    rows (Side: White/Black/Random, Level: Easy/Club/Active/Strong/Master/
    Grandmaster, Time: No limit/Blitz/Rapid/Classical); builds a complete
    `dic_var` and calls `ManagerPlayAgainstEngine.start()` directly, bypassing
    the full Play-Against-Engine popup entirely
  - `modern_fritz_ui._fritz_new_game`: helper that shows `WFritzNewGame` and starts
    the game directly — no ConfigurationsPAE round-trip, no Shortcuts indirection
  - `Modern Fritz.qss` / `.colors`: palette shifted from near-black (`#161616`) to
    Fritz medium-grey (`#252526` bg, `#2d2d2d` surface, `#3c3c3c` surface-2,
    `#505050` border, `#d4d4d4` text) — 98 colour values updated; Q1/Q2/Q3 checks
    pass clean; `BOARD_STATIC` preserved dark
  - Move quality colour coding in the PGN notation panel (Stage 5): Fritz-palette
    background tints for NAG-annotated moves — green shades for good/brilliant (!,
    !!), teal for interesting (!?), amber for dubious (?!), orange for mistake (?),
    red for blunder (??); monkey-patched onto the WBase instance at mode entry
    (`grid_color_fondo` + `ControlGrid.siColorFondo = True`) and fully removed on
    mode exit; NAG data requires Tutor/rating display to be active during play
  - Right-column layout: vertical `QSplitter` — home/analysis panel above
    `pgn_information` (move list); `on_mode_exit` restores `pgn_information` to the
    main splitter before cleanup
  - `UIModes.load_mode_hook`: normalise mode name to filename (spaces and hyphens →
    underscores; `"Modern Fritz"` → `modern_fritz_ui.py`)

- **Modern Fritz retro skin** (`feat/modern-fritz`, PR #5)
  - `Resources/Styles/Modern Fritz.qss` / `Modern Fritz.colors`: dark navy + Fritz-blue
    accent (`#1976d2`); 728-line QSS derived from Midnight with identical geometry
  - `Resources/Modes/modern-fritz.json`: full Classical feature set, pins `style` and
    `icons` so the Fritz look is automatic when the mode is selected
  - `docs/modern-fritz.md`: SDD covering palette, file roles, and authoring-rule compliance
  - `InitApp.init_app_style`: reads `active_mode().get("style")` and uses the mode-pinned
    QSS for the session (user's `x_style_mode` preference is preserved)
  - `InitApp.apply_live_style`: resolves `active_mode().get("icons")` as an `Icons` class
    attribute to allow mode-pinned icon pack without touching user preference
- **Theme overlay system — Steps 5–8** (`feat/overlay-steps-5-8`, PR #3)
  - `config_section` key in mode JSON: active mode can append a mode-owned tab
    (combobox/checkbox/spinbox/edit fields) to the General Configuration dialog
  - `configuration.mode_settings` dict: namespace-keyed storage persisted in the
    config pickle under `MODE_SETTINGS`; backwards-compatible (old pickles default `{}`)
  - `UIModes.load_mode_hook(mode_name)`: loads `actions/<mode>_ui.py` if present;
    `WindowConfig` calls `hook.patch_config_form(form, conf, overlay)` before `run()`
  - 27 classical-invariant unit tests in `tests/test_classical_invariant.py`
    (no Qt/display; run with `pytest tests/test_classical_invariant.py`)
  - Result unpack in `WindowConfig.options()` changed to index-based so an extra
    mode-section tab can never corrupt existing tab positions

- **UI integration testing framework** (`feat/ui-testing-framework`, PR #2)
  - `tests/ui/client.py`: `CaissaClient` wrapping the RemoteControl Unix socket;
    typed assertion helpers (`assert_dialog_field`, `assert_tab_exists`, etc.)
  - `tests/ui/conftest.py`: session-scoped `caissa_proc` + `client` fixtures;
    function-scoped `config_theme` fixture with automatic teardown restore
  - `tests/ui/test_overlay.py`: T-OVL-01–08 (Caissa theme label renames,
    hidden fields, tab renames, player-name round-trip)
  - `tests/ui/test_classical.py`: T-CLS-01–02 (classical invariant via live app)
  - `pytest.ini` with testpaths, markers, timeout config
  - `CAISSA_TEST=1` env-var guard in `Procesador.py` suppresses startup dialogs
    (update check, startup puzzles, first-time config) so tests reach home screen

- **Theme UI overlay system — Layer 1** (`feat/overlay-system`, PR #1)
  - `bin/Code/Config/FormOverlay.py`: `OverlayForm` proxy wrapping `FormLayout`;
    intercepts field builds to rename/hide labels; `result()` for safe named-field lookup
  - `load_overlay(theme_name)` reads `Resources/Styles/<name>.ui.json`; returns `{}`
    if absent (classical invariant preserved)
  - `Resources/Styles/Caissa.ui.json`: renames Mode→Theme, UI mode→Mode; hides
    Window style / Menu Play / Preventing system crashes; renames 5 tabs
  - `WindowConfig.options()` wrapped with `OverlayForm`; named-field unpack replaces
    fragile positional `*_ui_mode_rest` approach
  - `docs/ui-testing.md`: SDD for the UI testing framework
  - `docs/theme-mode-system.md`: SDD for the full Theme/Mode overlay architecture

- **Engineering standards and tooling**
  - `CLAUDE.md`: project guide with repo structure, key concepts, workflow rules
  - `docs/standards/coding-standards.md`: branch+PR workflow, commit message format,
    protected `main`, auto-merge policy
  - `docs/standards/spec-driven-development.md`: SDD-first requirement
  - `docs/standards/docstring-standards.md`: RST/Sphinx style
  - `docs/standards/error-handling.md`: domain exceptions, exc_info, raise-from
  - `docs/standards/logging-standard.md`: `%s`-style lazy formatting

- **RemoteControl commands** (`bin/Code/Debug/RemoteControl.py`)
  - `set_config <key> <value>`: sets a config attribute, saves, re-applies QSS
  - `open_config`: opens General Configuration dialog asynchronously via
    `QTimer.singleShot(0, proc.menu_options)`
  - Tests for both commands in `tests/test_remote_control.py`

### Fixed
- `RemoteControl._open_config` called `proc.opciones()` (non-existent); corrected
  to `proc.menu_options()`

---

## [Pre-release work — no version tag yet]

The sections below document work completed before the formal PR/branch workflow
was established (commits `7a657d4`…`991c2c7` on `main`).

### Added — Coach mode and UI Modes framework (Phase 5–7)

- **UI Modes framework** (`00ab3b8`)
  - `Resources/Modes/*.json`: mode definitions with `toolbar`, `menu_keys`,
    `toolbar_inject` allowlists
  - `bin/Code/UIModes/UIModes.py`: `load_modes()`, `active_mode()`,
    `allows_toolbar()`, `filter_menu_options()`, `toolbar_inject()`
  - `bin/Code/Menus/BaseMenu.py`: `filter_menu_options` called from `check_pending()`
  - `bin/Code/Main/WBase.py`: `pon_toolbar` applies toolbar filter + injects
    mode-defined actions
  - `Configuration.x_ui_mode`: new config key; added to `needs_reinit`
  - `WindowConfig.options()`: Mode combobox from `Resources/Modes/*.json` scan
  - `tools/dump_ui_keys.py`: introspects all menus + toolbar keys; outputs
    `tools/ui-keys.md`

- **Four focused modes** (`00ab3b8`)
  - `Resources/Modes/classical.json`: null allowlists — full upstream experience
  - `Resources/Modes/just-play.json`: board + clock only
  - `Resources/Modes/analyse.json`: engine output + PGN tree
  - `Resources/Modes/train.json`: tactics + Leitner + openings
  - `Resources/Modes/compete.json`: Elo ladders + tournaments
  - All modes include `TB_OPTIONS` so Configuration is always reachable (`991c2c7`)

- **Coach mode landing screen** (`245ec16`)
  - `bin/Code/UIModes/actions/coach_home.py`: 2×2 card grid (Play · Openings ·
    Review · Daily puzzle), registered as `caissa:coach_home`
  - `Resources/Modes/coach.json`: Coach mode JSON with `toolbar_inject`
  - `bin/Code/UIModes/actions/switch_mode.py`: `caissa:switch_mode` escape hatch
    present in every mode's toolbar

### Added — Caissa theme and icon system

- **Caissa/VSCode signature theme** (`9519c47`, `f8a035d` and refinements)
  - `Resources/Styles/Caissa.qss` / `Caissa.colors`: dark VS Code–inspired chrome,
    activity-bar sidebar, accent `#6366f1`, rounded corners, slim scrollbars
  - `Resources/Styles/VSCode.qss` (deprecated name, now Caissa)
  - Board colours matched to VS Code charcoal `#1e1e1e`
  - Balestegui2 piece set used as default (`3a6d8b0`)
  - Sidebar gap, separator lines, and wrench icon removed (`718de27`)

- **VS Code icon pack** (`4f961a1`, `27efbbb`, `b5c1ca6`)
  - 52 SVG overrides for home-screen and game-screen toolbar icons
  - Custom codicons-style toolbar icons matching the VS Code aesthetic
  - Adjourn icon normalised; sidebar icon consistency test suite added (`46afb7d`)
  - Stroke weights tuned to visual parity between home and play screens

- **Midnight and Daylight themes** (`94f106d`)
  - `Resources/Styles/Midnight.qss` / `Midnight.colors`
  - `Resources/Styles/Daylight.qss` / `Daylight.colors`
  - Shared 8px radius, 10px padding; identical geometry between dark and light
  - Palette covers: QScrollBar, QLineEdit, QSpinBox, QTextEdit, QProgressBar, tabs,
    headers, focus ring, selection highlight

- **Midnight/Daylight icon packs** (`5e2a6d8`)
  - `Resources/IntFiles/Iconos_midnight.*`, `Iconos_daylight.*`
  - Duotone recolour using `haz_sepia` pipeline; exclusion sets for semantic colours
    (Leitner boxes, Everest decorative, status LEDs)
  - `IconosBase.MIDNIGHT = 3`, `DAYLIGHT = 4` registered in `dic_files`

- **IS_DARK QPalette and CHROME_* colour keys** (`fd3e12f`)
  - `IS_DARK` flag in `.colors` files drives a full `QPalette` in `init_app_style`
  - 10 new `CHROME_*` keys (`CHROME_SURFACE`, `CHROME_ACCENT`, etc.) in all themes
  - Inline `setStyleSheet` calls for most-visible chrome sites routed through
    `Code.dic_colors`

- **Live retheme without restart** (`b4e4127`, `f8a035d`)
  - `InitApp.apply_live_style()`: re-applies QSS + palette immediately on config save
  - Icon pack change still requires restart; all other style changes are instant
  - RemoteControl `theme <name>` command applies theme atomically

### Added — macOS platform and foundation (Phase 0)

- **Apple Silicon native platform** (`36be1a3`)
  - `bin/OS/darwin/OSEngines.py`: native engine registry for arm64
  - Native engines committed to LFS: Stockfish 18 (0.5 MB + shared NNUE nets),
    Lc0 0.32.1 (1.8 MB), irina (92 KB), 10× Maia nets + books
  - `bin/OS/darwin/FasterCode.cpython-313-darwin.so`: arm64 C extension
  - `bin/OS/darwin/uci_options.sqlite`
  - All absolute Homebrew symlinks replaced with real relocatable binaries

- **macOS toolchain** (`02c3413`)
  - `tools/caissa`: main launcher (venv + `CAISSA_TEST` support)
  - `tools/caissa-ctl`: RemoteControl CLI client
  - `tools/lc-engine`: Docker bridge shim for Linux engine wrappers
  - `tools/gen_darwin_engines.py`: generates relocatable wrapper scripts
  - `tools/build_stockfish.sh`, `build_lc0.sh`, `build_irina.sh`,
    `build_drawfish.sh`: reproducible source builds

- **Docker optional / native Drawfish** (`4ae71bd`)
  - `OSEngines.py` availability probe: single `docker inspect` with 2 s timeout;
    skips bridged loop entirely when Docker is absent or stopped
  - Native `bin/OS/darwin/Engines/drawfish/drawfish` (arm64, no NNUE)
  - Relocatable wrapper generation: `REPO=$(cd … && pwd)` self-location
  - `eguzkilore` removed from native keys (was registering an ELF x86-64 binary
    as native arm64)
  - `Configuration.path_book` guarded against missing alias (unguarded dict lookup
    was taking down the Play against engine dialog)

- **Rename to Caissa** (`68afb07`)
  - `Code.lucas_chess` → `"Caissa"` (single assignment in `Translate.py`)
  - `VERSION = "1.0"`, `UPSTREAM_VERSION = "R 6.0.4"` (provenance preserved)
  - Auto-updater disabled: menu entry removed, `Update.update()` / `update_at_start()`
    short-circuited; `update_manual()` (local ZIP install) preserved
  - GPL §5(a) attribution in About dialog
  - `README.md`: platform (Apple Silicon, macOS 14+) stated in first screenful,
    badge row, requirements, install, engine roster, credits
  - `LucasChess.command` → `Caissa.command`; `tools/lucaschess` → `tools/caissa`

- **Stockfish NNUE repair** (`fe58582`)
  - LFS stub `.nnue` files caused Stockfish exit code 1 after first `go` command
  - Fixed by ensuring full LFS checkout of both NNUE files

### Added — Testing infrastructure

- **RemoteControl Unix socket server** (`f8a035d` and many subsequent commits)
  - `bin/Code/Debug/RemoteControl.py`: Qt-safe command dispatcher over
    `/tmp/caissa-control.sock`; 30+ commands covering ping, info, screenshot,
    toolbar, game control, UI inspection/interaction, dialog control
  - `tools/caissa-ctl`: CLI wrapper for manual use and debugging
  - `tests/test_remote_control.py`: live-app tests (23+ assertions); requires
    running Caissa process; auto-skips if socket absent

- **Sidebar icon consistency test suite** (`46afb7d`)
  - `tests/test_sidebar_icon_consistency.py`: asserts all sidebar icons render
    at consistent visual weight and size

### Fixed

- `dialog_cancel` was closing the main window instead of the topmost dialog
  (`9874f12`); all 23 RemoteControl tests green after fix
- Toolbar square-button enforcement: `abca1e7` fixed vertical icon-only toolbar
  to use 48×48 px buttons consistently
- Game toolbar draw icon and duplicate gears resolved (`d30be61`)

---

## [Upstream] — Lucas Chess R6.0.4

Base from which Caissa was forked. See
[lukasmonk/lucaschessR6](https://github.com/lukasmonk/lucaschessR6) for full
upstream history.
