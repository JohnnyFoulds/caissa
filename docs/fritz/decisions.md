# Architecture Decision Log — Fritz Layer

Each decision records what was decided, why, and when. Decisions are appended; never deleted.

---

## D1 — Mockup medium is PySide6, not Figma

**Resolved:** 2026-08-28  
**Decision:** Build mockups in PySide6 + the real `.qss`, rendered offscreen.  
**Rationale:** Four concrete reasons drove the rejection of Figma: (a) Figma is auto-layout and
vector; QSS has no flexbox, no grid, no proper box model — a design that looks right in Figma
routinely cannot be expressed in QSS, so approval would lag implementation. (b) The Talk-to-Figma
`export_node_as_image` server documents "limited support… returning base64 as text", so an agent
cannot reliably view its own exports. (c) Setup requires a Figma account, `Figma.app`, `bun`, a
running socket bridge, and a plugin `join_channel` — all steps the user must perform manually.
(d) The design would live outside the repo, so it could never be diffed or used as a test fixture.
PySide6 + QSS has none of these problems: the mockup is the shipping code, the render loop is
seconds, and all artefacts are in the repo.  
**Alternative considered:** Talk-to-Figma MCP — rejected for the four reasons above.

---

## D2 — The window is user-owned; the board fits the window

**Resolved:** 2026-08-28  
**Decision:** In Fritz modes, the board fits into whatever space the pane provides. `adjust_size`
is made inert via two early-return guards. The change is gated by `layout.fit_board_to_window`.  
**Rationale:** This is the single most-felt defect in the current mode. Lucas Chess resizes the
window to the board from nine entry points including every game start and home return. Real Fritz
does the exact opposite. Fixing it is foundational: pane sizes, splitter persistence and the
ribbon's height all depend on the window staying put.  
**Alternative considered:** Keep `adjust_size` and compensate with a post-resize fit — rejected
because the race between the two would produce visible flicker on every screen change.

---

## D3 — Design values live in the `.qss` via `qproperty-`, not in a `.tokens.json` sidecar

**Resolved:** 2026-08-28  
**Decision:** Every colour and pixel metric a custom widget needs is declared as a `QtCore.Property`
with a `qproperty-<name>` QSS line. No sidecar file, no dotted-path loader.  
**Rationale:** The existing `.colors` pre-parsers key on any line containing `#`, so
`qproperty-litColor: #30ff70;` under selector `WFritzLCD` registers as an editable row in
*Options → Colours* with zero new code. One file format instead of two, one loader instead of
two, and no risk of a token and a stylesheet disagreeing. Verified on this install before committing
to the approach.  
**Alternative considered:** `.tokens.json` sidecar with a `Tokens.py` loader — rejected because
it introduces a second file format and a second loader, and makes the `.colors` override chain
unreachable for custom-painted widgets.

---

## D4 — Light `Fritz` is the default theme; dark `Modern Fritz` is the sibling variant

**Resolved:** 2026-08-28  
**Decision:** `modern-fritz.json` uses `"style": "Fritz"` (light). The existing dark stylesheet
is preserved as `modern-fritz-dark.json` with `"style": "Modern Fritz"`.  
**Rationale:** Real Fritz chrome is light blue-grey. A mode named after Fritz that defaults to
dark reads as visually wrong to anyone familiar with the product. The ~1.5× QSS work was the
accepted trade.  
**Alternative considered:** Dark-only — rejected because it misrepresents Fritz.

---

## D5 — The ribbon is hosted inside the existing `QToolBar` as one `QWidgetAction`

**Resolved:** 2026-08-28  
**Decision:** `WRibbon` is wrapped in a `QWidgetAction` and added to `self.base.tb`.  
**Rationale:** `MainWindow` is a `QDialog` (inherits `LCDialog(QtWidgets.QDialog)`). There is no
`addToolBar`, no menubar, and no dock areas. There are zero `QDockWidget` uses in the codebase.
Hosting the ribbon inside the existing `QToolBar` keeps five upstream contracts alive unmodified:
`MainWindow.changeEvent`'s F11 hide/show, `toolbar_enable`, `get_toolbar()`, `equalize_toolbar_buttons`,
and all direct `setDisabled` callers in managers.  
**Alternative considered:** Convert `MainWindow` to a `QMainWindow` — rejected as a far larger,
Classical-Invariant-breaking change that buys nothing Fritz needs.

