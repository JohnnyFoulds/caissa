# Fritz Polish — Software Design Document

**Status:** Specified — implementation pending
**Branch:** `docs/fritz-polish` (this document), then one branch per phase — see `feature_steps.md`

<!-- Living document. Update alongside every design decision, constraint change, or interface
     change. Decisions are logged in docs/fritz/decisions.md and summarised in §2.4. -->

---

## 1. Problem Statement

Caissa's **Modern Fritz** UI mode works — it plays chess, it has a right-hand column with a player
header, an engine analysis table, an eval graph and the PGN grid — but placed next to a real Fritz 18
screenshot it reads as a Qt application wearing a dark stylesheet rather than a Fritz clone. The gaps
are not a list of cosmetic tweaks; three of them are structural, and each blocks the others.

**First, one codebase cannot currently serve two palettes.** The five `WFritz*` widgets each hardcode
a private hex palette in Python. `grep -n "WFritz" "Resources/Styles/Modern Fritz.qss"` returns
nothing, four of those values have already drifted out of sync with `Modern Fritz.colors`, and two of
the widgets paint via `paintEvent`/`fillRect` where a stylesheet can never reach them. Real Fritz
chrome is **light**, so the target palette is light with the existing dark kept as a sibling — which
is impossible until design values live in data rather than in Python constants.

**Second, Lucas Chess resizes the window to fit the board; Fritz does the exact opposite.**
`MainWindow.py:58-60` installs the main layout with Qt's default `SetDefaultConstraint`, so the
board's `setFixedSize` (`Board.py:703`) propagates into the *window's minimum* size and Qt force-grows
the window; `MainWindow.adjust_size` (`:272-294`) then loops `adjustSize()` and is reached from ten
entry paths, so the window visibly jumps on every game start and every return to the home screen.
Fritz's window is user-owned: you size it or maximize it, and the board fits into whatever space is
left. Pane sizes, splitter persistence and the ribbon's height all depend on getting this right.

**Third, there is no tier boundary anywhere, and the first two problems are symptoms of it.** Widgets
read configuration, open SQLite, poll engine output and monkey-patch each other's attributes
(`modern_fritz_ui.py:68` reassigns `base.grid_color_fondo`; `WFritzPlayerHeader` scrapes an HTML
string out of a `QLabel` every 500 ms). The dependency arrow also runs backwards: the *config loader*
measures widgets, because `Configuration.read_conf_boards` (`Configuration.py:639`) calls
`main_window.get_noboard_width()` to seed a default piece size. So persistence depends on
presentation, and "make it look like Fritz" keeps turning into "reach into five unrelated files".

This feature closes all three: it moves every design value into the `.qss`, inverts the
window/board sizing relationship for Fritz modes only, and establishes a pure-by-default feature
package (`bin/Code/Fritz/`) whose purity is asserted by a test rather than by convention. On top of
that foundation it delivers the visible Fritz identity — titled panes, LCD clocks, a notation tab
strip, a dense eval line, a light default theme and an Office-style ribbon.

Two of the deliverables are deliberately *not* Fritz-specific: the design methodology and the
layering rules ship as standards (`docs/standards/ui-design-process.md`,
`docs/standards/architecture.md`) so the next mode inherits them instead of re-deriving them.

---

## 2. Requirements

### 2.1 Business / Product Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Modern Fritz mode **MUST** read as Fritz at a glance to someone familiar with Fritz 18/19 — light chrome, titled panes, LCD clocks, a notation tab strip, a dense eval line, an Office-style ribbon — because a mode named after Fritz that does not resemble it undercuts the whole Mode system's premise. |
| BR-2 | The window **MUST** stay where the user puts it. This is the single most-felt defect in the current mode and the one behaviour change users will notice first. |
| BR-3 | The Classical Invariant **MUST** survive intact. `classical` mode remains the regression safety net and the fork's licence to diverge. |
| BR-4 | The design method and the layering rules **MUST** be reusable by future modes without re-litigation, so that `dos-fritz` and `win95-fritz` (and anything after them) are cheap rather than a second full-cost effort. |
| BR-5 | Every colour and pixel metric **MUST** be user-overridable through the existing `.colors` mechanism, so a Fritz theme is authorable without touching Python. |

### 2.2 Functional Requirements

Grouped by the phase that delivers them. RFC 2119 keywords are binding.

#### Foundations (Phase 0)

| ID | Requirement |
| --- | --- |
| FR-1 | The system **MUST** provide a pure module `Code.Fritz.QssRules` exposing `scan_qss`, `template_gaps` and `qproperties`, so the three QSS authoring rules (Q1/Q2/Q3, §3) are enforced by `make test` rather than by memory. |
| FR-2 | `Code.Fritz.ModeGateway` **MUST** be the only reader of `Resources/Modes/`, **MUST** cache the parsed mode set, and **MUST** expose `invalidate()` for tests. |
| FR-3 | The mode-JSON cache **MUST** reduce `Resources/Modes/` parsing to exactly one pass regardless of how many `allows_toolbar()` calls occur, because `allows_toolbar` is called once per toolbar key inside a list comprehension and a ribbon iterates ~54 keys. |
| FR-4 | A test **MUST** fail when any `qproperty-<name>` appearing in a shipped `.qss` does not resolve to a declared `QtCore.Property` on the named class, because Qt ignores an unknown `qproperty-` silently. |
| FR-5 | The design harness **MUST** render any named scene offscreen to a PNG using the real `.qss`, the real `Code.dic_colors` and the real icon pack, and **MUST** be a no-op with respect to a normal application start. |
| FR-6 | The harness **MUST NOT** write to a hardcoded `/tmp` path, **MUST NOT** shell out to a platform-specific opener, and **MUST** resolve every `Resources/` path through `Code.path_resource()` (N-FRITZ-9). |

#### Theming contract (Phases 1 and 6)

| ID | Requirement |
| --- | --- |
| FR-7 | Every custom-painted Caissa widget **MUST** take its design values — colours, pixel metrics, booleans, fonts — from the active `.qss` via `qproperty-` (E1), QSS box properties (E2) and QSS `font-*` (E3). A `#RRGGBB` literal in a widget module is permitted **only** as a `QtCore.Property` default, one per property. |
| FR-8 | Each metric setter **MUST** apply itself (e.g. `setBoxHeight` calls `setFixedHeight`), so no widget reads a metric during `__init__` and hopes. |
| FR-9 | State variants (pane active/inactive, selected, compact) **MUST** be expressed as dynamic properties with `[prop="value"]` selectors (E4), not as Python branches. |
| FR-10 | Every widget **MUST** render correctly with **no** stylesheet applied, using its `Property` defaults, which **MUST** equal the light `Fritz` theme's values. |
| FR-11 | No `WFritz*` module **MUST** read `Code.dic_colors` directly after Phase 1; colour access goes through `qproperty-` or `Code.Fritz.ThemeGateway`. |
| FR-12 | A light `Fritz` theme **MUST** ship as the Modern Fritz default, with the existing dark palette preserved as a sibling mode (`modern-fritz-dark.json`) sharing the same hook and ribbon. |
| FR-13 | `Fritz.qss` and `Modern Fritz.qss` **MUST** declare the **same set** of `qproperty-` names per selector, and **MUST** be geometrically identical once colour-bearing lines are stripped. |
| FR-14 | No existing `CHROME_*` key **MUST** be renamed, removed or re-scoped, and every `.colors` file **MUST** declare all ten — three are read from Python through an unguarded index (`InitApp.py:81-83`), so a missing key is a startup `KeyError` before any UI exists to report it. |
| FR-15 | `BOARD_STATIC` **MUST** remain dark in both themes: it is text drawn *on the board* (`Board2.py:115,126,138`), so following the light palette would make it vanish against light squares. |

