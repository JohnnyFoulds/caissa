#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Battle Chess is in 3D intro/demo mode (replaying Spassky game).
Click to dismiss demo, then switch to 2D, then test StartNewGame.
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

_START_X, _START_Y, _MENU_BAR_Y = 320, 200, 8


def rmb_nav(driver, item_y):
    """Navigate Settings menu from x=320 straight up, select item_y."""
    driver._move_to_amiga(_START_X, _START_Y)
    time.sleep(0.3)
    pt = Quartz.CGPoint(1000.0, 400.0)
    ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDown, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.5)
    for dx, dy in [(0, -(_START_Y - _MENU_BAR_Y)), (0, item_y - _MENU_BAR_Y)]:
        rem_x, rem_y = dx, dy
        while rem_x != 0 or rem_y != 0:
            sx = max(-89, min(89, rem_x)); sy = max(-89, min(89, rem_y))
            tx = (150. if sx > 0 else -150.) if abs(sx) >= 89 else sx / 0.74
            ty = (150. if sy > 0 else -150.) if abs(sy) >= 89 else sy / 0.74
            e = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseDragged, pt, Quartz.kCGMouseButtonRight)
            Quartz.CGEventSetDoubleValueField(e, Quartz.kCGMouseEventDeltaX, tx)
            Quartz.CGEventSetDoubleValueField(e, Quartz.kCGMouseEventDeltaY, ty)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
            time.sleep(0.04)
            rem_x -= sx; rem_y -= sy
        time.sleep(0.3)
    ev2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev2)


def snap(driver, path):
    img = driver.screenshot(); img.save(path); print(f"  → {path}"); return img


def olive_frac(img):
    arr = np.array(img.convert("RGB"))
    crop = arr[70:379+32, 100:443]  # board region (inclusive of title bar offset)
    h, w = crop.shape[:2]
    m = ((crop[:,:,0]>130)&(crop[:,:,0]<220)&(crop[:,:,1]>150)&(crop[:,:,1]<230)&(crop[:,:,2]<120))
    return m.sum()/(h*w)


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    snap(driver, "/tmp/intro_0.png")

    # Try LMB click to dismiss intro (multiple attempts)
    for attempt in range(5):
        print(f"Click attempt {attempt+1}...")
        driver.click(320, 250)  # board center
        time.sleep(1.5)
        img = snap(driver, f"/tmp/intro_click_{attempt}.png")
        frac = olive_frac(img)
        print(f"  olive frac: {frac:.3f}")
        if frac > 0.25:
            print("  → 2D mode detected after click!")
            break
    else:
        # Try pressing Escape or Space to dismiss intro
        print("Trying Escape key...")
        driver.key_code(53)  # Esc = 53
        time.sleep(2)
        snap(driver, "/tmp/intro_after_esc.png")

    snap(driver, "/tmp/after_intro_attempts.png")
    print("Attempting Settings → 2D Board (y=115)...")
    rmb_nav(driver, 115)
    time.sleep(2)
    img = snap(driver, "/tmp/after_settings_2d.png")
    frac = olive_frac(img)
    print(f"olive frac after Settings 2D: {frac:.3f}")

    # Also try StartNewGame
    print("\nTesting StartNewGame...")
    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    try:
        runner.run(driver, [StartNewGame()], ctx=ctx)
        time.sleep(8)
        snap(driver, "/tmp/after_newgame_3.png")
    except RuntimeError as e:
        print(f"StartNewGame error: {e}")
        snap(driver, "/tmp/newgame_fail.png")


if __name__ == "__main__":
    main()
