"""
bin/Code/Amiga/Driver.py — Input and screenshot driver for an FS-UAE window.

Wraps an :class:`FsUaeProcess` and provides:

- ``screenshot()`` — capture the FS-UAE window as a PIL Image
- ``screenshot_to(path)`` — save to file
- ``focus()`` — bring the window to the foreground
- ``click(x, y)`` — left-click at window-relative pixel coordinates
- ``move_to(x, y)`` — move the mouse to window-relative coordinates (one Quartz event)
- ``mousedown(x, y)`` / ``mouseup(x, y)`` — press/release without click
- ``key(name)`` — send a named key press (pyautogui names, e.g. "enter", "esc", "f1")
- ``key_code(keycode)`` — send a raw macOS virtual key code via Quartz
- ``calibrate(path)`` — take a screenshot and save it; used during calibration

All coordinates passed to public methods are **window-relative** (top-left of the
FS-UAE window = 0, 0).  The driver converts them to absolute screen coordinates
before actuation.

See also ``bin/Code/Dos/Driver.py`` — this module is structurally identical; the only
differences are the window-owner name (``"FS-UAE"`` vs ``"DOSBox-X"``) and the
absence of OCR helpers (those are deferred to a future phase).

:purity: adapter
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)

_SETTLE_S = 0.15   # seconds to pause after each input action
_FOCUS_S  = 0.30   # seconds to wait after focus() before clicking (FS-UAE is faster to focus)

# FS-UAE window owner name as reported by Quartz CGWindowListCopyWindowInfo.
_WINDOW_OWNER = "fs-uae"


class FsUaeProcess:
    """Minimal process proxy for an already-running FS-UAE instance.

    Unlike :class:`~Code.Dos.Process.DosBoxProcess`, this class does not manage
    process lifecycle; FS-UAE is launched externally (or via a subprocess call in
    :class:`~Code.Amiga.Activities.EnsureFsUaeRunning`).  It provides the window
    lookup methods used by :class:`FsUaeDriver`.

    :param config_path: Path to the FS-UAE ``.fs-uae`` configuration file.
    :param bin_path: Path to the ``fs-uae`` binary; default ``/opt/homebrew/bin/fs-uae``.
    """

    _FS_UAE_DEFAULT_BIN = Path("/opt/homebrew/bin/fs-uae")

    def __init__(
        self,
        config_path: str | Path,
        bin_path: str | Path | None = None,
    ) -> None:
        self._config_path = Path(config_path)
        self._bin_path = Path(bin_path) if bin_path else self._FS_UAE_DEFAULT_BIN
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def launch(self) -> None:
        """Start FS-UAE with the configured config file.

        :raises FileNotFoundError: If the binary or config file is missing.
        :raises RuntimeError: If FS-UAE is already running.
        """
        if self.is_running:
            raise RuntimeError("FS-UAE is already running")
        if not self._bin_path.exists():
            raise FileNotFoundError(f"FS-UAE binary not found: {self._bin_path}")
        if not self._config_path.exists():
            raise FileNotFoundError(f"FS-UAE config not found: {self._config_path}")
        logger.info("FsUaeProcess: launching %s", self._bin_path)
        self._proc = subprocess.Popen(
            [str(self._bin_path), str(self._config_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        """Terminate the FS-UAE process if we launched it."""
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    @property
    def is_running(self) -> bool:
        """True if FS-UAE is running (detected by window presence)."""
        return self.window_number() is not None

    # ------------------------------------------------------------------
    # Window lookup (Quartz)
    # ------------------------------------------------------------------

    def window_number(self) -> int | None:
        """Return the Quartz window number of the FS-UAE window, or None.

        :returns: Quartz ``kCGWindowNumber``, or ``None`` if no FS-UAE window is found.
        """
        try:
            import Quartz
        except ImportError:
            logger.warning("Quartz not available; window_number returns None")
            return None

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        best_wid: int | None = None
        best_area = 0
        for w in wins:
            if w.get("kCGWindowOwnerName", "") != _WINDOW_OWNER:
                continue
            layer = w.get("kCGWindowLayer", -1)
            if layer != 0:
                continue
            bounds = w.get("kCGWindowBounds", {})
            width  = int(bounds.get("Width",  0))
            height = int(bounds.get("Height", 0))
            if width < 100 or height < 100:
                continue  # skip SDL overlay rows and tiny helpers
            area = width * height
            if area > best_area:
                best_area = area
                best_wid = w.get("kCGWindowNumber")
        return best_wid

    def window_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (x, y, width, height) of the FS-UAE window in screen coordinates.

        :returns: ``(x, y, w, h)`` or ``None`` if the window is not found.
        """
        try:
            import Quartz
        except ImportError:
            return None

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        best: tuple[int, int, int, int] | None = None
        best_area = 0
        for w in wins:
            if w.get("kCGWindowOwnerName", "") != _WINDOW_OWNER:
                continue
            layer = w.get("kCGWindowLayer", -1)
            if layer != 0:
                continue
            bounds = w.get("kCGWindowBounds", {})
            x = int(bounds.get("X", 0))
            y = int(bounds.get("Y", 0))
            width  = int(bounds.get("Width",  0))
            height = int(bounds.get("Height", 0))
            if width < 100 or height < 100:
                continue
            area = width * height
            if area > best_area:
                best_area = area
                best = x, y, width, height
        return best

    def focus(self) -> None:
        """Bring the FS-UAE window to the foreground via NSRunningApplication.

        :raises RuntimeError: If the FS-UAE window cannot be found.
        """
        try:
            import Quartz
            from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
        except ImportError:
            logger.warning("AppKit not available; focus() is a no-op")
            return

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        pid = None
        for w in wins:
            if w.get("kCGWindowOwnerName", "") == _WINDOW_OWNER:
                pid = w.get("kCGWindowOwnerPID")
                break
        if pid is None:
            raise RuntimeError("FS-UAE window not found for focus()")
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)