#### Window and board sizing (Phase 2)

| ID | Requirement |
| --- | --- |
| FR-16 | In a mode whose `layout.fit_board_to_window` is true, the window **MUST** retain the size the user gave it across game start, game end, return to the home screen, mode-internal screen changes and the variations dialog. |
| FR-17 | The board **MUST** resize to fit the space its pane leaves, in whole `width_piece` steps. |
| FR-18 | A board fit **MUST NOT** persist `width_piece` to disk. `maximize_size` and `normal_size` both call `guardaEnDisco()`, so the fit path **MUST NOT** route through them. |
| FR-19 | A board fit **MUST** preserve board rotation and `dic_movables` (visual-director arrows and markers), because `redraw()` calls `escena.clear()` and hardcodes `is_white_bottom = True`. |
| FR-20 | The fit **MUST** be idempotent: feeding the resulting board width back in **MUST** yield the same `width_piece`. This is the property that makes an infinite resize loop impossible rather than merely guarded. |
| FR-21 | Window geometry and splitter sizes **MUST** survive a restart, per `key_video` namespace, and restore-down from maximized **MUST** return the user's pre-maximize size. |
| FR-22 | The board-config key (`BASE`/`BASEV`) **MUST** be selected by toolbar orientation, not by `key_video`, so introducing a third `key_video` value does not silently switch Fritz's persisted board config (`WBase.py:291`). |
| FR-23 | Board zoom (Ctrl+wheel, Ctrl+±) **MUST** be disabled in Fritz modes, because it writes `width_piece` + `guardaEnDisco()` which the next fit would override. Classical **MUST** keep it unchanged. |
| FR-24 | `layout` **MUST** be read such that both an absent key and an explicit `null` mean "no layout block", so every existing mode file's behaviour is unchanged without editing it. |

#### Panes, clocks, notation (Phases 3-5)

| ID | Requirement |
| --- | --- |
| FR-25 | Each Fritz pane **MUST** carry a title bar with the pane name left-aligned and `▾ ✕` controls right-aligned, and **MUST** be `objectName`-addressable for QSS. |
| FR-26 | `✕` **MUST** use the same hide path as the ribbon's Panes checkbox, so the two can never disagree. |
| FR-27 | A re-shown pane **MUST** return at no less than its `min_px`; it **MUST NOT** return at zero height. |
| FR-28 | Entering and leaving Fritz mode **MUST** leave `mw.base`'s layout structurally identical to a never-entered-Fritz baseline. |
| FR-29 | Clocks in Fritz **MUST** render as LCD digit boxes drawn with `QPainterPath`, with lit/dim colours, box metrics and segment thickness from `qproperty-`. |
| FR-30 | A single parser (`ClockModel.parse`) **MUST** handle all clock input forms — `H:MM:SS`, `MM:SS`, and the `<br><FONT SIZE="-4">` two-line HTML form that `WBase.set_clock_white` produces — so the display sites cannot drift apart. |
| FR-31 | `WBase.set_clock_white` **MUST NOT** be rewritten; the numeric path is an addition, because classical mode depends on the existing HTML behaviour. |
| FR-32 | The analysis pane **MUST** show a single dense eval line of the Fritz form `<Side> is <assessment>: <nag> (<cp>) Depth: <d>/<sd> <time> <nodes>`. |
| FR-33 | The notation pane **MUST** carry a six-entry tab strip (Notation, Training, Score sheet, LiveBook, Openings Book, My Moves) declared in data, with only *Notation* populated. |
| FR-34 | Notation cell rendering **MUST** be a `Delegados.EtiquetaPGN` subclass, not new widget code, so figurine rendering and the registered `ChessMerida.ttf` are inherited. |
| FR-35 | Two rows of NAG symbol buttons **MUST** apply the corresponding NAG to the current move through the existing NAG plumbing. |

#### Ribbon (Phase 7)

| ID | Requirement |
| --- | --- |
| FR-36 | The ribbon **MUST** be hosted inside the existing `QToolBar` as a single `QWidgetAction`, because `MainWindow` is a `QDialog` — there is no `addToolBar` and no dock areas. |
| FR-37 | A ribbon button **MUST** be wired by `setDefaultAction(base.dic_toolbar[key])`, adding **no** new dispatch code: text, icon, tooltip, enabled, visible and checkable all mirror in both directions. |
| FR-38 | Ribbon content **MUST** be data: `Resources/Ribbons/<name>.json`, referenced by a single new mode-JSON key `ribbon`. An absent key **MUST** mean no ribbon and a byte-identical existing code path. |
| FR-39 | A key present in `li_acciones` but absent from the ribbon map **MUST** go to an overflow group and **MUST NOT** be dropped — `TB_ACCEPT`, `TB_CHANGE` and the replay family are the only way out of some screens. |
| FR-40 | A mapped slot whose key is absent from `li_acciones` **MUST** grey out and stay visible (`missing_key_policy: "disable"`), keeping geometry stable across contexts. Explicit hiding **MUST** remain a distinguishable separate channel. |
| FR-41 | `sync()` **MUST** be idempotent and construct no widgets after the first call, because `pon_toolbar` fires on every screen change and twice per move during engine play. |
| FR-42 | `Ribbon.install` **MUST** return `None` and log with `exc_info=True` on any failure, so a malformed ribbon JSON degrades to the classic toolbar rather than a dead application. |
| FR-43 | The ribbon **MUST** pin its own height (`setFixedHeight` on both `WRibbon` and the `QToolBar`, after `ensurePolished()`) before the first board fit reads `minimumSizeHint()`. |
| FR-44 | `WRibbon` **MUST** remain mode-agnostic: the pane registry reaches it as an optional capability dict fetched from the mode hook, so `dos-fritz` and `win95-fritz` can reuse it unchanged. |
| FR-45 | The ribbon **MUST** switch to the contextually relevant tab on a change of `li_acciones`, but **MUST NOT** override a tab the user selected manually since that set last changed shape. |

#### Test and automation surface (Phases 2 and 7)

| ID | Requirement |
| --- | --- |
| FR-46 | The remote-control surface **MUST** gain the verbs needed to assert fixed-window and ribbon behaviour: `window_info`, `board_info`, `resize_window`, `set_window_state`, `set_splitter_sizes`, `click_tabbar`, `ribbon_info`, `select_ribbon_tab`, `click_ribbon`, `toggle_pane`. |
| FR-47 | All new Qt code for those verbs **MUST** live in `Code.Rpa.Driver.QtDriver`; `RemoteControl._dispatch` gains only a two-line delegation per verb. |
| FR-48 | Each new verb **MUST** have a hand-written probe in `tests/ui/rc_contract.json`, and for the two informational verbs those probes **MUST** be success-path rather than error-path probes. |
| FR-49 | The existing toolbar enumeration and click verbs **MUST** be *extended* rather than replaced, leaving their key sets unchanged so the contract lock holds and `T-FRITZ-04` passes without a test edit. |

