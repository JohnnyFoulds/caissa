"""
bin/Code/Amiga/Activities.py — RPA Activity layer for Battle Chess (Amiga) via FS-UAE.

Follows the CHECK_PRE → ACT → SETTLE → VERIFY pattern documented in
docs/rpa/state-machine.md.  Each Activity declares:

- ``check_pre_screenshot`` — whether CHECK_PRE must capture a screenshot.
  Set False when the precondition is unconditional so no screenshot is taken
  between adjacent activities (prevents excess Quartz calls).
- ``verify_screenshot``  — whether VERIFY must capture a screenshot.
  Set False when postcondition is trivially True.
- ``settle_ms`` — milliseconds to wait after execute() before first VERIFY.
- ``verify_ms`` — milliseconds to keep polling postcondition before timeout.

**Calibration note:** Activities that interact with the board (``PlayMove``,
``WaitForComputerReply``, ``ExtractComputerMove``) call helpers from
``BattleChess.py``.  Those helpers require ``_COL_X``, ``_RANK_Y``, and
``_BOARD_REGION`` to be populated.  Run the calibration procedure described in
``BattleChess.py`` before using board-touching activities against real FS-UAE.

:purity: adapter
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

    from Code.Amiga.Driver import FsUaeDriver, FsUaeProcess

logger = logging.getLogger(__name__)

_POLL_MS = 50   # ms between postcondition polls during VERIFY


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class AmigaActivity:
    """Base class for all Amiga-layer RPA activities.

    :cvar name: Display name used in logs and error messages.
    :cvar settle_ms: Wait after execute() before first postcondition call.
    :cvar verify_ms: Maximum wait for postcondition to return True.
    :cvar check_pre_screenshot: If True, AmigaRunner takes a screenshot for CHECK_PRE.
    :cvar verify_screenshot: If True, AmigaRunner takes screenshots during VERIFY.
    """

    name: str = "AmigaActivity"
    delay_before_ms: int = 0     # wait BEFORE execute() (UiPath DelayBefore)
    delay_after_ms: int = 0      # wait AFTER execute() before settle (UiPath DelayAfter)
    settle_ms: int = 200
    verify_ms: int = 5_000
    max_retries: int = 0         # re-run execute+verify this many extra times on timeout
    check_pre_screenshot: bool = True
    verify_screenshot: bool = True

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """Return True if the app is in the right state to execute.

        :param img: Current screenshot, or None if check_pre_screenshot=False.
        :param ctx: Shared context dict for passing state between activities.
        :returns: True if the activity may proceed.
        """
        raise NotImplementedError(f"{type(self).__name__}.precondition not implemented")

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Issue the driver actuation.

        Issue **one** driver action and return immediately.  Do not loop or
        sleep here — settle_ms and the VERIFY loop are the runner's job.

        :param driver: FsUaeDriver instance.
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

class AmigaRunner:
    """Sequential activity runner following CHECK_PRE → ACT → SETTLE → VERIFY.

    :param save_dir: Optional directory to write debug screenshots on failure.
    """

    def __init__(self, save_dir: str | None = None) -> None:
        self._save_dir = save_dir

    def run(
        self,
        driver: "FsUaeDriver",
        activities: list[AmigaActivity],
        ctx: dict | None = None,
    ) -> dict:
        """Execute *activities* in order.

        :param driver: FsUaeDriver to pass to each activity.
        :param activities: Activities to execute in sequence.
        :param ctx: Optional shared context dict; a fresh dict is created if None.
            Pass the same dict across multiple run() calls to share state (e.g. when
            splitting a game into per-move run() calls in a recording loop).
        :returns: Shared ctx dict populated by activities (same object as *ctx* if provided).
        :raises RuntimeError: If any precondition fails or postcondition times out.
        """
        if ctx is None:
            ctx = {}
        for act in activities:
            logger.debug("AmigaRunner: starting %s", act.name)

            # CHECK_PRE
            img = driver.screenshot() if act.check_pre_screenshot else None
            if not act.precondition(img, ctx):
                self._on_failure(driver, act, "precondition failed", ctx)
                raise RuntimeError(f"{act.name}: precondition failed")
            logger.debug("AmigaRunner: %s precondition OK", act.name)

            # ACT + VERIFY loop — retried up to max_retries times if postcondition times out.
            for attempt in range(act.max_retries + 1):
                if attempt > 0:
                    logger.warning("AmigaRunner: %s retry %d/%d", act.name, attempt, act.max_retries)

                # DELAY BEFORE (UiPath DelayBefore equivalent)
                if act.delay_before_ms > 0:
                    time.sleep(act.delay_before_ms / 1000.0)

                # ACT
                act.execute(driver, ctx)
                logger.debug("AmigaRunner: %s execute done (attempt %d)", act.name, attempt)

                # DELAY AFTER (UiPath DelayAfter equivalent)
                if act.delay_after_ms > 0:
                    time.sleep(act.delay_after_ms / 1000.0)

                # SETTLE — deadline-based
                settle_until = time.monotonic() + act.settle_ms / 1000.0
                while time.monotonic() < settle_until:
                    time.sleep(_POLL_MS / 1000.0)

                # VERIFY
                postcondition_ok = False
                if not act.verify_screenshot:
                    postcondition_ok = act.postcondition(None, ctx)
                    if not postcondition_ok and attempt >= act.max_retries:
                        self._on_failure(driver, act, "postcondition failed (no-screenshot path)", ctx)
                        raise RuntimeError(f"{act.name}: postcondition failed")
                else:
                    verify_until = time.monotonic() + act.verify_ms / 1000.0
                    while True:
                        img = driver.screenshot()
                        if act.postcondition(img, ctx):
                            postcondition_ok = True
                            logger.debug("AmigaRunner: %s postcondition OK", act.name)
                            break
                        if time.monotonic() >= verify_until:
                            if attempt >= act.max_retries:
                                self._on_failure(driver, act, "postcondition timed out", ctx)
                                raise RuntimeError(
                                    f"{act.name}: postcondition timed out after {act.verify_ms} ms"
                                )
                            break   # timeout → retry execute
                        time.sleep(_POLL_MS / 1000.0)

                if postcondition_ok:
                    break

        return ctx

    def _on_failure(
        self,
        driver: "FsUaeDriver",
        act: AmigaActivity,
        reason: str,
        ctx: dict,
    ) -> None:
        logger.error("AmigaRunner: %s — %s; ctx=%s", act.name, reason, ctx)
        if self._save_dir:
            try:
                ts = int(time.time())
                path = Path(self._save_dir) / f"{act.name}_failure_{ts}.png"
                driver.screenshot_to(path)
                logger.info("AmigaRunner: failure screenshot → %s", path)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Lifecycle activities
# ---------------------------------------------------------------------------

class EnsureFsUaeRunning(AmigaActivity):
    """Ensure FS-UAE is running; launch it if not.

    :param process: FsUaeProcess instance.
    """

    name = "EnsureFsUaeRunning"
    check_pre_screenshot = False
    verify_screenshot = False
    settle_ms = 1_000   # allow FS-UAE window to appear after launch
    verify_ms = 30_000  # cold launch can take ~20 s

    def __init__(self, process: "FsUaeProcess") -> None:
        self._process = process

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """Always True — we always check / ensure running state."""
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Launch FS-UAE if it is not already running."""
        if not self._process.is_running:
            logger.info("EnsureFsUaeRunning: launching FS-UAE")
            self._process.launch()
        else:
            logger.debug("EnsureFsUaeRunning: already running")

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the FS-UAE window is visible."""
        return self._process.is_running


# ---------------------------------------------------------------------------
# Game state activities
# ---------------------------------------------------------------------------

class LaunchBattleChessFromWorkbench(AmigaActivity):
    """Launch Battle Chess from the Amiga Workbench using two double-clicks.

    Launching requires two steps:
      1. Double-click the floppy-disk icon on the Workbench desktop — this opens
         a drawer window showing the disk contents.
      2. Double-click the BattleChess executable icon inside that window — this
         starts the game, which loads from ADF in ~15 seconds.

    precondition: Workbench is visible (brightness > 4.0).
    execute: double-click disk icon, wait for drawer to open, double-click executable.
    postcondition: title screen visible (brightness > 15, clearly game content).
    """

    name = "LaunchBattleChessFromWorkbench"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 3_000    # after execute, wait before first postcondition poll
    verify_ms = 60_000   # ADF load takes ~15s; title screen appears ~17s after launch

    # Amiga content pixels (screenshot_y − 32 px macOS title bar).
    # Calibrated 2026-08-30 with 1 icon on Workbench (BattleChess only, no ChessSaves):
    #   BattleChess disk icon centre: amiga (520, 88), screen (1160, 428).
    # NB: CGEventPost LMB does NOT reach FS-UAE on the Workbench — use
    #     workbench_double_click() (AppleScript Accessibility API) instead.
    _DISK_ICON_X = 520
    _DISK_ICON_Y = 88
    _EXEC_ICON_X = 278
    _EXEC_ICON_Y = 150

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when Workbench is visible."""
        return WaitForTitle().postcondition(img, ctx)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Open disk drawer, then launch the executable."""
        driver.workbench_double_click(self._DISK_ICON_X, self._DISK_ICON_Y)
        time.sleep(3.0)   # wait for drawer window to open
        driver.workbench_double_click(self._EXEC_ICON_X, self._EXEC_ICON_Y)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when title screen is visible (brightness > 15)."""
        if img is None:
            return False
        try:
            import numpy as np
            return float(np.array(img.convert("RGB")).mean()) > 15.0
        except Exception:  # noqa: BLE001
            return False