class FsUaeDriver:
    """Input and screenshot driver for a running FS-UAE window.

    :param process: An :class:`FsUaeProcess` instance (started or not yet started).
    """

    def __init__(self, process: FsUaeProcess) -> None:
        self._process = process
        self._sdl2_awake: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bounds(self) -> tuple[int, int, int, int]:
        bounds = self._process.window_bounds()
        if bounds is None:
            raise RuntimeError("FS-UAE window not found")
        return bounds

    def _abs(self, rel_x: int, rel_y: int) -> tuple[int, int]:
        """Convert window-relative coords to absolute screen coords."""
        x, y, _w, _h = self._bounds()
        return x + rel_x, y + rel_y

    def _wid(self) -> int:
        wid = self._process.window_number()
        if wid is None:
            raise RuntimeError("FS-UAE window ID not found")
        return wid

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def screenshot(self) -> "Image":
        """Capture the FS-UAE window and return a PIL Image.

        Uses ``screencapture -l <wid>`` with ``-o`` to strip the macOS drop-shadow,
        so (0, 0) maps exactly to the window top-left.

        :returns: PIL Image of the current FS-UAE window.
        :raises RuntimeError: If the FS-UAE window is not found.
        """
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        subprocess.run(
            ["screencapture", "-x", "-o", "-l", str(self._wid()), path],
            check=True,
        )
        img = Image.open(path)
        img.load()
        Path(path).unlink(missing_ok=True)
        return img

    def screenshot_to(self, path: str | Path) -> None:
        """Capture the FS-UAE window and save to *path* (PNG).

        :param path: Destination file path.
        """
        subprocess.run(
            ["screencapture", "-x", "-o", "-l", str(self._wid()), str(path)],
            check=True,
        )

    def calibrate(self, path: str | Path = "UserData/Retro/fsuae_calibration.png") -> "Image":
        """Take a screenshot, save it for calibration measurement, and return it.

        Call this once with FS-UAE running to produce the reference image from which
        board coordinates are measured.  Coordinates are then committed to
        ``BattleChess.py`` and ``CLAUDE.md``.

        :param path: Where to save the calibration image.
        :returns: PIL Image.
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img = self.screenshot()
        img.save(str(save_path))
        logger.info("FsUaeDriver: calibration screenshot saved → %s", save_path)
        return img

    # ------------------------------------------------------------------
    # Focus
    # ------------------------------------------------------------------

    def focus(self) -> None:
        """Bring the FS-UAE window to the foreground and wait briefly."""
        self._process.focus()
        time.sleep(_FOCUS_S)

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def move_to(self, rel_x: int, rel_y: int) -> None:
        """Move the mouse to window-relative coordinates (one Quartz MOUSEMOVE event).

        .. note::
            FS-UAE/SDL2 runs in **relative mouse mode** — absolute screen coordinates
            are ignored.  Use :meth:`move_delta` to move the cursor inside the emulator.
            This method is kept for compatibility with code that calls it before
            switching to delta-based navigation.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import Quartz

        ax, ay = self._abs(rel_x, rel_y)
        pt = Quartz.CGPoint(ax, ay)
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def move_delta(self, dx: int, dy: int) -> None:
        """Send a relative mouse-movement delta to SDL2.

        FS-UAE runs SDL2 in **relative mouse mode**: the Amiga cursor tracks delta
        movements, not absolute screen positions.  Use this instead of
        :meth:`move_to` for any cursor navigation inside the emulator.

        Calibration from live testing (2026-08-30):
        - Small deltas (≤200 per step): ~2× scale  (send 200 → ~100 Amiga px)
        - Larger deltas (400–600 per step): ~4.6× scale
        - Very large deltas (≥1000): heavily attenuated by macOS acceleration
        - Y scale: approximately 1.0 (1:1 send→image px for small steps)

        :param dx: Horizontal delta in Quartz units (positive = right).
        :param dy: Vertical delta in Quartz units (positive = down).
        """
        import Quartz

        self.focus()
        pt = Quartz.CGPoint(1000.0, 400.0)  # absolute pt is irrelevant in relative mode
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
        Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, float(dx))
        Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, float(dy))
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(_SETTLE_S)

    # ---------------------------------------------------------------------------
    # Calibrated cursor movement constants (measured 2026-08-30)
    #
    # SDL2 relative-mouse-mode physics on this machine:
    #  - Each kCGEventMouseMoved event moves the Amiga cursor at most _X_STEP_PX
    #    pixels in X, regardless of the send value once above _X_FULL_SEND.
    #  - Small deltas (send ≤ _X_SMALL_MAX) follow a linear scale: _X_SMALL_SCALE.
    #  - Y behaves identically to X.
    #  - After home_cursor(), the Amiga cursor is at (_HOME_X, _HOME_Y).
    #  - On a FRESH FS-UAE launch (no prior interaction), delta events do nothing
    #    until SDL2 mouse capture is activated. home_cursor() handles this by
    #    sending a click to the macOS title bar first.
    # ---------------------------------------------------------------------------
    _HOME_X       = 71    # amiga content X after home_cursor() — calibrated 2026-08-30
    _HOME_Y       = 21    # amiga content Y after home_cursor() — calibrated 2026-08-30
    _X_STEP_PX    = 89    # amiga pixels moved per full event (send ≥ _X_FULL_SEND)
    _X_FULL_SEND  = 150   # send value that saturates to _X_STEP_PX
    _X_SMALL_SCALE = 0.74  # amiga px per send unit for small deltas (send ≤ 100)
    _TITLE_BAR_H  = 32    # macOS title bar height in the window screenshot

    def _amiga_to_screen(self, rel_x: int, rel_y: int) -> "Quartz.CGPoint":
        """Convert Amiga content coordinates to macOS screen coordinates.

        Used for LMB button events so the click lands at the correct position
        in both SDL2 relative mode (where internal cursor position determines
        the click) and SDL2 absolute mode (where the event screen position is
        used directly).

        :param rel_x: Target X in Amiga content pixels.
        :param rel_y: Target Y in Amiga content pixels.
        :returns: Screen-space CGPoint for use in Quartz mouse events.
        """
        import Quartz
        bounds = self._process.window_bounds()
        if bounds is not None:
            win_x, win_y, _w, _h = bounds
            return Quartz.CGPoint(
                float(win_x + rel_x),
                float(win_y + self._TITLE_BAR_H + rel_y),
            )
        return Quartz.CGPoint(1000.0, 400.0)

    def wake_sdl2(self) -> None:
        """Activate SDL2 mouse capture by clicking the macOS title bar once.

        On a fresh FS-UAE launch, SDL2 ignores all HID delta events until
        mouse capture is activated.  Clicking the macOS title bar (y < 32)
        triggers capture without sending any input to the Amiga.

        Call this once after the game is visible.  Subsequent calls are no-ops.
        """
        if self._sdl2_awake:
            return
        import Quartz

        self.focus()
        bounds = self._process.window_bounds()
        if bounds is not None:
            win_x, win_y, win_w, _ = bounds
            pt_title = Quartz.CGPoint(win_x + win_w // 2, win_y + 15)
            for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
                ev = Quartz.CGEventCreateMouseEvent(
                    None, ev_type, pt_title, Quartz.kCGMouseButtonLeft
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
            time.sleep(0.2)
            self.focus()
        self._sdl2_awake = True

    def home_cursor(self) -> None:
        """Clamp the Amiga cursor to the top-left corner.

        Clicks the macOS title bar to (re-)activate SDL2 relative mouse capture,
        then sends ten (−200, −200) delta events to push the cursor to the
        top-left corner.  After this call the cursor is reliably at amiga content
        (_HOME_X, _HOME_Y).

        The title-bar click is safe to repeat — it does not interact with Amiga UI.
        It is required every call because focus can move to another app between
        test steps, which causes SDL2 to silently drop relative-mouse events.
        """
        import Quartz

        self.focus()
        # Click the macOS title bar to re-activate SDL2 relative mouse capture.
        bounds = self._process.window_bounds()
        if bounds is not None:
            win_x, win_y, win_w, _ = bounds
            pt_title = Quartz.CGPoint(win_x + win_w // 2, win_y + 15)
            for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
                ev = Quartz.CGEventCreateMouseEvent(
                    None, ev_type, pt_title, Quartz.kCGMouseButtonLeft
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)
            time.sleep(0.15)
            self.focus()
        # Push cursor to top-left with ten strong negative steps.
        pt = Quartz.CGPoint(1000.0, 400.0)
        for _ in range(10):
            ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, -200.0)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, -200.0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)

    def _cursor_pos(self, img: "Image") -> "tuple[int, int] | None":
        """Detect the Amiga cursor tip position in screenshot coordinates.

        Finds the top-most red pixel cluster in the screenshot (the cursor tip of
        the FS-UAE cursor arrow, which appears red).

        :param img: Screenshot PIL Image.
        :returns: ``(x, y)`` in screenshot pixels (including macOS title bar),
            or ``None`` if fewer than 3 red pixels found.
        """
        try:
            import numpy as np
            arr = np.array(img.convert("RGB"))
            # FS-UAE cursor: R>150, G<100, B<100
            mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)
            ys, xs = np.where(mask)
            if len(xs) < 3:
                return None
            top_idx = int(np.argmin(ys))
            return int(xs[top_idx]), int(ys[top_idx])
        except Exception:  # noqa: BLE001
            return None

    def _move_to_amiga(self, amiga_x: int, amiga_y: int) -> None:
        """Move the Amiga cursor to (*amiga_x*, *amiga_y*) using calibrated fixed steps.

        Both X and Y cap at ``_X_STEP_PX`` (89 px) per event.  Each event moves
        up to 89 px on each axis simultaneously.  The loop runs until both
        remaining X and Y reach zero — typically 2–5 events.

        :param amiga_x: Target X in Amiga content pixels (excluding title bar).
        :param amiga_y: Target Y in Amiga content pixels (excluding title bar).
        """
        import Quartz

        self.focus()
        self.home_cursor()
        time.sleep(0.1)

        remaining_x = amiga_x - self._HOME_X
        remaining_y = amiga_y - self._HOME_Y

        pt = Quartz.CGPoint(1000.0, 400.0)

        # Maximum small-step size: keep send ≤ 100 (linear scale zone).
        # send > 100 undershoots non-linearly; split larger remainders into
        # multiple events of ≤ _X_SMALL_MAX each.
        _X_SMALL_MAX = int(self._X_SMALL_SCALE * 100)  # 74 px

        while remaining_x != 0 or remaining_y != 0:
            step_x = max(-self._X_STEP_PX, min(self._X_STEP_PX, remaining_x))
            step_y = max(-self._X_STEP_PX, min(self._X_STEP_PX, remaining_y))

            # Cap small steps at _X_SMALL_MAX to avoid the transition zone.
            if 0 < abs(step_x) < self._X_STEP_PX and abs(step_x) > _X_SMALL_MAX:
                step_x = _X_SMALL_MAX if step_x > 0 else -_X_SMALL_MAX
            if 0 < abs(step_y) < self._X_STEP_PX and abs(step_y) > _X_SMALL_MAX:
                step_y = _X_SMALL_MAX if step_y > 0 else -_X_SMALL_MAX

            if abs(step_x) >= self._X_STEP_PX:
                send_x = float(self._X_FULL_SEND) if step_x > 0 else float(-self._X_FULL_SEND)
            else:
                send_x = step_x / self._X_SMALL_SCALE

            if abs(step_y) >= self._X_STEP_PX:
                send_y = float(self._X_FULL_SEND) if step_y > 0 else float(-self._X_FULL_SEND)
            else:
                send_y = step_y / self._X_SMALL_SCALE

            ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)

            remaining_x -= step_x
            remaining_y -= step_y

        logger.debug("_move_to_amiga: target(%d,%d) done", amiga_x, amiga_y)

    def _click_from_known(self, from_x: int, from_y: int, to_x: int, to_y: int) -> None:
        """Navigate from a known Amiga cursor position to (*to_x*, *to_y*) and left-click.

        Unlike :meth:`click`, this method does **not** call :meth:`home_cursor` first —
        it navigates using relative deltas from (*from_x*, *from_y*).  Use this when
        the cursor is known to be at (*from_x*, *from_y*) and homing would disrupt game
        state (e.g. the two-click chess move between source and destination squares).

        :param from_x: Known current Amiga cursor X.
        :param from_y: Known current Amiga cursor Y.
        :param to_x: Target Amiga cursor X.
        :param to_y: Target Amiga cursor Y.
        """
        import Quartz

        self.focus()
        remaining_x = to_x - from_x
        remaining_y = to_y - from_y
        pt = Quartz.CGPoint(1000.0, 400.0)

        while remaining_x != 0 or remaining_y != 0:
            step_x = max(-self._X_STEP_PX, min(self._X_STEP_PX, remaining_x))
            step_y = max(-self._X_STEP_PX, min(self._X_STEP_PX, remaining_y))
            send_x = (
                float(self._X_FULL_SEND if step_x > 0 else -self._X_FULL_SEND)
                if abs(step_x) >= self._X_STEP_PX
                else (step_x / self._X_SMALL_SCALE if step_x != 0 else 0.0)
            )
            send_y = (
                float(self._X_FULL_SEND if step_y > 0 else -self._X_FULL_SEND)
                if abs(step_y) >= self._X_STEP_PX
                else (step_y / self._X_SMALL_SCALE if step_y != 0 else 0.0)
            )
            ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
            Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)
            remaining_x -= step_x
            remaining_y -= step_y

        # Let SDL2 settle the cursor position before we click.
        time.sleep(0.15)
        pt_click = self._amiga_to_screen(to_x, to_y)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt_click, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.05)
        time.sleep(_SETTLE_S)

    def click(self, rel_x: int, rel_y: int) -> None:
        """Left-click at Amiga content coordinates (*rel_x*, *rel_y*).

        :param rel_x: Target X in Amiga content pixels (0 = left edge, excluding title bar).
        :param rel_y: Target Y in Amiga content pixels (0 = top of Amiga content).
        """
        import Quartz

        self._move_to_amiga(rel_x, rel_y)

        pt = self._amiga_to_screen(rel_x, rel_y)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.05)
        time.sleep(_SETTLE_S)

    def double_click(self, rel_x: int, rel_y: int) -> None:
        """Double-click at Amiga content coordinates (*rel_x*, *rel_y*).

        Moves cursor then sends two click pairs within the Amiga double-click timeout.

        .. note::
            This uses ``CGEventPost`` (HID tap) which only works when SDL2 has captured
            the mouse (i.e. during gameplay).  Use :meth:`workbench_double_click` when
            the Workbench is visible.

        :param rel_x: Target X in Amiga content pixels.
        :param rel_y: Target Y in Amiga content pixels.
        """
        import Quartz

        self._move_to_amiga(rel_x, rel_y)

        pt = self._amiga_to_screen(rel_x, rel_y)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.03)
        time.sleep(0.15)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 2)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.03)
        time.sleep(_SETTLE_S)

    def workbench_click(self, amiga_x: int, amiga_y: int) -> None:
        """Single click at absolute Amiga content coordinates (Workbench mode).

        On the Workbench, SDL2 is in **absolute** (non-captured) mouse mode.
        In this mode absolute ``CGEventPost`` events work correctly — the macOS
        cursor position maps directly to the Amiga cursor position.  Delta events
        do NOT work for click positioning when SDL2 is uncaptured.

        Do NOT call :meth:`_move_to_amiga` before this method — that sends delta
        events which activate SDL2 relative mode and break absolute position clicks.

        :param amiga_x: Target X in Amiga content pixels.
        :param amiga_y: Target Y in Amiga content pixels.
        """
        import Quartz

        bounds = self._process.window_bounds()
        if bounds is None:
            raise RuntimeError("FS-UAE window not found")
        win_x, win_y, _w, _h = bounds
        sx = float(win_x + amiga_x)
        sy = float(win_y + self._TITLE_BAR_H + amiga_y)

        self.focus()
        time.sleep(0.1)

        pt = Quartz.CGPoint(sx, sy)
        # Move cursor to position before clicking (gives SDL2 a chance to track it).
        ev_move = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, pt, 0
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_move)
        time.sleep(0.1)

        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(
                None, ev_type, pt, Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventSetIntegerValueField(
                ev, Quartz.kCGMouseEventClickState, 1
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)
        time.sleep(_SETTLE_S)

    def workbench_double_click(self, amiga_x: int, amiga_y: int) -> None:
        """Double-click at absolute Amiga content coordinates (Workbench mode).

        Uses absolute ``CGEventPost`` events — valid when SDL2 is in
        non-captured (absolute) mode.  Do NOT call :meth:`_move_to_amiga`
        first; delta events would switch SDL2 to relative mode and break this.

        Empirically verified 2026-08-30: absolute double-click with this timing
        opens Workbench disk-icon drawers reliably.

        :param amiga_x: Target X in Amiga content pixels.
        :param amiga_y: Target Y in Amiga content pixels.
        """
        import Quartz

        bounds = self._process.window_bounds()
        if bounds is None:
            raise RuntimeError("FS-UAE window not found")
        win_x, win_y, _w, _h = bounds
        sx = float(win_x + amiga_x)
        sy = float(win_y + self._TITLE_BAR_H + amiga_y)

        self.focus()
        time.sleep(0.1)

        pt = Quartz.CGPoint(sx, sy)
        ev_move = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, pt, 0
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_move)
        time.sleep(0.1)

        # First click (click state 1)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(
                None, ev_type, pt, Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventSetIntegerValueField(
                ev, Quartz.kCGMouseEventClickState, 1
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)
        time.sleep(0.12)   # within Workbench 1.3 double-click window (~250 ms)

        # Second click (click state 2)
        for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
            ev = Quartz.CGEventCreateMouseEvent(
                None, ev_type, pt, Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventSetIntegerValueField(
                ev, Quartz.kCGMouseEventClickState, 2
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(0.04)
        time.sleep(_SETTLE_S)

    def mousedown(self, rel_x: int, rel_y: int) -> None:
        """Press and hold the left mouse button, positioning with delta navigation.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import Quartz

        # Home + walk to position
        self.home_cursor()
        time.sleep(0.1)
        # Walk using the same logic as click()
        self.click(rel_x, rel_y)  # click also homes, which is fine

    def mouseup(self, rel_x: int, rel_y: int) -> None:
        """Release the left mouse button at current cursor position.

        :param rel_x: Unused — cursor is already positioned by mousedown.
        :param rel_y: Unused — cursor is already positioned by mousedown.
        """
        import Quartz

        pt = Quartz.CGPoint(1000.0, 400.0)
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(_SETTLE_S)

    def key(self, name: str) -> None:
        """Send a single key press to the FS-UAE window.

        :param name: Key name as understood by pyautogui (e.g. ``"enter"``, ``"esc"``,
            ``"f1"``, ``"space"``, ``"a"``).
        """
        import pyautogui

        self.focus()
        pyautogui.press(name)
        time.sleep(_SETTLE_S)

    def key_code(self, keycode: int) -> None:
        """Send a raw macOS virtual key code via Quartz.

        Use this when pyautogui's key names do not map correctly to the key you
        need (e.g. Amiga-specific function keys, joystick emulation keys).

        :param keycode: macOS virtual key code (e.g. 36 = Return, 53 = Esc).
        """
        import Quartz

        self.focus()
        time.sleep(0.3)  # ensure OS commits focus before keypress
        down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        time.sleep(0.05)
        up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
        time.sleep(_SETTLE_S)

    # ------------------------------------------------------------------
    # Pixel helpers
    # ------------------------------------------------------------------

    def pixel_diff_score(self, img_a: "Image", img_b: "Image") -> float:
        """Mean absolute pixel difference between two same-size images (0–255).

        :param img_a: First PIL Image.
        :param img_b: Second PIL Image (must be the same size).
        :returns: Mean absolute diff; 0 = identical.
        """
        import numpy as np

        a = np.array(img_a.convert("RGB"), dtype=np.int32)
        b = np.array(img_b.convert("RGB"), dtype=np.int32)
        return float(np.abs(a - b).mean())

    def changed_squares(
        self,
        before: "Image",
        after: "Image",
        sq_coords: dict[str, tuple[int, int]],
        sq_half_w: int,
        sq_half_h: int,
        threshold: float = 5.0,
    ) -> list[tuple[float, str]]:
        """Return squares that changed significantly between two screenshots.

        :param before: Screenshot before the action.
        :param after: Screenshot after the action.
        :param sq_coords: Mapping of square name → (cx, cy) window-relative.
        :param sq_half_w: Half-width of each square in pixels.
        :param sq_half_h: Half-height of each square in pixels.
        :param threshold: Minimum mean diff to include.
        :returns: List of (score, square_name), most-changed first.
        """
        import numpy as np

        b = np.array(before.convert("RGB"), dtype=np.int32)
        a = np.array(after.convert("RGB"),  dtype=np.int32)
        diff = np.abs(b - a)

        results: list[tuple[float, str]] = []
        h, w = diff.shape[:2]
        for sq_name, (cx, cy) in sq_coords.items():
            x0 = max(0, cx - sq_half_w)
            y0 = max(0, cy - sq_half_h)
            x1 = min(w, cx + sq_half_w)
            y1 = min(h, cy + sq_half_h)
            if x1 <= x0 or y1 <= y0:
                continue
            score = float(diff[y0:y1, x0:x1].mean())
            if score >= threshold:
                results.append((score, sq_name))
        results.sort(reverse=True)
        return results
