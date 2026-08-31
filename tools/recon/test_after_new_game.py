#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Diagnose state after StartNewGame: take screenshots at 0s, 2s, 5s after completion.
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
from Code.Amiga.Activities import AmigaRunner, StartNewGame

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()

    runner = AmigaRunner(save_dir="/tmp")
    runner.run(driver, [StartNewGame()])
    print("StartNewGame done")

    img0 = driver.screenshot(); img0.save("/tmp/after_newgame_0s.png"); print("0s screenshot saved")
    time.sleep(2.0)
    img2 = driver.screenshot(); img2.save("/tmp/after_newgame_2s.png"); print("2s screenshot saved")
    time.sleep(3.0)
    img5 = driver.screenshot(); img5.save("/tmp/after_newgame_5s.png"); print("5s screenshot saved")


if __name__ == "__main__":
    main()