class WaitForTitle(AmigaActivity):
    """Wait until the Battle Chess title screen is visible.

    precondition: always True — we are only waiting.
    execute: no-op.
    postcondition: title screen colour signature detected in screenshot.

    The exact colour thresholds are set after calibration.  The placeholder
    implementation returns True if the screenshot is non-trivially dark
    (FS-UAE window has content — anything but a black screen).
    """

    name = "WaitForTitle"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 0
    verify_ms = 60_000   # title can take ~45 s to appear on slow cold launch

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Wake SDL2 mouse capture so delta navigation works."""
        driver.wake_sdl2()

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the FS-UAE window has visible content.

        Checks mean pixel brightness > 4.0 (threshold calibrated from the
        Workbench screen, which has mean ~7.5 on a mostly-black desktop).

        :param img: Screenshot from the runner.
        :param ctx: Shared context dict.
        :returns: True if content is visible.
        """
        if img is None:
            return False
        try:
            import numpy as np
            arr = np.array(img.convert("RGB"), dtype=float)
            return float(arr.mean()) > 4.0
        except Exception:  # noqa: BLE001
            return False


class WaitForBoard(AmigaActivity):
    """Wait until the Battle Chess 2D board is visible.

    precondition: always True.
    execute: no-op.
    postcondition: board colour fraction above threshold.

    The ``_BOARD_REGION`` and colour thresholds must be calibrated before
    this activity's postcondition is meaningful.  The placeholder checks
    the same brightness heuristic as ``WaitForTitle``.
    """

    name = "WaitForBoard"
    check_pre_screenshot = False
    verify_screenshot = True
    settle_ms = 0
    verify_ms = 30_000

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        pass

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board region is visible.

        Placeholder until calibration populates ``_BOARD_REGION``.
        Uses the same brightness check as ``WaitForTitle``.
        """
        return _board_visible(img)


class AdvancePastTitle(AmigaActivity):
    """Dismiss the title screen / intro to reach the main menu or board.

    execute: press Enter (macOS key code 36) twice.  Amiga Battle Chess
    advances past intros on any key; Enter is the safest choice.

    precondition: title screen must be visible.
    postcondition: board (or menu) is visible.
    """

    name = "AdvancePastTitle"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 1_000   # wait for any intro animation to complete
    verify_ms = 30_000

    # macOS virtual key code for Return
    _ENTER_KEY = 36

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the title screen has content."""
        return WaitForTitle().postcondition(img, ctx)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Send two Enter keypresses to dismiss the title / intro."""
        driver.key_code(self._ENTER_KEY)
        time.sleep(0.5)
        driver.key_code(self._ENTER_KEY)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board or menu is visible after the title was dismissed."""
        return _board_visible(img)


