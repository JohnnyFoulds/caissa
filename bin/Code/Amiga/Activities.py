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
    settle_ms: int = 200
    verify_ms: int = 5_000
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

    def run(self, driver: "FsUaeDriver", activities: list[AmigaActivity]) -> dict:
        """Execute *activities* in order.

        :param driver: FsUaeDriver to pass to each activity.
        :param activities: Activities to execute in sequence.
        :returns: Shared ctx dict populated by activities.
        :raises RuntimeError: If any precondition fails or postcondition times out.
        """
        ctx: dict = {}
        for act in activities:
            logger.debug("AmigaRunner: starting %s", act.name)

            # CHECK_PRE
            img = driver.screenshot() if act.check_pre_screenshot else None
            if not act.precondition(img, ctx):
                self._on_failure(driver, act, "precondition failed", ctx)
                raise RuntimeError(f"{act.name}: precondition failed")
            logger.debug("AmigaRunner: %s precondition OK", act.name)

            # ACT
            act.execute(driver, ctx)
            logger.debug("AmigaRunner: %s execute done", act.name)

            # SETTLE — deadline-based
            settle_until = time.monotonic() + act.settle_ms / 1000.0
            while time.monotonic() < settle_until:
                time.sleep(_POLL_MS / 1000.0)

            # VERIFY
            if not act.verify_screenshot:
                if not act.postcondition(None, ctx):
                    self._on_failure(driver, act, "postcondition failed (no-screenshot path)", ctx)
                    raise RuntimeError(f"{act.name}: postcondition failed")
            else:
                verify_until = time.monotonic() + act.verify_ms / 1000.0
                while True:
                    img = driver.screenshot()
                    if act.postcondition(img, ctx):
                        logger.debug("AmigaRunner: %s postcondition OK", act.name)
                        break
                    if time.monotonic() >= verify_until:
                        self._on_failure(driver, act, "postcondition timed out", ctx)
                        raise RuntimeError(
                            f"{act.name}: postcondition timed out after {act.verify_ms} ms"
                        )
                    time.sleep(_POLL_MS / 1000.0)

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
    """Double-click the BattleChess disk icon in Amiga Workbench to launch the game.

    precondition: FS-UAE window has visible content (Workbench screen showing).
    execute: double-click at the BattleChess icon position.
    postcondition: screen brightness increases as the game loads (brightness > 10).

    Coordinates are Amiga content pixels (screenshot coords minus 32px title bar).
    ``double_click()`` now uses cursor detection + single-event delta, so these are
    the true target pixels, not walk-function units.
    """

    name = "LaunchBattleChessFromWorkbench"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 2_000    # wait for game to start loading
    verify_ms = 30_000   # game can take up to ~20s to load from ADF

    # Icon centre in Amiga content pixels (screenshot_y − 32px title bar).
    # Measured 2026-08-30 at window size 640×432.
    _ICON_X = 516
    _ICON_Y = 56

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when Workbench is visible (any content on screen)."""
        return WaitForTitle().postcondition(img, ctx)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Double-click the BattleChess disk icon."""
        driver.double_click(self._ICON_X, self._ICON_Y)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when game content is loading (brightness > 10).

        The Workbench screen has mean brightness ~7.5; the game loading screen
        is brighter (crack intro or game title).
        """
        if img is None:
            return False
        try:
            import numpy as np
            arr = np.array(img.convert("RGB"), dtype=float)
            return float(arr.mean()) > 10.0
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
        pass

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


class StartNewGame(AmigaActivity):
    """Trigger a new game from the demo board by clicking the centre of the board.

    After the copyright/intro has been dismissed, the game shows the 3D board
    in demo/attract mode.  A left-mouse-button click on the board starts a new
    game and brings up the game-setup dialog.

    precondition: board visible AND no dialog visible (demo state).
    execute: left-click at board centre using delta navigation.
    postcondition: board visible (game continues — may need further activities
        to navigate game-setup dialogs).

    **Board centre (window-relative, Amiga content):**
    Amiga 3D board occupies approximately the full 640×400 content area.
    Centre ≈ (320, 220) after the 32 px macOS title bar.
    """

    name = "StartNewGame"
    check_pre_screenshot = True
    verify_screenshot = True
    settle_ms = 2_000   # wait for game-start dialog/animation
    verify_ms = 15_000

    # Window-relative coordinates of board centre (including macOS title bar offset)
    _BOARD_CENTER_X = 320
    _BOARD_CENTER_Y = 220   # 32 px title bar + ~188 px into Amiga content

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img) and not AdvancePastCopyrightScreen._dialog_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Click the board centre to trigger the new-game dialog."""
        driver.click(self._BOARD_CENTER_X, self._BOARD_CENTER_Y)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        return _board_visible(img)


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
    settle_ms = 400     # wait for move animation to start
    verify_ms = 5_000   # move should register quickly

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
        return True

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Click from_sq then to_sq using the two-click move sequence.

        :param driver: FsUaeDriver.
        :param ctx: Context dict.
        :raises ValueError: If board geometry is not calibrated.
        """
        from Code.Amiga.BattleChess import sq_center
        fx, fy = sq_center(self._from_sq)
        tx, ty = sq_center(self._to_sq)
        # First click: select source piece
        driver.click(fx, fy)
        time.sleep(0.4)
        # Second click: move to destination
        driver.click(tx, ty)

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when the source square has changed (piece left).

        Compares the source square region against ``ctx["pre_move_img"]``.
        A significant pixel difference confirms the piece moved.

        :param img: Current screenshot (post-move).
        :param ctx: Must contain ``ctx["pre_move_img"]``.
        """
        if img is None or "pre_move_img" not in ctx:
            return False
        from Code.Amiga.BattleChess import sq_center, _SQ_HALF_W, _SQ_HALF_H  # type: ignore[attr-defined]
        if _SQ_HALF_W is None or _SQ_HALF_H is None:
            # Geometry not calibrated — postcondition always True in stub mode
            logger.warning("PlayMove.postcondition: geometry not calibrated, returning True")
            return True

        import numpy as np
        before = ctx["pre_move_img"]
        fx, fy = sq_center(self._from_sq)

        # Crop the source square from before and after
        x0, y0 = max(0, fx - _SQ_HALF_W), max(0, fy - _SQ_HALF_H)
        x1, y1 = fx + _SQ_HALF_W, fy + _SQ_HALF_H
        b = np.array(before.convert("RGB").crop((x0, y0, x1, y1)), dtype=np.int32)
        a = np.array(img.convert("RGB").crop((x0, y0, x1, y1)), dtype=np.int32)
        diff = float(np.abs(b - a).mean())
        return diff > 5.0


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
        """True when any square has changed significantly from the baseline.

        :param img: Current screenshot.
        :param ctx: Must contain ``ctx["after_our_move"]`` baseline.
        """
        if img is None:
            return False
        baseline = ctx.get("after_our_move")
        if baseline is None:
            return False

        from Code.Amiga.BattleChess import _BOARD_REGION, _SQ_HALF_W, _SQ_HALF_H  # type: ignore[attr-defined]
        if _BOARD_REGION is None:
            # Not calibrated: fall back to full-image diff
            import numpy as np
            b = np.array(baseline.convert("RGB"), dtype=np.int32)
            a = np.array(img.convert("RGB"), dtype=np.int32)
            return float(np.abs(b - a).mean()) > 3.0

        # Calibrated path: restrict diff to board region
        bx, by, bw, bh = _BOARD_REGION
        import numpy as np
        b_crop = np.array(baseline.convert("RGB").crop((bx, by, bx + bw, by + bh)), dtype=np.int32)
        a_crop = np.array(img.convert("RGB").crop((bx, by, bx + bw, by + bh)), dtype=np.int32)
        return float(np.abs(b_crop - a_crop).mean()) > 3.0


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
    settle_ms = 0
    verify_ms = 1_000

    def precondition(self, img: "Image | None", ctx: dict) -> bool:
        """True when a baseline exists and the board is visible."""
        return "after_our_move" in ctx and _board_visible(img)

    def execute(self, driver: "FsUaeDriver", ctx: dict) -> None:
        """Capture the post-AI-move screenshot and store it in ctx."""
        ctx["after_cpu_move"] = driver.screenshot()

    def postcondition(self, img: "Image | None", ctx: dict) -> bool:
        """Infer the computer move from the board diff and set ctx["computer_move"].

        :param img: Ignored (verify_screenshot=False).
        :param ctx: Must contain ``ctx["after_our_move"]`` and ``ctx["after_cpu_move"]``.
        :returns: True if a plausible UCI move was inferred.
        """
        baseline = ctx.get("after_our_move")
        current  = ctx.get("after_cpu_move")
        if baseline is None or current is None:
            return False

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

        import numpy as np
        b = np.array(baseline.convert("RGB"), dtype=np.float32)
        a = np.array(current.convert("RGB"), dtype=np.float32)

        deltas: list[tuple[float, str]] = []
        for sq_name, (cx, cy) in sq_coords.items():
            x0 = max(0, cx - _SQ_HALF_W)
            y0 = max(0, cy - _SQ_HALF_H)
            x1 = min(b.shape[1], cx + _SQ_HALF_W)
            y1 = min(b.shape[0], cy + _SQ_HALF_H)
            if x1 <= x0 or y1 <= y0:
                continue
            # Brightness delta: positive = brighter after = piece left = FROM
            delta = float((a[y0:y1, x0:x1].mean() - b[y0:y1, x0:x1].mean()))
            if abs(delta) > 3.0:
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
        logger.info("ExtractComputerMove: inferred move %s", move)
        return True


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
