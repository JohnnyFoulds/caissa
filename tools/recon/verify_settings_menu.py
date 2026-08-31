#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Open Settings menu from x=320 straight up (with _MENU_BAR_Y=8) and screenshot
at various Y positions to verify what items are visible and where (+) markers are.
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

    # Open Settings (straight up from x=320)
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.3)

    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    # Go straight up to menu bar y=8
    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))  # = -192
    time.sleep(0.4)  # let menu open

    # Screenshot at menu bar — should show Settings dropdown
    img0 = driver.screenshot()
    img0.save("/tmp/settings_at_menubar.png")
    print("Settings at menu bar → /tmp/settings_at_menubar.png")

    # Navigate down to y=115 (Human Plays Red area)
    _rmb_drag(pt, 0, 115 - _MENU_BAR_Y)  # +107
    time.sleep(0.3)
    img1 = driver.screenshot()
    img1.save("/tmp/settings_y115.png")
    print("Settings y=115 → /tmp/settings_y115.png")

    # Navigate to y=131
    _rmb_drag(pt, 0, 131 - 115)  # +16
    time.sleep(0.3)
    img2 = driver.screenshot()
    img2.save("/tmp/settings_y131.png")
    print("Settings y=131 → /tmp/settings_y131.png")

    # Navigate to y=163
    _rmb_drag(pt, 0, 163 - 131)  # +32
    time.sleep(0.3)
    img3 = driver.screenshot()
    img3.save("/tmp/settings_y163.png")
    print("Settings y=163 → /tmp/settings_y163.png")

    # Navigate to y=179
    _rmb_drag(pt, 0, 179 - 163)  # +16
    time.sleep(0.3)
    img4 = driver.screenshot()
    img4.save("/tmp/settings_y179.png")
    print("Settings y=179 → /tmp/settings_y179.png")

    # Release without selecting
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    print("Released. No selection made.")


if __name__ == "__main__":
    main()
