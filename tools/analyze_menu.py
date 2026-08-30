#!/usr/bin/env python3
"""Pixel-analyze menu bar columns to detect which column is highlighted."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "bin"))

from PIL import Image
import numpy as np

MENU_Y1, MENU_Y2 = 33, 68

def analyze(name, path):
    arr = np.array(Image.open(path).convert('RGB'))
    bar = arr[MENU_Y1:MENU_Y2, :, :]
    bright = (bar[:,:,0] > 200) & (bar[:,:,1] > 200) & (bar[:,:,2] > 200)
    col_brightness = bar.mean(axis=(0, 2))
    top5 = sorted(np.argsort(col_brightness)[-5:].tolist())
    print(f"{name}: bright_px={int(bright.sum()):4d}  mean={col_brightness.mean():.1f}  top5x={top5}")

for probe_x in [100, 170, 240, 310, 370, 430]:
    p = f'/tmp/mx_{probe_x}.png'
    if Path(p).exists():
        analyze(f'x{probe_x}', p)

# Sample y=47 pixels
arr0 = np.array(Image.open('/tmp/mx_100.png').convert('RGB'))
print("\nPixels at y=47 (menu bar center):")
for x in range(80, 500, 40):
    r, g, b = int(arr0[47,x,0]), int(arr0[47,x,1]), int(arr0[47,x,2])
    print(f"  x={x}: ({r:3d},{g:3d},{b:3d})")