### 2.3 Non-Functional Requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | A steady-state window resize **MUST** cost zero board redraws once `width_piece` stops changing, and a resize *drag* **MUST** coalesce into at most one fit per 60 ms. |
| NFR-2 | All public and non-public callables **MUST** have RST/Sphinx docstrings per `docs/standards/docstring-standards.md`, each carrying a `:spec:` traceability tag naming the requirement it serves. |
| NFR-3 | All signatures **MUST** carry complete type annotations, with `from __future__ import annotations` and modern unions. |
| NFR-4 | Branch coverage of `Code.Fritz` **MUST** be ≥ 90 %, measured against its own coverage configuration so that this feature's number and the RPA layer's number cannot mask each other. |
| NFR-5 | `pytest tests/unit` **MUST** remain free of any PySide6 or `FasterCode` import, including at collection time. The lazy `qt_app` bootstrap in `tests/conftest.py` **MUST NOT** be made eager. |
| NFR-6 | Every collected test **MUST** declare exactly one suite marker (`unit`, `ui`, `rpa`, `rpa_ui`, `rpa_cv`) as a module-level `pytestmark`. No new marker is introduced. |
| NFR-7 | `make docs` **MUST** produce zero Sphinx warnings (`-W --keep-going`). |
| NFR-8 | Every test assertion message **MUST** be prefixed `T-XXX-NN FAIL:` and **MUST** interpolate the observed value plus a diagnostic hint. |
| NFR-9 | Tests for a phase not yet implemented **MUST** exist up front as `@pytest.mark.xfail(strict=True, reason="Requires Phase N (<branch>)")`. `skip` **MUST NOT** be used for deferred work. |
| NFR-10 | No new runtime dependency is introduced. The design harness uses Pillow, already a dependency; `requirements.txt` is untouched. |

### 2.4 Constraints & Assumptions

- **Module location:** all new modules live under `bin/Code/Fritz/`. The five existing `WFritz*`
  widgets and the mode hooks stay in `bin/Code/UIModes/` and are edited in place — moving them is
  churn, and `UIModes.py` is the upstream-facing entry point.
- Python 3.13; PySide6 6.11.2; Pillow 12.3.0.
- No ABCs and **no `typing.Protocol`** — plain base classes raising `NotImplementedError`, per
  `docs/standards/coding-standards.md:70-74` (whose `:72` notes that `Protocol` is built on
  `ABCMeta`, so the prohibition covers both). Precedent: `bin/Code/ManagerBase/Manager.py:61`.
- Errors inherit `CaissaError` **via a domain base**: `FritzError(CaissaError)` in
  `Code/Fritz/Errors.py`, importing `CaissaError` from `Code.Rpa.Errors` — its documented home per
  `docs/standards/error-handling.md` §1.1, which explicitly declines to place a Caissa file in
  `bin/Code/Base/`.
- **Upstream is not re-tiered.** New Caissa code is pure by default; upstream is reached only through
  adapter modules. Upstream edits are confined to the enumerated set in §5.7.
- **`docs/future-directions.md` §0 is binding** on every path, process and shell-out this feature
  adds — see N-FRITZ-9.
- **Decisions taken** (full log with rationale and rejected alternatives in `docs/fritz/decisions.md`):

  | # | decision | resolution deadline |
  | --- | --- | --- |
  | D1 | Mockups are built in PySide6 + the real `.qss`, not in Figma | resolved |
  | D2 | The window is user-owned; the board fits the window | resolved |
  | D3 | Design values live in the `.qss` via `qproperty-`, not in a `.tokens.json` sidecar | resolved |
  | D4 | Light `Fritz` is the default theme; dark `Modern Fritz` is the sibling variant | resolved |
  | D5 | The ribbon is hosted inside the existing `QToolBar` as one `QWidgetAction` | resolved |
  | D6 | Board zoom is disabled in Fritz modes | resolved |
  | D7 | Seams are plain base classes raising `NotImplementedError` | resolved |
  | D8 | The four RPA object-tier defects are not fixed here | resolved |
  | D9 | `docs/modern-fritz.md` is superseded, not amended | resolved |
  | D10 | `Code.Fritz` gets its own coverage configuration and `make cov-fritz` target | resolved (Phase D) |
  | D11 | Seven-segment digits are `QPainterPath` polygons, not a shipped `.ttf` | resolved (Phase D) |

  **No decision is open.** Gate A fails if one is.

---

## 3. Terminology & Existing Infrastructure

| Term | Definition |
| --- | --- |
| **Classical Invariant** | `classical` mode + no theme overlay = upstream Lucas Chess R6 exactly. The only permitted addition is the `UI mode` combobox. |
| **UI mode** | A feature-set filter selected by `x_ui_mode`, defined by a JSON file in `Resources/Modes/`. Changing it triggers a process reinit (`Configuration.needs_reinit`). |
| **Theme** | A visual overlay selected by `x_style_mode`: a `Resources/Styles/<name>.qss` plus an optional `<name>.colors` and `<name>.ui.json`. |
| **E1 / E2 / E3 / E4** | The four verified mechanisms for driving a custom-painted widget from QSS: `qproperty-` + `QtCore.Property`; `WA_StyledBackground` + `drawPrimitive(PE_Widget)`; QSS `font-*`; dynamic properties with `[prop="value"]` selectors. Documented in `docs/fritz/qss-contract.md`. |
| **Q1** | *Never put a `#RRGGBB` on a line with more than one colon.* A **silent skip**, not a crash: both pre-parsers wrap `line.split(":")` in a bare `try/except continue` (`InitApp.py:52-55`, `WColors.py:292-295`). Consequence: the colour is never registered as overridable. |
| **Q2** | *Every key in `colors.template` must exist in the active `<style>.colors`.* The trigger is the **template**, not cross-`.colors` parity: `WColors.py:28-29` builds the row list from template + QSS, and `:193` indexes `dic_original[key]` unguarded — a genuine `KeyError` in *Options → Colours*. Extra keys in a `.colors` file are harmless. |
| **Q3** | *Selector on its own line, `{` on the next.* Also silent: `WColors.read_qss` stores the stripped line verbatim (`:286-288`), so `QWidget {` becomes the literal selector string and its keys match nothing. |
| **`key_video`** | The saved-geometry namespace (`"maind"` classically). It **also** selected the persisted board config until FR-22 decoupled the two. |
| **`li_acciones`** | The list of toolbar keys valid for the current screen, assigned at `WBase.py:526` and read by `MainWindow.closeEvent`, `set_hints` and `remove_hints`. |
| **Pane** | A `QSplitter` child (or, for `eval_bar` and `pgn_information`, a widget restored by a recorded `(layout, index)` pair). **Not** a `QDockWidget` — there are zero in the codebase. |
| **Slot** | One ribbon control: `{key, size, label?}`, where `key` resolves through `base.dic_toolbar`. |
| **Overflow** | The ribbon group receiving any `li_acciones` key with no mapped slot, so no screen becomes a dead end. |
| **Design harness** | `tools/design/` — a development tool, not a test. Renders scenes offscreen and builds the review sheet. Its reference crops are never committed. |
| **Oracle** | The external reference corpus: 41 official Fritz 18/19 captures outside the repo, reached via `CAISSA_FRITZ_REF`. |

