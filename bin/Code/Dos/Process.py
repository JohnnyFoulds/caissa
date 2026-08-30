"""
bin/Code/Dos/Process.py — DOSBox-X subprocess lifecycle management.

Launches DOSBox-X with a generated config that mounts a game directory on a
caller-specified drive letter, runs a startup command, then waits for the window
to appear.  Provides ``stop()`` and context-manager support.

**Stdlib only** — no Qt, no third-party imports.

:purity: dependency-free
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DOSBOXX_BIN = Path(
    "/Users/johannes/Documents/dos/dosbox-x.app/Contents/MacOS/dosbox-x"
)

# Drive letters already claimed by the user's DOSBox-X preference autoexec.
_RESERVED_DRIVES = {"C", "D", "Z"}

_BOOT_TIMEOUT_S = 15.0


class DosBoxProcess:
    """Manages a single DOSBox-X subprocess.

    :param game_dir: Host directory to expose as the game drive.
    :param launch_cmd: DOS command to run at startup (e.g. ``"BC.COM"``).
    :param drive: Drive letter to mount *game_dir* on (default ``"E"``).
        Must not be in the reserved set (C, D, Z).
    :param extra_conf: Optional extra ``[dosbox]`` / ``[cpu]`` / ``[sdl]``
        INI text appended verbatim to the generated config.
    """

    def __init__(
        self,
        game_dir: str | Path,
        launch_cmd: str,
        *,
        drive: str = "E",
        extra_conf: str = "",
    ) -> None:
        drive = drive.upper()
        if drive in _RESERVED_DRIVES:
            raise ValueError(
                f"drive {drive!r} is reserved by the user's DOSBox-X preferences; "
                f"choose one not in {sorted(_RESERVED_DRIVES)}"
            )
        self._game_dir = Path(game_dir)
        self._launch_cmd = launch_cmd
        self._drive = drive
        self._extra_conf = extra_conf
        self._proc: subprocess.Popen | None = None
        self._conf_file: str | None = None

    # ------------------------------------------------------------------
    # Config generation
    # ------------------------------------------------------------------

    def _write_conf(self) -> str:
        """Write a temporary DOSBox-X config and return its path."""
        conf = textwrap.dedent(f"""\
            [sdl]
            fullscreen=false
            windowresolution=original
            mouse_autolock=false

            [dosbox]
            machine=svga_s3
            memsize=16

            [cpu]
            cycles=auto

            {self._extra_conf}

            [autoexec]
            # Mount the game on drive {self._drive}: (avoids conflicts with user prefs C:/D:)
            mount {self._drive.lower()} {self._game_dir}
            {self._drive}:
            {self._launch_cmd}
        """)
        fd, path = tempfile.mkstemp(suffix=".conf", prefix="dosbox_caissa_")
        os.write(fd, conf.encode())
        os.close(fd)
        logger.debug("wrote DOSBox-X config to %s", path)
        return path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def attach(cls) -> "DosBoxProcess":
        """Attach to an already-running DOSBox-X window without launching a new one.

        Useful for interactive testing: start DOSBox manually, then attach
        from a script to drive it without an additional launch/quit cycle.
        Raises ``RuntimeError`` if no DOSBox-X window is found.

        :returns: A ``DosBoxProcess`` instance whose ``_proc`` is ``None``
            (so :meth:`stop` will not try to kill it) but whose
            :meth:`window_bounds`, :meth:`focus`, and :meth:`is_running` all
            work against the live window.
        :raises RuntimeError: If no DOSBox-X window is currently visible.
        """
        dummy = cls.__new__(cls)
        dummy._proc = None
        dummy._conf_file = None
        dummy._game_dir = Path(".")
        dummy._launch_cmd = ""
        dummy._drive = "E"
        dummy._extra_conf = ""

        if dummy.window_bounds() is None:
            raise RuntimeError("attach(): no DOSBox-X window found — is DOSBox-X running?")

        logger.info("attach(): connected to existing DOSBox-X window")
        return dummy

    @property
    def is_running(self) -> bool:
        """True if a DOSBox-X window is visible (works for attached instances too)."""
        return self.window_bounds() is not None

    def launch(self) -> "DosBoxProcess":
        """Start DOSBox-X and wait until the window appears.

        :returns: *self* for chaining.
        :raises RuntimeError: If DOSBox-X is already running or the binary
            cannot be found.
        """
        if self._proc is not None:
            raise RuntimeError("DosBoxProcess already running")
        if not _DOSBOXX_BIN.exists():
            raise RuntimeError(f"DOSBox-X binary not found at {_DOSBOXX_BIN}")

        self._conf_file = self._write_conf()
        cmd = [str(_DOSBOXX_BIN), "-conf", self._conf_file]
        logger.info("launching DOSBox-X: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_window()
        return self

    def _wait_for_window(self) -> None:
        """Block until the DOSBox-X window is visible or timeout."""
        deadline = time.monotonic() + _BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.window_bounds() is not None:
                logger.info("DOSBox-X window found (pid %d)", self._proc.pid)
                return
            time.sleep(0.5)
        logger.warning("DOSBox-X window not found within %.0fs", _BOOT_TIMEOUT_S)

    def stop(self) -> None:
        """Terminate DOSBox-X and clean up the temporary config file.

        Sends SIGTERM first, then clicks any "confirm quit" dialog that
        DOSBox-X may show before exiting.  Falls back to SIGKILL after 6 s.
        """
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # DOSBox-X may be waiting for a quit-confirmation dialog.
                self._click_quit_dialog()
                try:
                    self._proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._proc = None
            logger.info("DOSBox-X stopped")
        if self._conf_file and Path(self._conf_file).exists():
            Path(self._conf_file).unlink(missing_ok=True)
            self._conf_file = None

    def _click_quit_dialog(self) -> None:
        """Find and click the DOSBox-X quit-confirmation dialog."""
        try:
            import pyautogui  # type: ignore[import]
            import Quartz

            wins = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
            )
            for w in wins:
                if w.get("kCGWindowOwnerName", "") != "DOSBox-X":
                    continue
                bounds = w.get("kCGWindowBounds", {})
                ww = int(bounds.get("Width", 0))
                wh = int(bounds.get("Height", 0))
                # Dialogs are small; the game window is large
                if ww < 50 or ww > 500 or wh < 50 or wh > 300:
                    continue
                x = int(bounds.get("X", 0))
                y = int(bounds.get("Y", 0))
                # Click the right half of the dialog (typically the "Yes/OK" button)
                pyautogui.click(x + ww * 3 // 4, y + wh * 3 // 4)
                logger.debug("clicked quit dialog at (%d, %d)", x + ww * 3 // 4, y + wh * 3 // 4)
                time.sleep(0.5)
                return
        except Exception:  # noqa: BLE001
            pass

    @property
    def pid(self) -> int | None:
        """PID of the running DOSBox-X process, or None if not started."""
        return self._proc.pid if self._proc else None

    # ------------------------------------------------------------------
    # Window geometry (macOS)
    # ------------------------------------------------------------------

    def window_number(self) -> int | None:
        """Return the Quartz window number (kCGWindowNumber) of the DOSBox-X game window.

        Required for ``screencapture -l <wid>`` which captures a specific window
        regardless of its screen position or occlusion.

        :return: Integer window number, or ``None`` if no window is found.
        """
        try:
            import Quartz
            wins = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
            )
            fallback = None
            for w in wins:
                if w.get("kCGWindowOwnerName", "") != "DOSBox-X":
                    continue
                name = w.get("kCGWindowName", "")
                if not name:
                    continue
                bounds = w.get("kCGWindowBounds", {})
                if int(bounds.get("Width", 0)) < 100 or int(bounds.get("Height", 0)) < 100:
                    continue
                if not w.get("kCGWindowIsOnscreen", False):
                    continue
                game_title = name.split(": ", 1)[-1].upper()
                wid = w.get("kCGWindowNumber")
                if not game_title.startswith("DOSBOX-X"):
                    return wid
                fallback = wid
            return fallback
        except Exception:  # noqa: BLE001
            pass
        return None

    def window_bounds(self) -> tuple[int, int, int, int] | None:
        """Return the DOSBox-X window bounds as *(x, y, w, h)* in screen pixels.

        Uses Quartz ``CGWindowListCopyWindowInfo`` — works across all monitors
        and does not depend on Accessibility permissions or System Events.
        Returns ``None`` if no visible DOSBox-X window is found.

        When multiple named DOSBox-X windows are present (SDL1 creates a bare
        "DOSBOX-X" prompt window alongside the running game window), prefer the
        game window whose title does not start with "DOSBOX-X".

        :return: ``(x, y, w, h)`` or ``None``.
        """
        try:
            import Quartz
            wins = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
            )
            fallback = None
            for w in wins:
                if w.get("kCGWindowOwnerName", "") != "DOSBox-X":
                    continue
                name = w.get("kCGWindowName", "")
                if not name:
                    continue  # skip unnamed SDL backdrops and fullscreen layers
                bounds = w.get("kCGWindowBounds", {})
                width  = int(bounds.get("Width",  0))
                height = int(bounds.get("Height", 0))
                if width < 100 or height < 100:
                    continue  # skip menu-bar and zero-size windows
                x = int(bounds.get("X", 0))
                y = int(bounds.get("Y", 0))
                # Skip windows that are not currently on any display.
                if not w.get("kCGWindowIsOnscreen", False):
                    continue
                # Prefer the game window ("CHESS", "BATTLE CHESS", …) over the
                # bare DOS-prompt window whose title suffix is just "DOSBOX-X".
                game_title = name.split(": ", 1)[-1].upper()
                if not game_title.startswith("DOSBOX-X"):
                    return x, y, width, height
                fallback = (x, y, width, height)
            return fallback
        except Exception:  # noqa: BLE001
            pass
        return None

    def focus(self) -> None:
        """Bring the DOSBox-X window to the foreground.

        Uses ``NSRunningApplication.activateWithOptions_()`` which works for
        SDL1 windows that do not register with System Events.  Falls back to
        AppleScript if AppKit is unavailable.
        """
        pid = self._dosbox_pid()
        if pid is not None:
            try:
                from AppKit import (  # type: ignore[import]
                    NSRunningApplication,
                    NSApplicationActivateAllWindows,
                    NSApplicationActivateIgnoringOtherApps,
                )
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                if app is not None:
                    flags = NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
                    app.activateWithOptions_(flags)
                    return
            except Exception:  # noqa: BLE001
                pass
        # Fallback: AppleScript (may not work for SDL1 windows)
        script = (
            'tell application "System Events"\n'
            '  set frontmost of (first process whose name contains "dosbox-x") to true\n'
            'end tell'
        )
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)

    def _dosbox_pid(self) -> int | None:
        """Return the PID of the running DOSBox-X window process, or None."""
        try:
            import Quartz
            wins = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
            )
            fallback_pid = None
            for w in wins:
                if w.get("kCGWindowOwnerName", "") != "DOSBox-X":
                    continue
                name = w.get("kCGWindowName", "")
                if not name:
                    continue  # skip unnamed SDL backdrops
                bounds = w.get("kCGWindowBounds", {})
                if int(bounds.get("Width", 0)) < 100:
                    continue
                if not w.get("kCGWindowIsOnscreen", False):
                    continue
                game_title = name.split(": ", 1)[-1].upper()
                if not game_title.startswith("DOSBOX-X"):
                    return w.get("kCGWindowOwnerPID")
                fallback_pid = w.get("kCGWindowOwnerPID")
            return fallback_pid
        except Exception:  # noqa: BLE001
            pass
        return None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "DosBoxProcess":
        return self.launch()

    def __exit__(self, *_) -> None:
        self.stop()