class AdvancePastCopyrightScreen(AmigaActivity):
    """Press Enter until the copyright/intro dialog box is gone.

    The game shows a text dialog ("Euwe -- Keres, Match 1940 ..." from the crack
    intro, or the game's own copyright screen) over the 3D board.  Pressing Enter
    dismisses it.  This activity sends Enter up to ``_MAX_PRESSES`` times with a
    short pause between each, stopping as soon as the dialog is no longer visible.

    precondition: dialog is visible (dialog box colour signature detected).
    execute: send Enter once.
    postcondition: no dialog visible.
    """

    name = "AdvancePastCopyrightScreen"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 800
    verify_ms = 5_000
    _ENTER_KEY = 36

    # Colour of the dialog box border/background (yellow/gold in the screenshot).
    # The box occupies roughly the lower-center region of the 640×432 window.
    # This region contains the dialog when it is visible.
    _DIALOG_REGION = (150, 215, 260, 65)  # x, y, w, h in window pixels (incl. title bar)
    _DIALOG_YELLOW_THRESHOLD = 0.05       # min fraction of yellow pixels = dialog present

    @classmethod
    def _dialog_visible(cls, img: "Image | None") -> bool:
        """Return True if the copyright/intro dialog box is visible."""
        if img is None:
            return False
        try:
            import numpy as np
            x, y, w, h = cls._DIALOG_REGION
            arr = np.array(img.crop((x, y, x + w, y + h)).convert("RGB"))
            r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)
            # Yellow: high R+G, low B
            yellow = ((r > 150) & (g > 120) & (b < 100)).sum()
            frac = float(yellow) / (arr.shape[0] * arr.shape[1])
            return frac >= cls._DIALOG_YELLOW_THRESHOLD
        except Exception:  # noqa: BLE001
            return False

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the dialog box is visible."""
        return _board_visible(img) and self._dialog_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Send Enter up to 10 times until the dialog is gone."""
        for _ in range(10):
            driver.key_code(self._ENTER_KEY)
            time.sleep(0.8)
            try:
                img = driver.screenshot()
                if not self._dialog_visible(img):
                    break
            except Exception:  # noqa: BLE001
                pass

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the dialog is no longer visible."""
        return not self._dialog_visible(img)


class SelectTwoDBoard(AmigaActivity):
    """Switch Battle Chess to 2D board view via the in-game RMB menu.

    Holds the right mouse button to reveal the Amiga menu bar, navigates to
    Settings, and selects "2D Board". The 2D view is required for board
    coordinate automation (the 3D perspective does not have stable square
    centres).

    precondition: board visible (any view).
    execute: RMB-hold, navigate Settings → 2D Board, release.
    postcondition: board still visible (brightness > 10).
    """

    name = "SelectTwoDBoard"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 1_500    # wait for 2D board to fully render
    verify_ms = 10_000

    # Amiga content coordinates for RMB menu navigation.
    # Start point: board centre (hold RMB here).
    _START_X = 320
    _START_Y = 220
    # Settings menu item X on the menu bar (amiga content).
    _SETTINGS_X = 327
    # Menu bar Y (amiga content).
    _MENU_BAR_Y = 8
    # "2D Board" submenu item Y (amiga content).
    _TWO_D_BOARD_Y = 122

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Hold RMB, navigate to Settings > 2D Board, release to select."""
        import Quartz

        driver._move_to_amiga(self._START_X, self._START_Y)
        time.sleep(0.2)

        pt = Quartz.CGPoint(1000.0, 400.0)

        def _rmb_drag(dx: int, dy: int) -> None:
            remaining_x, remaining_y = dx, dy
            while remaining_x != 0 or remaining_y != 0:
                sx = max(-89, min(89, remaining_x))
                sy = max(-89, min(89, remaining_y))
                send_x = (150.0 if sx > 0 else -150.0) if abs(sx) >= 89 else sx / 0.74
                send_y = (150.0 if sy > 0 else -150.0) if abs(sy) >= 89 else sy / 0.74
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight
                )
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
                remaining_x -= sx
                remaining_y -= sy

        # RMB down
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.5)

        # Move UP to menu bar
        _rmb_drag(0, -(self._START_Y - self._MENU_BAR_Y))
        time.sleep(0.2)

        # Move RIGHT to Settings header
        _rmb_drag(self._SETTINGS_X - self._START_X, 0)
        time.sleep(0.3)

        # Move DOWN to "2D Board" submenu item
        _rmb_drag(0, self._TWO_D_BOARD_Y - self._MENU_BAR_Y)
        time.sleep(0.3)

        # Release RMB to select
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)