Existing infrastructure this feature reuses rather than reinvents:

| Facility | Location | Reused for |
| --- | --- | --- |
| Offscreen Qt bootstrap | `tests/conftest.py` `_bootstrap()` (lazy) | the design harness and the offscreen suites |
| `images_mean_diff`, `crop_button` | `tests/test_sidebar_icon_consistency.py` | lifted into `tools/design/compare.py`, imported back by the test |
| Whole-window capture | `QtDriver.screenshot`, `Driver.py:262-280` | `review.py --live` |
| Delegate-based cell painting | `Delegados.EtiquetaPGN`, attached at `WBase.py:349,355`; wired by `Grid.py:420` | `FritzEtiquetaPGN` (Phase 5) |
| Application font registration | `InitApp.py:149` (`ChessMerida.ttf`) | precedent only — D11 chose polygons |
| Toolbar `QAction` registry | `WBase.create_toolbar`, `dic_toolbar` | every ribbon slot (FR-37) |
| Driver seam + fakes | `Rpa/Driver.py:29,131`, `Rpa/Fakes.py` | the shape all Fritz seams copy |
| Frozen-safe resource paths | `Code.path_resource`, `bin/Code/__init__.py:36-40` | every `Resources/` read |
| Purity assertion by AST | `tests/unit/rpa/test_completeness.py:51-86` | extended transitively for `Code.Fritz` |

---

## 4. Architecture

`bin/Code/Fritz/` is a **flat feature package, sibling to `bin/Code/Rpa/`, pure by default, with Qt
confined to a named set of widget modules and that confinement asserted by an AST test.** This is not
a new architecture: it is the structure the RPA layer shipped and enforces, adopted verbatim so that
the two Caissa features have one shape rather than two. The three-tier vocabulary an earlier draft
used is dropped in favour of the RPA layer's "declared purity tier per module".

The dependency rule is one-way and executable: **pure → adapter → widget**, never the reverse, and
**upstream never imports `Code.Fritz`**.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ upstream Lucas Chess R6  (~60 packages, not re-tiered)                       │
│   Board/ Main/ ManagerBase/ QT/ Config/ Nags/ …                              │
│   reached ONLY through the adapter modules below                             │
└──────────────────────────────────────────────────────────────────────────────┘
          ▲                                          ▲
          │ reads (never writes presentation)        │ upstream must NOT import Code.Fritz
          │                                          │
┌─────────┴──────────────────────────────────────────┴─────────────────────────┐
│ bin/Code/Fritz/  — adapter modules (may import upstream Code.*)              │
│   ThemeGateway  ModeGateway  ConfigGateway  GeometryStore  EngineGateway     │
└──────────────────────────────────────────────────────────────────────────────┘
          ▲
          │ pure modules depend only downward
┌─────────┴────────────────────────────────────────────────────────────────────┐
│ bin/Code/Fritz/  — pure modules (stdlib + Types only; NO PySide6)            │
│   QssRules  BoardFit  ClockModel  EvalModel  RibbonModel                     │
│   PaneRegistry  NotationRowModel                                            │
│   ├─ Types.py   frozen dataclasses, ZERO third-party imports                 │
│   └─ Errors.py  FritzError(CaissaError)  ← Code.Rpa.Errors                   │
└──────────────────────────────────────────────────────────────────────────────┘
          ▲
          │ widgets apply decisions they do not make
┌─────────┴────────────────────────────────────────────────────────────────────┐
│ Qt allowlist                                                                 │
│   bin/Code/Fritz/    WFritzPane  WFritzLCD  WRibbon  Ribbon  Delegates       │
│   bin/Code/UIModes/  the five existing WFritz* widgets, UIModes, actions/    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Declared purity tiers

Normative. `tests/unit/fritz/test_completeness.py` asserts every row.

| module | tier | may import |
| --- | --- | --- |
| `Types.py` | **dependency-free** | stdlib only. Zero third-party imports, asserted separately. Reuses `Rpa.Types.Rect` rather than declaring a second geometry type |
| `Errors.py` | **dependency-free** | stdlib + `Code.Rpa.Errors` |
| `QssRules.py` | pure | `Types`, stdlib |
| `BoardFit.py` | pure | `Types`, stdlib |
| `ClockModel.py` | pure | `Types`, stdlib |
| `EvalModel.py` | pure | `Types`, stdlib, upstream `Code.Engines.EngineResponse` (verified Qt-free) |
| `RibbonModel.py` | pure | `Types`, `Errors`, stdlib |
| `PaneRegistry.py` | pure | `Types`, `Errors`, stdlib |
| `NotationRowModel.py` | pure **by declaration, Qt-tainted transitively** | `Types`, stdlib, upstream `Code.Base.Move` — which reaches `QtGui` via `Nags`. See §4.2 |
| `ThemeGateway.py` | adapter | upstream `Code.*`, `Nags`, stdlib |
| `ModeGateway.py` | adapter | upstream `Code.*`, stdlib |
| `ConfigGateway.py` | adapter | upstream `Code.*`, stdlib |
| `GeometryStore.py` | adapter | upstream `Code.*`, stdlib |
| `EngineGateway.py` | adapter | upstream `Code.*`, stdlib |
| `WFritzPane.py`, `WFritzLCD.py`, `WRibbon.py`, `Ribbon.py`, `Delegates.py` | **Qt allowlist** | Qt + everything above |

### 4.2 One correction to the RPA precedent, and why the test must be stricter

`bin/Code/Base/` is **not** entirely Qt-free. `Game.py:47` and `Move.py:8` both import
`Code.Nags.Nags`, and `Nags/Nags.py:3` imports `QtGui` — so `Game` and `Move` are Qt-tainted
*transitively* while showing no direct `PySide6` import. Two consequences:

1. `test_no_pyside6_import_outside_allowlist` must resolve imports **transitively**, whereas the RPA
   version (`tests/unit/rpa/test_completeness.py:51-86`) walks direct imports only. This is a genuine
   extension, and its maintenance cost is acknowledged in §10.
2. Any pure module wanting a `Game` or a `Move` in its signature cannot be tested in a truly Qt-free
   process. `EvalModel` is unaffected (the `mrm` is genuinely pure). `NotationRowModel` is affected,
   so its tests use the Qt-stubbing bootstrap from `tests/test_classical_invariant.py:26-52`.

The allowlist must also match on the **path relative to `bin/Code/Fritz/`**, not on basename: the RPA
version's basename match would exempt any file called `Driver.py` anywhere in the tree.

`Nags/Nags.py` is upstream and is **read from, never rewritten**. Note for `ThemeGateway`:
`nag_color()` is Qt-free but **not pure** — it declares `global xdic_colors` (`:244`) and lazily
memoises six unguarded `Code.dic_colors` reads (`:246-251`) that are never invalidated. So it is safe
to call from an adapter but not from a pure module, and `ThemeGateway.invalidate()` must reset
`Nags.xdic_colors` or a light↔dark swap serves stale colours.

