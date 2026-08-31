#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Test StartNewGame then wait 8s then PlayMove, to check if timing is the issue.
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
from Code.Amiga.Activities import AmigaRunner, StartNewGame, PlayMove

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")
    runner.run(driver, [StartNewGame()])
    print("StartNewGame done — waiting 8s before PlayMove")
    time.sleep(8.0)

    img = driver.screenshot()
    img.save("/tmp/before_playmove_after_wait.png")
    print("screenshot before PlayMove saved → /tmp/before_playmove_after_wait.png")

    runner2 = AmigaRunner(save_dir="/tmp")
    try:
        ctx = runner2.run(driver, [PlayMove("e2", "e4")])
        print("PlayMove(e2→e4): SUCCESS")
        after = driver.screenshot()
        after.save("/tmp/after_playmove_after_wait.png")
        print("after screenshot → /tmp/after_playmove_after_wait.png")
    except RuntimeError as exc:
        print(f"PlayMove FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
