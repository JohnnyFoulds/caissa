#!/usr/bin/env /opt/homebrew/bin/python3.14
"""Take a quick board screenshot."""
import sys, types, time
from pathlib import Path
_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")
p = FsUaeProcess(CONFIG)
d = FsUaeDriver(p)
d.wake_sdl2()
img = d.screenshot()
img.save("/tmp/board_state_check.png")
print("saved /tmp/board_state_check.png")
