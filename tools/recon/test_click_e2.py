#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Minimal diagnostic: click e2 ONCE and take a screenshot to see where the click lands.
Also try clicking on the board center first to clear any existing selection.
"""

import sys, types, time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.BattleChess import _COL_X, _RANK_Y

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

p = FsUaeProcess(CONFIG)
d = FsUaeDriver(p)

# Don't use wake_sdl2 — just use home_cursor directly inside click
img0 = d.screenshot()
img0.save("/tmp/diag0_before.png")
print("Before: saved /tmp/diag0_before.png")

# Click e4 first — clear any stale selection (empty square, deselects)
e4x, e4y = _COL_X["e"], _RANK_Y["4"]
print(f"Clicking e4 ({e4x},{e4y}) to clear selection...")
d.click(e4x, e4y)
time.sleep(0.3)
img1 = d.screenshot()
img1.save("/tmp/diag1_after_e4.png")
print("After e4 click: saved /tmp/diag1_after_e4.png")

# Now click e2
e2x, e2y = _COL_X["e"], _RANK_Y["2"]
print(f"Clicking e2 ({e2x},{e2y})...")
d.click(e2x, e2y)
time.sleep(0.3)
img2 = d.screenshot()
img2.save("/tmp/diag2_after_e2.png")
print("After e2 click: saved /tmp/diag2_after_e2.png")

# Now click e4
print(f"Clicking e4 ({e4x},{e4y})...")
d.click(e4x, e4y)
time.sleep(0.5)
img3 = d.screenshot()
img3.save("/tmp/diag3_after_e4_move.png")
print("After e4 click: saved /tmp/diag3_after_e4_move.png")

print("Done — check images for selection box position.")
