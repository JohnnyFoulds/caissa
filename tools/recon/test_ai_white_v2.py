#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Isolation test v2: SetAmigaPlaysRed + SetHumanPlaysBlue → StartNewGame → wait for AI White move.
Uses corrected x=320 (straight up into Settings) and y=136/162.
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
    AmigaRunner, StartNewGame,
    SetAmigaPlaysRed, SetHumanPlaysBlue, SetHumanPlaysRed, SetAmigaPlaysBlue,
    WaitForComputerReply, ExtractComputerMove,
)

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}

    # Step 1: Set AI as White (Amiga Plays Red + Human Plays Blue)
    print("SetAmigaPlaysRed...")
    runner.run(driver, [SetAmigaPlaysRed()], ctx=ctx)
    img = driver.screenshot(); img.save("/tmp/after_set_amiga_red_v2.png")
    print("  → /tmp/after_set_amiga_red_v2.png")

    print("SetHumanPlaysBlue...")
    runner.run(driver, [SetHumanPlaysBlue()], ctx=ctx)
    img = driver.screenshot(); img.save("/tmp/after_set_human_blue.png")
    print("  → /tmp/after_set_human_blue.png")

    # Step 2: Start a new game — AI should play White automatically
    print("StartNewGame...")
    runner.run(driver, [StartNewGame()], ctx=ctx)
    img = driver.screenshot(); img.save("/tmp/after_newgame_ai_white_v2.png")
    print("  → /tmp/after_newgame_ai_white_v2.png")

    # Step 3: Wait for AI White move
    print("WaitForComputerReply + ExtractComputerMove...")
    try:
        runner.run(driver, [WaitForComputerReply(), ExtractComputerMove()], ctx=ctx)
        move = ctx.get("computer_move")
        print(f"AI White move: {move}")
        img = driver.screenshot(); img.save("/tmp/after_ai_white_move_v2.png")
        print("  → /tmp/after_ai_white_move_v2.png")
        print("SUCCESS!" if move else "FAIL: no move extracted")
    except RuntimeError as exc:
        print(f"FAIL: {exc}")

    # Restore defaults
    print("Restoring defaults (SetHumanPlaysRed + SetAmigaPlaysBlue)...")
    runner.run(driver, [SetHumanPlaysRed(), SetAmigaPlaysBlue()], ctx=ctx)
    print("Done.")


if __name__ == "__main__":
    main()
