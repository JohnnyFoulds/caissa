"""
bin/Code/Amiga/BattleChess.py — Battle Chess (Amiga) board geometry constants.

**All values in this file are UNSET until a calibration run has been done.**

Calibration procedure:
  1. Launch FS-UAE with Resources/Retro/BattleChess.adf + kick34005.A500.
  2. Navigate to the 2D chess board view.
  3. Call ``FsUaeDriver(process).calibrate()`` to save a screenshot.
  4. Open the screenshot in Preview and use the pixel inspector to measure:
     - Board bounding box (left, top, width, height) in window-relative pixels.
     - Centre (x, y) of each file (a–h) and rank (1–8).
  5. Fill in the constants below and commit.
  6. Add the calibrated values to CLAUDE.md under
     "Amiga/FS-UAE Automation Layer (calibrated)".

See docs/rpa/new-target-guide.md §Step 5 for the full calibration protocol.

:purity: dependency-free
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

# FS-UAE window size as configured in BattleChess-ADF.fs-uae.
# Must match ``window_width`` and ``window_height`` in the config file.
_WINDOW_W = 640
_WINDOW_H = 400

# ---------------------------------------------------------------------------
# Workbench UI geometry — calibrated 2026-08-30
# ---------------------------------------------------------------------------

# Launching BattleChess from Workbench requires TWO double-clicks:
#   1. Double-click the floppy-disk icon → opens a drawer window showing its contents.
#   2. Double-click the BattleChess executable icon inside that window → launches the game.
# All coordinates are Amiga content pixels (screenshot_y − 32 px macOS title bar).
# Calibrated 2026-08-30 at window size 640×432.

# Step 1 — floppy disk icon on the Workbench desktop
WORKBENCH_DISK_ICON_X = 516
WORKBENCH_DISK_ICON_Y = 56

# Step 2 — BattleChess executable icon inside the opened drawer window
WORKBENCH_EXEC_ICON_X = 278
WORKBENCH_EXEC_ICON_Y = 150

# ---------------------------------------------------------------------------
# Board geometry — NOT YET CALIBRATED
#
# These are placeholder values. Do NOT use them for automation until
# a calibration run has replaced them with measured values.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Board geometry — calibrated 2026-08-30 from 2D board screenshot
#
# Measurements taken from 640×432 window (640×400 Amiga content + 32px macOS
# title bar). All coordinates are Amiga content pixels (screenshot_y − 32).
# Board boundaries (screenshot): left=155, top=48, right=486, bottom=332
# Square size: 41.4 × 35.5 px
# ---------------------------------------------------------------------------

# macOS title bar height added by screencapture (pixels above Amiga content).
# Add this to any Amiga-content Y before using it as a PIL crop coordinate.
_TITLE_BAR_H: int = 32

# Board bounding box: (left, top, width, height) in Amiga content pixels.
_BOARD_REGION: tuple[int, int, int, int] = (155, 16, 331, 284)

# Half-sizes for square hit-testing and diff scoring.
_SQ_HALF_W: int = 20
_SQ_HALF_H: int = 17

# File x-centres: column letter → Amiga content X (same as screenshot X).
_COL_X: dict[str, int] = {
    "a": 175, "b": 217, "c": 258, "d": 299,
    "e": 341, "f": 382, "g": 423, "h": 465,
}

# Rank y-centres: rank digit → Amiga content Y (screenshot_y − 32).
# Rank 1 at the bottom; rank 8 at the top.
_RANK_Y: dict[str, int] = {
    "8": 33,  "7": 69,  "6": 104, "5": 140,
    "4": 175, "3": 211, "2": 246, "1": 282,
}


def sq_center(square: str) -> tuple[int, int]:
    """Return the window-relative pixel centre of a chess square.

    :param square: Algebraic square name, e.g. ``"e2"``.
    :returns: ``(cx, cy)`` window-relative pixel coordinates.
    :raises ValueError: If the square is invalid or geometry is not calibrated.
    """
    if len(square) != 2:
        raise ValueError(f"invalid square: {square!r}")
    file_, rank = square[0].lower(), square[1]
    if file_ not in _COL_X:
        raise ValueError(
            f"file {file_!r} not in _COL_X — run calibration first"
        )
    if rank not in _RANK_Y:
        raise ValueError(
            f"rank {rank!r} not in _RANK_Y — run calibration first"
        )
    return _COL_X[file_], _RANK_Y[rank]


def all_sq_coords() -> dict[str, tuple[int, int]]:
    """Return a mapping of all 64 square names to window-relative pixel centres.

    :returns: ``{"a1": (cx, cy), ...}`` for all 64 squares.
    :raises ValueError: If geometry is not calibrated.
    """
    if not _COL_X or not _RANK_Y:
        raise ValueError("board geometry not calibrated — populate _COL_X and _RANK_Y first")
    return {
        f"{f}{r}": (_COL_X[f], _RANK_Y[r])
        for f in "abcdefgh"
        for r in "12345678"
    }
