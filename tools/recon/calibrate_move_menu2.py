#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Open the Move menu (second header from left, x=225) and screenshot
to find the 'Computer Plays' item's Y coordinate.
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

_START_X = 320
_START_Y = 200
_MENU_BAR_Y = 8
_MOVE_HEADER_X = 225   # Move menu header (Disk=175, Move=225, Settings=327, Level=...)


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


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.2)

    pt = Quartz.CGPoint(1000.0, 400.0)

    # RMB down
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    # Move UP to menu bar
    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))
    time.sleep(0.2)

    # Move LEFT to Move header (from 320 → 225)
    _rmb_drag(pt, _MOVE_HEADER_X - _START_X, 0)
    time.sleep(0.5)  # let Move menu open

    img = driver.screenshot()
    img.save("/tmp/move_menu.png")
    print("Move menu screenshot → /tmp/move_menu.png")
    print("Measure the Y of 'Computer Plays' in screenshot pixels, subtract 32 = Amiga content Y")

    # Release without selecting
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)


if __name__ == "__main__":
    main()
