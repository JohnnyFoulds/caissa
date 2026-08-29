"""
bin/Code/Dos/Activities.py — RPA Activity layer for Battle Chess / DOSBox-X automation.

Follows the CHECK_PRE → ACT → SETTLE → VERIFY pattern documented in
docs/rpa/state-machine.md.  Each Activity declares:

- ``check_pre_screenshot`` — whether CHECK_PRE must capture a screenshot.
  Set False when the precondition is unconditional so no screenshot is taken
  between adjacent activities (prevents selection-timeout between SourceClick
  and MoveToDest).
- ``verify_screenshot``  — whether VERIFY must capture a screenshot.
  Set False when postcondition is trivially True (same reason).
- ``settle_ms`` — milliseconds to wait after execute() before first VERIFY.
- ``verify_ms`` — milliseconds to keep polling postcondition before timeout.

:purity: adapter
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Code.Dos.Driver import DosBoxDriver
    from Code.Dos.Process import DosBoxProcess
    from PIL.Image import Image

logger = logging.getLogger(__name__)

_POLL_MS = 20  # ms between postcondition polls during VERIFY


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class DosActivity:
    """Base class for all Dos-layer RPA activities.

    :cvar name: Display name used in logs and error messages.
    :cvar settle_ms: Wait after execute() before first postcondition call.
    :cvar verify_ms: Maximum wait for postcondition to return True.
    :cvar check_pre_screenshot: If True, DosRunner takes a screenshot for CHECK_PRE.
    :cvar verify_screenshot: If True, DosRunner takes screenshots during VERIFY.
    """

    name: str = "DosActivity"
    settle_ms: int = 200
    verify_ms: int = 5000
    check_pre_screenshot: bool = True
    verify_screenshot: bool = True

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """Return True if the app is in the right state to execute.

        :param img: Current screenshot, or None if check_pre_screenshot=False.
        :param ctx: Shared context dict for passing state between activities.
        :returns: True if the activity may proceed.
        """
        raise NotImplementedError(f"{type(self).__name__}.precondition not implemented")

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """Issue the driver actuation.

        :param driver: DosBoxDriver instance.
        :param ctx: Shared context dict.
        """
        raise NotImplementedError(f"{type(self).__name__}.execute not implemented")

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """Return True if the action was performed successfully.

        Called repeatedly during VERIFY until True or timeout.

        :param img: Current screenshot, or None if verify_screenshot=False.
        :param ctx: Shared context dict.
        :returns: True if the postcondition is satisfied.
        """
        raise NotImplementedError(f"{type(self).__name__}.postcondition not implemented")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class DosRunner:
    """Sequential activity runner following CHECK_PRE → ACT → SETTLE → VERIFY.

    :param save_dir: Optional directory to write debug screenshots on failure.
    """

    def __init__(self, save_dir: str | None = None) -> None:
        self._save_dir = save_dir

    def run(self, driver: "DosBoxDriver", activities: list[DosActivity]) -> dict:
        """Execute *activities* in order.

        :param driver: DosBoxDriver to pass to each activity.
        :param activities: Activities to execute in sequence.
        :returns: Shared ctx dict populated by activities.
        :raises RuntimeError: If any precondition fails or postcondition times out.
        """
        ctx: dict = {}
        for act in activities:
            logger.debug("DosRunner: starting %s", act.name)

            # CHECK_PRE
            img = driver.screenshot() if act.check_pre_screenshot else None
            if not act.precondition(img, ctx):
                self._on_failure(driver, act, "precondition failed", ctx)
                raise RuntimeError(f"{act.name}: precondition failed")
            logger.debug("DosRunner: %s precondition OK", act.name)

            # ACT
            act.execute(driver, ctx)
            logger.debug("DosRunner: %s execute done", act.name)

            # SETTLE — deadline-based, no sleep in activity code
            settle_until = time.monotonic() + act.settle_ms / 1000.0
            while time.monotonic() < settle_until:
                time.sleep(_POLL_MS / 1000.0)

            # VERIFY
            if not act.verify_screenshot:
                # postcondition is trivially True; skip screenshot overhead
                if not act.postcondition(None, ctx):
                    self._on_failure(driver, act, "postcondition failed (no-screenshot path)", ctx)
                    raise RuntimeError(f"{act.name}: postcondition failed")
            else:
                verify_until = time.monotonic() + act.verify_ms / 1000.0
                while True:
                    img = driver.screenshot()
                    if act.postcondition(img, ctx):
                        logger.debug("DosRunner: %s postcondition OK", act.name)
                        break
                    if time.monotonic() >= verify_until:
                        self._on_failure(driver, act, "postcondition timed out", ctx)
                        raise RuntimeError(
                            f"{act.name}: postcondition timed out after {act.verify_ms}ms"
                        )
                    time.sleep(_POLL_MS / 1000.0)

        return ctx

    def _on_failure(self, driver: "DosBoxDriver", act: DosActivity, reason: str, ctx: dict) -> None:
        logger.error("DosRunner: %s — %s; ctx=%s", act.name, reason, ctx)
        if self._save_dir:
            try:
                ts = int(time.time())
                path = f"{self._save_dir}/{act.name}_failure_{ts}.png"
                driver.screenshot_to(path)
                logger.info("DosRunner: failure screenshot → %s", path)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Lifecycle activities
# ---------------------------------------------------------------------------

class EnsureDosBoxRunning(DosActivity):
    """Ensure DOSBox-X is running; launch it if not.

    :param process: DosBoxProcess instance (may or may not be started).
    """

    name = "EnsureDosBoxRunning"
    check_pre_screenshot = False
    verify_screenshot = False
    settle_ms = 500
    verify_ms = 20000

    def __init__(self, process: "DosBoxProcess") -> None:
        self._process = process

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """Always True — we always check / ensure running state."""
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """Launch DOSBox-X if it is not already running."""
        if not self._process.is_running:
            logger.info("EnsureDosBoxRunning: launching DOSBox-X")
            self._process.launch()
        else:
            logger.debug("EnsureDosBoxRunning: already running")

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the DOSBox-X window is visible."""
        return self._process.is_running