### 4.3 The QSS extension contract

Verified in this install, not reasoned about: `qproperty-` sets `QColor`, `int`, `bool` and `QBrush`
values on a Python subclass; a type selector on the subclass name resolves; `WA_StyledBackground`
plus `style().drawPrimitive(PE_Widget, opt, p, self)` as the first two lines of `paintEvent` makes
QSS `background-color` and `border-radius` render beneath custom painting; QSS `font-*` reaches
`self.font()`; and `unpolish()`/`polish()` re-applies `qproperty-` values after a theme swap.

The payoff that decided D3: both QSS pre-parsers key on *any* line containing a `#`, so
`qproperty-litColor: #30ff70;` under selector `WFritzLCD` registers as
`WFritzLCD|qproperty-litColor` in `dic_original` — an editable row in *Options → Colours*, overridable
from a `.colors` file, with **zero new code**. Custom-painted widgets end up *more* themeable than
QSS-styled ones. The full contract and the per-widget property tables live in
`docs/fritz/qss-contract.md`.

**The one limit is timing, not styling.** `qproperty-` values arrive at *polish* time. Anything
consumed before a widget exists — the mode hook's initial splitter sizes, `default_size`,
`right_col_width`, `compact_below_height` — cannot come from QSS and lives in the mode JSON's
`layout` block.

---

## 5. Interface Contract

Operations are stated as `(actor, operation, preconditions, postconditions, error semantics, NFR
constraints)`. Preconditions and postconditions are given per member; NFR-2, NFR-3 and NFR-8 apply to
every member and are not repeated.

### 5.1 `Code.Fritz.Types` — dependency-free dataclasses

Frozen, `slots=True`.

| Member | Kind | Description |
| --- | --- | --- |
| `PaneSpec(key, label, default_px, min_px)` | dataclass | Identity and sizing policy of one pane. Pre: `0 < min_px <= default_px`. |
| `RibbonSlot(key, size, label, tab_id, group_id)` | dataclass | One ribbon control. `size` ∈ `{"large", "small"}`. |
| `EvalSummary(text, nag, cp, depth, seldepth, nodes, ms)` | dataclass | The dense eval line, decomposed. `cp` is `None` for a mate score. |
| `FitResult(width_piece, ancho, clamped)` | dataclass | Outcome of a board fit. `clamped` is true exactly when the `MIN_ANCHO` floor was hit. |
| `NotationRow(text, figurine_glyph, nag_nums, chip_color, indent_level, is_current)` | dataclass | Everything `FritzEtiquetaPGN.paint` needs, so the delegate branches on nothing. |

`Rect` is **not** redeclared — `Rpa.Types.Rect` (`:37-40`, `x`/`y`/`w`/`h`, logical DPR-1 pixels) is
imported and re-exported.

### 5.2 `Code.Fritz.QssRules` — pure

Post: none of these functions performs I/O beyond consuming a string the caller read.

| Member | Kind | Description |
| --- | --- | --- |
| `scan_qss(text)` | function → `list[tuple[int, str, str]]` | Q1 and Q3 violations as `(line_no, rule, line)`. Empty for a compliant file. Raises `QssContractError` on an unbalanced brace rather than mis-parsing. |
| `template_gaps(template_keys, colors_keys)` | function → `list[str]` | Q2: template keys absent from a `.colors` key set, sorted. Empty is the passing state. |
| `qproperties(text)` | function → `dict[str, dict[str, str]]` | `{selector: {name: value}}` for every `qproperty-` line. Values containing commas (gradients, `rgba()`) are preserved whole. `{}` for a file with none. |

### 5.3 Pure models

| Member | Kind | Description |
| --- | --- | --- |
| `BoardFit.ancho_for_width_piece(ap, tam_frontera, margin_center)` | function → `int` | The arithmetic of `Board.redraw()` (`:698-700`) with no side effects, including the interpolation-bucket lookup. |
| `BoardFit.width_piece_for_ancho(target, …)` | function → `int` | Bisection over `[MIN_AP, 200]`; the largest `ap` whose `ancho <= target`. Monotonic in `target`. |
| `BoardFit.fit(pane_w, pane_h, overhead_w, overhead_h, safety, min_ancho)` | function → `FitResult` | The whole clamp chain. Post: idempotent (FR-20); `ap >= MIN_AP` for any input, including zero or negative panes. |
| `ClockModel.parse(text)` | function → `float \| None` | Seconds from `H:MM:SS`, `MM:SS` or the two-line HTML form. `None` — never an exception — for unparseable input. |
| `ClockModel.format(seconds, show_tenths)` | function → `str` | Display string. Pre: `seconds >= 0`; negative clamps to zero. |
| `ClockModel.digits(seconds)` | function → `str` | The exact glyph string `WFritzLCD` paints, so the widget makes no formatting decision. |
| `EvalModel.describe(mrm)` | function → `EvalSummary` | Delegates to `describe_values`. Pre: `mrm` is an `EngineResponse` (Qt-free upstream type). |
| `EvalModel.describe_values(cp, depth, seldepth, nodes, ms)` | function → `EvalSummary` | The assessment ladder and cp→NAG mapping, thresholds from `_CAP_CP = 600` / `_MATE_CP = 30000`. Sign is side-to-move relative. |
| `PaneRegistry.register(spec)` | function → `None` | Registering an existing key **replaces** rather than duplicates. |
| `PaneRegistry.names()` | function → `list[str]` | Registration order — the ribbon's checkbox order depends on it. |
| `PaneRegistry.spec(key)` | function → `PaneSpec` | Raises `PaneNotRegisteredError` for an unknown key. |
| `PaneRegistry.restore_px(key, current_px)` | function → `int` | `current_px` if already non-zero, else `default_px`; floored at `min_px`. This is FR-27 as arithmetic. |
| `NotationRowModel.row(move)` | function → `NotationRow` | Decides chip, colour and indent so the delegate does not. |
| `RibbonModel.load(path)` | function → `RibbonSpec` | Parses and validates. Raises `RibbonSpecError` with the offending id on any schema breach. |
| `RibbonModel.state(spec, li_acciones)` | function → `dict[str, tuple[bool, bool, str]]` | Per-slot `(visible, enabled, tab_id)`. Pure — this is FR-40 in full. |
| `RibbonModel.overflow(spec, li_acciones)` | function → `list[str]` | Keys with no mapped slot. Empty is the required state for Fritz's allowlist (FR-39). |
| `RibbonModel.best_tab(spec, li_acciones)` | function → `str` | Highest `len(set(slot_keys) & set(li_acciones))`. Ties resolve to the earlier tab. |
| `RibbonModel.compact(height)` | function → `bool` | Whether to render `large` slots as `small`. |

### 5.4 Adapter modules