---

## D6 — Board zoom is disabled in Fritz modes

**Resolved:** 2026-08-28  
**Decision:** `board.allowed_extern_resize(False)` in Fritz. Ctrl+wheel and Ctrl+± are no-ops.  
**Rationale:** Both write `width_piece` and then `guardaEnDisco()`. The fit path would immediately
override whatever they wrote, so zoom would appear intermittently broken. Real Fritz has no board
zoom either — you resize the pane. Classical mode is unaffected.  
**Alternative considered:** Persist zoom to `width_piece` and feed it as the fit's minimum — rejected
because it creates a second authority on board size and makes T-FIX-08 unprovable.

---

## D7 — Seams are plain base classes raising `NotImplementedError`

**Resolved:** 2026-08-28  
**Decision:** No `abc.ABC`, no `typing.Protocol`. Plain base classes, matching the `Driver`/`QtDriver`/
`FakeDriver` shape and the `Manager.py:61` precedent (~35 subclasses).  
**Rationale:** `docs/standards/coding-standards.md:72` explicitly prohibits both: "`typing.Protocol`
is built on `ABCMeta`, so this prohibition covers both." The RPA work widened the rule and it is now
binding on all new Caissa code.  
**Alternative considered:** `typing.Protocol` as a type-check-only escape hatch — rejected when the
prohibition was widened.

---

## D8 — The four RPA object-tier defects are not fixed in this feature

**Resolved:** 2026-08-28  
**Decision:** The Fritz layer uses bare remote-control verbs throughout (`find_widget`, `click_toolbar`,
`screenshot` and the new Phase 2 verbs), not the object-tier `rpa_find`/`rpa_act` surface.  
**Rationale:** Four defects in the RPA layer make its object-tier unusable for Fritz widgets: a
key-name mismatch across the driver seam, non-recursive `snapshot()` consumers, five wrong constructor
calls in `Service._build_activity`, and an `AttributeError` in `rpa_find`. These belong in that
feature's Gate E `production_readiness.md` findings list, not in this scope. The bare verbs work today.  
**Alternative considered:** Fix the RPA defects as part of this work — rejected because that would
tie two features' Gate E milestones together.

---

## D9 — `docs/modern-fritz.md` is superseded, not amended

**Resolved:** 2026-08-28  
**Decision:** `git mv` the still-accurate content into `docs/fritz/concepts.md` and `docs/fritz/theming.md`
stubs. The file is deleted. Three drifted claims are reported in the PR body.  
**Rationale:** The file names `WFritzEnginePanel` (shipped as `WFritzAnalysisTable`), gives the palette
as `#161616`/`#1f1f1f` (shipped `#252526`/`#1e1e1e`), and states *"Q2: Same 88-key set"* (the number
is wrong and the rule is mis-described). Amending it would require updating three wrong claims while
the feature spec supersedes it more completely. `spec-driven-development.md:102-103` grandfathers only
`theme-mode-system.md` and `ui-testing.md`; this file is not on the list.  
**Alternative considered:** Add a third grandfather entry — rejected; that keeps a stale document in
the discoverable location and grows the exception list unnecessarily.

---

## D10 — `Code.Fritz` gets its own coverage configuration and `make cov-fritz` target

**Resolved:** 2026-08-28  
**Decision:** A second config file (`fritz.coveragerc`) with `source = Code.Fritz` and `fail_under = 90`,
plus a `make cov-fritz` target. The RPA config (`[run] source = Code.Rpa`) is not changed.  
**Rationale:** A shared denominator would mean the RPA feature's Gate E coverage claim and the Fritz
feature's claim can mask each other — a phase that regresses Fritz coverage below 90% would still
pass if RPA coverage is high enough. Independent gates make each claim verifiable.  
**Alternative considered:** Extend the existing `.coveragerc` — rejected for the masking reason above.

---

## D11 — Seven-segment digits are `QPainterPath` polygons, not a shipped `.ttf`

