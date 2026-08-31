#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Isolation test for PlayMove — Activity development protocol step 3.

Runs ONLY PlayMove("e2", "e4") against the live FS-UAE instance and reports
whether the activity succeeds.  Run this BEFORE chaining PlayMove into a workflow.

Usage (FS-UAE must already be running with Battle Chess 2D board visible):
    /opt/homebrew/bin/python3.14 tools/recon/test_play_move_isolation.py
"""

import sys
import types
import logging
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))

# Prevent Code/__init__.py from executing (imports psutil/charset_normalizer
# which are not available under python3.14 on this machine).
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import AmigaRunner, PlayMove

CONFIG = _REPO / "BattleChess-ADF.fs-uae"


def main():
    process = FsUaeProcess(CONFIG)
    if not process.is_running:
        print("ERROR: FS-UAE is not running — start it first")
        sys.exit(1)

    driver = FsUaeDriver(process)

    # Wake SDL2 once
    driver.wake_sdl2()
    time.sleep(0.5)

    # Capture baseline screenshot before the test
    before = driver.screenshot()
    before.save("/tmp/test_play_move_before.png")
    print("baseline screenshot → /tmp/test_play_move_before.png")

    runner = AmigaRunner(save_dir="/tmp")
    try:
        ctx = runner.run(driver, [PlayMove("e2", "e4")])
        print("PlayMove(e2→e4): SUCCESS")
        print(f"ctx keys: {list(ctx.keys())}")
    except RuntimeError as exc:
        print(f"PlayMove(e2→e4): FAILED — {exc}")
        sys.exit(1)

    after = driver.screenshot()
    after.save("/tmp/test_play_move_after.png")
    print("post-move screenshot → /tmp/test_play_move_after.png")


if __name__ == "__main__":
    main()