| Member | Kind | Description |
| --- | --- | --- |
| `ModeGateway.modes()` | function → `dict[str, dict]` | Cached; the single reader of `Resources/Modes/`, resolved via `Code.path_resource`. |
| `ModeGateway.invalidate()` | function → `None` | Test seam. Post: the next `modes()` re-parses exactly once. |
| `ModeGateway.active()` / `.layout()` / `.ribbon_name()` | functions | `layout()` returns `{}` for both an absent key and an explicit `null` (FR-24). |
| `ModeGateway.hook_module_name(mode)` | function → `str` | Honours the new optional `hook` key, falling back to the name-derived path. |
| `ThemeGateway.color(key)` | function → `str` | `Code.dic_colors` with the `qproperty-` default as fallback. Never raises. |
| `ThemeGateway.is_dark()` / `.active_style()` | functions | Read `IS_DARK` and the active style name. |
| `ThemeGateway.nag_color(num)` | function → `str` | Adapter over upstream `Nags.nag_color`; returns hex, not a `QColor`. |
| `ThemeGateway.invalidate()` | function → `None` | Post: `Nags.xdic_colors` is `{}` (§4.2). |
| `ConfigGateway.pgn_width()` / `.with_figurines()` / `.width_piece()` / `.ui_mode()` | functions | The complete set of `configuration.x_*` reads the Fritz widgets need. Post: no widget reads `configuration` directly. |
| `ConfigGateway.set_width_piece(v, persist)` | function → `None` | Pre: `persist is False` on every fit path. This is FR-18's enforcement point. |
| `GeometryStore.save_window(key, rect, state)` / `.load_window(key)` | functions | Owns the `_MAXIMIZED_` encoding and `key_video` namespacing. Never saves while fullscreen (the geometry would be the screen). |
| `GeometryStore.save_splitters(key, sizes)` / `.load_splitters(key)` | functions | Post: a restore is applied only when `len(sizes) == splitter.count()`. |
| `GeometryStore.clamp_to_screens(rect, screens)` | function → `Rect` | Pure over a list of rects, so FM-12 is a unit test. |
| `EngineGateway.latest_analysis()` | function → `mrm \| None` | Reads `WAnalysisBar.control_state`. The only impure part of the eval path. |

### 5.5 Widget modules

| Member | Kind | Description |
| --- | --- | --- |
| `WFritzPane(spec, content)` | class | Title bar + content. Pre: `spec` is registered. `qproperty-titleHeight/titleTop/titleBottom/titlePadX`. |
| `WFritzLCD` | class | `QPainterPath` seven-segment box. `qproperty-litColor/dimColor/boxHeight/boxWidth/segmentThickness`. Accepts a numeric time or, as a documented fallback, the HTML string. |
| `WRibbon` / `WRibbonPage` / `WRibbonGroup` / `WRibbonPanesGroup` | classes | Presentation only; every behavioural decision arrives from `RibbonModel`. `qproperty-ribbonHeight`. |
| `Ribbon.install(base, spec)` | function → `Ribbon \| None` | Pre: every `QAction` exists (call site is after both `setToolTip` calls). Post: `WRibbon` and the `QToolBar` are both `setFixedHeight` after `ensurePolished()` (FR-43). Returns `None` and logs `exc_info=True` on any exception (FR-42). |
| `Ribbon.sync(li_acciones)` | method → `QToolBar` | Idempotent; no widget construction after the first call (FR-41). Checkbox state re-read under `blockSignals(True)`. |
| `Delegates.FritzEtiquetaPGN` | class | `Delegados.EtiquetaPGN` subclass overriding `paint` only, fed by `NotationRowModel`. |

### 5.6 Mode-JSON and ribbon-JSON schema additions

| Key | Where | Meaning |
| --- | --- | --- |
| `layout.fit_board_to_window` | mode JSON | Enables the whole of Phase 2 for that mode. Absent/`null` → false. |
| `layout.default_size`, `layout.right_col_width`, `layout.compact_below_height`, `layout.notation_tabs` | mode JSON | The values `qproperty-` cannot deliver in time. |
| `ribbon` | mode JSON | Basename in `Resources/Ribbons/`. Absent → no ribbon. |
| `hook` | mode JSON | Optional explicit hook module, so two modes can share one hook. |

`Resources/Ribbons/<name>.json` carries `$schema_version`, `default_tab`, `missing_key_policy`,
`quick_access`, `overflow` and `tabs[].groups[].slots[]`. **A new directory, deliberately:**
`UIModes.load_modes()` globs every `*.json` in `Resources/Modes/`, so a ribbon file placed there would
appear as a phantom mode in the switch-mode menu.

### 5.7 The complete set of upstream edits

Exhaustive and normative. Anything not listed here is out of scope for upstream modification.

| file | edit | phase |
| --- | --- | --- |
| `Main/InitApp.py` | `split(":", 1)` + selector `rstrip(" {")` in the QSS pre-parser (~2 lines) | 0 (optional, revertable) |
| `QT/WColors.py` | the same two, plus `dic_original.get(key, …)` at `:193` (~3 lines) | 0 (optional, revertable) |
| `UIModes/UIModes.py` | mode loading delegates to `ModeGateway`; public functions become pass-throughs | 0 |
| `Main/MainWindow.py` | `_fit_board` computed pre-`__init__`; two-line guards on `adjust_size` and `_adjust_tamh`; `SetNoConstraint` + `setMinimumSize(0,0)`; the `changeEvent` Fritz branch; the fit scheduler; `save_video`/`restore_video` via `GeometryStore` | 2 |
| `Main/WBase.py` | `key = "BASEV" if not x_tb_orientation_horizontal else "BASE"` at `:291` | 2 |
| `Main/WInformation.py` | `_fit_board` guard at `:308` | 2 |
| `ManagerBase/…/ManagerResistance.py` | `_fit_board` guard at `:295` | 2 |
| `QT/LCDialog.py` | `register_splitter` replace-by-name + `unregister_splitter`; `len(li_sp) == sp.count()` at `:122` | 2 |
| `Board/Board.py` | add `fit_to` and `fit_to_width_piece`; `calc_width_mx_piece` untouched | 2 |
| `Rpa/Driver.py` | the ten new `QtDriver` verb methods | 2, 7 |
| `Debug/RemoteControl.py` | two lines of delegation per verb | 2, 7 |
| `Main/WBase.py` | the three `create_toolbar`/`pon_toolbar` ribbon edits (~14 net lines) | 7 |
| `Main/LucasChessGui.py` | one line calling `LogSetup.configure()` — filed as `fix(rpa)`, see §10 | separate |

---

## 6. Error Semantics

| Condition | Behaviour |
| --- | --- |
| `qproperties()` meets an unbalanced brace | Raises `QssContractError(path, line_no)`. Never returns a partial parse. |
| `RibbonModel.load` meets a schema breach (bad `$schema_version`, duplicate tab/group id, duplicate `key`) | Raises `RibbonSpecError` naming the offending id. |
| `RibbonModel.load` or any part of `Ribbon.install` raises | `Ribbon.install` catches, logs `logger.warning(..., exc_info=True)`, returns `None`. The classic toolbar renders instead. **Never a dead application** (FR-42). |
| A ribbon slot key does not resolve in `dic_toolbar` | The slot is dropped with `logger.warning(..., exc_info=True)`. `dic_toolbar.get(key)`, never the unguarded index at `WBase.py:519`. Also caught at compile time by T-RMAP-02. |
| `PaneRegistry.spec` / `restore_px` given an unknown key | Raises `PaneNotRegisteredError(key)`. |
| `ClockModel.parse` given unparseable text | Returns `None`. Parsing a clock label is a display concern; an exception here would break a 500 ms poll. |
| `BoardFit.fit` given a zero or negative pane | Returns `FitResult(MIN_AP, …, clamped=True)`. Clipping beats raising (FM-2). |
| `GeometryStore` reads a saved geometry that is offscreen | Clamped via `clamp_to_screens`, reusing `LCDialog`'s existing multi-monitor logic (`:106-107,131-154`) rather than a second implementation. |
| `sp.sizes()` on a deleted C++ splitter object | `except RuntimeError` + `logger.warning(..., exc_info=True)`. Already latent; splitter persistence makes it reachable on every quit (FM-5). |
| A template key is missing from the active `.colors` | Today: `KeyError` in *Options → Colours*. After the optional §0.2b hardening: a grey cell plus a logged warning. |
| A `qproperty-` name is mistyped in a `.qss` | Qt ignores it silently and the widget keeps its default. **No runtime error is possible**, which is why `tests/test_qproperty_contract.py` exists (FR-4). |