class StartNewGame(AmigaActivity):
    """Start a new game via Disk > New Game in the RMB menu.

    Holds the right mouse button to reveal the menu bar, navigates to
    Disk, then selects "New Game".

    precondition: board visible (any game state).
    execute: RMB-hold, navigate Disk → New Game, release.
    postcondition: board visible (game reset to starting position).

    Menu coordinates (Amiga content, calibrated 2026-08-30):
      Disk header  x≈175, menu-bar y=8
      Load Game   y≈83
      Save Game   y≈96
      New Game    y≈109
    """

    name = "StartNewGame"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 4_000   # Battle Chess needs ~4s after "New Game" before accepting input
    verify_ms = 15_000

    _START_X    = 175   # x near Disk menu header
    _START_Y    = 220
    _DISK_X     = 175
    _MENU_BAR_Y = 8
    _NEW_GAME_Y = 109   # "New Game" item in Disk submenu

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Hold RMB, navigate to Disk > New Game, release."""
        import Quartz

        driver._move_to_amiga(self._START_X, self._START_Y)
        time.sleep(0.2)

        pt = Quartz.CGPoint(1000.0, 400.0)

        def _rmb_drag(dx: int, dy: int) -> None:
            remaining_x, remaining_y = dx, dy
            while remaining_x != 0 or remaining_y != 0:
                sx = max(-89, min(89, remaining_x))
                sy = max(-89, min(89, remaining_y))
                send_x = (150.0 if sx > 0 else -150.0) if abs(sx) >= 89 else sx / 0.74
                send_y = (150.0 if sy > 0 else -150.0) if abs(sy) >= 89 else sy / 0.74
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight
                )
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
                remaining_x -= sx
                remaining_y -= sy

        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.5)

        _rmb_drag(0, -(self._START_Y - self._MENU_BAR_Y))   # up to menu bar
        time.sleep(0.3)
        _rmb_drag(0, self._NEW_GAME_Y - self._MENU_BAR_Y)   # down to New Game
        time.sleep(0.3)

        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)


class _SetPlayerMode(AmigaActivity):
    """Base for player-mode menu activities (Human/Amiga Plays Red/Blue).

    Holds RMB at (320, 200) and navigates STRAIGHT UP to the menu bar —
    this enters the Settings header (x≈315-355) from below without crossing
    other headers.  Going via x=255 (lateral drag) enters the Move menu
    instead, which is wrong.

    Calibrated 2026-08-30:
      Settings header: enter straight up from x=320
      Menu bar top:    Amiga content y=0 (_MENU_BAR_Y=0)
      Human Plays Red:   cursor y=123
      Amiga Plays Red:   cursor y=136
      Modem Plays Red:   cursor y=149
      Human Plays Blue:  cursor y=162
      Amiga Plays Blue:  cursor y=175
    """

    name = "_SetPlayerMode"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 500
    verify_ms = 3_000

    _MENU_BAR_Y: int = 8   # Amiga menu bar is at y=8 in content coordinates
    # Start position — must be directly below Settings header so we enter it
    # from below without crossing Move or Disk headers.
    _START_X: int = 320
    _START_Y: int = 200
    # Y of the target menu item — overridden by subclasses.
    _ITEM_Y: int = 0

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        import Quartz

        driver._move_to_amiga(self._START_X, self._START_Y)
        time.sleep(0.2)

        pt = Quartz.CGPoint(1000.0, 400.0)

        def _rmb_drag(dx: int, dy: int) -> None:
            remaining_x, remaining_y = dx, dy
            while remaining_x != 0 or remaining_y != 0:
                sx = max(-89, min(89, remaining_x))
                sy = max(-89, min(89, remaining_y))
                send_x = (
                    (150.0 if sx > 0 else -150.0)
                    if abs(sx) >= 89
                    else (sx / 0.74 if sx != 0 else 0.0)
                )
                send_y = (
                    (150.0 if sy > 0 else -150.0)
                    if abs(sy) >= 89
                    else (sy / 0.74 if sy != 0 else 0.0)
                )
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight
                )
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
                remaining_x -= sx
                remaining_y -= sy

        # RMB down
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.5)

        # Move STRAIGHT UP to menu bar — no lateral movement, so we enter
        # Settings from directly below without sweeping through Move/Disk headers.
        _rmb_drag(0, -(self._START_Y - self._MENU_BAR_Y))
        time.sleep(0.3)

        # Move DOWN to the target item
        _rmb_drag(0, self._ITEM_Y - self._MENU_BAR_Y)
        time.sleep(0.2)

        # RMB up → selects the item
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

        # Park cursor off-board
        driver._move_to_amiga(50, 50)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)


class SetAmigaPlaysRed(_SetPlayerMode):
    """Make the Amiga (AI) play as Red (the bottom/White side).

    Must be paired with ``SetHumanPlaysBlue`` before ``StartNewGame`` to
    record a corpus game where the AI plays White.  Restore with
    ``SetHumanPlaysRed`` + ``SetAmigaPlaysBlue`` when done.

    Calibrated 2026-08-30: Settings header x=320 (straight up).
    Menu items (16px uniform spacing, confirmed from visual navigation):
      Human Plays Red:  cursor y=131
      Amiga Plays Red:  cursor y=147
      Modem Plays Red:  cursor y=163
      Human Plays Blue: cursor y=179
      Amiga Plays Blue: cursor y=195
    """

    name = "SetAmigaPlaysRed"
    _ITEM_Y = 147


class SetHumanPlaysRed(_SetPlayerMode):
    """Restore the default: human plays as Red (the bottom/White side).

    Calibrated 2026-08-30: Settings header x=320, item y=131.
    """

    name = "SetHumanPlaysRed"
    _ITEM_Y = 131


class SetHumanPlaysBlue(_SetPlayerMode):
    """Make the Human play as Blue (the top/Black side).

    Use with ``SetAmigaPlaysRed`` before ``StartNewGame`` for AI-as-White games.

    Calibrated 2026-08-30: Settings header x=320, item y=179.
    """

    name = "SetHumanPlaysBlue"
    _ITEM_Y = 179


class SetAmigaPlaysBlue(_SetPlayerMode):
    """Restore the default: Amiga (AI) plays as Blue (the top/Black side).

    Use after an AI-as-White game to return to the standard setup.

    Calibrated 2026-08-30: Settings header x=320, item y=195.
    """

    name = "SetAmigaPlaysBlue"
    _ITEM_Y = 195


class PlayMove(AmigaActivity):
    """Click a chess move on the board: from_sq → to_sq (two-click style).

    Battle Chess uses two-click move entry: click the source square to select
    the piece, then click the destination square to complete the move.  Each
    click requires a prior MOUSEMOVE event (SDL needs cursor-enter before click).

    **Requires calibration:** ``_COL_X`` and ``_RANK_Y`` in ``BattleChess.py``
    must be populated before this activity works correctly.

    :param from_sq: Source square in algebraic notation (e.g. ``"e2"``).
    :param to_sq: Destination square in algebraic notation (e.g. ``"e4"``).
    """

    name = "PlayMove"
    check_pre_screenshot = True
    verify_screenshot = True
    delay_before_ms = 500   # let any prior animation finish before we click
    delay_after_ms = 500    # let the move animation start before postcondition polling
    settle_ms = 500
    verify_ms = 8_000
    max_retries = 2          # retry full two-click sequence if piece didn't move

    def __init__(self, from_sq: str, to_sq: str) -> None:
        self._from_sq = from_sq.lower()
        self._to_sq = to_sq.lower()
        self.name = f"PlayMove({from_sq}→{to_sq})"

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board is visible.

        Also captures the baseline screenshot for postcondition comparison.

        :param img: Current screenshot.
        :param ctx: Context dict; sets ``ctx["pre_move_img"]``.
        """
        if not _board_visible(img):
            return False
        ctx["pre_move_img"] = img
        ctx["our_from_sq"] = self._from_sq
        ctx["our_to_sq"] = self._to_sq
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Click from_sq then to_sq using the two-click move sequence.

        Both clicks use driver.click() which calls home_cursor() each time.
        home_cursor() clicks the macOS title bar (y<32), re-activating SDL2
        relative mouse capture without touching Amiga game UI — so the piece
        selection from the first click survives the second home_cursor call.

        On retry, clicking from_sq again deselects (if selected) so the retry
        cycle handles stale selection without an explicit off-board click.

        :param driver: FsUaeDriver.
        :param ctx: Context dict.
        :raises ValueError: If board geometry is not calibrated.
        """
        from Code.Amiga.BattleChess import sq_center
        fx, fy = sq_center(self._from_sq)
        tx, ty = sq_center(self._to_sq)
        # First click: select source piece.
        driver.click(fx, fy)
        # Second click: complete the move.  Use full click() (with home_cursor)
        # so SDL2 relative mouse capture is re-activated before navigating to the
        # destination.  Tests confirmed the Battle Chess two-click timeout allows
        # for the ~1.5 s this takes.
        driver.click(tx, ty)
        # Wait for the move animation to start, then park cursor off-board.
        time.sleep(0.5)
        driver._move_to_amiga(50, 50)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the source square has changed (piece left).

        Compares the source square region against ``ctx["pre_move_img"]``.
        A significant pixel difference confirms the piece moved.

        :param img: Current screenshot (post-move).
        :param ctx: Must contain ``ctx["pre_move_img"]``.
        """
        if img is None or "pre_move_img" not in ctx:
            return False
        from Code.Amiga.BattleChess import sq_center, _SQ_HALF_W, _SQ_HALF_H, _TITLE_BAR_H  # type: ignore[attr-defined]
        if _SQ_HALF_W is None or _SQ_HALF_H is None:
            # Geometry not calibrated — postcondition always True in stub mode
            logger.warning("PlayMove.postcondition: geometry not calibrated, returning True")
            return True

        import numpy as np
        before = ctx["pre_move_img"]
        fx, fy = sq_center(self._from_sq)
        tx, ty = sq_center(self._to_sq)
        # _RANK_Y values are Amiga content Y; add title-bar offset for PIL crops.
        fy_s = fy + _TITLE_BAR_H
        ty_s = ty + _TITLE_BAR_H

        def _inner_changed(sq_x: int, sq_y: int) -> bool:
            # Battle Chess Amiga renders pieces at the outer ring of each square,
            # not the centre — use the full half-size, not a halved inner region.
            hw = max(1, _SQ_HALF_W)
            hh = max(1, _SQ_HALF_H)
            x0, y0 = sq_x - hw, sq_y - hh
            x1, y1 = sq_x + hw, sq_y + hh
            b = np.array(before.convert("RGB").crop((x0, y0, x1, y1)), dtype=np.int32)
            a = np.array(img.convert("RGB").crop((x0, y0, x1, y1)), dtype=np.int32)
            return float(np.abs(b - a).mean()) >= 8.0

        # Both from_sq and to_sq must have changed: piece left source, arrived at dest.
        src_vacated = _inner_changed(fx, fy_s)
        dst_occupied = _inner_changed(tx, ty_s)
        if src_vacated and dst_occupied:
            # Capture stable post-move baseline for WaitForComputerReply.
            ctx["after_our_move"] = img
            return True
        return False


