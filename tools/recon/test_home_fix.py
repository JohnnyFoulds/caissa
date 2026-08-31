#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Verify _HOME_X=45 fix. Click g1 (x=423) — should select the knight.
Then deselect, click d2 (x=299) — should select the d2 pawn.
Takes screenshots at each step.
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.BattleChess import _COL_X, _RANK_Y

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def snap(driver, path):
    img = driver.screenshot()
    img.save(path)
    print(f"  → {path}")
    return img


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    snap(driver, "/tmp/fix_start.png")
    print(f"HOME_X={driver._HOME_X}, HOME_Y={driver._HOME_Y}")
    print(f"g1: x={_COL_X['g']}, y={_RANK_Y['1']}")
    print(f"d2: x={_COL_X['d']}, y={_RANK_Y['2']}")

    # Click g1 to select knight
    print("\nClicking g1 (knight)...")
    gx, gy = _COL_X["g"], _RANK_Y["1"]
    driver.click(gx, gy)
    time.sleep(0.5)
    snap(driver, "/tmp/fix_g1_click.png")

    # Click g1 again to deselect
    print("Clicking g1 again to deselect...")
    driver.click(gx, gy)
    time.sleep(0.5)
    snap(driver, "/tmp/fix_g1_deselect.png")

    # Click d2 to select pawn (board at 1.e4 e5, d2 has a pawn)
    print("Clicking d2 (pawn)...")
    dx, dy = _COL_X["d"], _RANK_Y["2"]
    driver.click(dx, dy)
    time.sleep(0.5)
    snap(driver, "/tmp/fix_d2_click.png")

    # Deselect
    print("Clicking d2 again to deselect...")
    driver.click(dx, dy)
    time.sleep(0.5)
    snap(driver, "/tmp/fix_d2_deselect.png")

    print("\nDone. Check /tmp/fix_g1_click.png and /tmp/fix_d2_click.png for selection boxes.")


if __name__ == "__main__":
    main()
