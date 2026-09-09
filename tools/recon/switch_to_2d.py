#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Game is in 3D intro mode. Navigate Settings menu → '2D Board' (y=115)
to switch to 2D mode. Then test StartNewGame.
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
import numpy as np
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

_START_X = 320
_START_Y = 200
_MENU_BAR_Y = 8
_2D_BOARD_Y = 115


def rmb_drag(pt, dx, dy):
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


def select_settings_item(driver, item_y):
    """Open Settings menu from x=320 straight up, navigate to item_y, release."""
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.3)
    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)
    rmb_drag(pt, 0, -(_START_Y - _MENU_BAR_Y))   # straight up to menu bar
    time.sleep(0.3)
    rmb_drag(pt, 0, item_y - _MENU_BAR_Y)          # down to item
    time.sleep(0.3)
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)
    print(f"Selected Settings y={item_y}")


def is_2d_mode(driver):
    import numpy as np
    img = driver.screenshot()
    arr = np.array(img.convert("RGB"))
    tb = 32
    crop = arr[tb + 38:tb + 379, 100:443]
    h, w = crop.shape[:2]
    # 2D board: olive/yellow-green flat squares (higher fraction than 3D)
    olive = ((crop[:,:,0] > 130) & (crop[:,:,0] < 220) &
             (crop[:,:,1] > 150) & (crop[:,:,1] < 230) &
             (crop[:,:,2] < 120))
    frac = olive.sum() / (h * w)
    print(f"  2D check: olive frac = {frac:.3f}")
    return frac >= 0.25, frac  # 2D board ~0.40, 3D board ~0.14


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    img0 = driver.screenshot(); img0.save("/tmp/before_2d_switch.png")
    print("Before → /tmp/before_2d_switch.png")
    is2d, frac = is_2d_mode(driver)
    print(f"Currently in 2D mode: {is2d} (frac={frac:.3f})")

    if not is2d:
        print(f"\nSelecting '2D Board' from Settings menu (y={_2D_BOARD_Y})...")
        select_settings_item(driver, _2D_BOARD_Y)
        time.sleep(2)
        img1 = driver.screenshot(); img1.save("/tmp/after_2d_switch.png")
        print("After 2D switch → /tmp/after_2d_switch.png")
        is2d, frac = is_2d_mode(driver)
        print(f"Now in 2D mode: {is2d} (frac={frac:.3f})")

    if is2d:
        print("\nNow in 2D mode. Testing StartNewGame with ChessSaves disk...")
        runner = AmigaRunner(save_dir="/tmp")
        ctx = {}
        runner.run(driver, [StartNewGame()], ctx=ctx)
        time.sleep(8)
        img2 = driver.screenshot(); img2.save("/tmp/after_newgame_2d.png")
        print("After NewGame → /tmp/after_newgame_2d.png")
        is2d_after, frac2 = is_2d_mode(driver)
        print(f"Still 2D: {is2d_after} (frac={frac2:.3f})")
    else:
        print("ERROR: still not in 2D mode after selection")


if __name__ == "__main__":
    main()
