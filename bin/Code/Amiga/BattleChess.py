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

# BattleChess disk icon centre in Amiga content coordinates (EXCLUDING macOS title bar).
# click() / double_click() now use cursor detection + single-event delta, so these
# are true content-pixel targets: (screenshot_x, screenshot_y - 32px_title_bar).
# Measured from screenshot at window size 640×432, 2026-08-30.
WORKBENCH_ICON_X = 516
WORKBENCH_ICON_Y = 56

# ---------------------------------------------------------------------------
# Board geometry — NOT YET CALIBRATED
#
# These are placeholder values. Do NOT use them for automation until
# a calibration run has replaced them with measured values.
# ---------------------------------------------------------------------------

# Board bounding box in window-relative pixels: (left, top, width, height).
# Set after calibration.
_BOARD_REGION: tuple[int, int, int, int] | None = None

# Half-sizes for square hit-testing and diff scoring.
# Amiga BC squares are likely similar to the DOS version (~55×47 px).
# Set after calibration.
_SQ_HALF_W: int | None = None
_SQ_HALF_H: int | None = None

# File x-centres (window-relative pixels): column letter → pixel x.
# Set after calibration.
_COL_X: dict[str, int] = {}

# Rank y-centres (window-relative pixels): rank digit → pixel y.
# Rank 1 at the bottom of the board; rank 8 at the top.
# Set after calibration.
_RANK_Y: dict[str, int] = {}


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
