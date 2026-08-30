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
_WINDOW_OWNER = "FS-UAE"


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
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        )
        for w in wins:
            if w.get("kCGWindowOwnerName", "") != _WINDOW_OWNER:
                continue
            layer = w.get("kCGWindowLayer", -1)
            if layer != 0:
                continue
            wid = w.get("kCGWindowNumber")
            if wid is not None:
                return wid
        return None

    def window_bounds(self) -> tuple[int, int, int, int] | None:
        """Return (x, y, width, height) of the FS-UAE window in screen coordinates.

        :returns: ``(x, y, w, h)`` or ``None`` if the window is not found.
        """
        try:
            import Quartz
        except ImportError:
            return None

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        )
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
            if width > 0 and height > 0:
                return x, y, width, height
        return None

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
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
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

        Sends a single event rather than pyautogui's interpolated path — games that
        track hover position (like Battle Chess) may react to intermediate events.

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

    def click(self, rel_x: int, rel_y: int) -> None:
        """Left-click at window-relative (*rel_x*, *rel_y*).

        Sends MOUSEMOVE → MOUSEDOWN → MOUSEUP so SDL registers the cursor position
        before the click (SDL requires a cursor-enter event before clicks register).

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import Quartz

        self.focus()
        ax, ay = self._abs(rel_x, rel_y)
        pt = Quartz.CGPoint(ax, ay)

        # MOUSEMOVE first — SDL needs cursor-enter before click
        mv = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mv)
        time.sleep(0.2)

        # MOUSEDOWN
        down = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        time.sleep(0.08)

        # MOUSEUP
        up = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
        time.sleep(_SETTLE_S)

    def mousedown(self, rel_x: int, rel_y: int) -> None:
        """Press and hold the left mouse button at window-relative coordinates.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import Quartz

        self.focus()
        ax, ay = self._abs(rel_x, rel_y)
        pt = Quartz.CGPoint(ax, ay)
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def mouseup(self, rel_x: int, rel_y: int) -> None:
        """Release the left mouse button at window-relative coordinates.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import Quartz

        ax, ay = self._abs(rel_x, rel_y)
        pt = Quartz.CGPoint(ax, ay)
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
