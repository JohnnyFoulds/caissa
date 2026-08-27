#!/usr/bin/env python3
"""
render_codicons.py — render VS Code codicon SVGs to 32×32 PNGs for the vscode icon pack.

Run from bin/_genicons/:
    QT_QPA_PLATFORM=offscreen python3 render_codicons.py
"""
import os
import sys

from PIL import Image
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

CODICONS_DIR = os.path.expanduser(
    "~/.vscode/extensions/swiftlang.swift-vscode-2.16.7"
    "/node_modules/@vscode/codicons/src/icons/"
)
OUT_DIR = os.path.join(os.path.dirname(__file__), "overrides", "vscode")
SIZE = 32

# VS Code dark-theme icon colour: light grey, matching _tint_vscode white endpoint
ICON_COLOR = (212, 212, 212)

ICONS = [
    "check",
    "close",
    "save",
    "save-as",
    "folder-opened",
    "copy",
    "clippy",
    "trash",
    "discard",
    "add",
    "edit",
    "insert",
    "debug-step-back",
    "triangle-left",
    "triangle-right",
    "chevron-left",
    "chevron-right",
    "arrow-up",
    "arrow-down",
    "debug-pause",
    "debug-continue",
    "dash",
    "refresh",
    "search",
    "filter",
    "eye",
    "question",
    "database",
    "library",
    "tag",
    "history",
    "star-full",
    "gear",
    "target",
]


def render_icon(name: str) -> bool:
    svg_path = os.path.join(CODICONS_DIR, f"{name}.svg")
    out_path = os.path.join(OUT_DIR, f"{name}.png")

    if not os.path.isfile(svg_path):
        print(f"  MISSING svg: {name}", file=sys.stderr)
        return False

    renderer = QSvgRenderer(svg_path)
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    # Save to a temp file then load with PIL (QImage.save needs QIODevice or filepath)
    tmp_path = out_path + ".tmp.png"
    img.save(tmp_path)

    pil_img = Image.open(tmp_path).convert("RGBA")
    os.remove(tmp_path)
    _, _, _, alpha = pil_img.split()

    # Codicons render as black fills; replace RGB with light grey, keep alpha for shape
    colored = Image.new("RGBA", pil_img.size, (*ICON_COLOR, 255))
    colored.putalpha(alpha)
    colored.save(out_path)
    return True


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    os.makedirs(OUT_DIR, exist_ok=True)
    ok = skip = 0
    for name in ICONS:
        out_path = os.path.join(OUT_DIR, f"{name}.png")
        if os.path.isfile(out_path):
            print(f"  skip (exists): {name}.png")
            skip += 1
            continue
        if render_icon(name):
            print(f"  rendered: {name}.png")
            ok += 1
        else:
            skip += 1

    print(f"\nDone: {ok} rendered, {skip} skipped.")


if __name__ == "__main__":
    main()
