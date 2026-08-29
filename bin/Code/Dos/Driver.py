"""
bin/Code/Dos/Driver.py — Input and screenshot driver for a DOSBox-X window.

Wraps a :class:`~Code.Dos.Process.DosBoxProcess` and provides:

- ``screenshot()`` — capture the DOSBox-X window as a PIL Image
- ``click(x, y)`` — click at window-relative pixel coordinates
- ``key(name)`` — send a key by name (e.g. ``"enter"``, ``"esc"``, ``"f1"``)
- ``move_to(x, y)`` — move the mouse to window-relative coordinates

All coordinates passed to public methods are **window-relative** (top-left of
the DOSBox-X window = 0, 0).  The driver converts them to absolute screen
coordinates before actuation.

**Purity tier: adapter** — imports stdlib + pyautogui + PIL + Code.Dos.Process.
No Qt imports.

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
_FOCUS_S  = 0.80   # seconds to wait after focus() before clicking


class DosBoxDriver:
    """Input and screenshot driver for a running DOSBox-X window.

    :param process: A started :class:`~Code.Dos.Process.DosBoxProcess`.
    :raises RuntimeError: If the process is not running.
    """

    def __init__(self, process) -> None:
        from Code.Dos.Process import DosBoxProcess
        if not isinstance(process, DosBoxProcess):
            raise TypeError(f"expected DosBoxProcess, got {type(process).__name__}")
        self._process = process

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bounds(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) of the DOSBox-X window; raise if not found."""
        bounds = self._process.window_bounds()
        if bounds is None:
            raise RuntimeError("DOSBox-X window not found")
        return bounds

    def _abs(self, rel_x: int, rel_y: int) -> tuple[int, int]:
        """Convert window-relative coords to absolute screen coords."""
        x, y, _w, _h = self._bounds()
        return x + rel_x, y + rel_y

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def _wid(self) -> int:
        """Return the Quartz window number; raise if not found."""
        wid = self._process.window_number()
        if wid is None:
            raise RuntimeError("DOSBox-X window ID not found")
        return wid

    def screenshot(self) -> "Image":
        """Capture the DOSBox-X window and return a PIL Image.

        Uses ``screencapture -l <wid>`` to capture by window ID, so the result
        is correct regardless of the window's screen position or occlusion.

        :return: PIL Image of the current DOSBox-X window contents.
        :raises RuntimeError: If the window cannot be found.
        """
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        subprocess.run(
            # -o strips the window drop-shadow so the image is exactly the
            # window size and (0,0) maps to window top-left.
            ["screencapture", "-x", "-o", "-l", str(self._wid()), path],
            check=True,
        )
        img = Image.open(path)
        img.load()
        Path(path).unlink(missing_ok=True)
        return img

    def screenshot_to(self, path: str | Path) -> None:
        """Capture the DOSBox-X window and save to *path*.

        :param path: Destination file path (PNG).
        """
        subprocess.run(
            ["screencapture", "-x", "-o", "-l", str(self._wid()), str(path)],
            check=True,
        )

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def focus(self) -> None:
        """Bring the DOSBox-X window to the foreground and wait briefly."""
        self._process.focus()
        time.sleep(_FOCUS_S)

    def click(self, rel_x: int, rel_y: int, *, button: str = "left") -> None:
        """Click at window-relative (*rel_x*, *rel_y*).

        :param rel_x: X offset from the left edge of the DOSBox-X window.
        :param rel_y: Y offset from the top edge of the DOSBox-X window.
        :param button: Mouse button — ``"left"``, ``"right"``, or ``"middle"``.
        """
        import pyautogui

        self.focus()
        ax, ay = self._abs(rel_x, rel_y)
        pyautogui.click(ax, ay, button=button)
        time.sleep(_SETTLE_S)

    def double_click(self, rel_x: int, rel_y: int) -> None:
        """Double-click at window-relative coordinates.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        """
        import pyautogui

        self.focus()
        ax, ay = self._abs(rel_x, rel_y)
        pyautogui.doubleClick(ax, ay)
        time.sleep(_SETTLE_S)

    def move_to(self, rel_x: int, rel_y: int) -> None:
        """Move the mouse to window-relative coordinates without clicking.

        Sends a single ``kCGEventMouseMoved`` Quartz event rather than
        pyautogui's interpolated move.  pyautogui.moveTo dispatches many
        intermediate MOUSEMOVE events along the path; games that track
        hover position (like Battle Chess) may react to those intermediate
        events and reset internal state.  One event is what we want.

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

    def key(self, name: str) -> None:
        """Send a single key press to the DOSBox-X window.

        :param name: Key name as understood by pyautogui (e.g. ``"enter"``,
            ``"esc"``, ``"f1"``, ``"space"``, ``"a"``).
        """
        import pyautogui

        self.focus()
        pyautogui.press(name)
        time.sleep(_SETTLE_S)

    def keys(self, *names: str) -> None:
        """Send a sequence of key presses.

        :param names: Key names to press in order.
        """
        for name in names:
            self.key(name)

    def hotkey(self, *names: str) -> None:
        """Send a key combination (all keys held simultaneously).

        :param names: Keys to hold, e.g. ``("ctrl", "c")``.
        """
        import pyautogui

        self.focus()
        pyautogui.hotkey(*names)
        time.sleep(_SETTLE_S)

    def type_text(self, text: str, interval: float = 0.05) -> None:
        """Type a string character by character.

        :param text: Text to type.
        :param interval: Seconds between each keystroke.
        """
        import pyautogui

        self.focus()
        pyautogui.typewrite(text, interval=interval)
        time.sleep(_SETTLE_S)

    def wait(self, seconds: float) -> None:
        """Sleep for *seconds*.

        :param seconds: Duration to wait.
        """
        time.sleep(seconds)

    # ------------------------------------------------------------------
    # OCR helpers
    # ------------------------------------------------------------------

    def find_text_center(
        self,
        text: str,
        *,
        psm: str = "6",
        min_conf: float = 10.0,
    ) -> tuple[int, int] | None:
        """Return the window-relative centre of *text* on the current screen.

        Takes a fresh screenshot, runs Tesseract, and returns the pixel centre
        of the first match.  Returns ``None`` if the text is not found.

        Intended for RPA state verification and menu navigation where the
        exact coordinates of a UI element are not known in advance.

        :param text: Text string to locate (case-insensitive).
        :param psm: Tesseract page-segmentation mode (default ``"6"``).
        :param min_conf: Minimum OCR confidence threshold.
        :returns: ``(rel_x, rel_y)`` window-relative pixel centre, or ``None``.
        """
        from Code.Dos.Ocr import find_text_bounds

        img = self.screenshot()
        bounds = find_text_bounds(img, text, psm=psm, min_conf=min_conf)
        if bounds is None:
            logger.debug("find_text_center: %r not found on screen", text)
            return None
        left, top, width, height = bounds
        cx, cy = left + width // 2, top + height // 2
        logger.debug("find_text_center: %r at (%d, %d)", text, cx, cy)
        return cx, cy

    # ------------------------------------------------------------------
    # Board vision — pixel-based state verification (no cloud calls)
    # ------------------------------------------------------------------

    def crop_region(
        self,
        img: "Image",
        rel_x: int,
        rel_y: int,
        width: int,
        height: int,
    ) -> "Image":
        """Crop a rectangle from a screenshot already taken.

        All coordinates are window-relative.  Useful for isolating a single
        chess square or UI region for pixel comparison.

        :param img: PIL Image from :meth:`screenshot`.
        :param rel_x: Left edge of the crop (window-relative).
        :param rel_y: Top edge of the crop (window-relative).
        :param width: Width of the crop in pixels.
        :param height: Height of the crop in pixels.
        :returns: Cropped PIL Image.
        """
        return img.crop((rel_x, rel_y, rel_x + width, rel_y + height))

    def pixel_diff_score(self, img_a: "Image", img_b: "Image") -> float:
        """Return the mean absolute pixel difference between two same-size images.

        A score of 0 means identical; higher values indicate greater change.
        Use this to verify that an action produced a visible board change.

        :param img_a: First PIL Image.
        :param img_b: Second PIL Image.
        :returns: Mean absolute difference (float, 0–255 range per channel).
        """
        import numpy as np

        a = np.array(img_a.convert("RGB"), dtype=np.int32)
        b = np.array(img_b.convert("RGB"), dtype=np.int32)
        return float(np.abs(a - b).mean())

    def changed_squares(
        self,
        before: "Image",
        after: "Image",
        sq_coords: dict,
        sq_half_w: int,
        sq_half_h: int,
        threshold: float = 5.0,
    ) -> list[tuple[float, str]]:
        """Return squares that changed significantly between two screenshots.

        Each square is checked by computing the mean absolute pixel diff of
        its bounding box.  Squares are returned sorted descending by diff score.

        :param before: PIL Image taken before the action.
        :param after: PIL Image taken after the action.
        :param sq_coords: Mapping of ``square_name → (cx, cy)`` in window-relative pixels.
        :param sq_half_w: Half the square width (crop extends ±sq_half_w from centre).
        :param sq_half_h: Half the square height.
        :param threshold: Minimum mean diff to include in results.
        :returns: List of ``(score, square_name)`` tuples, most-changed first.
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

    def has_colored_border(
        self,
        img: "Image",
        rel_x: int,
        rel_y: int,
        width: int,
        height: int,
        *,
        min_pixels: int = 50,
    ) -> bool:
        """Return True if the region contains a selection-box border.

        Detects both the green (r<80,g>150,b<80) and blue (r<80,g<80,b>150)
        selection colors that Battle Chess uses for the active-square highlight.
        The highlight flickers between both colors, so either is accepted.

        :param img: PIL Image to inspect.
        :param rel_x: Left edge of region (window-relative).
        :param rel_y: Top edge of region (window-relative).
        :param width: Region width.
        :param height: Region height.
        :param min_pixels: Minimum matching pixel count to qualify as "selected".
        :returns: ``True`` if a selection-colored border is visible.
        """
        import numpy as np

        crop = img.crop((rel_x, rel_y, rel_x + width, rel_y + height))
        arr = np.array(crop.convert("RGB"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        green_sel = (r < 80) & (g > 150) & (b < 80)
        blue_sel  = (r < 80) & (g < 80) & (b > 150)
        return int((green_sel | blue_sel).sum()) >= min_pixels

    def click_at_current_pos(self, abs_x: int, abs_y: int) -> None:
        """Send MOUSEDOWN then MOUSEUP at absolute *(abs_x, abs_y)* without
        first sending a MOUSEMOVE event.

        Use this instead of :meth:`click` when the cursor is already at the
        target position and an extra MOUSEMOVE event would reset the game's
        internal state (e.g. clearing piece selection in Battle Chess).

        :param abs_x: Absolute screen X coordinate.
        :param abs_y: Absolute screen Y coordinate.
        """
        import Quartz

        pt = Quartz.CGPoint(abs_x, abs_y)
        ev_down = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
        time.sleep(0.08)
        ev_up = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)
        time.sleep(_SETTLE_S)

    def mousedown(self, rel_x: int, rel_y: int, *, button: str = "left") -> None:
        """Press and hold a mouse button at window-relative coordinates.

        Does *not* release.  Pair with :meth:`mouseup` and intervening
        :meth:`move_to` calls to implement drag and right-click-hold menus.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        :param button: ``"left"``, ``"right"``, or ``"middle"``.
        """
        import pyautogui

        self.focus()
        ax, ay = self._abs(rel_x, rel_y)
        pyautogui.mouseDown(ax, ay, button=button)

    def mouseup(self, rel_x: int, rel_y: int, *, button: str = "left") -> None:
        """Release a mouse button at window-relative coordinates.

        :param rel_x: X offset from window left edge.
        :param rel_y: Y offset from window top edge.
        :param button: ``"left"``, ``"right"``, or ``"middle"``.
        """
        import pyautogui

        ax, ay = self._abs(rel_x, rel_y)
        pyautogui.mouseUp(ax, ay, button=button)
        time.sleep(_SETTLE_S)

    def wait_for_region_change(
        self,
        rel_x: int,
        rel_y: int,
        width: int,
        height: int,
        *,
        timeout_s: float = 30.0,
        poll_s: float = 0.5,
        threshold: float = 3.0,
    ) -> bool:
        """Poll until a screen region changes significantly or *timeout_s* expires.

        Useful for waiting on CPU turns, loading screens, or animation completion.
        The baseline is captured immediately before polling begins.

        :param rel_x: Left edge of the region (window-relative).
        :param rel_y: Top edge of the region (window-relative).
        :param width: Region width.
        :param height: Region height.
        :param timeout_s: Maximum wait time in seconds.
        :param poll_s: Seconds between polls.
        :param threshold: Mean absolute pixel diff threshold to count as "changed".
        :returns: ``True`` if a change was detected; ``False`` if timed out.
        """
        import numpy as np

        def _crop_arr(img: "Image") -> "np.ndarray":
            crop = img.crop((rel_x, rel_y, rel_x + width, rel_y + height))
            return np.array(crop.convert("RGB"), dtype=np.int32)

        baseline = _crop_arr(self.screenshot())
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(poll_s)
            current = _crop_arr(self.screenshot())
            score = float(np.abs(baseline - current).mean())
            if score >= threshold:
                logger.debug(
                    "wait_for_region_change: detected change (score=%.1f)", score
                )
                return True
        logger.debug("wait_for_region_change: timed out after %.0fs", timeout_s)
        return False

    def find_all_text_on_screen(
        self,
        *,
        psm: str = "6",
        min_conf: float = 10.0,
    ) -> list[tuple[str, int, int, int, int]]:
        """OCR the current screen and return all recognised text with bounds.

        :param psm: Tesseract PSM mode.
        :param min_conf: Minimum confidence threshold.
        :returns: List of ``(text, left, top, width, height)`` in window-relative
            pixels.
        """
        from Code.Dos.Ocr import find_all_text

        img = self.screenshot()
        return find_all_text(img, psm=psm, min_conf=min_conf)
