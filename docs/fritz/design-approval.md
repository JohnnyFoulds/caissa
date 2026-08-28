# Fritz Design Approval

**Status:** Pending — gate not yet reached  
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

**Status:** Not started

| Scene | Reviewed | Notes |
|---|---|---|
| Full window — light palette, variant A | ⬜ | |
| Full window — light palette, variant B | ⬜ | |
| Full window — light palette, variant C | ⬜ | |

**Direction chosen:** —  
**Date:** —  
**Signed off by:** —

---

## Round 2 — Per-Scene Detail

**Status:** Not started

| Scene | Approved | Notes |
|---|---|---|
| `clocks` — LCD digit boxes vs Fritz reference | ⬜ | |
| `pane_titlebar` — gradient title bar, `▾ ✕` buttons | ⬜ | |
| `notation_tabs` — six-tab strip, NAG rows | ⬜ | |
| `eval_line` — dense eval summary format | ⬜ | |
| `nag_row` — two NAG button rows, chip colours | ⬜ | |
| `ribbon_home` — ribbon height, tab labels, group captions | ⬜ | |
| `full_window` — complete assembled UI vs Fritz reference | ⬜ | |

**Date:** —  
**Signed off by:** —

---

## Gate Status

Phase 3 (`feat/fritz-panes`) is **blocked** until both rounds are signed off and all seven rows above
are ✅.

Phases 1 and 2 may proceed without this gate.
