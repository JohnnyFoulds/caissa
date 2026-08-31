#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Restart FS-UAE (now with ChessSaves.adf on DF1) and test that StartNewGame
no longer shows the 'Insert ChessSaves disk' dialog.
"""

import sys
import types
import time
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

_BOARD_REGION = (100, 38, 443, 379)  # left, top, right, bottom in Amiga content


def screenshot_and_save(driver, path):
    img = driver.screenshot()
    img.save(path)
    print(f"  → {path}")
    return img


def board_visible(driver):
    """Return True if board-coloured pixels exceed threshold (game is on screen)."""
    import numpy as np
    try:
        img = driver.screenshot()
        arr = np.array(img.convert("RGB"))
        # Crop to title-bar-adjusted board region
        tb = 32  # title bar
        r = _BOARD_REGION
        crop = arr[tb + r[1]:tb + r[3], r[0]:r[2]]
        h, w = crop.shape[:2]
        # Board squares: yellowish-green (olive). R~170, G~190, B~80
        olive = ((crop[:,:,0] > 130) & (crop[:,:,0] < 220) &
                 (crop[:,:,1] > 150) & (crop[:,:,1] < 230) &
                 (crop[:,:,2] < 120))
        frac = olive.sum() / (h * w)
        print(f"  board_visible: olive frac = {frac:.3f}")
        return frac > 0.05
    except Exception as e:
        print(f"  board_visible error: {e}")
        return False


def wait_for_board(driver, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if board_visible(driver):
            return True
        time.sleep(5)
    return False


def kill_fsuae():
    result = subprocess.run(["pkill", "-f", "fs-uae"], capture_output=True)
    print(f"pkill fs-uae: returncode={result.returncode}")
    time.sleep(3)


def main():
    # Take current state before killing
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    wid = process.window_number()
    if wid:
        screenshot_and_save(driver, "/tmp/before_restart.png")
        print(f"FS-UAE running (wid={wid}), taking screenshot then killing...")
    else:
        print("FS-UAE not running, launching fresh...")

    kill_fsuae()

    # Relaunch
    print(f"Launching FS-UAE with config: {CONFIG}")
    proc = subprocess.Popen(
        ["/opt/homebrew/bin/fs-uae", str(CONFIG)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  PID: {proc.pid}")
    print("Waiting 20s for window to appear...")
    time.sleep(20)

    process2 = FsUaeProcess(CONFIG)
    driver2 = FsUaeDriver(process2)

    screenshot_and_save(driver2, "/tmp/boot_20s.png")

    print("Waiting for board to be visible (up to 120s)...")
    if not wait_for_board(driver2, timeout=120):
        screenshot_and_save(driver2, "/tmp/board_timeout.png")
        print("ERROR: board not visible after 120s")
        return

    time.sleep(3)
    driver2.wake_sdl2()
    screenshot_and_save(driver2, "/tmp/board_ready.png")
    print("Board visible!")

    # Test StartNewGame
    print("\nTesting StartNewGame...")
    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    runner.run(driver2, [StartNewGame()], ctx=ctx)

    time.sleep(8)
    screenshot_and_save(driver2, "/tmp/after_newgame_fresh.png")
    print("Done! Is board at startpos?")


if __name__ == "__main__":
    main()
