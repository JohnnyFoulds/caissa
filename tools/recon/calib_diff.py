#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Calibrate click coordinates via diff-based detection.
Before/after screenshot diff shows where the selection box appeared.
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


def diff_center(before, after, threshold=20):
    """Find center of changed pixels between two screenshots."""
    arr_b = np.array(before.convert("RGB")).astype(int)
    arr_a = np.array(after.convert("RGB")).astype(int)
    diff = np.abs(arr_a - arr_b).max(axis=2)
    ys, xs = np.where(diff > threshold)
    if len(xs) < 10:
        return None, 0
    cx = int(xs.mean())
    cy = int(ys.mean())
    return (cx, cy - _TITLE_BAR_H), len(xs)  # amiga coords


def click_and_diff(driver, code_x, code_y, label):
    """Click, diff, report actual position, deselect."""
    baseline = driver.screenshot()
    driver.click(code_x, code_y)
    time.sleep(0.5)
    after = driver.screenshot()
    after.save(f"/tmp/cdiff_{label}.png")

    center, npx = diff_center(baseline, after)
    if center and npx >= 10:
        ax, ay = center
        print(f"  {label}: code=({code_x},{code_y}) → diff_center=({ax},{ay}) "
              f"[{npx}px changed] error=({ax-code_x},{ay-code_y})")
    else:
        print(f"  {label}: code=({code_x},{code_y}) → NO change detected ({npx}px)")

    # Deselect (click same position)
    driver.click(code_x, code_y)
    time.sleep(0.4)
    return center


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    print(f"HOME_X={driver._HOME_X}\n")

    # Click each square in rank 1 and rank 2
    print("Rank 1 (a1..h1):")
    for col in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        click_and_diff(driver, _COL_X[col], _RANK_Y["1"], f"{col}1")
        time.sleep(0.3)

    print("\nRank 2 (d2, e2):")
    for col in ["d", "e"]:
        click_and_diff(driver, _COL_X[col], _RANK_Y["2"], f"{col}2")
        time.sleep(0.3)

    print("\nDone.")


if __name__ == "__main__":
    main()
