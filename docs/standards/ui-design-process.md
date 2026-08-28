# UI Design Process

## Purpose

This document fixes the design methodology Caissa uses for every visual feature. It exists so that
the next mode, the next theme, or the next widget redesign starts from a tested process rather than
re-deriving one. The Fritz Polish feature is the reference implementation; see §10.

---

## 1. Core Principle

**Design in the shipping medium.** The mockup MUST be PySide6 + the real `.qss`, rendered offscreen.
It MUST NOT be a picture of the intended result (Figma, Sketch, Keynote, a PNG someone drew by hand).

Why this matters: a design that looks right in a vector tool routinely cannot be expressed in QSS
because QSS has no flexbox, no grid, and no proper box model. If approval happens in Figma, the
"translation step" from Figma to QSS is where the design is actually made — the approval was on the
wrong artefact.

When the mockup is PySide6 + QSS, what you approve is literally the code that ships. There is no
translation gap and no fidelity loss.

---

## 2. Why Not a Design Tool

For reference, the four reasons Figma was rejected for this codebase — generalised:

1. **Lossy translation.** Any design tool that is not Qt produces a picture of the target rather than
   the target. The gap shows up at implementation time, when it is too late.
2. **No reliable round-trip for agents.** An AI agent cannot reliably view its own exports from
   cloud-based design tools. The feedback loop becomes "read JSON and reason about pixels I cannot see",
   which defeats the purpose of a visual review.
3. **Manual setup chain.** External tools require accounts, installers, running services and plugin
   handshakes — steps the user must perform, contradicting the goal of a low-friction process.
4. **Artefacts outside the repo.** A design that cannot be committed cannot be diffed, reviewed in a
   PR, or used as a test fixture.

---

## 3. The Oracle

An external reference corpus MUST exist before design begins. For a mode that imitates an existing
product (Fritz, DOS chess, etc.), this is official screenshots of that product.

The corpus MUST live outside the repo when it is third-party-copyrighted. Place it at
`Path.home() / "Pictures" / "<feature>-reference"` and reach it through a `CAISSA_<FEATURE>_REF`
environment variable defaulting to that path.

The naming reason is explicit: third-party screenshots in a public GPL-3.0 repo is a licensing
problem. The reference crops are a development oracle for the author, not committed test fixtures.

---

## 4. The Render Loop

```
edit Resources/Styles/<name>.qss
    → tools/design/fritz_mock.py --scene <name>   (~1-2 s, no app restart)
    → renders the widget offscreen
    → saves <design-out>/<scene>.png
    → author reads the PNG
    → tools/design/compare.py <scene>.png --ref <ref-crop>
    → prints a 0-255 mean-abs-diff score
    → edit the .qss, repeat
```

The offscreen bootstrap (`QT_QPA_PLATFORM=offscreen`) MUST reuse `tests/conftest.py`'s
`_bootstrap()` function so the render uses the real fonts, the real `Code.dic_colors`, and the real
icon pack. Never create a second `QApplication` instance; import and call `_bootstrap()`.

The design output directory MUST be `Path(tempfile.gettempdir()) / "caissa-design"` by default,
overridable via `CAISSA_DESIGN_OUT`. This path MUST be set once in `tools/design/__init__.py` and
imported everywhere else. Never hardcode `/tmp/` — see `docs/future-directions.md` §0.

---

## 5. The Approval Gate

Before implementing any visual phase (phases that change what users see), a two-round approval cycle
MUST run and the sign-off MUST be recorded in `docs/<feature>/design-approval.md`.

**Round 1 — layout and palette, full window.** Render 2-3 full-window candidates. The reviewer picks
a direction or rejects all of them. Rejection triggers another round.

**Round 2 — per-scene detail.** One row per scene in the review sheet, each with the Fritz reference
crop on the left and the Caissa mockup on the right, plus a mean-abs-diff score. The reviewer approves
scene by scene. A rejected scene triggers another iteration on that scene alone.

**The review artifact** is `<design-out>/review.html`, built by `tools/design/review.py` and opened
by it via `webbrowser.open(url)`. Never shell out to `open` or `xdg-open` — `webbrowser.open` is the
stdlib, cross-platform equivalent.

