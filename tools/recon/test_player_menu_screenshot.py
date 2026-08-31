#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Hold RMB open at the second menu (x=255) and screenshot at the target y positions
to verify which item is highlighted before releasing.
Also tests reversed order: StartNewGame → SetAmigaPlaysRed.
"""

import sys
import types
import logging
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

import Quartz
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = _REPO / "BattleChess-ADF.fs-uae"

_START_X = 320
_START_Y = 200
_MENU_BAR_Y = 8
_SECOND_MENU_X = 255


def _rmb_drag(driver, pt, dx, dy):
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


def open_second_menu(driver, pt):
    """Open the second menu at x=255. Cursor starts at _START_X, _START_Y."""
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.2)

    # RMB down
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    # Move UP to menu bar
    _rmb_drag(driver, pt, 0, -(_START_Y - _MENU_BAR_Y))
    time.sleep(0.2)

    # Move LEFT to second menu header
    _rmb_drag(driver, pt, _SECOND_MENU_X - _START_X, 0)
    time.sleep(0.5)  # let menu open


def close_menu(pt, release_y):
    """Navigate to release_y and release RMB."""
    _rmb_drag(None, pt, 0, release_y - _MENU_BAR_Y)
    time.sleep(0.1)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    # Step 1: StartNewGame (reverse order test)
    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    print("StartNewGame first...")
    runner.run(driver, [StartNewGame()], ctx=ctx)
    print("Done.")

    pt = Quartz.CGPoint(1000.0, 400.0)

    # Step 2: Open the second menu and screenshot at y=115 (Human Plays Red)
    print("Opening second menu (x=255), navigating to y=115 (Human Plays Red)...")
    open_second_menu(driver, pt)
    _rmb_drag(driver, pt, 0, 115 - _MENU_BAR_Y)
    time.sleep(0.3)
    img1 = driver.screenshot()
    img1.save("/tmp/menu_at_y115.png")
    print("  screenshot at y=115 → /tmp/menu_at_y115.png")

    # Move DOWN to y=131 (Amiga Plays Red)
    _rmb_drag(driver, pt, 0, 131 - 115)
    time.sleep(0.3)
    img2 = driver.screenshot()
    img2.save("/tmp/menu_at_y131.png")
    print("  screenshot at y=131 → /tmp/menu_at_y131.png")

    # Release at y=131 to select "Amiga Plays Red"
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)

    # Step 3: screenshot after release — did the AI start thinking?
    img3 = driver.screenshot()
    img3.save("/tmp/after_set_amiga_red_reversed.png")
    print("  screenshot after SetAmigaPlaysRed → /tmp/after_set_amiga_red_reversed.png")

    print("Now waiting 30s for AI to move (it should play first since Amiga Plays Red)...")
    time.sleep(30.0)
    img4 = driver.screenshot()
    img4.save("/tmp/after_30s_wait.png")
    print("  screenshot after 30s → /tmp/after_30s_wait.png")
    print("Check: has the board changed from startpos?")


if __name__ == "__main__":
    main()
