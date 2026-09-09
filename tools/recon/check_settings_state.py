#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Open Settings menu from x=320 straight up and screenshot to see current (+) markers.
Also screenshot the board to see its current state.
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
_MENU_BAR_Y = 0


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

    # Take current board state
    img0 = driver.screenshot()
    img0.save("/tmp/current_board.png")
    print("Current board → /tmp/current_board.png")

    # Open Settings menu at x=320 (straight up), navigate to y=115 (top of player items)
    # to see all player items with (+) markers
    driver._move_to_amiga(320, _START_Y)
    time.sleep(0.3)

    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))  # straight up
    time.sleep(0.3)
    _rmb_drag(pt, 0, 115)  # down to y=115 area (between 2D Board and Human Plays Red)
    time.sleep(0.5)

    img1 = driver.screenshot()
    img1.save("/tmp/settings_at_115.png")
    print("Settings at y=115 → /tmp/settings_at_115.png")

    # Navigate further down to see Blue items
    _rmb_drag(pt, 0, 60)  # down to y=175 area (Amiga Plays Blue)
    time.sleep(0.3)

    img2 = driver.screenshot()
    img2.save("/tmp/settings_at_175.png")
    print("Settings at y=175 → /tmp/settings_at_175.png")

    # Release without selecting
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    print("Released. Check (+) markers for current player settings.")


if __name__ == "__main__":
    main()
