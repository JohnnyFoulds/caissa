#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Hold RMB and navigate to the Move menu header, then screenshot.
Based on the Disk menu screenshot, Move header is at x≈255.
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

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver

CONFIG = _REPO / "BattleChess-ADF.fs-uae"

# Move header is to the right of Disk (175). Estimate: 255.
_MOVE_HEADER_X = 255
_MENU_BAR_Y = 8


def _rmb_drag(driver_pt, dx, dy):
    import Quartz
    pt = driver_pt
    remaining_x, remaining_y = dx, dy
    while remaining_x != 0 or remaining_y != 0:
        sx = max(-89, min(89, remaining_x))
        sy = max(-89, min(89, remaining_y))
        send_x = (150.0 if sx > 0 else -150.0) if abs(sx) >= 89 else (sx / 0.74 if sx != 0 else 0.0)
        send_y = (150.0 if sy > 0 else -150.0) if abs(sy) >= 89 else (sy / 0.74 if sy != 0 else 0.0)
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight)
        Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaX, send_x)
        Quartz.CGEventSetDoubleValueField(ev, Quartz.kCGMouseEventDeltaY, send_y)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.04)
        remaining_x -= sx
        remaining_y -= sy


def main():
    import Quartz

    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    # Start at board centre
    driver._move_to_amiga(320, 200)
    time.sleep(0.2)

    pt = Quartz.CGPoint(1000.0, 400.0)

    # RMB down
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    # Move UP to menu bar
    _rmb_drag(pt, 0, -(200 - _MENU_BAR_Y))
    time.sleep(0.2)

    # Move LEFT to Move header (from 320 → 255, dx=-65)
    _rmb_drag(pt, _MOVE_HEADER_X - 320, 0)
    time.sleep(0.5)  # let Move menu open

    img = driver.screenshot()
    img.save("/tmp/move_menu_open.png")
    print("Move menu screenshot → /tmp/move_menu_open.png")
    print("Measure Y of 'Computer plays' item in Amiga content pixels (screenshot_y - 32)")

    # Release
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)


if __name__ == "__main__":
    main()
