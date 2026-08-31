#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
FS-UAE is at Workbench with ChessSaves + BattleChess icons.
Double-click BattleChess to launch, wait for board, then test StartNewGame.
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

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

import numpy as np
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

# BattleChess icon position with ChessSaves disk also mounted
# Two icons stack: ChessSaves ≈ (516, 38), BattleChess ≈ (516, 94) in Amiga content
_BATTLECHES_ICON_X = 516
_BATTLECHES_ICON_Y = 94  # adjusted down because ChessSaves icon is above it


def screenshot_and_save(driver, path):
    img = driver.screenshot()
    img.save(path)
    print(f"  → {path}")
    return img


def board_visible(img):
    arr = np.array(img.convert("RGB"))
    tb = 32
    # olive/yellow-green board squares
    crop = arr[tb + 38:tb + 379, 100:443]
    h, w = crop.shape[:2]
    olive = ((crop[:,:,0] > 130) & (crop[:,:,0] < 220) &
             (crop[:,:,1] > 150) & (crop[:,:,1] < 230) &
             (crop[:,:,2] < 120))
    frac = olive.sum() / (h * w)
    return frac > 0.05, frac


def wait_for_board(driver, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        img = driver.screenshot()
        visible, frac = board_visible(img)
        print(f"  olive frac = {frac:.3f}")
        if visible:
            return True
        time.sleep(5)
    return False


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    img0 = screenshot_and_save(driver, "/tmp/workbench_before_launch.png")
    v, f = board_visible(img0)
    print(f"Board visible before launch: {v} (frac={f:.3f})")

    if v:
        print("Board already visible — skipping launch step")
    else:
        print(f"Double-clicking BattleChess icon at ({_BATTLECHES_ICON_X}, {_BATTLECHES_ICON_Y})...")
        driver.double_click(_BATTLECHES_ICON_X, _BATTLECHES_ICON_Y)
        time.sleep(3)
        screenshot_and_save(driver, "/tmp/after_doubleclick.png")

        print("Waiting for board...")
        if not wait_for_board(driver, timeout=90):
            screenshot_and_save(driver, "/tmp/board_timeout.png")
            print("ERROR: board not visible after 90s")
            return

        time.sleep(3)

    screenshot_and_save(driver, "/tmp/board_ready.png")
    print("Game board ready!")

    # Test StartNewGame
    print("\nTesting StartNewGame (with ChessSaves disk on DF1)...")
    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    runner.run(driver, [StartNewGame()], ctx=ctx)

    time.sleep(8)
    screenshot_and_save(driver, "/tmp/after_newgame_with_saves_disk.png")
    print("Done! Check: startpos board? No 'Insert disk' dialog?")


if __name__ == "__main__":
    main()
