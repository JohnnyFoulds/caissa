import json
import os

import Code
from Code.Main import InitApp
from Code.QT import IconosBase


def _hex_to_argb(hex_str: str) -> int:
    """Convert #RRGGBB to Qt's packed 0xAARRGGBB integer (full opacity)."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0xFF << 24) | (r << 16) | (g << 8) | b


def load_themes() -> list:
    """Return sorted list of theme dicts loaded from Resources/CaissaThemes/*.json."""
    folder = Code.path_resource("CaissaThemes")
    themes = []
    if not os.path.isdir(folder):
        return themes
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(folder, fname), encoding="utf-8") as f:
                    themes.append(json.load(f))
            except Exception:
                pass
    return themes


def find_theme(name: str) -> dict | None:
    for t in load_themes():
        if t.get("name") == name:
            return t
    return None


def _apply_board(config_board, theme: dict):
    """Apply board colors and piece set from theme to config_board."""
    board_colors = theme.get("board")
    if board_colors:
        o_tema = config_board.grabaTema()
        color_map = {
            "light_squares": "x_colorBlancas",
            "dark_squares":  "x_colorNegras",
            "exterior":      "x_colorExterior",
            "text":          "x_colorTexto",
            "border":        "x_colorFrontera",
        }
        for json_key, tema_key in color_map.items():
            if board_colors.get(json_key):
                o_tema[tema_key] = _hex_to_argb(board_colors[json_key])
        config_board.leeTema(o_tema)

    pieces = theme.get("pieces")
    if pieces:
        config_board.change_the_pieces(pieces)


def apply_theme(name: str):
    """Atomically apply a named Caissa theme: chrome, icons, board colors, pieces."""
    theme = find_theme(name)
    if theme is None:
        return

    conf = Code.configuration

    # -- chrome --
    if theme.get("style"):
        conf.x_style_mode = theme["style"]
    if theme.get("icons"):
        conf.x_style_icons = getattr(
            IconosBase.icons, theme["icons"], IconosBase.icons.NORMAL
        )
    conf.x_caissa_theme = name
    conf.graba()

    InitApp.apply_live_style(conf)

    # -- board (colors + pieces) --
    if (theme.get("board") or theme.get("pieces")) and Code.procesador:
        board = getattr(Code.procesador, "board", None)
        if board and hasattr(board, "config_board"):
            _apply_board(board.config_board, theme)
            board.config_board.guardaEnDisco()
            board.draw_window()
