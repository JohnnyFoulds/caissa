#!/usr/bin/env /opt/homebrew/bin/python3.14
"""Start a new game to reset board to initial position."""
import sys, types, time
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
from Code.Amiga.Activities import AmigaRunner, StartNewGame
CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")
p = FsUaeProcess(CONFIG)
d = FsUaeDriver(p)
d.wake_sdl2()
runner = AmigaRunner(save_dir="/tmp")
ctx = {}
print("Starting new game...")
runner.run(d, [StartNewGame()], ctx=ctx)
time.sleep(10)
img = d.screenshot()
img.save("/tmp/new_game_board.png")
print("Done — see /tmp/new_game_board.png")
