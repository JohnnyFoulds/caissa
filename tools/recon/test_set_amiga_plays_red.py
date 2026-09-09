#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Isolation test for SetAmigaPlaysRed (UiPath Test Activity protocol).
1. StartNewGame (confirm board visible)
2. SetAmigaPlaysRed (navigate second menu, select Amiga Plays Red)
3. Screenshot → /tmp/after_set_amiga_plays_red.png
4. Verify manually: screenshot should show "Amiga Plays Red" with + marker in the menu
   (or simply verify the board is still visible after the menu navigation).
"""

import sys
import types
import logging
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, StartNewGame, SetAmigaPlaysRed

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}
    print("Running StartNewGame...")
    runner.run(driver, [StartNewGame()], ctx=ctx)
    print("StartNewGame: SUCCESS")

    print("Running SetAmigaPlaysRed...")
    runner.run(driver, [SetAmigaPlaysRed()], ctx=ctx)
    print("SetAmigaPlaysRed: SUCCESS")

    img = driver.screenshot()
    img.save("/tmp/after_set_amiga_plays_red.png")
    print("screenshot → /tmp/after_set_amiga_plays_red.png")
    print("Check screenshot: board should be visible, Amiga Plays Red menu item selected.")


if __name__ == "__main__":
    main()