class FocusDosBox(DosActivity):
    """Bring the DOSBox-X window to the foreground.

    Placed before any click sequence so that pyautogui events reach the right
    window.  settle_ms provides a small wait for the OS to complete the focus
    transition before any follow-up activities issue actuations.
    """

    name = "FocusDosBox"
    check_pre_screenshot = False
    verify_screenshot = False
    settle_ms = 400

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        driver.focus()

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return True


class DismissTitleScreen(DosActivity):
    """Press ENTER to advance from the Battle Chess title/splash screen to the board.

    After a fresh DOSBox launch the game shows a splash screen; ENTER advances
    to the chess board.  ``postcondition`` verifies that the board colour
    signature is present.

    precondition: always True — used on fresh-launch paths only.
    execute: focus DOSBox, wait for title content, press ENTER twice.
    postcondition: board colour fraction ≥ threshold (delegates to EnsureBoard2D).
    """

    name = "DismissTitleScreen"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 500
    verify_ms = 20000   # board may take up to 15s to appear after ENTER

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    # Minimum board-region colour fraction that indicates some game content
    # is on screen (title screen partially loaded; above a black loading screen).
    _TITLE_MIN_FRACTION = 0.03

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """Focus DOSBox, wait for title to load, then press ENTER to advance.

        ``driver.focus()`` is called BEFORE the key presses so ENTER goes to
        DOSBox and not to whatever the user had focused — firing ENTER via
        kCGHIDEventTap without focus first was the root cause of it going to the
        wrong window when the user was typing elsewhere.

        Key code 36 = Return on macOS. First ENTER may be consumed by SDL gaining
        focus; second reliably advances Battle Chess.
        """
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            img = driver.screenshot()
            if EnsureBoard2D._board_visible(img):
                return  # already at the board — no key needed
            from Code.Dos.BattleChess import _BOARD_REGION
            import numpy as np
            bx, by, bw, bh = _BOARD_REGION
            arr = np.array(img.crop((bx, by, bx + bw, by + bh)).convert("RGB"))
            r, g, b_ch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            frac = float(
                ((r > 100) & (g > 100) & (b_ch < 80) & (r.astype(int) + g > 220)).sum()
            ) / arr.shape[0] / arr.shape[1]
            if frac >= self._TITLE_MIN_FRACTION:
                break  # title screen has loaded enough content — advance now
            time.sleep(0.5)

        # Focus MUST come before any keyboard event, otherwise ENTER goes to the
        # OS foreground window (which may be the user's terminal or editor).
        driver.focus()
        time.sleep(0.3)  # let the OS commit focus before keypresses

        import Quartz
        for _ in range(2):
            down = Quartz.CGEventCreateKeyboardEvent(None, 36, True)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            time.sleep(0.05)
            up = Quartz.CGEventCreateKeyboardEvent(None, 36, False)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            time.sleep(0.35)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return EnsureBoard2D._board_visible(img)