Per `docs/standards/error-handling.md`: every catch site carries `exc_info=True`; wrapping uses
`raise … from exc`; there is no `except Exception: pass` and no `except BaseException` in new code.

---

## 7. Non-Functional Constraints (N)

| ID | Constraint |
| --- | --- |
| N-FRITZ-1 | New Qt code lives **only** in the declared widget-module allowlist (§4.1). Asserted transitively by AST. |
| N-FRITZ-2 | `Types.py` has **zero** third-party imports. |
| N-FRITZ-3 | No widget module contains a `#RRGGBB` outside a `QtCore.Property` default, a `configuration.x_` attribute access, an `import sqlite3`, or a `guardaEnDisco` call. |
| N-FRITZ-4 | Upstream modules import nothing from `Code.Fritz`, so `git diff` against upstream R6 stays additive. |
| N-FRITZ-5 | No pixel value in a widget module. Colours and metrics arrive from `.qss`; pre-polish values arrive from the mode JSON's `layout` block. |
| N-FRITZ-6 | No test asserts full-window pixel equality. Committed visual assertions are limited to intra-run `grab()` comparison, non-background pixel counts with a floor, and the two manifest-registered `rpa_cv` template-presence tests — each paired with an object-tier assertion (`docs/ui-testing.md` §7.1). |
| N-FRITZ-7 | Capture is DPR-1 and in-process (`widget.grab()` / `QTest`) only. Never `pyautogui`, `mss` or CoreGraphics. |
| N-FRITZ-8 | The Fritz reference corpus is **never committed** — third-party copyright in a GPL-3.0 repo. It is reached through `CAISSA_FRITZ_REF`. |
| N-FRITZ-9 | `docs/future-directions.md` §0 applies in full: no hardcoded `/tmp` (use `tempfile.gettempdir()`), no `os.path` separator literals, no `shell=True` with Unix syntax, no platform-specific opener (`webbrowser.open`), and every `Resources/` path through `Code.path_resource()`. These keep the Windows packaging path open. |
| N-FRITZ-10 | No new pytest marker. Every test declares exactly one of the five existing suite markers. |
| N-FRITZ-11 | No new runtime dependency; `requirements.txt` untouched. |
| N-FRITZ-12 | The design harness is inert with respect to a normal start (`CAISSA_DESIGN=0` path) and is not importable from shipped code. |

---

## 8. Classical Invariant Impact

**The boilerplate does not apply and cannot be used.** The RPA layer could state that it *"adds no
widget, toolbar entry, menu entry, mode JSON, QSS rule, overlay, or render-time config key"*. This
feature adds **all** of those. `docs/standards/spec-driven-development.md:58` requires explicit
justification and approval where the invariant cannot simply be preserved, so this section is that
justification, and it argues **mode-gated isolation** rather than absence.

### 8.1 The four isolation arguments

1. **Nothing activates when `x_ui_mode == "classical"`.** Every behaviour in this feature is reached
   through one of two data gates: `layout.fit_board_to_window` (Phase 2) or `ribbon` (Phase 7), both
   absent from `classical.json`; or through the mode hook `modern_fritz_ui.py`, which classical never
   loads. `layout` is **absent entirely from all six non-Fritz mode files** and present-but-`null` in
   exactly the three Fritz ones, and `ModeGateway.layout()` treats absent and `null` alike — so the
   default is off by construction, not by a test.

2. **The new data files are additive and unreferenced by classical.** `Fritz.qss`, `Fritz.colors`,
   `modern-fritz-dark.json` and `Resources/Ribbons/modern-fritz.json` are new files. No existing
   `.qss` selector is modified — every Fritz rule is a new `#WFritz*` / `#WRibbon*` /
   `QSplitter::handle` block appended to the two Fritz stylesheets only.

3. **The upstream edits are enumerated, minimal and structurally inert in classical.** §5.7 is the
   complete list. Each is either behind a `self._fit_board` / `self.ribbon` guard that is false in
   classical, or behaviour-preserving by construction:
   - The `adjust_size` / `_adjust_tamh` guards are two-line early returns leaving both bodies
     **byte-identical**, so a diff shows only the guard. Classical still resizes the window to the
     board, exactly as upstream.
   - `WBase.py:291`'s board-config key changes from `key_video == "maind"` to
     `not x_tb_orientation_horizontal`. Classical horizontal → `BASE`, classical vertical → `BASEV`:
     the same two outcomes the old expression produced, because `key_video` had exactly two values.
     This edit exists **to protect** the invariant — leaving it would silently switch Fritz to
     `BASEV` and share a persisted board config with vertical-toolbar classical users.
   - `LCDialog.register_splitter`'s replace-by-name and `len(li_sp) == sp.count()` are **bug fixes**
     to latent defects (a `RuntimeError` on deleted C++ objects, a silently dropped 4-element
     restore). Classical benefits; nothing regresses.
   - The `pon_toolbar` edit hoists an existing assignment and moves an existing `clear()` around a new
     early return that classical never takes.
   - The optional §0.2b pre-parser hardening is gated behind an **additions-only** snapshot test over
     all ten existing `.qss`/`.colors` pairs, and is revertable on its own if the diff is not clean.

4. **The one classical-visible addition is the pre-existing permitted one.** The `UI mode` combobox
   already exists and is unchanged. This feature adds nothing else to classical's surface.

### 8.2 Positive enforcement

Isolation is argued *and* tested; neither substitutes for the other.

| check | what it proves |
| --- | --- |
| `tests/test_classical_invariant.py` | must pass **unchanged** at every phase boundary. Not amended by this feature. |
| `workflows/classical_invariant.py` | the RPA workflow asserting the invariant against the **running** app. Required green by Gate E. |
| **T-FIX-11** | live: in classical, `adjust_size` still runs (window height tracks the board), `key_video` is `"maind"`, and the T-FRITZ suite passes. |
| **T-FIX-12** | live, both directions: Ctrl+wheel changes `ancho` in classical and does not in Fritz. |
| **T-FIX-14** | on a fresh profile, Fritz's `width_piece` equals classical-horizontal's, and entering Fritz creates **no** `BASEV` entry. |
| **T-RIB-10** | live: with `x_ui_mode = classical`, `ribbon_info.present` is false, `toolbar_size.h < 80`, the eight classical toolbar texts are present, and `find_widget WRibbon` raises. |
| **T-LIT-05/06** | `BOARD_STATIC` is dark in both themes; `IS_DARK` differs correctly. |
| **T-QPS-01/02** | the pre-parser snapshot diff is additions-only. |
| **T-RMAP-06/07** | none of the six non-Fritz mode JSONs contains a `ribbon` key, and `Resources/Modes/` contains no `*.ribbon.json`. |
| `test_completeness.py` N-FRITZ-4 | no upstream module imports `Code.Fritz`. |

