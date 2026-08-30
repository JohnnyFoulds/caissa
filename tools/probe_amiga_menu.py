#!/usr/bin/env python3
"""
Calibrate FS-UAE menu navigation coordinates.
Uses kCGHIDEventTap (not CGEventPostToPid) with proper window-click focus.
"""
import subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bin"))

import Quartz

def find_fsuae():
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    for w in wins:
        if "fs-uae" in (w.get("kCGWindowOwnerName") or "").lower():
            b = w.get("kCGWindowBounds", {})
            return (int(w["kCGWindowNumber"]),
                    int(b["X"]), int(b["Y"]),
                    int(b["Width"]), int(b["Height"]))
    return None, 640, 308, 640, 432

WID, WX, WY, WW, WH = find_fsuae()
print(f"FS-UAE: WID={WID} @ ({WX},{WY}) size=({WW}x{WH})")

TAP = Quartz.kCGHIDEventTap

def post(ev_type, rx, ry, btn=Quartz.kCGMouseButtonRight):
    pt = Quartz.CGPoint(WX + rx, WY + ry)
    ev = Quartz.CGEventCreateMouseEvent(None, ev_type, pt, btn)
    Quartz.CGEventPost(TAP, ev)

def move(rx, ry):
    Quartz.CGWarpMouseCursorPosition((WX + rx, WY + ry))
    post(Quartz.kCGEventMouseMoved, rx, ry, Quartz.kCGMouseButtonLeft)

def left_click(rx, ry):
    post(Quartz.kCGEventLeftMouseDown, rx, ry, Quartz.kCGMouseButtonLeft)
    time.sleep(0.05)
    post(Quartz.kCGEventLeftMouseUp,   rx, ry, Quartz.kCGMouseButtonLeft)

def shot(name):
    subprocess.run(["screencapture", "-x", "-o", "-l", str(WID), f"/tmp/{name}"],
                   capture_output=True)

# Focus FS-UAE via left-click on window centre (works when bundle ID is empty)
print("Focusing FS-UAE via window click...")
left_click(WW // 2, WH // 2)
time.sleep(0.5)

# Cursor-enter event to game area
move(WW // 2, WH // 2)
time.sleep(0.4)

MENU_Y = 33    # same as DOS version: 28px title bar + 5px into game content

print(f"\nProbing x positions at MENU_Y={MENU_Y}...")
for test_x in [100, 160, 220, 280, 330, 370, 430]:
    print(f"  x={test_x} ...", end="", flush=True)
    move(test_x, MENU_Y)
    time.sleep(0.35)
    post(Quartz.kCGEventRightMouseDown, test_x, MENU_Y)
    time.sleep(0.8)    # hold: let submenu fully render
    shot(f"col_{test_x}.png")
    post(Quartz.kCGEventRightMouseUp, test_x, MENU_Y)
    time.sleep(0.6)
    print(" done")

print("\nAll screenshots at /tmp/col_*.png")