**Resolved:** 2026-08-28  
**Decision:** `WFritzLCD` draws its digits as `QPainterPath` polygon segments. No seven-segment font
file is bundled.  
**Rationale:** `docs/future-directions.md` §0 requires that bundled assets be enumerable by
PyInstaller and forbids assuming an unbundled asset is present. A `.ttf` would require a licence
check and a PyInstaller bundling case. Polygons give exact control of segment thickness and of the
dim "off" segments that are most of Fritz's LCD visual signature. `qproperty-segmentThickness` makes
the polygon route themeable at no extra cost. The Phase 0 mockup renders a font-based variant
alongside the polygon one so the shape is still reviewed; only the implementation mechanism is decided.  
**Alternative considered:** `QFontDatabase.addApplicationFont` with a bundled seven-segment `.ttf` —
rejected on cost and licensing grounds relative to polygons.

---

## D12 — Raster Pillow mockup precedes the PySide6 widget harness

**Resolved:** 2026-08-29  
**Decision:** Design iteration starts with a pure-Pillow raster script (`tools/design/fritz_compare.py`)
before any PySide6 widget code is written. The PySide6 harness (`tools/design/fritz_mock.py`) is
used only once the raster design is approved.  
**Rationale:** The Pillow loop is seconds per render, requires no Qt display, and produces a
side-by-side comparison image that is easy to review. The PySide6 harness renders real widgets with
real QSS, which is accurate but slower to iterate on and requires an offscreen display. Separating
the two phases keeps the design loop fast during the visual exploration stage.  
**How to apply:** Raster mockup approval comes first. Once the layout and group choices are signed
off in the raster mockup, the PySide6 harness is updated to match the agreed design.

---

## D13 — Hint / Suggestion are plain action buttons; Coaching group uses `?` icon

**Resolved:** 2026-08-29  
**Decision:** The Caissa "Coaching" ribbon group contains two small flat buttons — Hint and
Suggestion — each using a `?` icon. They are not radio buttons, not toggles, and not grouped as a
selection control.  
**Rationale:** Confirmed from Fritz 18 manual (`https://help.chessbase.com/Fritz/18/Eng/000018.htm`, `https://help.chessbase.com/Fritz/18/Eng/000070.htm`): Hint and Suggestion are plain one-shot actions. An earlier mockup used a circle outline icon that visually resembled a
radio button; this was incorrect and has been replaced with the `?` icon.  
**Alternative considered:** Radio buttons / toggle buttons — rejected because the Fritz manual
confirms these are one-time actions, not mode selections.

---

## D14 — macOS QTabBar tab shapes require a full custom paintEvent

**Resolved:** 2026-08-29  
**Decision:** `_FlatTabBar` subclasses `QTabBar` and owns `paintEvent` entirely. No QSS selector
or `QProxyStyle.drawControl` override is used for tab shape.  
**Rationale:** macOS AppKit bypasses Qt's QSS rendering for native tab shapes. `border-radius: 0`
in QSS and `QStyleFactory.create("Fusion")` both fail to remove rounded corners on macOS.
Owning `paintEvent` gives full platform-independent control of tab geometry and colour.
Same pattern as `_FritzPaneCheckBox` in the same file.  
**Alternative considered:** `QProxyStyle.drawControl(CE_TabBarTabShape)` — rejected; it also
routes through the native style on macOS and produces the same rounded result.

---

## D15 — `QFrame.VLine` is unreliable for 1px separators; use plain `QWidget`

**Resolved:** 2026-08-29  
**Decision:** Ribbon group separators are plain `QWidget` instances with `WA_StyledBackground`,
`setFixedWidth(1)`, and `background-color` set via QSS.  
**Rationale:** `QFrame.VLine` with `Plain` shadow still renders a thick bar on macOS because its
internal minimum-size heuristics override Python `setFixedWidth(1)` when QSS is applied at polish
time. `background-color` in QSS also paints the full implicit widget area rather than a 1px line.
A plain `QWidget` with `WA_StyledBackground` and `setFixedWidth(1)` has no such baggage — `background-color`
paints exactly the 1px-wide widget.  
**Alternative considered:** `QFrame.VLine` + `min-width: 1px; max-width: 1px` in QSS — rejected;
QSS width constraints are overridden by the frame's own size policy at polish time.

---

## D16 — QSS `font-size` on a parent selector does not cascade to child widgets

