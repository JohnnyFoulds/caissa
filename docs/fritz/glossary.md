# Glossary

Terms used in the Caissa Fritz layer, with Fritz 18/19 equivalents where applicable.

---

| Term | Definition | Fritz equivalent |
|---|---|---|
| **`adjust_size`** | `MainWindow` method that loops `adjustSize()` to shrink the window to the board. Inert in Fritz modes via a two-line early-return guard. | — |
| **adapter module** | A `bin/Code/Fritz/` module that may import upstream `Code.*`. Acts as an anti-corruption layer so pure modules never reach upstream internals directly. | — |
| **`ancho`** | Board pixel width (= height) at the current `width_piece`. Computed by `BoardFit.ancho_for_width_piece`. | — |
| **Classical Invariant** | `classical` mode + no theme overlay = upstream Lucas Chess R6 exactly. The Fritz layer must never activate in classical mode. | — |
| **design harness** | `tools/design/` — development tools only, not a test. Renders scenes offscreen to PNG, diffs them against reference crops, builds the review HTML sheet. Reference images are never committed. | — |
| **`dic_toolbar`** | `WBase` attribute holding a `QAction` per toolbar key. The ribbon wires every slot with `setDefaultAction(dic_toolbar[key])` — no new dispatch code. | — |
| **E1** | `qproperty-<name>` + `QtCore.Property` — the primary mechanism for driving custom-painted widget values from QSS. | — |
| **E2** | `WA_StyledBackground` + `drawPrimitive(PE_Widget)` — makes the QSS box model (`background-color`, `border-radius`) render beneath custom painting. | — |
| **E3** | QSS `font-family` / `font-size` / `font-weight` — drives `self.font()` in `paintEvent` without a `Property`. | — |
| **E4** | Dynamic properties + `[prop="value"]` QSS selectors — expresses state variants (pane active, side to move, compact) without Python branches. | — |
| **`fit_board_to_window`** | Boolean key inside the mode JSON's `layout` block. When true, enables the fixed-window model for that mode. Absent and `null` both mean false. | — |
| **`FritzError`** | Domain base exception for the Fritz layer. Inherits `CaissaError` from `Code.Rpa.Errors`. | — |
| **Gate A** | Spec completeness check — all eleven `feature_spec.md` sections present, Classical Invariant impact stated, no open decision. **All implementation is blocked until Gate A passes.** | — |
| **Gate H** | Docs completeness check — new terms in `glossary.md`, new decisions in `decisions.md`, `make docs` clean. Must pass before a phase's PR is opened. | — |
| **`guardaEnDisco`** | `Board` method that persists `width_piece` to the config pickle. The fit path must never call it. `ConfigGateway.set_width_piece(v, persist=False)` is the enforcement point. | — |
| **`key_video`** | Saved-geometry namespace key. `"maind"` in classical, `"fritzd"` in Fritz. Decoupled from the board-config key (`BASE` / `BASEV`) in Phase 2. | — |
| **`layout` block** | Optional JSON object inside a mode JSON file, keyed `"layout"`. Carries values that must be read before any widget is polished: `fit_board_to_window`, `default_size`, `right_col_width`, `compact_below_height`, `notation_tabs`. | — |
| **`li_acciones`** | List of toolbar keys valid for the current screen, set at `WBase.py:526`. Read by `MainWindow.closeEvent`, `set_hints`, `remove_hints` and — after Phase 7 — `Ribbon.sync`. | — |
| **LCD clock** | `WFritzLCD` — a `QPainterPath`-drawn seven-segment digit box. Segment shapes are polygons, not a font. Colours and metrics from `qproperty-`. | Fritz clock widget |
| **mode hook** | `bin/Code/UIModes/actions/<name>_ui.py` — optional module loaded only when its mode is active, providing `on_mode_enter`, `on_mode_exit` and, from Phase 7, `pane_api()`. | — |
| **mode JSON** | `Resources/Modes/<name>.json` — defines the mode's toolbar allowlist, toolbar_inject, style, icons, layout and ribbon keys. | — |
| **`ModeGateway`** | `bin/Code/Fritz/ModeGateway.py` — the single reader of `Resources/Modes/`. Caches the parsed set; exposes `invalidate()` for tests. | — |
| **`N-FRITZ-n`** | Non-functional constraint ID for the Fritz layer. Listed in `feature_spec.md` §7. | — |
| **overflow group** | Ribbon group that receives any `li_acciones` key with no mapped slot. Ensures no screen becomes a dead end. | — |
| **pane** | A `QSplitter` child (or a widget restored by a recorded `(layout, index)` pair for `eval_bar` and `pgn_information`). Not a `QDockWidget`. | Panel |
| **`PaneRegistry`** | `bin/Code/Fritz/PaneRegistry.py` — pure sizing decisions: `register`, `names`, `spec`, `restore_px`. No widgets. | — |
| **pure module** | A `bin/Code/Fritz/` module that imports only stdlib + other pure modules + Qt-free upstream types. Asserted transitively by AST test. | — |
| **Q1** | QSS authoring rule: never put `#RRGGBB` on a line with more than one colon. Violation is a **silent skip** — the colour is never registered as overridable, not a crash. | — |
| **Q2** | QSS authoring rule: every key in `colors.template` must exist in the active `<style>.colors`. Violation is a **`KeyError` crash** in *Options → Colours*. Extra keys in a `.colors` file are harmless. | — |
| **Q3** | QSS authoring rule: selector on its own line, `{` on the next. Violation is a **silent miss** — the whole block is stored under a garbled key and its overrides never apply. | — |
| **ribbon** | The Office-style `WRibbon` widget hosted inside the existing `QToolBar` as one `QWidgetAction`. Content defined in `Resources/Ribbons/<name>.json`. | Ribbon |
| **`RibbonModel`** | `bin/Code/Fritz/RibbonModel.py` — pure: loads and validates the ribbon JSON, computes per-slot state, overflow list, best contextual tab. | — |
| **slot** | One ribbon control: `{key, size, label?}`. `key` resolves through `dic_toolbar`. | Button / gallery entry |
| **strangler-fig** | The layering strategy: new Caissa code is pure by default and reaches upstream only through adapters. Upstream is not re-tiered. | — |
| **`ThemeGateway`** | `bin/Code/Fritz/ThemeGateway.py` — adapter over `Code.dic_colors`, `IS_DARK`, and `Nags.nag_color`. Provides `invalidate()` so a theme swap re-reads. | — |
| **`width_piece`** | Integer board-square side in logical pixels. `BoardFit.width_piece_for_ancho` returns the largest value whose resulting `ancho` fits the pane. | — |