class WaitForComputerReply(AmigaActivity):
    """Wait until the computer (Amiga AI) has made its move.

    Detects a board change relative to the snapshot taken after our move.

    precondition: board visible.
    execute: no-op — we wait for the AI to act.
    postcondition: a board square has changed from the post-move baseline.

    ``verify_ms = 120_000`` (2 minutes) to accommodate slow AI think times.
    After our move is confirmed, set ``ctx["after_our_move"]`` before calling
    this activity so the baseline is the stable post-our-move screenshot.
    """

    name = "WaitForComputerReply"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 3_000   # let click-highlight artefacts from our move decay
    verify_ms = 120_000

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board is visible.

        Captures the baseline if ``ctx["after_our_move"]`` is not yet set.
        """
        if not _board_visible(img):
            return False
        if "after_our_move" not in ctx:
            ctx["after_our_move"] = img
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        pass

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when a square OTHER than our own from/to has changed from pre-move state.

        Compares against ``ctx["pre_move_img"]`` (board before our move) and skips
        ``ctx["our_from_sq"]`` and ``ctx["our_to_sq"]`` so our own move does not
        trigger a false positive.  This approach handles a fast Amiga AI that responds
        before PlayMove.postcondition has a chance to capture a clean baseline.

        :param img: Current screenshot.
        :param ctx: Must contain ``ctx["pre_move_img"]``; ``our_from_sq`` / ``our_to_sq``
            are used to exclude our own squares from the comparison.
        """
        if img is None:
            return False

        baseline = ctx.get("pre_move_img") or ctx.get("after_our_move")
        if baseline is None:
            return False

        from Code.Amiga.BattleChess import all_sq_coords, _SQ_HALF_W, _SQ_HALF_H, _TITLE_BAR_H  # type: ignore[attr-defined]
        if _SQ_HALF_W is None:
            import numpy as np
            b = np.array(baseline.convert("RGB"), dtype=np.int32)
            a = np.array(img.convert("RGB"), dtype=np.int32)
            return float(np.abs(b - a).mean()) > 3.0

        our_from = ctx.get("our_from_sq")
        our_to = ctx.get("our_to_sq")

        import numpy as np
        b = np.array(baseline.convert("RGB"), dtype=np.float32)
        a = np.array(img.convert("RGB"), dtype=np.float32)

        try:
            sq_coords = all_sq_coords()
        except ValueError:
            return False

        hw = max(1, _SQ_HALF_W // 2)
        hh = max(1, _SQ_HALF_H // 2)
        for sq_name, (cx, cy) in sq_coords.items():
            if sq_name in (our_from, our_to):
                continue
            cy_s = cy + _TITLE_BAR_H
            x0, y0 = cx - hw, cy_s - hh
            x1, y1 = cx + hw, cy_s + hh
            if x1 <= x0 or y1 <= y0:
                continue
            diff = float(np.abs(b[y0:y1, x0:x1] - a[y0:y1, x0:x1]).mean())
            if diff >= 8.0:
                return True
        return False


class ExtractComputerMove(AmigaActivity):
    """Determine which squares changed to infer the computer's move.

    Compares ``ctx["after_our_move"]`` against the current screenshot.
    The two most-changed squares are the from_sq and to_sq.

    Uses the brightness-delta rule:
        positive delta (brighter after) → piece LEFT → FROM square
        negative delta (darker after)   → piece ARRIVED → TO square

    This rule was established empirically for the DOSBox version and is
    expected to apply to the Amiga version with the same board rendering.

    :postcondition: Sets ``ctx["computer_move"]`` to the UCI string (e.g. ``"c7c5"``).
    """

    name = "ExtractComputerMove"
    check_pre_screenshot = True
    verify_screenshot = False   # postcondition checks ctx, not a new screenshot
    delay_before_ms = 2_000    # let piece animation complete before capturing
    settle_ms = 0
    verify_ms = 1_000

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when a baseline exists and board is visible.

        Accepts ``pre_move_img``, ``pre_trigger_img``, or ``after_our_move`` as baseline.
        The AI-as-White flow sets ``after_our_move`` in ``WaitForComputerReply.precondition``
        rather than ``pre_move_img`` (which is set by ``PlayMove``).
        """
        has_baseline = (
            "pre_move_img" in ctx
            or "pre_trigger_img" in ctx
            or "after_our_move" in ctx
        )
        return has_baseline and _board_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Capture the post-AI-move screenshot and store it in ctx."""
        ctx["after_cpu_move"] = driver.screenshot()

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """Infer the computer move from the board diff and set ctx["computer_move"].

        :param img: Ignored (verify_screenshot=False).
        :param ctx: Must contain ``ctx["after_our_move"]`` and ``ctx["after_cpu_move"]``.
        :returns: True if a plausible UCI move was inferred.
        """
        baseline = ctx.get("pre_move_img") or ctx.get("pre_trigger_img") or ctx.get("after_our_move")
        current  = ctx.get("after_cpu_move")
        if baseline is None or current is None:
            return False
        our_from = ctx.get("our_from_sq")
        our_to = ctx.get("our_to_sq")

        from Code.Amiga.BattleChess import all_sq_coords, _SQ_HALF_W, _SQ_HALF_H  # type: ignore[attr-defined]
        if _SQ_HALF_W is None or _SQ_HALF_H is None:
            logger.warning("ExtractComputerMove: geometry not calibrated, cannot extract move")
            ctx["computer_move"] = None
            return True  # don't block the workflow; move on with None

        try:
            sq_coords = all_sq_coords()
        except ValueError:
            logger.warning("ExtractComputerMove: board not calibrated")
            ctx["computer_move"] = None
            return True

        from Code.Amiga.BattleChess import _TITLE_BAR_H  # type: ignore[attr-defined]

        import numpy as np
        b = np.array(baseline.convert("RGB"), dtype=np.float32)
        a = np.array(current.convert("RGB"), dtype=np.float32)

        # Use inner half-size crops so the pawn pixel fraction is higher → stronger signal.
        hw = max(1, _SQ_HALF_W // 2)
        hh = max(1, _SQ_HALF_H // 2)

        deltas: list[tuple[float, str]] = []
        for sq_name, (cx, cy) in sq_coords.items():
            if sq_name in (our_from, our_to):
                continue   # skip our own move's squares
            # cy is Amiga content Y; offset to screenshot coordinates for PIL crop.
            cy_s = cy + _TITLE_BAR_H
            x0 = max(0, cx - hw)
            y0 = max(0, cy_s - hh)
            x1 = min(b.shape[1], cx + hw)
            y1 = min(b.shape[0], cy_s + hh)
            if x1 <= x0 or y1 <= y0:
                continue
            # Brightness delta: positive = brighter after = piece left = FROM
            delta = float((a[y0:y1, x0:x1].mean() - b[y0:y1, x0:x1].mean()))
            if abs(delta) > 2.5:
                deltas.append((delta, sq_name))

        if len(deltas) < 2:
            logger.warning("ExtractComputerMove: fewer than 2 changed squares — AI still thinking?")
            return False

        # Most positive delta = FROM; most negative delta = TO
        deltas.sort(key=lambda t: t[0])
        to_sq   = deltas[0][1]   # most negative (darkened = piece arrived)
        from_sq = deltas[-1][1]  # most positive (brightened = piece left)
        move = f"{from_sq}{to_sq}"
        ctx["computer_move"] = move
        ctx.setdefault("computer_moves", []).append(move)
        logger.info("ExtractComputerMove: inferred move %s", move)
        return True


class TriggerComputerMove(AmigaActivity):
    """Make the computer play the current side's move via the Move menu.

    Use this when you want the AI to play as White: call it after ``StartNewGame``
    before playing any human move.  The AI will choose and execute a White opening
    move; ``ExtractComputerMove`` then reads it from the board diff vs startpos.

    precondition: board visible (game started, no move played yet).
    execute: open Move menu (RMB hold), navigate to the "Computer Plays" item, release.
    postcondition: board changed from the pre-trigger baseline (AI made a move).

    **Calibration required** — ``_MOVE_X`` and ``_COMPUTER_PLAYS_Y`` must be
    measured from a real FS-UAE screenshot of the Move menu before this activity
    works.  Take a screenshot with RMB held, identify the "Computer plays" item's
    Y coordinate, and update these constants.
    """

    name = "TriggerComputerMove"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 1_000
    verify_ms = 60_000   # AI may think for up to 60 s

    # Amiga content coordinates for Move menu navigation (calibrated 2026-08-30).
    # Move header is at x≈235-255; enter STRAIGHT UP from directly below.
    # Move menu items (cursor y, Amiga content):
    #   Force Move:   y≈90   — make computer play current side immediately
    #   Take Back:    y≈102
    #   Replay:       y≈115
    #   Suggest Move: y≈127
    _START_X = 240
    _START_Y = 220
    _MENU_BAR_Y = 8
    _FORCE_MOVE_Y = 90   # "Force Move" item y in Amiga content; spacing same as Settings items

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when board is visible; captures baseline for postcondition."""
        if not _board_visible(img):
            return False
        ctx["pre_trigger_img"] = img
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Hold RMB, navigate to Move > Computer Plays, release."""
        import Quartz

        driver._move_to_amiga(self._START_X, self._START_Y)
        time.sleep(0.2)

        pt = Quartz.CGPoint(1000.0, 400.0)

        def _rmb_drag(dx: int, dy: int) -> None:
            remaining_x, remaining_y = dx, dy
            while remaining_x != 0 or remaining_y != 0:
                sx = max(-89, min(89, remaining_x))
                sy = max(-89, min(89, remaining_y))
                send_x = (150.0 if sx > 0 else -150.0) if abs(sx) >= 89 else sx / 0.74
                send_y = (150.0 if sy > 0 else -150.0) if abs(sy) >= 89 else sy / 0.74
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight
                )
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
                Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
                remaining_x -= sx
                remaining_y -= sy

        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.5)

        _rmb_drag(0, -(self._START_Y - self._MENU_BAR_Y))   # straight up to menu bar
        time.sleep(0.3)
        _rmb_drag(0, self._FORCE_MOVE_Y - self._MENU_BAR_Y) # down to Force Move
        time.sleep(0.3)

        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the board has changed from the pre-trigger baseline."""
        baseline = ctx.get("pre_trigger_img")
        if img is None or baseline is None:
            return False
        from Code.Amiga.BattleChess import _BOARD_REGION, _TITLE_BAR_H  # type: ignore[attr-defined]
        if _BOARD_REGION is None:
            import numpy as np
            b = np.array(baseline.convert("RGB"), dtype=np.int32)
            a = np.array(img.convert("RGB"), dtype=np.int32)
            return float(np.abs(b - a).mean()) > 3.0
        bx, by, bw, bh = _BOARD_REGION
        by_s = by + _TITLE_BAR_H
        import numpy as np
        b_crop = np.array(baseline.convert("RGB").crop((bx, by_s, bx + bw, by_s + bh)), dtype=np.int32)
        a_crop = np.array(img.convert("RGB").crop((bx, by_s, bx + bw, by_s + bh)), dtype=np.int32)
        return float(np.abs(b_crop - a_crop).mean()) > 3.0


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _board_visible(img: "Image | None") -> bool:
    """Return True if the image shows visible content (non-black screen).

    Placeholder until board geometry is calibrated and a colour-fraction
    check can be implemented.  Checks mean brightness > 10.

    :param img: Screenshot to inspect, or None.
    :returns: True if content is visible.
    """
    if img is None:
        return False
    try:
        import numpy as np
        arr = np.array(img.convert("RGB"), dtype=float)
        return float(arr.mean()) > 10.0
    except Exception:  # noqa: BLE001
        return False
