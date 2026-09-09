#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Measure actual home cursor position by clicking AT the home position
(after home_cursor) and seeing which square gets selected.
Strategy:
  1. home_cursor() — cursor goes to HOME
  2. send ZERO delta events (just click at current position)
  3. take screenshot and see which square got selected
"""

import sys, types, time
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

import logging
logging.basicConfig(level=logging.WARNING)
import Quartz

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.BattleChess import _TITLE_BAR_H

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")

p = FsUaeProcess(CONFIG)
d = FsUaeDriver(p)
d.wake_sdl2()

# Start fresh
img_before = d.screenshot()
img_before.save("/tmp/home_before.png")
arr_before = np.array(img_before.convert("RGB")).astype(int)

# Run home_cursor manually
print("Calling home_cursor()...")
d.home_cursor()
time.sleep(0.1)

# Click at the HOME position (send NO extra deltas, just click where cursor is)
print("Clicking at current (home) position...")
pt = Quartz.CGPoint(1000.0, 400.0)
for ev_type in [Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp]:
    ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    time.sleep(0.05)
time.sleep(0.5)

img_after = d.screenshot()
img_after.save("/tmp/home_after.png")
arr_after = np.array(img_after.convert("RGB")).astype(int)

# Diff to find where the selection appeared
diff = np.abs(arr_after - arr_before).max(axis=2)
threshold = 20
ys, xs = np.where(diff > threshold)

if len(xs) >= 10:
    cx = int(xs.mean())
    cy = int(ys.mean())
    amiga_x = cx
    amiga_y = cy - _TITLE_BAR_H
    print(f"Home position from diff: screenshot({cx},{cy}) → amiga({amiga_x},{amiga_y})")
    print(f"Currently coded HOME_X={d._HOME_X}, HOME_Y={d._HOME_Y}")
    print(f"Error: ({amiga_x - d._HOME_X}, {amiga_y - d._HOME_Y})")
else:
    print(f"No change detected ({len(xs)} px diff) — click may have missed board")
    print("Check /tmp/home_before.png and /tmp/home_after.png")

# Deselect
d.click(amiga_x if len(xs)>=10 else 50, amiga_y if len(xs)>=10 else 50)
