# Fritz Layer — Concepts

**Status:** Living — updated alongside `docs/features/fritz-polish/feature_spec.md`  
**Audience:** Developers building on or modifying the Fritz layer  
**See also:** `docs/fritz/glossary.md`, `docs/fritz/qss-contract.md` *(Phase 0)*

---

## Mode-Gated Visual Overlay

Fritz mode is not a separate application. It is a **visual and behavioural overlay** that activates
when `x_ui_mode` is one of the Fritz modes (`modern-fritz`, `modern-fritz-dark`) and is completely
inactive in `classical` and all other modes.

The overlay is gated at two points:

1. **Mode JSON keys.** `Resources/Modes/modern-fritz.json` declares `"fit_board_to_window": true`
   inside its `layout` block and `"ribbon": "modern-fritz"`. Every existing mode file either lacks
   these keys or has `"layout": null`, so the default is off by construction. `ModeGateway.layout()`
   treats both absent and `null` as `{}`.

2. **The mode hook.** `bin/Code/UIModes/actions/modern_fritz_ui.py` is loaded only when its mode
   is active. Classical mode never loads it. All Fritz-specific widget creation, pane wiring and
   splitter setup lives in the hook's `on_mode_enter` / `on_mode_exit`.

When `x_ui_mode` switches, the process restarts (`Configuration.needs_reinit` includes `x_ui_mode`).
So enter/exit is a process boundary, not a widget swap.

### The Classical Invariant

`classical` mode + no theme overlay = upstream Lucas Chess R6 exactly. This is the regression safety
net. Every Fritz feature is mode-gated so that classical never sees it. The only permitted addition in
classical: the `UI mode` combobox.

---

## The `qproperty-` Contract (E1-E4)

Custom-painted Caissa widgets can be driven from the `.qss` through four verified mechanisms.

### E1 — `qproperty-` + `QtCore.Property`

Declare a property on the widget class:

```python
@QtCore.Property(QtGui.QColor)
def litColor(self) -> QtGui.QColor:
    return self._lit_color

@litColor.setter
def litColor(self, v: QtGui.QColor) -> None:
    self._lit_color = v
    self.update()
```

Then in the `.qss`:

```qss
WFritzLCD
{
qproperty-litColor: #30ff70;
}
```

Qt sets the property at polish time. Because the pre-parsers key on any line containing `#`, the
value is also registered in `dic_original` and appears in *Options → Colours*, overridable from a
`.colors` file, with zero new code.

**The one timing constraint:** `qproperty-` values arrive at polish time — after `__init__`. Anything
consumed before a widget exists (initial splitter sizes, default window size) cannot come from QSS
and lives in the mode JSON's `layout` block instead.

### E2 — `WA_StyledBackground` + `drawPrimitive(PE_Widget)`

Place these two lines at the start of `paintEvent` to make `background-color`, `border` and
`border-radius` work under custom painting:

```python
opt = QStyleOption()
opt.initFrom(self)
self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, opt, painter, self)
```

And in `__init__`:

```python
self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
```

Without E2, QSS box properties are silently ignored on a custom-painted widget.

### E3 — QSS `font-family` / `font-size` / `font-weight`

Set in the `.qss` and read from `self.font()` in `paintEvent`. No `Property` is needed. This
replaces hardcoded `setFamily("Menlo")` calls.

### E4 — Dynamic properties + `[prop="value"]` selectors

Set a dynamic property on the widget and add a QSS selector for it:

```python
self.setProperty("paneActive", "1")
self.style().unpolish(self)
self.style().polish(self)
```

```qss
WFritzPane[paneActive="1"]
{
qproperty-titleTop: #d0e4f4;
}
```

This is the codebase's own existing idiom for state variants — `QLabel[type="clock"]` appears in
nine of the ten shipped `.qss` files.

### Why custom-painted widgets are more themeable, not less

Both QSS pre-parsers (`InitApp.py:44-62`, `WColors.read_qss`) key on any line containing `#`. So
`qproperty-litColor: #30ff70;` under selector `WFritzLCD` registers as `WFritzLCD|qproperty-litColor`
in `dic_original` — an editable row in *Options → Colours*, overridable from a `.colors` file, with
**zero new code**. A custom-painted widget driven by E1 ends up more themeable than a plain QSS widget.

---

## Fixed Window vs Fit-Board

Lucas Chess resizes the main window to fit the board. Fritz does the opposite.

**The Lucas Chess model:** `Board.setFixedSize(ancho, ancho)` propagates into the window's minimum
size because `MainWindow` installs its layout with Qt's default `SetDefaultConstraint`. Then
`adjust_size` loops `adjustSize()` from nine entry points including every game start and home
return, so the window visibly jumps.

**The Fritz model:** the window is user-owned. You size it, maximize it, or leave it. The board fits
into whatever space the pane provides, in whole `width_piece` steps.

The switch is gated by `layout.fit_board_to_window` in the mode JSON. When true:

- `MainWindow` installs its layout with `SetNoConstraint` + `setMinimumSize(0, 0)`, breaking the
  board-drives-window coupling.
- `adjust_size` and `_adjust_tamh` return immediately with no-op guards.
- `_fit_board_now` reads `base.minimumSizeHint() − board.ancho` to measure overhead (ribbon, player
  header, clock row, margins) without enumerating them, then fits the board to the remaining space.
- Four loop-breaking guards prevent the fit → `resizeEvent` → fit cycle.

The arithmetic lives in `bin/Code/Fritz/BoardFit.py` (pure, no Qt), tested as a characterisation
table before any UI code is written.

---

## The Purity Architecture

`bin/Code/Fritz/` is a flat feature package, sibling to `bin/Code/Rpa/`, pure by default. Qt is
confined to a named allowlist of widget modules, and that confinement is asserted by an AST test at
every commit.

The dependency arrow runs one way: **pure → adapter → widget**. Upstream Lucas Chess R6 code never
imports `Code.Fritz`.

New Caissa code is pure by default. Upstream is reached only through adapter modules
(`ThemeGateway`, `ModeGateway`, `ConfigGateway`, `GeometryStore`, `EngineGateway`). This is the
strangler-fig pattern: the upstream ~60 packages are not re-tiered — that would break the Classical
Invariant — but new code builds a clean layer above them.

See `docs/standards/architecture.md` for the full rules and the executable AST test.
