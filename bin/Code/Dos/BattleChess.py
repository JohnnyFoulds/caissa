"""
bin/Code/Dos/BattleChess.py — Battle Chess DOS automation via DOSBox-X.

Provides :class:`BattleChessSession`: a state-machine-driven automation
layer that launches Battle Chess in DOSBox-X, navigates menus, makes moves,
and detects CPU responses.

All public action methods follow the RPA pattern::

    CHECK_PRE → ACT → SETTLE → VERIFY

Pure pixel-inspection helpers are separated from side-effecting actions so
they can be called with a pre-existing PIL Image without touching the
running session.  Call them as ``bc.is_selected(img, "e2")`` — they never
produce screenshots themselves.

Board geometry is calibrated for the **2D view** at the default 640×428
DOSBox-X window size.

:purity: adapter
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

    from Code.Dos.Driver import DosBoxDriver

logger = logging.getLogger(__name__)

_GAME_DIR   = Path("/Users/johannes/Documents/dosbox/oldgames/bc")
_LAUNCH_CMD = "BC.COM"

# ------------------------------------------------------------------
# Board geometry — 2D view, calibrated at 640×428 window.
# Board bounds: x=100..543, y=38..417 (window-relative).
# Square size: ~55.4 wide × 47.4 tall.
# White (pink) at bottom, ranks 1-2; black (blue/dark) at top, ranks 7-8.
# ------------------------------------------------------------------

_SQ_HALF_W = 27   # pixels from square center to left/right edge
_SQ_HALF_H = 23   # pixels from square center to top/bottom edge

# Board bounding box in window-relative pixels: (left, top, width, height)
_BOARD_REGION = (100, 38, 443, 379)

# File x-centres (window-relative pixels)
_COL_X: dict[str, int] = {
    "a": 127, "b": 183, "c": 238, "d": 293,
    "e": 349, "f": 404, "g": 459, "h": 515,
}

# Rank y-centres (window-relative pixels); rank 1 at bottom
_RANK_Y: dict[str, int] = {
    "1": 393, "2": 345, "3": 298, "4": 251,
    "5": 203, "6": 156, "7": 109, "8":  61,
}

# Pre-computed centre coords for every square, e.g. {"e2": (349, 345)}
_SQUARE_COORDS: dict[str, tuple[int, int]] = {
    col + rank: (_COL_X[col], _RANK_Y[rank])
    for col in _COL_X
    for rank in _RANK_Y
}

# Minimum selection-color pixels required to count a square as "selected"
_SELECTION_MIN_PX = 50

# Mean pixel-diff threshold at which we consider a square to have "changed"
_CHANGE_THRESHOLD = 5.0

# Board-region poll parameters for waiting on CPU response
_CPU_POLL_S       = 0.5
_CPU_CHANGE_SCORE = 3.0


def square_center(square: str) -> tuple[int, int]:
    """Return window-relative centre pixel of *square*.

    :param square: Algebraic square name, e.g. ``"e2"``.
    :returns: ``(rel_x, rel_y)``.
    :raises KeyError: If *square* is not a valid algebraic name.
    """
    return _SQUARE_COORDS[square.lower()]


# ==================================================================
# Pure pixel-inspection helpers
# All accept a PIL Image already captured; none produce side-effects.
# ==================================================================

def inner_square_changed(
    before: Image,
    after: Image,
    square: str,
    *,
    threshold: float = 10.0,
) -> bool:
    """Return True if the **inner core** of *square* changed significantly.

    Uses only the inner ½-size crop of the square, which is dominated by
    piece pixels rather than the selection border or cursor edge.  This makes
    the check immune to cursor-hover artefacts and selection-box flicker that
    trip the full-square diff.

    :param before: Screenshot before the action.
    :param after: Screenshot after the action.
    :param square: Algebraic square name.
    :param threshold: Mean absolute diff threshold (0–255) to call "changed".
    :returns: ``True`` if the inner core changed more than *threshold*.
    """
    import numpy as np

    cx, cy = square_center(square)
    hw = max(1, _SQ_HALF_W // 2)
    hh = max(1, _SQ_HALF_H // 2)

    def _crop(img: Image) -> np.ndarray:
        return np.array(
            img.crop((cx - hw, cy - hh, cx + hw, cy + hh)).convert("RGB"),
            dtype=np.int32,
        )

    diff = float(np.abs(_crop(before) - _crop(after)).mean())
    logger.debug("inner_square_changed: %s diff=%.1f (threshold=%.1f)", square, diff, threshold)
    return diff >= threshold


def board_crop(img: Image) -> Image:
    """Crop *img* to the board region only.

    :param img: Full-window PIL Image.
    :returns: Cropped PIL Image containing only the chessboard.
    """
    x, y, w, h = _BOARD_REGION
    return img.crop((x, y, x + w, y + h))


def square_crop(img: Image, square: str) -> Image:
    """Crop *img* to the bounding box of *square*.

    :param img: Full-window PIL Image.
    :param square: Algebraic square name.
    :returns: Small cropped PIL Image of that square.
    """
    cx, cy = square_center(square)
    return img.crop((
        cx - _SQ_HALF_W, cy - _SQ_HALF_H,
        cx + _SQ_HALF_W, cy + _SQ_HALF_H,
    ))


def is_selected(img: Image, square: str) -> bool:
    """Return True if *square* shows the Battle Chess selection highlight.

    The highlight flickers between bright green and bright blue; both are
    accepted.

    :param img: Full-window PIL Image.
    :param square: Algebraic square name.
    :returns: ``True`` if a selection border is visible.
    """
    import numpy as np

    cx, cy = square_center(square)
    crop = img.crop((
        cx - _SQ_HALF_W, cy - _SQ_HALF_H,
        cx + _SQ_HALF_W, cy + _SQ_HALF_H,
    ))
    arr = np.array(crop.convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green = (r < 80) & (g > 150) & (b < 80)
    blue  = (r < 80) & (g < 80) & (b > 150)
    return int((green | blue).sum()) >= _SELECTION_MIN_PX


def is_white_piece_at(img: Image, square: str) -> bool:
    """Return True if *square* likely contains a white (pink/cream) piece.

    White pieces in 2D Battle Chess are rendered in pinkish tones.
    The check uses the inner core (half the square size) to avoid border noise.

    :param img: Full-window PIL Image.
    :param square: Algebraic square name.
    :returns: ``True`` if enough pink-toned pixels are present.
    """
    import numpy as np

    cx, cy = square_center(square)
    hw, hh = _SQ_HALF_W // 2, _SQ_HALF_H // 2
    crop = img.crop((cx - hw, cy - hh, cx + hw, cy + hh))
    arr = np.array(crop.convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Pink/cream: high R, moderate G, moderate B; red channel dominates
    pink = (r > 150) & (r > g + 30) & (r > b + 10)
    return int(pink.sum()) >= 8


def is_black_piece_at(img: Image, square: str) -> bool:
    """Return True if *square* likely contains a black (blue/dark) piece.

    Black pieces in 2D Battle Chess are rendered in blue-ish dark tones.

    :param img: Full-window PIL Image.
    :param square: Algebraic square name.
    :returns: ``True`` if enough blue-dark-toned pixels are present.
    """
    import numpy as np

    cx, cy = square_center(square)
    hw, hh = _SQ_HALF_W // 2, _SQ_HALF_H // 2
    crop = img.crop((cx - hw, cy - hh, cx + hw, cy + hh))
    arr = np.array(crop.convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Blue/dark: blue channel dominant, relatively dark
    blue_dark = (b > 80) & (b > r + 20) & (b > g + 10) & ((r.astype(int) + g + b) < 300)
    return int(blue_dark.sum()) >= 8


def has_piece_at(img: Image, square: str) -> bool:
    """Return True if *square* contains either a white or black piece.

    :param img: Full-window PIL Image.
    :param square: Algebraic square name.
    :returns: ``True`` if a piece is detected.
    """
    return is_white_piece_at(img, square) or is_black_piece_at(img, square)


def detect_changed_squares(
    before: Image,
    after: Image,
    *,
    threshold: float = _CHANGE_THRESHOLD,
) -> list[tuple[float, str]]:
    """Return squares that changed significantly between two screenshots.

    Computes per-square mean pixel diff, returns all squares above *threshold*
    sorted descending by change magnitude.

    :param before: PIL Image taken before the action.
    :param after: PIL Image taken after the action.
    :param threshold: Minimum mean diff (0–255) to include in results.
    :returns: List of ``(score, square_name)`` tuples, most-changed first.
    """
    import numpy as np

    b_arr = np.array(before.convert("RGB"), dtype=np.int32)
    a_arr = np.array(after.convert("RGB"),  dtype=np.int32)
    diff  = np.abs(b_arr - a_arr)
    h, w  = diff.shape[:2]

    results: list[tuple[float, str]] = []
    for sq, (cx, cy) in _SQUARE_COORDS.items():
        x0 = max(0, cx - _SQ_HALF_W)
        y0 = max(0, cy - _SQ_HALF_H)
        x1 = min(w, cx + _SQ_HALF_W)
        y1 = min(h, cy + _SQ_HALF_H)
        if x1 <= x0 or y1 <= y0:
            continue
        score = float(diff[y0:y1, x0:x1].mean())
        if score >= threshold:
            results.append((score, sq))
    results.sort(reverse=True)
    return results


def board_state(img: Image) -> dict[str, str]:
    """Classify all 64 squares as empty, white piece, or black piece.

    Uses color detection on each square's inner core crop.  A high pixel-count
    threshold (50) ensures that sprite overflow from an adjacent rank — where
    only the top of a tall piece enters the crop — does not trigger a false
    piece detection.  A full piece body contributes 100–300 qualifying pixels;
    overflow contributes fewer than 50.

    :param img: Full-window PIL Image.
    :returns: Dict mapping each square name to ``'w'`` (white/pink piece),
              ``'b'`` (black/blue piece), or ``''`` (empty).
    """
    import numpy as np

    arr = np.array(img.convert("RGB"), dtype=np.int32)
    ih, iw = arr.shape[:2]
    hw = max(1, _SQ_HALF_W // 2)
    hh = max(1, _SQ_HALF_H // 2)
    # Minimum colored pixels in the inner core to count as a piece presence.
    # After animation settles (0.8s), a piece body contributes 50-300 px and
    # overflow from an adjacent rank contributes ~5-15 px.  Threshold 20 gives
    # clear separation while reliably detecting all piece types.
    _MIN_PIECE_PX = 20

    state: dict[str, str] = {}
    for sq, (cx, cy) in _SQUARE_COORDS.items():
        x0 = max(0, cx - hw)
        y0 = max(0, cy - hh)
        x1 = min(iw, cx + hw)
        y1 = min(ih, cy + hh)
        crop = arr[y0:y1, x0:x1]
        r, g, b = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        pink = int(((r > 150) & (r > g + 30) & (r > b + 10)).sum())
        blue = int(((b > 80) & (b > r + 20) & (b > g + 10) & (r + g + b < 300)).sum())
        if pink >= _MIN_PIECE_PX:
            state[sq] = "w"
        elif blue >= _MIN_PIECE_PX:
            state[sq] = "b"
        else:
            state[sq] = ""
    return state


def _infer_from_candidates(
    before: Image,
    after: Image,
    candidates: list[tuple[float, str]],
) -> tuple[str, str] | None:
    """Infer from/to from a pre-filtered candidate list using brightness DELTA.

    Like :func:`infer_move` but skips the change-detection step — use this
    when the caller has already identified which squares changed for one side.

    Direction rule: use brightness(after) - brightness(before) for each square.
    - Positive delta (square got brighter): a dark piece LEFT → FROM square.
    - Negative delta (square got darker): a dark piece ARRIVED → TO square.
    This works for both white and black pieces because the side that got
    brighter lost its piece and the side that got darker gained one.
    The old "brighter in before = from" heuristic failed for black pieces
    (dark pieces) because a dark piece on a dark/medium square was LESS bright
    than the now-empty destination, so from/to were reversed.

    :param before: Board state before the move.
    :param after: Board state after the move.
    :param candidates: ``[(score, square_name), ...]`` for the squares of interest.
    :returns: ``(from_sq, to_sq)`` or ``None`` if fewer than 2 candidates.
    """
    import numpy as np

    if len(candidates) < 2:
        logger.debug("_infer_from_candidates: fewer than 2 candidates — ambiguous")
        return None

    sq_a = candidates[0][1]
    sq_b = candidates[1][1]

    def _mean_brightness(img: Image, sq: str) -> float:
        arr = np.array(square_crop(img, sq).convert("L"), dtype=np.float32)
        return float(arr.mean())

    # delta > 0 means the square got brighter: a piece left (FROM).
    # delta < 0 means the square got darker: a piece arrived (TO).
    delta_a = _mean_brightness(after, sq_a) - _mean_brightness(before, sq_a)
    delta_b = _mean_brightness(after, sq_b) - _mean_brightness(before, sq_b)
    logger.debug(
        "_infer_from_candidates: %s Δbright=%.1f  %s Δbright=%.1f",
        sq_a, delta_a, sq_b, delta_b,
    )
    # The square with the more-positive delta is the FROM (piece left it).
    return (sq_a, sq_b) if delta_a >= delta_b else (sq_b, sq_a)


def infer_move(before: Image, after: Image) -> tuple[str, str] | None:
    """Infer the from/to squares of a move from two screenshots.

    Finds the two most-changed squares, then uses brightness of the *before*
    image to determine which was the source (brighter before = had a piece).

    :param before: Board state before the move.
    :param after: Board state after the move.
    :returns: ``(from_sq, to_sq)`` or ``None`` if ambiguous.
    """
    import numpy as np

    changed = detect_changed_squares(before, after)
    if len(changed) < 2:
        logger.debug("infer_move: fewer than 2 changed squares — ambiguous")
        return None

    sq_a = changed[0][1]
    sq_b = changed[1][1]

    def _mean_brightness(img: Image, sq: str) -> float:
        arr = np.array(square_crop(img, sq).convert("L"), dtype=np.float32)
        return float(arr.mean())

    # Use brightness delta (after - before): the square that got brighter
    # had a piece leave it (FROM); the square that got darker gained a piece (TO).
    # This correctly handles both white and black pieces.
    delta_a = _mean_brightness(after, sq_a) - _mean_brightness(before, sq_a)
    delta_b = _mean_brightness(after, sq_b) - _mean_brightness(before, sq_b)
    logger.debug("infer_move: %s Δbright=%.1f  %s Δbright=%.1f", sq_a, delta_a, sq_b, delta_b)

    # More-positive delta = FROM (piece left, square brightened).
    if delta_a >= delta_b:
        return sq_a, sq_b
    return sq_b, sq_a


# ==================================================================
# BattleChessSession — state-machine-driven automation
# ==================================================================

class BattleChessSession:
    """One automated Battle Chess session.

    :param level: Difficulty level 1–9 (1 = fastest / most deterministic).
    :param save_dir: Directory for debug screenshots.  Created if absent.
    """

    def __init__(
        self,
        level: int = 1,
        save_dir: str | Path = "/tmp/bc_session",
    ) -> None:
        self._level   = max(1, min(9, level))
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._process = None
        self._driver: DosBoxDriver | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        level: int = 1,
        save_dir: str | Path = "/tmp/bc_session",
    ) -> BattleChessSession:
        """Launch DOSBox-X with Battle Chess if not running, then attach.

        Uses :class:`~Code.Dos.Activities.EnsureDosBoxRunning` as the first
        RPA activity so the tool self-recovers from a closed or missing DOSBox
        window without any manual intervention.

        :param level: Difficulty level 1–9.
        :param save_dir: Directory for debug screenshots.
        :returns: Initialised session instance (DOSBox confirmed running).
        :raises RuntimeError: If DOSBox-X cannot be launched within the timeout.
        """
        from Code.Dos.Activities import (
            DismissTitleScreen,
            DosRunner,
            EnsureBoard2D,
            EnsureDosBoxRunning,
            FocusDosBox,
            WaitForBoardReady,
        )
        from Code.Dos.Driver import DosBoxDriver
        from Code.Dos.Process import DosBoxProcess

        session = cls.__new__(cls)
        session._level = max(1, min(9, level))
        session._save_dir = Path(save_dir)
        session._save_dir.mkdir(parents=True, exist_ok=True)

        process = DosBoxProcess(
            game_dir=_GAME_DIR,
            launch_cmd=_LAUNCH_CMD,
            drive="E",
        )
        session._process = process
        session._driver = DosBoxDriver(process)

        runner = DosRunner(save_dir=str(session._save_dir))
        runner.run(session._driver, [
            EnsureDosBoxRunning(process),
            FocusDosBox(),
            DismissTitleScreen(),  # press ENTER to advance past the splash screen
            EnsureBoard2D(),       # switch from 3D to 2D view via settings menu
            WaitForBoardReady(),   # confirms 2D board colour fraction ≥ threshold
        ])
        logger.info("BattleChessSession.open: DOSBox-X confirmed running, board visible")
        return session

    @classmethod
    def attach(
        cls,
        level: int = 1,
        save_dir: str | Path = "/tmp/bc_session",
    ) -> BattleChessSession:
        """Attach to an already-running DOSBox-X Battle Chess window.

        Useful for interactive testing without a full launch/quit cycle.

        :param level: Difficulty level assumed for corpus entries.
        :param save_dir: Directory for debug screenshots.
        :returns: Initialised session instance.
        :raises RuntimeError: If no DOSBox-X window is visible.
        """
        from Code.Dos.Driver import DosBoxDriver
        from Code.Dos.Process import DosBoxProcess

        session = cls.__new__(cls)
        session._level = max(1, min(9, level))
        session._save_dir = Path(save_dir)
        session._save_dir.mkdir(parents=True, exist_ok=True)
        session._process = DosBoxProcess.attach()
        session._driver = DosBoxDriver(session._process)
        logger.info("BattleChessSession attached to running DOSBox-X")
        return session

    def start(self) -> BattleChessSession:
        """Launch DOSBox-X with Battle Chess and wait for the title screen.

        :returns: *self* for chaining.
        """
        from Code.Dos.Driver import DosBoxDriver
        from Code.Dos.Process import DosBoxProcess

        logger.info("starting Battle Chess session (level %d)", self._level)
        self._process = DosBoxProcess(
            game_dir=_GAME_DIR,
            launch_cmd=_LAUNCH_CMD,
            drive="E",
        ).launch()
        self._driver = DosBoxDriver(self._process)
        logger.info("waiting for Battle Chess to load…")
        time.sleep(6)
        return self

    def stop(self) -> None:
        """Terminate DOSBox-X."""
        if self._process is not None:
            self._process.stop()
            self._process = None
            self._driver = None

    def __enter__(self) -> BattleChessSession:
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _shot(self, name: str = "") -> Image:
        """Take a screenshot, optionally saving it for debugging."""
        img = self._driver.screenshot()
        if name:
            img.save(str(self._save_dir / f"{name}.png"))
        return img

    # ------------------------------------------------------------------
    # Menu navigation — right-click-hold mechanic
    # ------------------------------------------------------------------

    def open_menu(self) -> None:
        """Hold the right mouse button down to reveal the Battle Chess menu bar.

        The menu bar appears along the top of the screen while right-click is
        held.  Follow with :meth:`hover_menu_item` then :meth:`release_menu`.

        :raises RuntimeError: If the driver is not initialised.
        """
        # Press and hold right-click near the top-left of the board.
        # The exact position is not critical; anywhere on the game area works.
        logger.debug("opening Battle Chess menu (right-click hold)")
        self._driver.mousedown(200, 200, button="right")
        time.sleep(0.3)  # wait for menu bar to appear

    def hover_menu_item(self, rel_x: int, rel_y: int) -> None:
        """Hover the mouse to a menu item while keeping right-click held.

        :param rel_x: Window-relative X of the target item.
        :param rel_y: Window-relative Y of the target item.
        """
        self._driver.move_to(rel_x, rel_y)
        time.sleep(0.2)

    def release_menu(self, rel_x: int, rel_y: int) -> None:
        """Release right-click at *(rel_x, rel_y)* to select the hovered item.

        :param rel_x: Window-relative X of the target item.
        :param rel_y: Window-relative Y of the target item.
        """
        self._driver.mouseup(rel_x, rel_y, button="right")
        time.sleep(0.4)

    # ------------------------------------------------------------------
    # State: 2D/3D view detection and switching
    # ------------------------------------------------------------------

    def switch_to_2d(self) -> bool:
        """Navigate Settings → 2D Board if not already in 2D view.

        Uses OCR to locate the "2D Board" menu item under Settings.
        Returns True if the switch was (or already was) successful.

        :returns: ``True`` if 2D mode is active after this call.
        """
        from Code.Dos.Ocr import find_nth_text_bounds

        logger.info("switch_to_2d: opening settings menu")
        # Hold right-click to reveal the menu bar
        self._driver.mousedown(200, 200, button="right")
        time.sleep(0.4)

        # Take screenshot with menu open and OCR to find "Settings"
        img = self._driver.screenshot()
        # "Settings" top-level is roughly at (320, ~12) in a 640-wide window
        # but use OCR to be robust to different window sizes
        from Code.Dos.Ocr import find_text_bounds
        settings_bounds = find_text_bounds(img, "Settings", psm="7", min_conf=10.0)
        if settings_bounds:
            sx = settings_bounds[0] + settings_bounds[2] // 2
            sy = settings_bounds[1] + settings_bounds[3] // 2
        else:
            # Fallback: Settings is the 3rd item in the menu bar (after Disk, Move)
            sx, sy = 320, 12
            logger.debug("switch_to_2d: OCR missed Settings, using fallback (%d,%d)", sx, sy)

        # Hover over Settings to open its submenu
        self._driver.move_to(sx, sy)
        time.sleep(0.3)

        # Re-screenshot to find "2D Board" in the submenu
        img2 = self._driver.screenshot()
        img2.save(str(self._save_dir / "menu_settings_open.png"))

        bounds_2d = find_nth_text_bounds(img2, "Board", 2, min_conf=10.0)
        if bounds_2d:
            tx = bounds_2d[0] + bounds_2d[2] // 2
            ty = bounds_2d[1] + bounds_2d[3] // 2
            logger.info("switch_to_2d: found 2D Board at (%d,%d), releasing", tx, ty)
        else:
            # Fallback position from prior calibration
            tx, ty = 399, 179
            logger.debug("switch_to_2d: OCR missed 2D Board, using fallback (%d,%d)", tx, ty)

        self._driver.move_to(tx, ty)
        time.sleep(0.2)
        self._driver.mouseup(tx, ty, button="right")
        time.sleep(0.5)
        logger.info("switch_to_2d: menu released")
        return True

    # ------------------------------------------------------------------
    # CHECK — piece state queries
    # ------------------------------------------------------------------

    def has_piece(self, img: Image, square: str) -> bool:
        """Return True if either a white or black piece is visible at *square*.

        :param img: Screenshot already taken.
        :param square: Algebraic square name.
        :returns: ``True`` if a piece is present.
        """
        return is_white_piece_at(img, square) or is_black_piece_at(img, square)

    # ------------------------------------------------------------------
    # ACT — piece selection
    # ------------------------------------------------------------------

    def select_piece(self, square: str) -> bool:
        """Click *square* to select the piece there.

        Pattern: CHECK_PRE (piece present) → ACT (click) → SETTLE → VERIFY (selected).

        :param square: Algebraic square name of the piece to select.
        :returns: ``True`` if selection was confirmed.
        :raises RuntimeError: If no piece is at *square* before clicking.
        """
        img_pre = self._shot(f"select_pre_{square}")

        if not self.has_piece(img_pre, square):
            raise RuntimeError(f"select_piece: no piece visible at {square}")

        cx, cy = square_center(square)
        logger.debug("select_piece: clicking %s (%d,%d)", square, cx, cy)
        self._driver.click(cx, cy)
        time.sleep(0.35)

        # VERIFY: poll up to 3 times for the selection border to appear
        for attempt in range(3):
            img_post = self._shot(f"select_post_{square}_{attempt}")
            if is_selected(img_post, square):
                logger.info("select_piece: %s selected (attempt %d)", square, attempt)
                return True
            time.sleep(0.15)

        logger.warning("select_piece: selection NOT confirmed at %s", square)
        return False

    # ------------------------------------------------------------------
    # ACT — make a full move
    # ------------------------------------------------------------------

    def make_move(
        self,
        from_sq: str,
        to_sq: str,
        *,
        wait_for_cpu_s: float = 20.0,
    ) -> str | None:
        """Make a move and return the CPU's reply as a UCI string.

        Composed of five Activities driven by :class:`~Code.Dos.Activities.DosRunner`::

            FocusDosBox    — bring window to foreground (settle 400 ms)
            SourceDragDown — CHECK_PRE piece present; ACT MOUSEDOWN at source; settle 200 ms
            DragToDest     — ACT MOUSEDRAGGED to dest; settle 150 ms; no screenshots
            DragRelease    — ACT MOUSEUP at dest; settle 200 ms; VERIFY source changed
            WaitCpuReply   — VERIFY ≥2 squares changed vs baseline (excluding our squares)

        Battle Chess 2D uses drag-to-move (MOUSEDOWN at source, MOUSEUP at dest);
        the earlier two-click approach never registered because the game does not
        use a click-to-select + click-to-move protocol.

        :param from_sq: Source square, e.g. ``"e2"``.
        :param to_sq: Destination square, e.g. ``"e4"``.
        :param wait_for_cpu_s: Seconds to wait for CPU response.
        :returns: CPU move as UCI string, e.g. ``"e7e5"``, or ``None``.
        """
        from Code.Dos.Activities import (
            DosRunner,
            DragRelease,
            DragToDest,
            FocusDosBox,
            SourceDragDown,
            WaitCpuReply,
            WaitForBoardReady,
        )

        logger.info("make_move: %s → %s", from_sq, to_sq)

        runner = DosRunner(save_dir=str(self._save_dir))
        wait_cpu = WaitCpuReply(from_sq, to_sq)
        wait_cpu.verify_ms = int(wait_for_cpu_s * 1000)

        try:
            ctx = runner.run(self._driver, [
                FocusDosBox(),
                WaitForBoardReady(),        # verify board is playable before touching input
                SourceDragDown(from_sq),
                DragToDest(to_sq),
                DragRelease(from_sq),
                wait_cpu,
            ])
        except RuntimeError as exc:
            logger.error("make_move: %s", exc)
            return None

        return ctx.get("cpu_move")

    # ------------------------------------------------------------------
    # Corpus helper
    # ------------------------------------------------------------------

    def record_corpus_entry(
        self,
        fen: str,
        our_move: str,
        cpu_move: str,
        level: int | None = None,
        moves_from_startpos: list[str] | None = None,
        path: str | Path = "Resources/Retro/Corpus/dos-manual.jsonl",
    ) -> None:
        """Append one corpus entry to *path*.

        Schema is compatible with ``Code.Retro.Oracle.load_corpus`` — only
        ``fen``, ``level``, and ``expected_uci`` are required by the loader;
        extra keys are ignored.

        :param fen: FEN of the position before the CPU's move.
        :param our_move: Our move in UCI notation, e.g. ``"e2e4"``.
        :param cpu_move: Observed CPU reply in UCI notation.
        :param level: Game level (defaults to session level).
        :param moves_from_startpos: Optional move sequence for provenance.
        :param path: Output JSONL file (appended, created if absent).
        """
        import json

        entry: dict = {
            "fen": fen,
            "level": level if level is not None else self._level,
            "expected_uci": cpu_move,
            "source": "dos-manual",
            "our_move": our_move,
        }
        if moves_from_startpos:
            entry["moves_from_startpos"] = moves_from_startpos

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("corpus entry appended: %s → %s (level %d)", our_move, cpu_move, entry["level"])
