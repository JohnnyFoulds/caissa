# Fritz Mode — Initial Idea

**Status:** FROZEN at scope-lock  
**Date:** 2026-08-29  
**Author:** Johannes Foulds

---

## Problem statement

Caissa's Fritz mode has an approved ribbon design (`docs/fritz/ribbon-design.md`,
`docs/fritz/design-approval.md` Round 3) and a working ribbon widget layer
(`bin/Code/Fritz/WRibbon.py`), but no specification of what the mode actually *does*.
Two concrete problems flow from that gap.

**Problem 1 — The landing screen contradicts Fritz's UX.**  
Fritz mode opens onto a right-hand panel titled "Modern Fritz" (literal string in
`bin/Code/UIModes/WFritzHome.py:52`) with three cards: New Game, Load Game, Enter &
Analyse. Real Fritz 18 has no such screen inside the chess UI. It boots directly into a
live board with panes open and the engine analysing. The landing screen does nothing the
ribbon cannot do, confuses users familiar with Fritz, and means the approved ribbon is
hidden behind a screen that doesn't belong.

**Problem 2 — Most ribbon buttons are undefined or broken.**  
The `▼` dropdown chevron on every large button is a string literal appended to the button
text (`WRibbon.py:762-768`) — no popup exists anywhere in the codebase. `"toggle": true`
appears in `docs/fritz/ribbon-design.md:446` and is read by no code. `caissa:std_layout`
and `caissa:play_now` are literal `pass` stubs. The Board ▸ Display checkboxes have no
`key` and are decorative. The `pane_api` the ribbon depends on is captured at a moment
when `Procesador.main_window` is still `None`, so pane checkboxes are permanently inert.
Nothing currently states what any of the approved buttons *should do*.

## The north star

The Fritz 18 manual is live at `https://help.chessbase.com/Fritz/18/Eng/<page>.htm`.
Every behavioural claim in this SDD cites a specific page URL rather than an
unverifiable PDF page number. The manual established the key fact that drives the
entire boot-state design:

> "the program is set after the first start on the Infinite analysis mode… So you have
> to select a Playing level first before you can play directly against the program."
> — `https://help.chessbase.com/Fritz/18/Eng/000128.htm`

## Decisions taken at scope-lock

These decisions are final and cannot be re-opened without a new SDD:

| Question | Decision |
|---|---|
| Boot state | **Infinite Analysis, manual-faithful.** Board in initial position, panes open, engine analysing continuously, engine does not reply to moves. User picks Home ▸ Levels to start a real game. |
| SDD scope | Whole mode, one feature directory, Phases 0–6, ships incrementally (one branch = one phase = one PR). |
| Existing red tests + doc drift | Folded into Phase 0 — fix before any new code lands. |

## Open questions at scope-lock

*None — all answered before freezing this document.*

- Boot state question (answered above via manual `000128` + `000056` + `000027`).
- SDD scope (answered above — whole mode, phased).
- Red tests (answered above — Phase 0).

## Out of scope

- Fritz features with no Lucas Chess implementation: ChessBase Live, LiveBook, online
  play, database browser, media player, DGT board, tournament arbiter mode.
- Classic Lucas Chess features absent from Fritz mode by design: training puzzles,
  competition ladder, resistance mode, tactics trainer, leagues, databases.
- Converting `MainWindow` from `QDialog` to `QMainWindow`.
- Any work in `classical` mode — the Classical Invariant is inviolable.
