---
**Status:** Living — updated through Phase 4
**Implements:** E1-E4 ``qproperty-`` contract for all Fritz custom-painted widgets
**Audience:** Widget authors, theme authors, ``test_qproperty_contract.py`` maintainers
**See also:** ``docs/standards/ui-design-process.md`` §7, ``Resources/Styles/Modern Fritz.qss``
---

# Fritz QSS Contract

Every custom-painted Fritz widget exposes its design values through the E1–E4
mechanism so they arrive from the `.qss` — not from Python module constants.
This file is the single authoritative list of every `qproperty-` declaration,
which themes must include and `test_qproperty_contract.py` validates.

## E1–E4 recap

| # | Mechanism | What it buys |
|---|---|---|
| **E1** | `qproperty-<name>` in `.qss` + `QtCore.Property(…, getter, setter)` in Python | Any value a `paintEvent` needs (colours, metrics, booleans) — arrives at polish time, user-editable in *Options → Colours* when it is a single `#RRGGBB` line |
| **E2** | `setAttribute(WA_StyledBackground)` + `style().drawPrimitive(PE_Widget, …)` as the first two lines of `paintEvent` | QSS `background-color`, `border`, `border-radius`, `padding` render *beneath* custom painting |
| **E3** | `font-family`, `font-size`, `font-weight` in QSS | `self.font()` in `paintEvent` — replaces every hardcoded `setFamily("Menlo")` call |
| **E4** | Dynamic Qt properties + `[prop="value"]` QSS selectors | State variants (active/inactive, side-to-move, light/dark) as stylesheet selectors |

**Authoring rule (Q1):** one `#RRGGBB` hex per single-colon line so the `.colors`
pre-parser registers it as an editable key.  Use two `qproperty-` colour lines
instead of a `qlineargradient(…)` to keep both gradient stops editable.

---

## WFritzPane

File: `bin/Code/Fritz/WFritzPane.py`  
Phase: 3 (`feat/fritz-panes`)  
Selector: `WFritzPane`

| Property | Type | Default | Purpose |
|---|---|---|---|
| `qproperty-titleHeight` | `int` | `20` | Height of the gradient title bar in px; setter calls `setFixedHeight` on the bar |
| `qproperty-titleTop` | `QColor` | `#3c3c3c` | Top colour of the vertical gradient |
| `qproperty-titleBottom` | `QColor` | `#2d2d2d` | Bottom colour of the vertical gradient |
| `qproperty-titlePadX` | `int` | `6` | Horizontal padding for the pane-name label |

Font, text colour and button hover states come from the `#WFritzPaneTitle`
selector (E3 + standard QSS); no `qproperty-` needed for those.

```qss
WFritzPane
{
qproperty-titleHeight: 20;
qproperty-titleTop: #3c3c3c;
qproperty-titleBottom: #2d2d2d;
qproperty-titlePadX: 6;
background-color: #1e1e1e;
border: 1px solid #505050;
}

#WFritzPaneTitle
{
font-size: 8pt;
font-weight: bold;
color: #cccccc;
}
```

**E2 note:** both `WFritzPane` and `_PaneTitleBar` call `drawPrimitive(PE_Widget)`
so QSS `background-color` / `border-radius` render beneath the gradient.

---

---

## WFritzLCD

File: `bin/Code/Fritz/WFritzLCD.py`  
Phase: 4 (`feat/fritz-clocks-eval`)  
Selector: `WFritzLCD`

| Property | Type | Default | Purpose |
|---|---|---|---|
| `qproperty-litColor` | `QColor` | `#00ff88` | Colour of lit (on) segments |
| `qproperty-dimColor` | `QColor` | `#103a18` | Colour of dim (off) segments |
| `qproperty-boxHeight` | `int` | `34` | Fixed height in px; setter calls `setFixedHeight` |
| `qproperty-boxWidth` | `int` | `108` | Fixed width in px; setter calls `setFixedWidth` |
| `qproperty-segmentThickness` | `int` | `4` | Segment bar thickness in px (scaled to actual height at paint time) |

The box background and border-radius come from QSS `background-color` / `border-radius` (E2).
Font properties are accepted via E3 but the widget does not use `self.font()` in painting —
segment geometry is computed from `boxWidth`/`boxHeight` only.

```qss
WFritzLCD
{
qproperty-litColor: #00ff88;
qproperty-dimColor: #103a18;
qproperty-boxHeight: 34;
qproperty-boxWidth: 108;
qproperty-segmentThickness: 4;
background-color: #000000;
border-radius: 2px;
}
```

**Input forms accepted by `set_time_text`:**

- `MM:SS` — plain clock string
- `H:MM:SS` — hours shown
- `MM:SS<br><FONT SIZE="-4">…` — HTML two-line form from `WBase.set_clock_white/black`

Parsing is delegated to `ClockModel.parse` + `ClockModel.digits`; on parse failure the
widget falls back to the first five printable characters of the stripped string.

**E2 note:** `WA_StyledBackground` is set in `__init__` and `drawPrimitive(PE_Widget)` is
called first in `paintEvent` so QSS `background-color` renders beneath the segments.

---

## `#WFritzEvalSummary`

Widget: `QtWidgets.QLabel` child of `WFritzAnalysisTable`  
Phase: 4 (`feat/fritz-clocks-eval`)  
Selector: `#WFritzEvalSummary`

This label is a plain `QLabel` — no custom painting, no `qproperty-` contract.
All styling is via standard QSS properties.

```qss
#WFritzEvalSummary
{
font-size: 8pt;
color: #cccccc;
padding: 2px 8px;
}
```

Format produced by `WFritzAnalysisTable._update_eval_summary`:

```
White is slightly better: ⩲ (+0.42) Depth: 24/45 00:00:16 51157kN
```

---

## Planned widgets (future phases)

| Widget | Phase | Properties to be declared |
|---|---|---|
| `WRibbon` | 7 | `ribbonHeight` |
| `WRibbonTabBar` | 7 | `tabActiveTop`, `tabActiveBottom`, `tabInactiveTop`, `tabInactiveBottom` |

Each widget's full table will be added here when its phase lands.

---

## Invariants enforced by `test_qproperty_contract.py`

1. Every `qproperty-<name>` entry in a `.qss` `WFritz*` or `WRibbon*` selector
   resolves to a declared `QtCore.Property` on the named class
   (`staticMetaObject.indexOfProperty(name) >= 0`).
2. Each widget instantiated under `Fritz` and `Modern Fritz` reports different
   resolved values for colour properties (proves the `.qss` blocks differ as expected).
3. Each widget instantiated with **no** stylesheet still renders with non-`#000000`
   foreground (the Python defaults-are-sane rule).
4. `WA_StyledBackground` is set on every custom-painted widget.
