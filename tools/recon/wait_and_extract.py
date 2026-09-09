#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Board is at e2-e4 played, AI is thinking.
Wait for AI move then extract it.
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
from Code.Amiga.Activities import AmigaRunner, WaitForComputerReply, ExtractComputerMove

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")


def snap(driver, path):
    img = driver.screenshot(); img.save(path); print(f"  → {path}"); return img


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")

    # Capture current board as the "after our move" baseline
    baseline = driver.screenshot()
    baseline.save("/tmp/wait_baseline.png")
    print("Baseline (after e2-e4) → /tmp/wait_baseline.png")

    ctx = {
        "after_our_move": baseline,
        "our_from_sq": "e2",
        "our_to_sq": "e4",
    }

    print("Waiting for AI move (up to 120s)...")
    try:
        runner.run(driver, [WaitForComputerReply(), ExtractComputerMove()], ctx=ctx)
        move = ctx.get("computer_move")
        print(f"AI move: {move}")
        snap(driver, "/tmp/after_ai_reply.png")
        if move:
            print(f"SUCCESS! Corpus entry: 1.e4 → AI plays {move}")
        else:
            print("FAIL: no move in context")
    except RuntimeError as e:
        print(f"FAIL: {e}")
        snap(driver, "/tmp/wait_fail2.png")


if __name__ == "__main__":
    main()
