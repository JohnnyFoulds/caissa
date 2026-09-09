#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Measure actual cursor position after _move_to_amiga for several target squares.
Reports where the cursor actually lands using _cursor_pos().
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
logging.basicConfig(level=logging.INFO)

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.BattleChess import _COL_X, _RANK_Y, _TITLE_BAR_H

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def measure(driver, amiga_x, amiga_y, label):
    driver._move_to_amiga(amiga_x, amiga_y)
    time.sleep(0.2)
    img = driver.screenshot()
    pos = driver._cursor_pos(img)
    if pos is not None:
        # Convert screenshot coords to amiga content coords
        actual_x = pos[0]
        actual_y = pos[1] - _TITLE_BAR_H
        print(f"  {label}: target=({amiga_x},{amiga_y}) "
              f"cursor_screenshot={pos} → amiga=({actual_x},{actual_y}) "
              f"error=({actual_x-amiga_x},{actual_y-amiga_y})")
    else:
        print(f"  {label}: target=({amiga_x},{amiga_y}) — cursor NOT detected")
    return img


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    print(f"HOME_X={driver._HOME_X}, HOME_Y={driver._HOME_Y}")
    print(f"_TITLE_BAR_H={_TITLE_BAR_H}")

    # First, home the cursor and measure home position
    driver.home_cursor()
    time.sleep(0.3)
    img = driver.screenshot()
    pos = driver._cursor_pos(img)
    if pos:
        ax, ay = pos[0], pos[1] - _TITLE_BAR_H
        print(f"\nHome position: cursor_screenshot={pos} → amiga=({ax},{ay})")
    else:
        print("\nHome position: cursor NOT detected")

    print("\nMeasuring target squares:")
    targets = [
        (_COL_X["a"], _RANK_Y["1"], "a1"),
        (_COL_X["d"], _RANK_Y["2"], "d2"),
        (_COL_X["e"], _RANK_Y["2"], "e2"),
        (_COL_X["g"], _RANK_Y["1"], "g1"),
        (_COL_X["h"], _RANK_Y["1"], "h1"),
    ]
    for ax, ay, label in targets:
        measure(driver, ax, ay, label)

    print("\nDone. HOME_X may need further adjustment if errors are large.")


if __name__ == "__main__":
    main()
