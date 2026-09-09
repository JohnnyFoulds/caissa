#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Find Move menu header by starting cursor directly below it (no lateral drag).
Try x = 205, 210, 215, 220 as start positions, navigate straight up to y=8.
The Move menu should show: "Computer Plays", "Hint", etc. (NOT Sound/Board/Player).
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
_START_Y = 220
_MENU_BAR_Y = 8


def _rmb_drag(pt, dx, dy):
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


def try_straight_up(driver, start_x, label):
    """Press RMB at (start_x, _START_Y), navigate STRAIGHT UP to menu bar, screenshot."""
    driver._move_to_amiga(start_x, _START_Y)
    time.sleep(0.3)

    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))   # straight up, no horizontal
    time.sleep(0.5)

    img = driver.screenshot()
    path = f"/tmp/straight_up_x{start_x}.png"
    img.save(path)
    print(f"  {label}: start_x={start_x} → {path}")

    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    time.sleep(0.5)


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    # Try each x — start directly below potential Move header locations
    for x in [195, 205, 210, 215, 220]:
        try_straight_up(driver, x, f"x={x}")

    print("Which x shows a DIFFERENT menu (not Sound/Board/Player)?")
    print("The Move menu should show: Computer Plays, Hint, etc.")


if __name__ == "__main__":
    main()
