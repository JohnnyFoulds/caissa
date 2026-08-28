# Fritz Polish — Initial Idea

**Status:** FROZEN — scope locked 2026-08-28  
**Frozen by:** Johannes Foulds  
**Next artefact:** [feature_spec.md](feature_spec.md)

---

## Problem Statement

Caissa's Modern Fritz mode plays chess and shows the right pieces in the right places, but placed
next to a real Fritz 18 screenshot it reads as a Qt application wearing a dark stylesheet rather
than a Fritz clone. Three structural problems block any cosmetic progress:

1. The five `WFritz*` widgets each hardcode their own hex palette in Python. `grep -n "WFritz"
   "Resources/Styles/Modern Fritz.qss"` returns nothing, four values have already drifted from
   `Modern Fritz.colors`, and two widgets paint via `paintEvent`/`fillRect` where QSS can never
   reach them. One codebase cannot currently serve two palettes.
2. `MainWindow.adjust_size` loops `adjustSize()` from nine entry points including every game start
   and every home-screen return, so the window visibly jumps. Fritz's window is user-owned: you
   size it or maximize it and the board fits what is left.
3. Widgets read config, open SQLite, poll engine output and monkey-patch each other. The dependency
   arrow also runs backwards: the config loader measures widgets. So "make it look like Fritz"
   keeps reaching into unrelated files.

The intended outcome is a Modern Fritz mode that reads as Fritz at a glance — light chrome, titled
panes, LCD clocks, a notation tab strip, a dense eval line, an Office-style ribbon, a window that
stays where the user puts it — with every design value editable from a `.qss`/`.colors` file and
the logic sitting in unit-tested pure modules rather than inside widgets. Two deliverables — the
design process and the layering rules — are written as standards so the next mode inherits them.

| real Fritz 18/19 | Caissa Modern Fritz today |
|---|---|
| light blue-grey chrome, white content | uniformly dark `#252526` / `#1e1e1e` |
| panes have title bars with name + `▾ ✕` | no pane titles — anonymous `QSplitter` children |
| clocks are black LCD digit boxes | `QLabel` with `00:00` and an HTML `<FONT>` second line |
| notation tab strip: 6 tabs | bare `Grid` with no tabs |
| two rows of NAG symbol buttons | none |
| one dense eval line: `Black is slightly better: ∓ (-0.60) Depth: 24/45 …` | 3 PV rows + mostly-empty graph |
| Office ribbon: File / Home / Board / Training / Analysis / Opening / Engine | one row of 32px text-under-icon buttons |
| window stays where the user puts it | window resizes itself to fit the board |

## Business Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Modern Fritz mode MUST read as Fritz at a glance — light chrome, titled panes, LCD clocks, a notation tab strip, a dense eval line, an Office-style ribbon |
| BR-2 | The window MUST stay where the user puts it across game start, game end and all screen changes |
| BR-3 | The Classical Invariant MUST survive intact — `classical` mode + no theme overlay = upstream Lucas Chess R6 exactly |
| BR-4 | The design methodology and layering rules MUST be reusable by future modes without re-litigation |
| BR-5 | Every colour and pixel metric MUST be user-overridable through the existing `.colors` mechanism |

## Confirmed Decisions (at scope-lock)

| Decision | Choice |
|---|---|
| Mockup medium | PySide6 + the real `.qss` rendered offscreen — not Figma |
| Window ownership | User-owned; board fits the window |
| Design values storage | `.qss` via `qproperty-` — no `.tokens.json` sidecar |
| Default theme | Light `Fritz`; existing dark kept as `modern-fritz-dark` sibling |
| Ribbon host | Inside the existing `QToolBar` as one `QWidgetAction` |
| Board zoom in Fritz | Disabled — writes `width_piece` that the next fit overrides |
| Seam pattern | Plain base classes raising `NotImplementedError`; no `abc.ABC`, no `typing.Protocol` |
| RPA object-tier defects | Not fixed in this feature — RPA feature's Gate E business |
| `docs/modern-fritz.md` | Superseded via `git mv`, not amended |
| Coverage config | Separate config + `make cov-fritz` target — independent 90% gates |
| Seven-segment digits | `QPainterPath` polygons — no shipped `.ttf` |

## Open Questions (to be resolved in feature_spec.md)

All decisions were resolved before or during spec-writing and are recorded in
`docs/fritz/decisions.md` as D1–D11. No question remained open at scope-lock.
