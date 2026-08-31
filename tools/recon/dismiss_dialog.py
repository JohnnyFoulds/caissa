#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Dismiss 'Insert ChessSaves disk' dialog using ABSOLUTE screen coordinates,
exactly as wake_sdl2() does for the title bar click.
"""

import sys
import types
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

import Quartz
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver

CONFIG = _REPO / "BattleChess-ADF.fs-uae"
_TITLE_BAR_H = 32  # macOS title bar


def abs_click(driver, amiga_x, amiga_y):
    """Click at Amiga content coordinates using absolute screen coordinates."""
    bounds = driver._process.window_bounds()
    if bounds is None:
        print("ERROR: window not found")
        return
    win_x, win_y, win_w, win_h = bounds
    # Amiga content y=0 starts BELOW the macOS title bar
    scr_x = win_x + amiga_x
    scr_y = win_y + _TITLE_BAR_H + amiga_y
    print(f"  window bounds: {bounds}")
    print(f"  clicking absolute: ({scr_x}, {scr_y})")

    driver.focus()
    time.sleep(0.3)

    pt = Quartz.CGPoint(scr_x, scr_y)
    for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
        ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.1)


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    img0 = driver.screenshot()
    img0.save("/tmp/before_abs_click.png")
    print("Before → /tmp/before_abs_click.png")

    # Click at dialog center using absolute screen coordinates
    print("Clicking dialog center with absolute coordinates...")
    abs_click(driver, 320, 185)
    time.sleep(2.0)

    img1 = driver.screenshot()
    img1.save("/tmp/after_abs_click_1.png")
    print("After (2s) → /tmp/after_abs_click_1.png")

    # Try a second click
    abs_click(driver, 320, 185)
    time.sleep(3.0)
    img2 = driver.screenshot()
    img2.save("/tmp/after_abs_click_2.png")
    print("After second click → /tmp/after_abs_click_2.png")


if __name__ == "__main__":
    main()