### 8.3 The residual risk, stated plainly

`adjust_size` remains in the codebase, dormant behind a guard, because ten entry paths and the whole
classical path depend on it — and one of those paths is a **stored callable**
(`MainWindow.py:49` hands `self.adjust_size` to `Board.set_dispatch_size`, re-entered from
`Board.width_changed`), which no `grep` for call sites reveals. The guard is therefore placed in the
**callee**, which covers every path including that one. The residual risk is that a future
contributor adds a second `set_dispatch_size` caller and reintroduces the coupling with no test
failing. This is recorded in `docs/fritz/troubleshooting.md` and in §10.

---

## 9. Implementation Sequence

See `feature_steps.md` for the phase-by-phase breakdown with files, test names and spec refs, and
`implementation_plan.md` for the per-session blocks.

Ordering constraints that are not merely preference:

| constraint | why |
| --- | --- |
| Phase D before **all** code | Gate A: `docs/process/sdd-workflow.md:32`. |
| Phase 0's `load_modes` cache before Phases 2 and 7 | both call `mode_layout()` on the cached dict; the ribbon would otherwise force ~486 JSON parses per screen change. |
| Phase 1 before Phases 3-6 | it is what makes one codebase serve two palettes; doing the light theme first means writing every colour twice. |
| Phase 2 before Phases 3 and 7 | Phase 3 changes pane heights and Phase 7 adds ~60 px of toolbar. Both are absorbed automatically by Phase 2's `minimumSizeHint()`-based fit, but if `adjust_size` is still live they each fight `board.setFixedSize`. |
| Phase 2 before every later phase's RPA tests | the new verbs and the `_widget_geometry` fix land there. |
| Each phase's pure model before its widget | the arithmetic and state machines are proven by `make test` in seconds; the widget work that follows is then only about pixels. |
| **The design gate blocks Phases 3-7 only** | Phases 1 and 2 carry no visual design content — a de-hardcoding refactor with an intended visual delta of nil, and sizing *behaviour*. They proceed in parallel with the review. |

---

## 10. Out of Scope

- **Re-tiering upstream Lucas Chess R6.** Sixty packages, no coverage to protect them, and it would
  break the Classical Invariant on day one. The rule is strangler-fig: new code is pure by default,
  upstream is reached through adapters. The honest description of the result is "layered islands in a
  monolith", not "n-tier app".
- **Converting `MainWindow` to a `QMainWindow`.** It would buy a menubar, `addToolBar` and dock
  areas, none of which Fritz needs (Fritz's panes are fixed-position), at the cost of a
  Classical-Invariant-breaking change.
- **`QDockWidget` panes.** Floating, undocking and drag-to-rearrange are excluded. `WFritzPane`'s `▾`
  menu offers Hide, Reset size and the sibling list — nothing that fakes a dock.
- **The four RPA object-tier defects** (D8): the key-name mismatch across the driver seam, the
  non-recursive `snapshot()` consumers, `Service._build_activity`'s five wrong constructor calls, and
  `rpa_find`'s `AttributeError`. They are the RPA feature's Gate E business. This feature uses the
  bare remote-control verbs throughout, which work today. Two Fritz-specific `AppState` gaps
  (`_at_home_screen`'s widget-name test, `_has_any_manager`'s `"Manager" in cls` substring) are filed
  in the same issue.
- **Fixing `Board.calc_width_mx_piece`.** It reads screen geometry, is reachable only via the
  `width_piece == 1000` sentinel, hardcodes `limit -= 80` and assumes a `92/80` interpolation ratio
  while ignoring `tamFrontera`. Phase 2 adds alongside it and asserts it is unreachable in Fritz.
  Characterisation tests deliberately pin current behaviour **including these quirks**; fixing them is
  separate, later, testable work.
- **Real content for the placeholder tabs.** Training, Score sheet, LiveBook, Openings Book and
  My Moves are present-but-empty. LiveBook and Openings Book need online services and an
  opening-book pane that does not exist.
- **`Workers/Worker.py:173`'s clock pair.** A fourth `type="clock"` site in a separate top-level
  window not reached through the mode hook. Out of scope for LCD substitution; **in** scope for the
  Phase 6 QSS check, since any `QLabel[type="clock"]` rule reaches it and its 8 pt sizing can clip
  under a rule tuned for 26 pt. Excluded from T-LCD-06 by name so nobody "fixes" the test.
- **Wine as an oracle.** Fritz is commercial (only the 1998 5.32 release is freeware, predating the
  ribbon entirely) and Wine on Apple Silicon needs CrossOver + Rosetta. Consequence: some ribbon
  group assignments are inferred from two screenshots rather than documented, and are marked as
  judgement calls in `docs/fritz/ribbon.md`. Most ChessBase help pages for the ribbon return 404.
- **Two defects noted for separate `fix(rpa)` commits, not fixed as part of a Fritz phase:**
  `Main/LogSetup.py` is **dead code** (nothing imports it, so `CAISSA_LOG_LEVEL` currently does
  nothing), and `make test-ui`'s help text advertises a `CAISSA_TEST=1` the recipe never sets. Both
  are reported rather than propagated, per `docs/claude_code/prompts.md:144-147`.
- **CI.** `.github/` does not exist. Every check here is run by hand via the `Makefile`. This is the
  weakest point of the arrangement and is stated as such rather than papered over.

---

## 11. Changelog

| Date | Author | Change |
| --- | --- | --- |
| 2026-08-28 | Claude Sonnet 4.6 | Initial spec. Gate A candidate. D10 and D11 resolved at authoring time; no decision left open. |

---

## References

- `docs/features/fritz-polish/initial_idea.md` — frozen problem statement and the open-question table
- `docs/features/fritz-polish/feature_steps.md` — phases, files, test names
- `docs/features/fritz-polish/implementation_plan.md` — per-session blocks
- `docs/fritz/` — product documentation (`README`, `concepts`, `glossary`, `decisions`,
  `qss-contract`, `theming`, `ribbon`, `testing`, `troubleshooting`, `design-approval`)
- `docs/standards/ui-design-process.md`, `docs/standards/architecture.md` — the two standards this
  feature adds
- `docs/standards/spec-driven-development.md`, `docs/process/sdd-workflow.md` — the process this
  document conforms to
- `docs/standards/coding-standards.md`, `docstring-standards.md`, `error-handling.md`,
  `logging-standard.md`
- `docs/ui-testing.md` §7.1 — the CV/screenshot amendment this feature uses exactly twice
- `docs/future-directions.md` §0 — the cross-platform rules of N-FRITZ-9
- `docs/rpa/` and `docs/features/rpa-layer/` — the conventions this feature inherits
- `docs/theme-mode-system.md` — the reference SDD and the Theme/Mode overlay architecture
