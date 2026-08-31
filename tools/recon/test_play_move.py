#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Test PlayMove(e2, e4) on the 2D board at starting position.
This is the key test: do LMB clicks work for chess moves in Battle Chess Amiga?
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

import numpy as np
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import (
    AmigaRunner, PlayMove, WaitForComputerReply, ExtractComputerMove,
)

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def snap(driver, path):
    img = driver.screenshot(); img.save(path); print(f"  → {path}"); return img


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    img0 = snap(driver, "/tmp/before_e2e4.png")
    print(f"Board visible: brightness={float(np.array(img0.convert('RGB')).mean()):.1f}")

    runner = AmigaRunner(save_dir="/tmp")
    ctx = {}

    print("\nTesting PlayMove(e2, e4)...")
    try:
        runner.run(driver, [PlayMove("e2", "e4")], ctx=ctx)
        snap(driver, "/tmp/after_e2e4.png")
        print("PlayMove: OK — piece moved!")
    except RuntimeError as e:
        snap(driver, "/tmp/playmove_fail.png")
        print(f"PlayMove: FAIL — {e}")
        return

    print("\nWaiting for AI response...")
    try:
        runner.run(driver, [WaitForComputerReply(), ExtractComputerMove()], ctx=ctx)
        move = ctx.get("computer_move")
        print(f"AI move: {move}")
        snap(driver, "/tmp/after_ai_move.png")
        if move:
            print("SUCCESS! AI responded with a valid move.")
        else:
            print("FAIL: no move extracted from context")
    except RuntimeError as e:
        snap(driver, "/tmp/wait_fail.png")
        print(f"WaitForComputerReply/ExtractComputerMove: FAIL — {e}")


if __name__ == "__main__":
    main()
