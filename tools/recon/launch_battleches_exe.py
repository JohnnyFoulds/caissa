#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
The BattleChess disk window is open. Double-click the BattleChess
executable icon (inside the window) to launch the game.
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

import numpy as np
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

# BattleChess exe icon inside the disk window
# Screenshot shows icon at approximately (280, 165) → Amiga content (280, 133)
_EXE_X = 280
_EXE_Y = 155  # slightly above icon center to hit the icon not the label


def screenshot_and_save(driver, path):
    img = driver.screenshot()
    img.save(path)
    print(f"  → {path}")
    return img


def board_visible(img):
    arr = np.array(img.convert("RGB"))
    tb = 32
    crop = arr[tb + 38:tb + 379, 100:443]
    h, w = crop.shape[:2]
    olive = ((crop[:,:,0] > 130) & (crop[:,:,0] < 220) &
             (crop[:,:,1] > 150) & (crop[:,:,1] < 230) &
             (crop[:,:,2] < 120))
    frac = olive.sum() / (h * w)
    return frac > 0.05, frac


def wait_for_board(driver, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        img = driver.screenshot()
        visible, frac = board_visible(img)
        print(f"  olive frac = {frac:.3f}")
        if visible:
            return img
        time.sleep(5)
    return None


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    screenshot_and_save(driver, "/tmp/before_exe_launch.png")

    print(f"Double-clicking BattleChess exe at ({_EXE_X}, {_EXE_Y})...")
    driver.double_click(_EXE_X, _EXE_Y)
    time.sleep(3)
    screenshot_and_save(driver, "/tmp/after_exe_doubleclick.png")

    print("Waiting for game board (up to 120s)...")
    img = wait_for_board(driver, timeout=120)
    if img is None:
        screenshot_and_save(driver, "/tmp/exe_launch_timeout.png")
        print("ERROR: board not visible after 120s")
        return

    time.sleep(3)
    screenshot_and_save(driver, "/tmp/game_loaded.png")
    print("Game loaded!")

    # Test StartNewGame with ChessSaves disk
    print("\nTesting StartNewGame (ChessSaves disk on DF1)...")
    from Code.Amiga.Activities import AmigaRunner, StartNewGame
    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    runner.run(driver, [StartNewGame()], ctx=ctx)

    time.sleep(8)
    screenshot_and_save(driver, "/tmp/after_newgame_with_saves.png")
    print("Done! Is board at startpos? No dialog?")


if __name__ == "__main__":
    main()
