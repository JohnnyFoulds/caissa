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
