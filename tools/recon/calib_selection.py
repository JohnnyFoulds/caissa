#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Click each rank-1 square and detect selection box position.
Reports code_target → actual_selection_x to find the true coordinate offset.
After each click, clicks again to deselect before moving to next square.
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
import logging
logging.basicConfig(level=logging.WARNING)

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.BattleChess import _COL_X, _RANK_Y, _TITLE_BAR_H

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def find_selection_box(img):
    """Find blue or red selection box in the board area.
    Returns (cx, cy) of the selection box center in Amiga content coords,
    or None if not found.
    """
    arr = np.array(img.convert("RGB"))
    # Board region in screenshot coords
    # _BOARD_REGION = (155, 16, 331, 284) → left=155, top=16+32=48 in screenshot
    board_left = 155
    board_top = _TITLE_BAR_H + 16  # 48
    board_right = 155 + 331  # 486
    board_bot = _TITLE_BAR_H + 16 + 284  # 332

    crop = arr[board_top:board_bot, board_left:board_right]

    # Blue selection: high B, low R, low G
    blue = (crop[:,:,2] > 150) & (crop[:,:,0] < 100) & (crop[:,:,1] < 100)
    # Red/pink selection: high R, low-mid G, low-mid B
    red = (crop[:,:,0] > 180) & (crop[:,:,1] < 80) & (crop[:,:,2] < 80)

    for mask, color in [(blue, "blue"), (red, "red")]:
        ys, xs = np.where(mask)
        if len(xs) >= 5:
            cx = int(xs.mean()) + board_left  # screenshot x
            cy = int(ys.mean()) + board_top   # screenshot y
            amiga_x = cx  # screenshot x = amiga x (no horizontal offset)
            amiga_y = cy - _TITLE_BAR_H  # remove title bar
            return amiga_x, amiga_y, color, len(xs)

    return None


def click_and_detect(driver, code_x, code_y, label):
    """Click at (code_x, code_y), detect selection box, then deselect."""
    driver.click(code_x, code_y)
    time.sleep(0.4)
    img = driver.screenshot()
    result = find_selection_box(img)
    img.save(f"/tmp/calib_{label}.png")

    if result:
        ax, ay, color, npx = result
        print(f"  {label}: code=({code_x},{code_y}) → selection=({ax},{ay}) [{color}, {npx}px] "
              f"error=({ax-code_x},{ay-code_y})")
    else:
        print(f"  {label}: code=({code_x},{code_y}) → NO selection detected")

    # Deselect: click same square again
    driver.click(code_x, code_y)
    time.sleep(0.4)
    return result


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    print(f"HOME_X={driver._HOME_X}, HOME_Y={driver._HOME_Y}\n")

    # Click each rank-1 square (a1 through h1)
    print("Clicking rank-1 squares (code targets → actual selection):")
    for col in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        cx = _COL_X[col]
        cy = _RANK_Y["1"]
        click_and_detect(driver, cx, cy, f"{col}1")
        time.sleep(0.3)

    print("\nClicking rank-2 squares (a2 through h2):")
    for col in ["d", "e"]:
        cx = _COL_X[col]
        cy = _RANK_Y["2"]
        click_and_detect(driver, cx, cy, f"{col}2")
        time.sleep(0.3)

    print("\nDone. Check /tmp/calib_*.png for visual confirmation.")


if __name__ == "__main__":
    main()
