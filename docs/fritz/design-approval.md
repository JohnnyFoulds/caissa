# Fritz Design Approval

**Status:** APPROVED — gate passed 2026-08-28  
**Audience:** The sign-off record; filled in at the Phase 0 design gate  
**See also:** `docs/standards/ui-design-process.md` §5 for the gate procedure

---

## What This Document Is

This is the dated sign-off checklist required by `docs/standards/ui-design-process.md` §5 before
any implementation of visual phases (Phases 3-7) can begin. Phases 1 and 2 may proceed in parallel
with the review.

The sign-off is given after two rounds of mockup review, both run via `tools/design/review.py`.

---

## Round 1 — Layout and Palette (full window)

**Status:** Approved — dark variant accepted as the direction for implementation  
**Date:** 2026-08-28  
**Signed off by:** JohnnyFoulds

| Scene | Reviewed | Notes |
|---|---|---|
| Full window — dark palette (`full_dark.png`) | ✅ | Right column layout confirmed: clocks → engine analysis → eval profile → notation+NAG |

**Direction chosen:** Dark variant mockup as the structural reference. Not pixel-perfect; used as
a starting point for implementation. Light theme follows in Phase 6 from the same structure.

---

## Round 2 — Per-Scene Detail

**Status:** Approved — accepted as starting points, to be refined during implementation  
**Date:** 2026-08-28  
**Signed off by:** JohnnyFoulds

| Scene | Approved | Notes |
|---|---|---|
| `clocks` — LCD digit boxes vs Fritz reference | ✅ | QPainterPath 7-seg digits, two boxes (time + increment) per side |
| `pane_titlebar` — gradient title bar, `▾ ✕` buttons | ✅ | Layout correct; gradient colours to be refined in Phase 3 |
| `notation_tabs` — flowing text + NAG toolbar embedded | ✅ | Flowing inline text (not grid); NAG at bottom of pane; Score sheet tab is the grid |
| `eval_line` — dense eval summary format | ✅ | Single-line format with NAG symbol, cp, depth, time, nodes |
| `nag_row` — two NAG button rows, chip colours | ✅ | Lives inside notation pane, not a separate pane; QLabel buttons (QToolButton invisible offscreen) |
| `eval_profile` — bar chart between engine and notation | ✅ | Added in this session; green/blue bars, current-position marker |
| `full_window` — complete assembled UI vs Fritz reference | ✅ | Structural layout accepted; content and proportions will refine with real data |

---

## Round 3 — Ribbon Tab Design (all tabs)

**Status:** Approved — raster mockup sign-off 2026-08-29
**Date:** 2026-08-29
**Signed off by:** JohnnyFoulds

Design rendered via `tools/design/fritz_compare.py`.
**Approved mockup committed:** [`docs/fritz/assets/ribbon_mockup_approved_2026-08-29.png`](assets/ribbon_mockup_approved_2026-08-29.png)

| Panel | Approved | Notes |
|---|---|---|
| FILE backstage panel | ✅ | Blue sidebar + white item list (New Game, Open, Recent, Save, Save As, separator, Options, Engines, Quit) |
| HOME tab | ✅ | Play (New Game▼, Levels▼), Game (Resign/Draw/Abort/Takeback 2×2), Coaching (Hint/Suggestion), Panes checkboxes |
| BOARD tab | ✅ | Appearance (Flip Board active=blue, Piece Style▼, Square Color▼), View checkboxes |
| ANALYSIS tab | ✅ | Play (Play Now), Tutor (Pause/Continue grayed/Stop), Navigate (Prev/Next), Tools (Config/Utilities) |
| ENGINE tab | ✅ | Engine (Select Engine▼), Settings (Engine Properties, UCI Options, Kibitzer) |
| VIEW tab | ✅ | Layout (Standard Layouts▼, Full Screen), Panes checkboxes |

Tabs confirmed: **Home, Board, Analysis, Engine, View** (Training and Opening removed; File is backstage, not a content tab).

---

## Gate Status

Gate **PASSED**. Phases 3–7 may proceed.

Phases 1 and 2 were approved to proceed in parallel with the review per the plan.

### Key structural decisions locked in by this approval

1. Right column order: Clocks → Engine analysis → Eval profile → Notation (with NAG embedded)
2. Notation tab shows flowing inline text; Score sheet tab shows the move grid
3. NAG annotation toolbar is part of the notation pane, not a standalone pane
4. LCD clock boxes use QPainterPath 7-segment polygons (D11, not a shipped .ttf)
5. Pane title bars with name + `▾` menu + `✕` close button