**Resolved:** 2026-08-29  
**Decision:** Every ribbon child widget selector that requires a specific font size carries its own
explicit `font-size` rule in QSS (`#WRibbonPages QToolButton`, `#WRibbonGroupCaption`,
`#WRibbonPages QCheckBox`).  
**Rationale:** Qt's QSS `font-size` on a parent widget (e.g. `WRibbon { font-size: 10pt; }`) does
not cascade through the widget hierarchy to child widgets. Each widget is styled independently.
Python `setFont()` on a parent widget does cascade, but is overridden by any explicit QSS rule on
a child — so an explicit QSS font on a child trumps a Python parent font.  
**Alternative considered:** Python `setFont()` on the parent — rejected; child QSS rules override it,
creating an order-of-operations trap where the visible font depends on which stylesheet is loaded.

---

## D17 — Layout `setSpacing` and QSS `margin` both contribute to visual gaps; use only one

**Resolved:** 2026-08-29  
**Decision:** Ribbon group separator `QWidget` carries `margin: 8px 0px` in QSS (top/bottom only).
Horizontal spacing between groups comes entirely from the `QHBoxLayout.setSpacing(4)` on the page
layout.  
**Rationale:** If the separator has both a QSS horizontal margin (e.g. `margin: 4px 6px`) and the
layout has `setSpacing(4)`, the visual gap between groups is the sum of both — `4 + 6 + 1 + 6 + 4
= 21px` — which looks fat even though the line itself is 1px. Setting horizontal margin to 0 on the
separator and letting layout spacing control horizontal gaps keeps the total gap predictable.

---

## D18 — `_swap_home_to_analysis` is deleted, not patched

**Resolved:** 2026-08-29  
**Decision:** `_swap_home_to_analysis` (`modern_fritz_ui.py:354-495`) is deleted in Phase 1.
Its replacement is `_build_fritz_right_col(mw)`, which both the boot path and the game-start
path call.  
**Rationale:** `_swap_home_to_analysis` has two defects that cannot be fixed in isolation:
it early-returns `False` when `_fritz_home is None` (`:368-371`), which is the permanent
state after the landing screen is deleted; and it mutates `right_col` positionally, assuming
the first child is always `WFritzHome` (`:405`, `:410-411`, `:414`). A patch that removes
the early-return and fixes the positional mutation is larger than a clean rewrite, and
leaves dead code paths. `_build_fritz_right_col` is the single function that builds the
right column from the `_PANE_SPECS` order; it is idempotent and safe to call twice.  
**Alternative considered:** Patch `_swap_home_to_analysis` — rejected because the function
is premised on a widget (`WFritzHome`) that no longer exists.

---

## D19 — `WFritzHome.py` is deleted, not archived or emptied

**Resolved:** 2026-08-29  
**Decision:** `bin/Code/UIModes/WFritzHome.py` is deleted (`git rm`) in Phase 1.
Its 33 associated `#WFritzHome*` QSS rules across three stylesheets are also deleted.  
**Rationale:** The file has zero callers after the boot-state change. Keeping an empty or
stub file wastes the purity-tier AST walk's attention and leaves dead QSS rules. Deleted
files are still reachable in git history for any future reference.  
**Alternative considered:** Leave an empty module or a deprecation notice — rejected as
dead code.

---

## D20 — The `voyager2` route in `_dispatch_non_game_action` is removed, not fixed

**Resolved:** 2026-08-29  
**Decision:** `modern_fritz_ui.py:513` (`sh.play_menu().run_exec("voyager2")`) is deleted.
The correct call for "Set up position" is `Voyager.voyager_position(mw, position)` called
directly from the New Game ▼ panel's "Set up position" item.  
**Rationale:** `play_menu().run_exec("voyager2")` routes through `BaseMenu.run_exec` →
`PlayMenu.run_select`, which has no `voyager2` attribute, causing an `AttributeError` that
is silently swallowed (`:515-516`). The only place `"voyager2"` is a real key is
`Openings/WindowOpeningLine.py:744`, an unrelated opening-study dialog. `Voyager.voyager_position()`
(`Voyager/Voyager.py:1038`) is the correct entry point for position setup.  
**Alternative considered:** Add `voyager2` to `PlayMenu` — rejected; that would add a
Lucas Chess internal routing key for a Fritz-specific use case, violating the architectural
boundary.