**Implementation of visual phases MUST NOT begin before sign-off is recorded.** This is the visual
counterpart of SDD's "no code before a reviewed spec". The benefit is that when you first see the
feature it looks right, rather than arriving at the end of a phase wondering whether it was what was
intended.

---

## 6. Phase-Exit Re-Review

Every visual phase MUST end with `tools/design/review.py --live` run against the real running app.

The `--live` flag replaces the mockup column in the review sheet with a screenshot from
`QtDriver.screenshot` over the remote-control socket — the actual running application, not an
isolated widget tree. Mockups cannot show live data, engine output or real board position, so this
step is the check that the static approval translates to dynamic behaviour.

Phases 1 and 2 are structural (de-hardcoding refactor and window-sizing behaviour) and have no visual
content; they are exempt from this step.

---

## 7. Extending QSS to Custom Widgets

Custom-painted Caissa widgets MUST take their design values from the `.qss`, not from Python
constants. A `#RRGGBB` literal in a widget module is permitted only as a `QtCore.Property` default,
one per property. This applies to every new widget and MUST be retrofitted to existing ones as part of
a theming phase.

The four verified mechanisms, in the order to reach for them:

| # | Mechanism | What it buys |
|---|---|---|
| E1 | `qproperty-<name>` + `QtCore.Property` | Any value a `paintEvent` needs: colours, pixel metrics, booleans, brushes |
| E2 | `WA_StyledBackground` + `drawPrimitive(PE_Widget, opt, p, self)` | QSS box model under custom painting: `background-color`, `border-radius` |
| E3 | QSS `font-family` / `font-size` / `font-weight` | `self.font()` in `paintEvent`; no `Property` needed |
| E4 | Dynamic properties + `[prop="value"]` selectors | State variants without Python branches |

Because both `.colors` pre-parsers key on any line containing `#`, a `qproperty-` line like
`qproperty-litColor: #30ff70;` registers as an editable row in *Options → Colours* and is
overridable from a `.colors` file — with zero new code. Custom-painted widgets become *more*
themeable than QSS-styled ones.

Every widget's spec MUST declare its `qproperty-` contract: property name, type, default value,
and the QSS line form.

The three QSS authoring rules (Q1/Q2/Q3) apply to every `.qss` and `.colors` file. They are
enforced by `tests/unit/fritz/test_qss_rules.py`; never rely on memory alone.

---

## 8. The Qt Escalation Ladder

Use the cheapest rung that works. Document in the spec which rung each widget uses and why.

| Rung | Mechanism | When to use |
|---|---|---|
| 1 | QSS selectors | Flat fills, borders, padding, hover states on standard widgets |
| 2 | `QStyledItemDelegate.paint` | Custom cell rendering in table/list views |
| 3 | `paintEvent` + `QPainter` / `QPainterPath` | Gradient fills, rounded/trapezoid shapes, LCD digits |
| 4 | `QProxyStyle.drawControl` | Shapes that must apply identically to multiple widget types |

Dropping below QSS for *painting* no longer forfeits `.qss` retheming — §7's E1-E4 contract carries
the values back up. "Custom-painted" does not mean "not themeable".

---

## 9. What Is Not a Test

The design harness is a **development tool**, not a test. Its reference crops MUST NOT be committed.
Running it is how the author iterates and how the reviewer reviews; it has no role in `make test`.

The committed visual assertions are limited to the six conditions in `docs/ui-testing.md` §7.1:

1. No full-window pixel equality.
2. Assertions limited to template-presence and OCR text location.
3. Reference PNG + JSON sidecar under `Resources/Rpa/Reference/`.
4. Templates registered in `Resources/Rpa/Templates/manifest.json`.
5. Capture at DPR-1 via `widget.grab()` / `QTest` only.
6. Every CV assertion paired with an object-tier assertion; tests carry `rpa_cv` marker.

A visual phase SHOULD prefer an object-tier assertion (`ribbon_info`, `find_widget`, `qproperty-`
resolution) and reach for CV only where widget inspection is not possible.

---

## 10. Reference Implementation

The Fritz Polish feature (`docs/features/fritz-polish/`) is the first application of this process.
It covers seven visual phases, a full oracle corpus, a complete round-1/round-2 approval cycle, and
the `tools/design/` harness. Read it alongside this document for a worked example.
