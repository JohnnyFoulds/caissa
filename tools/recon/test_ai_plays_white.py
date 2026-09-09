#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Verify the AI-as-White flow: SetAmigaPlaysRed → StartNewGame → WaitForComputerReply → ExtractComputerMove.
If SetAmigaPlaysRed worked, the AI should automatically play a White opening move.
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
from Code.Amiga.Activities import (
    AmigaRunner, StartNewGame, SetAmigaPlaysRed, SetHumanPlaysRed,
    WaitForComputerReply, ExtractComputerMove,
)

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}

    print("SetAmigaPlaysRed + StartNewGame...")
    runner.run(driver, [SetAmigaPlaysRed(), StartNewGame()], ctx=ctx)
    print("Done. Waiting for AI White move...")

    img = driver.screenshot()
    img.save("/tmp/after_newgame_amiga_white.png")
    print("screenshot → /tmp/after_newgame_amiga_white.png")

    runner.run(driver, [WaitForComputerReply(), ExtractComputerMove()], ctx=ctx)

    move = ctx.get("computer_move")
    if move:
        print(f"AI White move: {move}")
        img2 = driver.screenshot()
        img2.save("/tmp/after_ai_white_move.png")
        print("screenshot → /tmp/after_ai_white_move.png")
    else:
        print("FAIL: no move extracted")

    print("Restoring Human Plays Red...")
    runner.run(driver, [SetHumanPlaysRed()], ctx=ctx)
    print("Done.")


if __name__ == "__main__":
    main()
