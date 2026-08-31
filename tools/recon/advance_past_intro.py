#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Try to advance past the crack intro and switch to 2D mode.
1. Check if the intro is active
2. Try AdvancePastCopyrightScreen (sends Enter)
3. Try SelectTwoDBoard (y=122 — note: different from the y=115 tried earlier)
4. Take screenshots at each step
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
from Code.Amiga.Activities import (
    AmigaRunner, SelectTwoDBoard, StartNewGame,
    AdvancePastCopyrightScreen,
)

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def snap(driver, path):
    img = driver.screenshot(); img.save(path); print(f"  → {path}"); return img


def check_2d(img):
    arr = np.array(img.convert("RGB"))
    crop = arr[70:411, 100:443]
    h, w = crop.shape[:2]
    olive = ((crop[:,:,0]>130)&(crop[:,:,0]<220)&(crop[:,:,1]>150)&(crop[:,:,1]<230)&(crop[:,:,2]<120))
    frac = olive.sum()/(h*w)
    return frac >= 0.25, frac


def check_dialog(img):
    """Check for the pink/magenta dialog box."""
    arr = np.array(img.crop((150, 197, 500, 260)).convert("RGB"))
    r, g, b = arr[:,:,0].astype(float), arr[:,:,1].astype(float), arr[:,:,2].astype(float)
    # Magenta/pink: high R, low G, high B
    magenta = ((r > 150) & (g < 100) & (b > 100)).sum()
    frac = float(magenta) / (arr.shape[0] * arr.shape[1])
    return frac >= 0.05, frac


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    img0 = snap(driver, "/tmp/advance_start.png")
    is2d, frac2d = check_2d(img0)
    has_dlg, frac_dlg = check_dialog(img0)
    print(f"  2D: {is2d} (frac={frac2d:.3f}), dialog: {has_dlg} (frac={frac_dlg:.3f})")

    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}

    # Try AdvancePastCopyrightScreen directly (bypassing precondition check)
    # by calling execute() manually multiple times
    print("\nSending Enter x10 to dismiss intro...")
    driver.focus()
    for i in range(10):
        driver.key_code(36)  # Return
        time.sleep(1.0)
        img = driver.screenshot()
        is2d, f = check_2d(img)
        dlg, fd = check_dialog(img)
        print(f"  [{i+1}] 2D={is2d}(f={f:.3f}), dialog={dlg}(fd={fd:.3f})")
        if is2d:
            print("  Switched to 2D!")
            break
        img.save(f"/tmp/enter_{i}.png")

    snap(driver, "/tmp/after_enter_attempts.png")

    # Try SelectTwoDBoard with the Activity (y=122)
    print(f"\nRunning SelectTwoDBoard (y=122)...")
    try:
        runner.run(driver, [SelectTwoDBoard()], ctx=ctx)
        print("SelectTwoDBoard: OK")
    except RuntimeError as e:
        print(f"SelectTwoDBoard: FAIL — {e}")

    time.sleep(2)
    img1 = snap(driver, "/tmp/after_select2d.png")
    is2d, frac2d = check_2d(img1)
    print(f"  After SelectTwoDBoard: 2D={is2d} frac={frac2d:.3f}")

    if is2d:
        print("\nSuccess: 2D mode active. Running StartNewGame...")
        runner.run(driver, [StartNewGame()], ctx=ctx)
        time.sleep(8)
        snap(driver, "/tmp/after_newgame_2d_final.png")
    else:
        print("\nStill not in 2D mode. Taking screenshot for analysis.")
        snap(driver, "/tmp/still_3d.png")


if __name__ == "__main__":
    main()