# ---------------------------------------------------------------------------
# Board state activities
# ---------------------------------------------------------------------------

class WaitForBoardReady(DosActivity):
    """Poll until the Battle Chess 2D board is visible (game finished loading).

    Use this immediately after :class:`EnsureDosBoxRunning` to avoid sending
    input while the title screen or intro animation is still showing.
    ``verify_ms`` defaults to 30 s which covers a cold DOSBox launch.

    precondition: always True — we are just waiting, not gating.
    execute: no-op.
    postcondition: True when the board colour signature is detected.
    """

    name = "WaitForBoardReady"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 0
    verify_ms = 30000

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        pass

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return EnsureBoard2D._board_visible(img)


class EnsureBoard2D(DosActivity):
    """Verify the board is in 2D top-down view; navigate there if not.

    CHECK_PRE: board must be visible in any mode (game has loaded).
    execute(): CHECK current mode via pixel heuristic; if 3D, right-click-hold
               the Settings menu and drag to '2D Board' to switch.
    postcondition: board-fraction heuristic confirms 2D mode.

    Menu navigation coordinates are window-relative (image y=0 at window top-
    left including macOS title bar, game content starts at y≈28).  Calibrated
    empirically on Battle Chess DOS under DOSBox-X at 640×428 window size.
    """

    name = "EnsureBoard2D"
    settle_ms = 1500   # wait for 2D switch animation to complete
    verify_ms = 10000

    # --- Pixel heuristic thresholds ---
    # Board-coloured pixel fraction over the _BOARD_REGION crop:
    #   2D mode: ~0.40  (flat grid fills the whole crop)
    #   3D mode: ~0.14  (perspective shrinks coverage; sky fills upper portion)
    #   Any board: > 0.10 (both modes; used to confirm game is at the board)
    _BOARD_MIN_FRACTION = 0.10   # "board visible in any mode" threshold
    _2D_MODE_FRACTION   = 0.25   # "definitely 2D" threshold (midpoint 0.10–0.40)

    # --- Menu navigation (window-relative pixel coordinates) ---
    # Trigger: right-click-hold 5 px below the macOS title bar activates the
    # Amiga-style pull-down menu; x=320 (centre) lands in the 'Settings' column.
    _MENU_X    = 320
    _MENU_Y    = 33    # 28 px title bar + 5 px into game content
    # '2D Board' dropdown item position (calibrated by sweep):
    _ITEM_2D_X = 410
    _ITEM_2D_Y = 180
    # Cancel position: far right, outside all menu items:
    _CANCEL_X  = 600
    _CANCEL_Y  = 33

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board is visible in any mode (game has loaded)."""
        return self._board_visible(img)

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """Switch to 2D mode if not already there.

        CHECK: pixel heuristic detects current mode.
        ACT:   right-click-hold on Settings menu → drag to '2D Board' → release.
        No-op if already in 2D.
        """
        import Quartz

        bounds = driver._process.window_bounds()
        if bounds is None:
            raise RuntimeError("EnsureBoard2D: DOSBox-X window not found")
        wx, wy, _, _ = bounds

        def _move(rx: int, ry: int) -> None:
            e = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventMouseMoved, (wx + rx, wy + ry), Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

        def _rdown(rx: int, ry: int) -> None:
            e = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventRightMouseDown, (wx + rx, wy + ry), Quartz.kCGMouseButtonRight
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

        def _rdrag(rx: int, ry: int) -> None:
            e = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventRightMouseDragged, (wx + rx, wy + ry), Quartz.kCGMouseButtonRight
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

        def _rup(rx: int, ry: int) -> None:
            e = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventRightMouseUp, (wx + rx, wy + ry), Quartz.kCGMouseButtonRight
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

        driver.focus()

        # CHECK: is the board already in 2D mode?
        current = driver.screenshot()
        if self._is_2d_mode(current):
            logger.info("EnsureBoard2D: already in 2D mode — no action needed")
            return

        # ACT: open Settings menu and navigate to '2D Board'.
        # Move cursor into game area first so SDL registers a cursor-enter event.
        _move(self._MENU_X, self._MENU_Y)
        time.sleep(0.35)

        _rdown(self._MENU_X, self._MENU_Y)
        time.sleep(0.6)   # hold — Settings dropdown appears

        _rdrag(self._ITEM_2D_X, self._ITEM_2D_Y)
        time.sleep(0.3)   # hover over '2D Board'

        _rup(self._ITEM_2D_X, self._ITEM_2D_Y)
        logger.info("EnsureBoard2D: released on '2D Board' — switch in progress")

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the 2D flat board is confirmed visible."""
        return self._is_2d_mode(img)

    @staticmethod
    def _is_2d_mode(img: "Image | None") -> bool:
        """Return True if the board is in 2D flat top-down view.

        In 2D mode the flat grid fills ~40 % of the board crop.
        In 3D mode perspective leaves only ~14 % coverage (sky above the board).
        Threshold 0.25 sits cleanly between the two.
        """
        if img is None:
            return False
        import numpy as np
        from Code.Dos.BattleChess import _BOARD_REGION
        bx, by, bw, bh = _BOARD_REGION
        arr = np.array(img.crop((bx, by, bx + bw, by + bh)).convert("RGB"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        mask = (r > 100) & (g > 100) & (b < 80) & (r.astype(int) + g > 220)
        fraction = float(mask.sum()) / max(1, arr.shape[0] * arr.shape[1])
        logger.debug("EnsureBoard2D._is_2d_mode: fraction=%.3f", fraction)
        return fraction >= EnsureBoard2D._2D_MODE_FRACTION

    @staticmethod
    def _board_visible(img: "Image | None") -> bool:
        """Return True when ANY board (2D or 3D) is visible.

        Used by precondition to confirm the game has loaded and is showing
        the board rather than a title screen or loading screen.
        Threshold 0.10 is cleared by both 2D (~0.40) and 3D (~0.14) modes.
        """
        if img is None:
            return False
        import numpy as np
        from Code.Dos.BattleChess import _BOARD_REGION
        bx, by, bw, bh = _BOARD_REGION
        arr = np.array(img.crop((bx, by, bx + bw, by + bh)).convert("RGB"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        mask = (r > 100) & (g > 100) & (b < 80) & (r.astype(int) + g > 220)
        fraction = float(mask.sum()) / max(1, arr.shape[0] * arr.shape[1])
        logger.debug("EnsureBoard2D._board_visible: fraction=%.3f", fraction)
        return fraction >= EnsureBoard2D._BOARD_MIN_FRACTION


# ---------------------------------------------------------------------------
# Move activities — two-click: SourceClick → DestClick
#
# Battle Chess 2D uses two-click move mechanics:
#   1. MOUSEMOVED to source → CLICK source   (piece selected, highlight appears)
#   2. MOUSEMOVED to dest   → CLICK dest     (piece moves to dest)
#
# The MOUSEMOVED before each click is REQUIRED — SDL ignores a click that
# arrives without a preceding cursor-enter event at that location.
#
# Timing contract:
#   SourceClick.settle_ms=400   wait for selection highlight to appear
#   DestClick.settle_ms=300     wait for move animation to start
#   DestClick.verify_ms=5000    poll for both squares to change vs baseline
# ---------------------------------------------------------------------------

class SourceClick(DosActivity):
    """Move cursor to source square and click to select the piece.

    Captures the baseline screenshot before clicking so DestClick can
    compare before/after for move verification.

    :param from_sq: Algebraic source square, e.g. ``"e2"``.
    """

    name = "SourceClick"
    check_pre_screenshot = True
    verify_screenshot = False
    settle_ms = 400   # wait for selection highlight to appear

    def __init__(self, from_sq: str) -> None:
        self.from_sq = from_sq

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """Capture baseline; always True (piece presence checked by has_piece_at)."""
        if img is None:
            return False
        ctx["baseline"] = img
        ctx["from_sq"] = self.from_sq
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """MOUSEMOVED to source, then full click (DOWN + UP)."""
        import Quartz
        import time as _t
        from Code.Dos.BattleChess import square_center
        cx, cy = square_center(self.from_sq)
        ax, ay = driver._abs(cx, cy)
        ctx["src_abs"] = (ax, ay)
        pt = Quartz.CGPoint(ax, ay)
        # Move cursor first so SDL receives cursor-enter before click
        mv = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mv)
        _t.sleep(0.2)
        down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        _t.sleep(0.08)
        up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return True


class DestClick(DosActivity):
    """Move cursor to destination square and click to complete the move.

    postcondition verifies that BOTH source and destination changed vs the
    baseline captured in SourceClick.precondition.

    :param to_sq: Algebraic destination square, e.g. ``"e4"``.
    :param from_sq: Source square (for postcondition check).
    """

    name = "DestClick"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 300
    verify_ms = 5000

    def __init__(self, to_sq: str, from_sq: str) -> None:
        self.to_sq   = to_sq
        self.from_sq = from_sq

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """MOUSEMOVED to dest, then full click (DOWN + UP)."""
        import Quartz
        import time as _t
        from Code.Dos.BattleChess import square_center
        tx, ty = square_center(self.to_sq)
        ax, ay = driver._abs(tx, ty)
        ctx["dest_abs"] = (ax, ay)
        ctx["to_sq"]    = self.to_sq
        pt = Quartz.CGPoint(ax, ay)
        mv = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mv)
        _t.sleep(0.2)
        down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        _t.sleep(0.08)
        up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when BOTH source and destination changed vs the pre-click baseline.

        inner_square_changed(baseline, img, sq) compares the inner 13×11 px core
        of sq.  A pawn leaving its square and arriving at the destination both
        produce diffs well above the default threshold of 10.
        """
        from Code.Dos.BattleChess import inner_square_changed
        baseline = ctx.get("baseline")
        from_sq  = ctx.get("from_sq", self.from_sq)
        to_sq    = ctx.get("to_sq", self.to_sq)
        if baseline is None or img is None:
            return False
        source_vacated = inner_square_changed(baseline, img, from_sq)
        dest_occupied  = inner_square_changed(baseline, img, to_sq)
        logger.debug(
            "DestClick.postcondition: source %s vacated=%s  dest %s occupied=%s",
            from_sq, source_vacated, to_sq, dest_occupied,
        )
        if source_vacated and dest_occupied:
            ctx["after_our_move"] = img
            return True
        return False


# Legacy aliases — keep old callers compiling.
SourceDragDown = SourceClick
DragToDest     = DestClick   # note: DragToDest now takes (to_sq, from_sq)
DragRelease    = DestClick
ClickDest      = DestClick
MoveToDest     = DestClick


class WaitCpuReply(DosActivity):
    """Poll until the CPU makes a move and detect it.

    precondition: True (assumes our move was already verified by ClickDest).
    execute: no-op — purely an observation step.
    postcondition: detect ≥2 squares changed vs baseline, excluding our
                   from/to squares.  Store result in ctx["cpu_move"].

    :param from_sq: Our source square (excluded from CPU-change detection).
    :param to_sq: Our destination square (excluded from CPU-change detection).
    """

    name = "WaitCpuReply"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 3000    # wait for our move's selection-highlight artefacts to decay
    verify_ms = 90000   # Battle Chess on hardest setting can take >30s

    def __init__(self, from_sq: str, to_sq: str) -> None:
        self.from_sq = from_sq
        self.to_sq = to_sq

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "DosBoxDriver", ctx: dict) -> None:
        """No actuation — we are waiting for an external event (CPU move)."""

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when CPU has moved; stores inferred move in ctx['cpu_move']."""
        from Code.Dos.BattleChess import detect_changed_squares, _infer_from_candidates

        # Prefer after_our_move as the comparison baseline — it is a stable
        # screenshot captured AFTER our move settled, so click artefacts at
        # squares adjacent to our dest (e.g. e3 beside e4) are already "baked
        # in" and won't fire as false CPU-move candidates.
        # Fall back to pre-move baseline + exclusion list when after_our_move
        # is not yet available (first poll before DestClick verified).
        ref = ctx.get("after_our_move") or ctx.get("baseline")
        if ref is None or img is None:
            return False

        changed = detect_changed_squares(ref, img)
        if ctx.get("after_our_move") is not None:
            # after_our_move already has our pieces in their new positions;
            # any changed square must be the CPU's.
            cpu_candidates = list(changed)
        else:
            cpu_candidates = [
                (s, n) for s, n in changed
                if n not in (self.from_sq, self.to_sq)
            ]
        if len(cpu_candidates) < 2:
            return False

        result = _infer_from_candidates(ref, img, cpu_candidates)
        if result is None:
            return False

        cpu_from, cpu_to = result

        # Double-check: both inferred squares must show a real inner-core change
        # vs the reference.  This mirrors the same verification used in
        # DestClick.postcondition for our own moves — it rejects false positives
        # where _infer_from_candidates picks noisy candidates that happen to
        # pass the brightness test but are not actually vacated/occupied.
        from Code.Dos.BattleChess import inner_square_changed
        if not (inner_square_changed(ref, img, cpu_from) and inner_square_changed(ref, img, cpu_to)):
            logger.debug(
                "WaitCpuReply: double-check failed for %s→%s (not both squares changed)",
                cpu_from, cpu_to,
            )
            return False

        ctx["cpu_move"] = cpu_from + cpu_to
        logger.info("WaitCpuReply: CPU played %s", ctx["cpu_move"])
        return True


# ---------------------------------------------------------------------------
# Internal Quartz helper (no time.sleep — caller's settle_ms handles timing)
# ---------------------------------------------------------------------------

def _quartz_click_abs(ax: int, ay: int) -> None:
    """Send Quartz MOUSEDOWN + MOUSEUP at absolute coordinates.

    Does NOT send a preceding MOUSEMOVE event.  The cursor must already be
    at or near (ax, ay) — use ``driver.move_to()`` first.

    The 80 ms pause between DOWN and UP matches Battle Chess's minimum
    click-registration threshold.  This is intrinsic to the click event,
    not settle time between activities.

    :param ax: Absolute screen X.
    :param ay: Absolute screen Y.
    """
    import Quartz

    pt = Quartz.CGPoint(ax, ay)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.08)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
