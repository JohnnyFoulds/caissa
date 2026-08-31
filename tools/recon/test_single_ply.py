#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Single-ply chain test: StartNewGame → PlayMove(e2e4) → WaitForComputerReply → ExtractComputerMove.

Tests the full corpus-recording pipeline for one move before running multi-ply.
Run with FS-UAE running and Battle Chess 2D board visible.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import (
    AmigaRunner, StartNewGame, PlayMove,
    WaitForComputerReply, ExtractComputerMove,
)

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    if not process.is_running:
        print("ERROR: FS-UAE is not running")
        sys.exit(1)

    driver = FsUaeDriver(process)
    driver.wake_sdl2()
    time.sleep(0.5)

    activities = [
        StartNewGame(),
        PlayMove("e2", "e4"),
        WaitForComputerReply(),
        ExtractComputerMove(),
    ]

    runner = AmigaRunner(save_dir="/tmp")
    try:
        ctx = runner.run(driver, activities)
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)

    move = ctx.get("computer_move")
    print(f"\n=== RESULT ===")
    print(f"Our move:       e2e4")
    print(f"Computer reply: {move}")
    print(f"ctx keys: {list(ctx.keys())}")

    after = driver.screenshot()
    after.save("/tmp/test_single_ply_final.png")
    print("final screenshot → /tmp/test_single_ply_final.png")


if __name__ == "__main__":
    main()
