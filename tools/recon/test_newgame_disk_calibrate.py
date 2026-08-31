#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Hold Disk menu open and screenshot at y=109 to confirm which item the cursor is on.
Then release without selecting, take screenshot to see board state.
If board is stuck, try 'Quit' and restart.
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
_START_X = 175
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


def open_disk_at_y(driver, target_y, screenshot_name):
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.3)
    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)
    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))  # up to menu bar
    time.sleep(0.3)
    _rmb_drag(pt, 0, target_y - _MENU_BAR_Y)     # down to target y
    time.sleep(0.4)
    img = driver.screenshot()
    img.save(f"/tmp/{screenshot_name}.png")
    print(f"Disk at y={target_y} → /tmp/{screenshot_name}.png")
    # Release WITHOUT selecting
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    time.sleep(0.3)


def select_new_game(driver, new_game_y):
    """Actually select New Game at the given Y."""
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.3)
    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)
    _rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))
    time.sleep(0.3)
    _rmb_drag(pt, 0, new_game_y - _MENU_BAR_Y)
    time.sleep(0.3)
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    print(f"Selected y={new_game_y} (should be New Game)")
    time.sleep(6.0)
    img = driver.screenshot()
    img.save(f"/tmp/after_newgame_y{new_game_y}.png")
    print(f"Board after select → /tmp/after_newgame_y{new_game_y}.png")


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    # Screenshot current board state
    img0 = driver.screenshot(); img0.save("/tmp/disk_current_board.png")
    print("Current board → /tmp/disk_current_board.png")

    # Open Disk menu at y=83, 96, 109 to see which item is where
    for y in [83, 96, 109]:
        open_disk_at_y(driver, y, f"disk_y{y}")

    # Now select y=96 (try "New Game" — which might actually be there)
    print("\nSelecting Disk menu at y=96 (expected New Game)...")
    select_new_game(driver, 96)


if __name__ == "__main__":
    main()
