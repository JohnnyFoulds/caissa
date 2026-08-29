"""
tools/design/fritz_compare.py — Pillow-based Fritz ribbon comparison renderer.

Renders Caissa Fritz ribbon mockups for all tabs using Pillow.  The output is
a stacked-panel PNG showing every tab's ribbon content plus the File backstage
panel.  Used as the design-iteration tool *before* implementing QSS / WRibbon.

Workflow
────────
    python3 tools/design/fritz_compare.py
    # opens ~/Pictures/fritz-reference/caissa_all_tabs.png

Ribbon design decisions (from Fritz 18 manual, pages 31-35, 62-63, 73):
  - Group captions appear BELOW the content area with NO separator line above them.
  - Caption text is dark (~#444), NOT gray.
  - Buttons have NO visible border at rest (flat, border only on hover).
  - Buttons with ▼ indicate a dropdown submenu opens on click.
  - Resign / Offer Draw / Abort are individual flat icon buttons (NOT radio buttons).
  - Hint / Suggestion are action buttons in the Help menu (NOT radio buttons).
  - Fritz group names are category names ("Play", "Game") not action names.
  - Dropdown open = floating panel below button, thin border + item list.
  - Tabs: File (blue), Home, Board, Analysis, Engine, View.
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── colours (pixel-sampled from Fritz 18 screenshots) ─────────────────────────
BG         = "#efeff2"   # ribbon background (near-white, slight blue-grey)
FILE_BLUE  = "#005b99"   # File tab button fill
FILE_TEXT  = "#ffffff"
TAB_TEXT   = "#222222"
SEL_ACCENT = "#0060b0"   # blue bar under selected tab
SEP_LINE   = "#c4c4c8"   # vertical group separators + tab hairlines
CAP_TEXT   = "#444444"   # group caption text (NOT gray — Fritz uses dark)
ICON_DARK  = "#444444"
ICON_BLUE  = "#005a9e"
ICON_RED   = "#b33a00"
ICON_GREEN = "#2a7a2a"
ICON_AMBER = "#8a5c00"
PANE_CHECK = "#0060b0"
DROP_BG    = "#ffffff"   # dropdown panel background
DROP_BORDER= "#b0b0b8"   # dropdown panel border
DROP_HOVER = "#e0e8f4"   # highlighted item in dropdown
DROP_HEAD  = "#005b99"   # dropdown header bar (same as File tab)
BTN_ACTIVE = "#0060b0"   # large button active/toggled fill
BTN_ACTIVE_TEXT = "#ffffff"
DISABLED   = "#aaaaaa"   # greyed-out button text

# ── tab list (in ribbon order; File is always first and blue) ─────────────────
TABS = ["Home", "Board", "Analysis", "Engine", "View"]

# ── logical geometry (1× pixel units) ────────────────────────────────────────
W      = 820
TAB_H  = 26
CONT_H = 84
CAP_H  = 20
H      = TAB_H + CONT_H + CAP_H   # 130 px

# ── supersampling (2× render → LANCZOS scale-down for crisp text) ─────────────
SCALE = 2


def _font(logical_size):
    size = logical_size * SCALE
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/SFNSText.ttf",
              "/System/Library/Fonts/Geneva.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


F_SM  = _font(9)
F_MED = _font(10)
F_TAB = _font(11)
F_CAP = _font(9)
F_LBL = _font(12)   # sheet section labels


def S(x):
    """Convert logical 1× coordinate to 2× canvas coordinate."""
    return int(x * SCALE)


# ── draw helpers ───────────────────────────────────────────────────────────────

def center_text(draw, text, font, x0, x1, y, fill="#222222"):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text(((x0 + x1 - tw) // 2, y), text, font=font, fill=fill)


def text_w(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


# ── icon primitives ────────────────────────────────────────────────────────────

def draw_pawn(draw, cx, cy, size, color=ICON_BLUE):
    s = size // 2
    draw.ellipse([cx-s, cy+s//2, cx+s, cy+s], fill=color)
    draw.rectangle([cx-s//3, cy-s//4, cx+s//3, cy+s//2], fill=color)
    draw.ellipse([cx-s//2, cy-s, cx+s//2, cy-s//4], fill=color)


def draw_flag(draw, cx, cy, size, color=ICON_RED):
    s = size // 2
    draw.line([(cx-s//2, cy+s), (cx-s//2, cy-s)], fill=color, width=S(2))
    draw.polygon([(cx-s//2, cy-s), (cx+s, cy-s//3), (cx-s//2, cy+s//4)], fill=color)


def draw_circle_half(draw, cx, cy, size, color=ICON_GREEN):
    s = size // 2
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], outline=color, width=S(2))
    draw.line([(cx-s+S(2), cy), (cx+s-S(2), cy)], fill=color, width=S(2))


def draw_king(draw, cx, cy, size, color=ICON_DARK):
    s = size // 2
    draw.rectangle([cx-S(1), cy-s, cx+S(1), cy-s+S(6)], fill=color)
    draw.rectangle([cx-S(3), cy-s+S(2), cx+S(3), cy-s+S(4)], fill=color)
    draw.polygon([(cx-s//2, cy+s), (cx+s//2, cy+s),
                  (cx+s//3, cy-s+S(8)), (cx-s//3, cy-s+S(8))], fill=color)


def draw_back_arrow(draw, cx, cy, size, color=ICON_DARK):
    s = size // 2
    draw.polygon([(cx-s, cy), (cx, cy-s//2), (cx, cy+s//2)], fill=color)
    draw.rectangle([cx, cy-S(2), cx+s, cy+S(2)], fill=color)


def draw_levels_icon(draw, cx, cy, size, color=ICON_DARK):
    s = size // 2
    for i, frac in enumerate([0.5, 0.9, 0.65, 1.0]):
        bh = int(s * frac)
        bx = cx - s + i * (s // 2)
        draw.rectangle([bx, cy+s-bh, bx+s//2-S(2), cy+s], fill=color)


def draw_lightbulb(draw, cx, cy, size, color=ICON_BLUE):
    s = size // 2
    draw.ellipse([cx-s, cy-s, cx+s, cy+s//3], outline=color, width=S(2))
    draw.rectangle([cx-s//3, cy+s//4, cx+s//3, cy+s], outline=color, width=S(2))


def draw_arrow_suggest(draw, cx, cy, size, color=ICON_BLUE):
    s = size // 2
    draw.ellipse([cx-s, cy-s, cx+s//3, cy+s//3], outline=color, width=S(2))
    draw.line([(cx+s//4, cy+s//4), (cx+s, cy+s)], fill=color, width=S(3))
    draw.polygon([(cx+s, cy), (cx+s+S(4), cy+s+S(4)), (cx, cy+s)], fill=color)


def draw_dropdown_arrow(draw, cx, y, color=ICON_DARK):
    hw = S(4)
    draw.polygon([(cx-hw, y), (cx+hw, y), (cx, y+S(5))], fill=color)


def draw_checkbox(draw, x, y, size, checked, tick_color=PANE_CHECK):
    draw.rectangle([x, y, x+size, y+size], outline="#888888", fill="#ffffff",
                   width=max(1, S(1)))
    if checked:
        m = size // 5
        draw.line([(x+m, y+size//2),
                   (x+size//2-m, y+size-m-m),
                   (x+size-m, y+m)], fill=tick_color, width=max(1, S(2)))


def draw_flip_arrows(draw, cx, cy, size, color=ICON_DARK):
    """Two curved arrows indicating flip/rotate."""
    s = size // 2
    draw.arc([cx-s, cy-s, cx+s, cy+s], start=15, end=165, fill=color, width=S(3))
    draw.polygon([(cx+s, cy-s//3), (cx+s+S(4), cy+s//3), (cx+s-S(4), cy+s//4)], fill=color)
    draw.arc([cx-s, cy-s, cx+s, cy+s], start=195, end=345, fill=color, width=S(3))
    draw.polygon([(cx-s, cy+s//3), (cx-s-S(4), cy-s//3), (cx-s+S(4), cy-s//4)], fill=color)


def draw_chess_piece(draw, cx, cy, size, color=ICON_DARK):
    """Simple bishop-like piece silhouette."""
    s = size // 2
    draw.ellipse([cx-s//3, cy-s, cx+s//3, cy-s//2], fill=color)
    draw.line([(cx, cy-s), (cx, cy-s//3)], fill=color, width=S(2))
    draw.ellipse([cx-s//2, cy-s//3, cx+s//2, cy+s//4], fill=color)
    draw.rectangle([cx-s//2, cy+s//4, cx+s//2, cy+s], fill=color)
    draw.rectangle([cx-s, cy+s-S(4), cx+s, cy+s], fill=color)


def draw_color_swatch(draw, cx, cy, size, color=ICON_DARK):
    """Checkered square swatch for square color."""
    s = size // 2
    q = s // 2  # noqa: F841
    draw.rectangle([cx-s, cy-s, cx+s, cy+s], outline=color, width=max(1, S(1)))
    draw.rectangle([cx-s, cy-s, cx, cy], fill="#8b6040")
    draw.rectangle([cx, cy, cx+s, cy+s], fill="#8b6040")
    draw.rectangle([cx, cy-s, cx+s, cy], fill="#f0d9b5")
    draw.rectangle([cx-s, cy, cx, cy+s], fill="#f0d9b5")


def draw_play_triangle(draw, cx, cy, size, color=ICON_GREEN):
    """► play symbol."""
    s = size // 2
    draw.polygon([(cx-s//2, cy-s), (cx+s, cy), (cx-s//2, cy+s)], fill=color)


def draw_pause_bars(draw, cx, cy, size, color=ICON_AMBER):
    """⏸ pause symbol."""
    s = size // 2
    w = max(S(3), s // 2)
    draw.rectangle([cx-s, cy-s, cx-s+w, cy+s], fill=color)
    draw.rectangle([cx+s-w, cy-s, cx+s, cy+s], fill=color)


def draw_stop_square(draw, cx, cy, size, color=ICON_RED):
    """■ stop symbol."""
    s = size // 2 - S(2)
    draw.rectangle([cx-s, cy-s, cx+s, cy+s], fill=color)


def draw_left_arrow(draw, cx, cy, size, color=ICON_DARK):
    """◀ previous."""
    s = size // 2
    draw.polygon([(cx+s//2, cy-s), (cx-s, cy), (cx+s//2, cy+s)], fill=color)


def draw_right_arrow(draw, cx, cy, size, color=ICON_DARK):
    """▶ next."""
    s = size // 2
    draw.polygon([(cx-s//2, cy-s), (cx+s, cy), (cx-s//2, cy+s)], fill=color)


def draw_wrench(draw, cx, cy, size, color=ICON_DARK):
    """Simple wrench / tools icon."""
    s = size // 2
    draw.ellipse([cx-s, cy-s, cx-s//3, cy-s//3], outline=color, width=S(2))
    draw.line([(cx-s//2, cy-s//2), (cx+s, cy+s)], fill=color, width=S(3))
    draw.ellipse([cx+s//3, cy+s//3, cx+s, cy+s], outline=color, width=S(2))


def draw_gear(draw, cx, cy, size, color=ICON_DARK):
    """Gear / settings icon."""
    s = size // 2
    draw.ellipse([cx-s//2, cy-s//2, cx+s//2, cy+s//2], outline=color, width=S(2))
    for angle in range(0, 360, 45):
        import math
        ra, rb = math.radians(angle), math.radians(angle+20)  # noqa: F841
        x1, y1 = cx + int(s*0.55*math.cos(ra)), cy + int(s*0.55*math.sin(ra))
        x2, y2 = cx + int(s*math.cos(ra)), cy + int(s*math.sin(ra))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=S(2))


def draw_cpu_chip(draw, cx, cy, size, color=ICON_BLUE):
    """CPU/processor icon for Select Engine."""
    s = size // 2
    inner = max(2, s * 3 // 4)
    draw.rectangle([cx-inner, cy-inner, cx+inner, cy+inner],
                   outline=color, fill="#d8e8f8", width=max(1, S(1)))
    pin = max(2, s // 4)
    for i in [-inner//2, 0, inner//2]:
        draw.line([(cx+i, cy-inner-pin), (cx+i, cy-inner)], fill=color, width=max(1, S(1)))
        draw.line([(cx+i, cy+inner), (cx+i, cy+inner+pin)], fill=color, width=max(1, S(1)))
    for j in [-inner//2, inner//2]:
        draw.line([(cx-inner-pin, cy+j), (cx-inner, cy+j)], fill=color, width=max(1, S(1)))
        draw.line([(cx+inner, cy+j), (cx+inner+pin, cy+j)], fill=color, width=max(1, S(1)))


def draw_layout_panes(draw, cx, cy, size, color=ICON_DARK):
    """Grid of pane rectangles for Standard Layouts."""
    s = size // 2
    draw.rectangle([cx-s, cy-s, cx+S(2), cy+s], outline=color, width=S(2))
    draw.rectangle([cx+S(4), cy-s, cx+s, cy-S(2)], outline=color, width=S(2))
    draw.rectangle([cx+S(4), cy+S(2), cx+s, cy+s], outline=color, width=S(2))


def draw_fullscreen(draw, cx, cy, size, color=ICON_DARK):
    """Four corner-arrows for Full Screen."""
    s = size // 2
    m = S(4)
    draw.polygon([(cx-s, cy-s), (cx-s+m, cy-s), (cx-s, cy-s+m)], fill=color)
    draw.polygon([(cx+s, cy-s), (cx+s-m, cy-s), (cx+s, cy-s+m)], fill=color)
    draw.polygon([(cx-s, cy+s), (cx-s+m, cy+s), (cx-s, cy+s-m)], fill=color)
    draw.polygon([(cx+s, cy+s), (cx+s-m, cy+s), (cx+s, cy+s-m)], fill=color)
    draw.rectangle([cx-s+S(1), cy-s+S(1), cx+s-S(1), cy+s-S(1)],
                   outline=color, width=1)


# ══════════════════════════════════════════════════════════════════════════════
# Dropdown panel
# ══════════════════════════════════════════════════════════════════════════════

def draw_dropdown_panel(draw, bx, by, items, selected=0, header=None):
    """Draw an open dropdown panel (Fritz manual p.34-35 visual pattern).

    Optional *header* string adds a blue header bar at the top.
    """
    ITEM_H = S(18)
    PAD_X  = S(8)
    all_labels = items if header is None else items
    max_w = max(text_w(draw, t, F_SM) for t in all_labels) + PAD_X * 2
    if header:
        max_w = max(max_w, text_w(draw, header, F_SM) + PAD_X * 2)
    pw = max(S(100), max_w)
    head_h = S(20) if header else 0
    ph = head_h + S(4) + len(items) * ITEM_H + S(4)

    draw.rectangle([bx+S(2), by+S(2), bx+pw+S(2), by+ph+S(2)], fill="#d0d0d4")
    draw.rectangle([bx, by, bx+pw, by+ph], fill=DROP_BG, outline=DROP_BORDER,
                   width=max(1, S(1)))
    if header:
        draw.rectangle([bx, by, bx+pw, by+head_h], fill=DROP_HEAD)
        center_text(draw, header, F_SM, bx, bx+pw,
                    by + (head_h - S(9))//2, fill="#ffffff")

    for i, label in enumerate(items):
        iy = by + head_h + S(4) + i * ITEM_H
        if i == selected:
            draw.rectangle([bx+S(1), iy, bx+pw-S(1), iy+ITEM_H], fill=DROP_HOVER)
        draw.text((bx + PAD_X, iy + (ITEM_H - S(9))//2), label,
                  font=F_SM, fill=TAB_TEXT)


# ══════════════════════════════════════════════════════════════════════════════
# Shared structural drawing helpers
# ══════════════════════════════════════════════════════════════════════════════

def _draw_tab_bar(draw, selected_tab, sw):
    """Draw the full tab bar row on *draw*.  Returns (ty0, ty1)."""
    ty0, ty1 = 0, S(TAB_H)
    draw.rectangle([0, ty0, sw-1, ty1], fill=BG)

    FILE_W = S(40)
    draw.rectangle([0, ty0, FILE_W, ty1+S(1)], fill=FILE_BLUE)
    center_text(draw, "File", F_TAB, 0, FILE_W,
                ty0 + (ty1 - ty0 - S(10))//2, fill=FILE_TEXT)

    PAD = S(12)
    tx  = FILE_W + S(2)
    for tab in TABS:
        is_sel = tab == selected_tab
        tw = text_w(draw, tab, F_TAB)
        bw = tw + PAD * 2
        if is_sel:
            draw.rectangle([tx, ty0, tx+bw, ty1+S(1)], fill=BG)
            draw.rectangle([tx, ty0, tx+bw, ty0+S(2)], fill=SEL_ACCENT)
            draw.line([(tx, ty0+S(2)), (tx, ty1+S(1))], fill=SEP_LINE, width=1)
            draw.line([(tx+bw, ty0+S(2)), (tx+bw, ty1+S(1))], fill=SEP_LINE, width=1)
        tab_fill = SEL_ACCENT if is_sel else TAB_TEXT
        draw.text((tx + PAD, ty0 + (ty1-ty0-S(10))//2), tab,
                  font=F_TAB, fill=tab_fill)
        tx += bw + S(1)

    draw.line([(0, ty1), (sw-1, ty1)], fill=SEP_LINE, width=1)
    return ty0, ty1


def _draw_vsep(draw, cx, cy0, cy1):
    draw.line([(cx, cy0+S(4)), (cx, cy1-S(4))], fill=SEP_LINE, width=1)


def _draw_caption_row(draw, cap_y, groups, sw):
    """Draw the caption strip below the content area."""
    draw.rectangle([0, cap_y, sw-1, cap_y + S(CAP_H)], fill=BG)
    for gx0, gx1, label in groups:
        center_text(draw, label, F_CAP, gx0, gx1, cap_y + S(5), fill=CAP_TEXT)


def _large_btn(draw, bx, by, w, icon_fn, icon_color, label, lbh,
               active=False, dropdown=False):
    """Draw a large ribbon button (icon + text + optional ▼)."""
    bg = BTN_ACTIVE if active else None  # noqa: F841
    if active:
        draw.rectangle([bx, by, bx+w, by+lbh], fill=BTN_ACTIVE)
    if icon_fn:
        icon_fn(draw, bx+w//2, by+S(26),
                S(22), BTN_ACTIVE_TEXT if active else icon_color)
    lbl_fill = BTN_ACTIVE_TEXT if active else TAB_TEXT
    center_text(draw, label, F_SM, bx, bx+w,
                by + lbh - S(20), fill=lbl_fill)
    if dropdown:
        draw_dropdown_arrow(draw, bx+w//2, by+lbh-S(8),
                            color=BTN_ACTIVE_TEXT if active else ICON_DARK)


def _small_btn(draw, bx, by, w, h, icon_fn, icon_color, label,
               icon_r=None, disabled=False):
    """Draw a small ribbon button (icon-left, text-right)."""
    if icon_r is None:
        icon_r = S(9)
    fill = DISABLED if disabled else TAB_TEXT
    icol = DISABLED if disabled else icon_color
    if icon_fn:
        icon_fn(draw, bx + S(12), by + h//2, icon_r, icol)
    draw.text((bx + S(26), by + (h - S(9))//2), label, font=F_SM, fill=fill)


# ══════════════════════════════════════════════════════════════════════════════
# Per-tab content renderers
# (each receives an active ImageDraw, cy0 / cy1 in 2× coords, and draws the
#  content + captions, returning a list of (x0, x1, caption) tuples)
# ══════════════════════════════════════════════════════════════════════════════

def _draw_home_content(d, cy0, cy1, cap_y, sw, show_dropdown=False):
    cx = S(6)
    LBH = S(CONT_H - 4)
    SM_H = (S(CONT_H) - S(8)) // 2

    # ─ Play group: New Game + Levels ─
    LBW  = S(58)
    LBW2 = S(46)
    bx, by = cx, cy0 + S(2)
    _large_btn(d, bx, by, LBW, draw_pawn, ICON_BLUE, "New Game", LBH, dropdown=True)
    cx += LBW + S(4)

    bx2, by2 = cx, cy0 + S(2)
    if show_dropdown:
        d.rectangle([bx2-S(1), by2-S(1), bx2+LBW2+S(1), by2+LBH+S(1)],
                    fill="#e4eaf4", outline=SEP_LINE, width=1)
    _large_btn(d, bx2, by2, LBW2, draw_levels_icon, ICON_DARK, "Levels", LBH, dropdown=True)
    cx += LBW2 + S(8)
    play_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Game group: 4 small in 2×2 ─
    SM_W = S(70)
    ICON_R = S(9)
    btns = [("Resign",     draw_flag,       ICON_RED),
            ("Offer Draw", draw_circle_half, ICON_GREEN),
            ("Abort",      draw_king,        ICON_DARK),
            ("Takeback",   draw_back_arrow,  ICON_DARK)]
    game_x0 = cx
    for i, (label, fn, color) in enumerate(btns):
        col, row = i % 2, i // 2
        bx3 = cx + col * (SM_W + S(2))
        by3 = cy0 + S(4) + row * (SM_H + S(2))
        _small_btn(d, bx3, by3, SM_W, SM_H, fn, color, label, ICON_R)
    cx += (SM_W + S(2)) * 2 + S(6)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Coaching group ─
    COACH_W = S(78)
    coach_x0 = cx
    HINT_ICONS = [(draw_lightbulb, ICON_BLUE, "Hint"),
                  (draw_arrow_suggest, ICON_BLUE, "Suggestion")]
    for i, (fn, color, label) in enumerate(HINT_ICONS):
        by4 = cy0 + S(4) + i * (SM_H + S(2))
        _small_btn(d, cx, by4, COACH_W, SM_H, fn, color, label, ICON_R)
    cx += COACH_W + S(8)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Panes group ─
    panes = [("Players", True), ("Engine analysis", True),
             ("Eval profile", True), ("Notation", True), ("Eval bar", False)]
    COL_W = S(128)
    CB    = S(12)
    pane_x0 = cx
    for i, (name, chk) in enumerate(panes):
        col, row = i // 3, i % 3
        px = cx + col * COL_W
        py = cy0 + S(6) + row * S(22)
        draw_checkbox(d, px, py+S(1), CB, chk)
        d.text((px + CB + S(4), py), name, font=F_SM, fill=TAB_TEXT)
    pane_x1 = cx + COL_W * 2

    # Dropdown panel (shown open if requested)
    if show_dropdown:
        drop_bx = S(6) + LBW + S(4)
        drop_by = cy0 + LBH + S(4)
        draw_dropdown_panel(d, drop_bx, drop_by,
                            ["Blitz 5min", "Blitz 3+2", "Rapid 15min",
                             "Classical 30min", "Custom…"], selected=0)

    groups = [
        (S(6),       play_end,    "Play"),
        (game_x0,    game_x0 + (SM_W+S(2))*2, "Game"),
        (coach_x0,   coach_x0 + COACH_W,       "Coaching"),
        (pane_x0,    pane_x1,                   "Panes"),
    ]
    _draw_caption_row(d, cap_y, groups, sw)


def _draw_board_content(d, cy0, cy1, cap_y, sw):
    cx = S(6)
    LBH = S(CONT_H - 4)
    SM_H = (S(CONT_H) - S(8)) // 2  # noqa: F841

    # ─ Appearance group: Flip Board (active/toggled), Piece Style▼, Square Color▼ ─
    LBW = S(58)
    appear_x0 = cx

    # Flip Board — shown as active (blue fill)
    bx, by = cx, cy0 + S(2)
    _large_btn(d, bx, by, LBW, draw_flip_arrows, ICON_DARK, "Flip Board", LBH, active=True)
    cx += LBW + S(4)

    _large_btn(d, cx, cy0+S(2), LBW, draw_chess_piece, ICON_DARK, "Piece Style", LBH, dropdown=True)
    cx += LBW + S(4)

    _large_btn(d, cx, cy0+S(2), LBW, draw_color_swatch, ICON_DARK, "Square Color", LBH, dropdown=True)
    cx += LBW + S(8)
    appear_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ View group: checkboxes ─
    view_x0 = cx
    CB = S(12)
    view_items = [("Coordinates", True), ("Show arrows", True), ("Show hints", False)]
    for i, (name, chk) in enumerate(view_items):
        py = cy0 + S(8) + i * S(24)
        draw_checkbox(d, cx, py+S(1), CB, chk)
        d.text((cx + CB + S(4), py), name, font=F_SM, fill=TAB_TEXT)
    view_end = cx + S(120)

    groups = [
        (appear_x0, appear_end, "Appearance"),
        (view_x0,   view_end,   "View"),
    ]
    _draw_caption_row(d, cap_y, groups, sw)


def _draw_analysis_content(d, cy0, cy1, cap_y, sw):
    cx = S(6)
    LBH = S(CONT_H - 4)
    SM_H = (S(CONT_H) - S(8)) // 2
    SM_W = S(90)
    ICON_R = S(9)

    # ─ Play group: Play Now (large) ─
    LBW = S(56)
    play_x0 = cx
    _large_btn(d, cx, cy0+S(2), LBW, draw_play_triangle, ICON_GREEN, "Play Now", LBH)
    cx += LBW + S(8)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Tutor group: Pause / Continue (grayed) / Stop ─
    tutor_x0 = cx
    tutor_btns = [
        (draw_pause_bars,  ICON_AMBER,  "Pause Tutor",    False),
        (draw_play_triangle, ICON_GREEN, "Continue Tutor", True),   # disabled, grayed
        (draw_stop_square, ICON_RED,    "Stop Tutor",     False),
    ]
    for i, (fn, color, label, dis) in enumerate(tutor_btns):
        by_t = cy0 + S(4) + i * (SM_H + S(2)) // 2 * 2  # evenly spaced
        # 3 buttons stacked, use row spacing
    # Use 2-row layout (top row 2 btns, bottom 1)
    row_h = (S(CONT_H) - S(8)) // 3
    for i, (fn, color, label, dis) in enumerate(tutor_btns):
        by_t = cy0 + S(4) + i * (row_h + S(2))
        _small_btn(d, cx, by_t, SM_W, row_h, fn, color, label, ICON_R, disabled=dis)
    cx += SM_W + S(8)
    tutor_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Navigate group: Previous, Next ─
    nav_x0 = cx
    nav_btns = [
        (draw_left_arrow,  ICON_DARK, "Previous"),
        (draw_right_arrow, ICON_DARK, "Next"),
    ]
    for i, (fn, color, label) in enumerate(nav_btns):
        by_n = cy0 + S(4) + i * (SM_H + S(2))
        _small_btn(d, cx, by_n, SM_W, SM_H, fn, color, label, ICON_R)
    cx += SM_W + S(8)
    nav_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Tools group: Config, Utilities ─
    tools_x0 = cx
    tools_btns = [
        (draw_gear,   ICON_DARK, "Config"),
        (draw_wrench, ICON_DARK, "Utilities"),
    ]
    for i, (fn, color, label) in enumerate(tools_btns):
        by_t2 = cy0 + S(4) + i * (SM_H + S(2))
        _small_btn(d, cx, by_t2, SM_W, SM_H, fn, color, label, ICON_R)
    tools_end = cx + SM_W

    groups = [
        (play_x0,   play_x0 + LBW,  "Play"),
        (tutor_x0,  tutor_end,       "Tutor"),
        (nav_x0,    nav_end,         "Navigate"),
        (tools_x0,  tools_end,       "Tools"),
    ]
    _draw_caption_row(d, cap_y, groups, sw)


def _draw_engine_content(d, cy0, cy1, cap_y, sw):
    cx = S(6)
    LBH = S(CONT_H - 4)
    SM_H = (S(CONT_H) - S(8)) // 2  # noqa: F841
    SM_W = S(110)
    LBW  = S(68)
    ICON_R = S(9)

    # ─ Engine group: Select Engine▼ (large) ─
    engine_x0 = cx
    _large_btn(d, cx, cy0+S(2), LBW, draw_cpu_chip, ICON_BLUE, "Select Engine", LBH, dropdown=True)
    cx += LBW + S(8)
    engine_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Settings group: Engine Properties, UCI Options, Kibitzer ─
    settings_x0 = cx
    row_h = (S(CONT_H) - S(8)) // 3
    settings_btns = [
        (draw_gear,       ICON_DARK, "Engine Properties"),
        (draw_wrench,     ICON_DARK, "UCI Options"),
        (draw_levels_icon, ICON_DARK, "Kibitzer"),
    ]
    for i, (fn, color, label) in enumerate(settings_btns):
        by_s = cy0 + S(4) + i * (row_h + S(2))
        _small_btn(d, cx, by_s, SM_W, row_h, fn, color, label, ICON_R)
    settings_end = cx + SM_W

    groups = [
        (engine_x0,   engine_end,   "Engine"),
        (settings_x0, settings_end, "Settings"),
    ]
    _draw_caption_row(d, cap_y, groups, sw)


def _draw_view_content(d, cy0, cy1, cap_y, sw):
    cx = S(6)
    LBH = S(CONT_H - 4)
    SM_H = (S(CONT_H) - S(8)) // 2  # noqa: F841
    LBW  = S(62)
    SM_W = S(90)  # noqa: F841
    CB   = S(12)
    ICON_R = S(9)  # noqa: F841

    # ─ Layout group: Standard Layouts▼ (large), Full Screen (large toggle) ─
    layout_x0 = cx
    _large_btn(d, cx, cy0+S(2), LBW, draw_layout_panes, ICON_DARK,
               "Standard Layouts", LBH, dropdown=True)
    cx += LBW + S(4)
    _large_btn(d, cx, cy0+S(2), LBW, draw_fullscreen, ICON_DARK,
               "Full Screen", LBH)
    cx += LBW + S(8)
    layout_end = cx - S(4)

    _draw_vsep(d, cx-S(4), cy0, cy1)
    cx += S(4)

    # ─ Panes group: mirror of Home panes ─
    pane_x0 = cx
    panes = [("Players", True), ("Engine analysis", True),
             ("Eval profile", True), ("Notation", True), ("Eval bar", False)]
    COL_W = S(128)
    for i, (name, chk) in enumerate(panes):
        col, row = i // 3, i % 3
        px = cx + col * COL_W
        py = cy0 + S(6) + row * S(22)
        draw_checkbox(d, px, py+S(1), CB, chk)
        d.text((px + CB + S(4), py), name, font=F_SM, fill=TAB_TEXT)
    pane_end = cx + COL_W * 2

    groups = [
        (layout_x0, layout_end, "Layout"),
        (pane_x0,   pane_end,   "Panes"),
    ]
    _draw_caption_row(d, cap_y, groups, sw)


# ══════════════════════════════════════════════════════════════════════════════
# Tab renderer
# ══════════════════════════════════════════════════════════════════════════════

def render_tab(selected_tab="Home", show_dropdown=False):
    """Render the ribbon with *selected_tab* active.

    Returns a PIL Image at (W, H) after 2× → 1× LANCZOS downscale.
    """
    sw, sh = S(W), S(H)
    img = Image.new("RGB", (sw, sh), BG)
    d   = ImageDraw.Draw(img)

    ty0, ty1 = _draw_tab_bar(d, selected_tab, sw)

    cy0 = ty1 + S(1)
    cy1 = cy0 + S(CONT_H)
    cap_y = cy1

    if selected_tab == "Home":
        _draw_home_content(d, cy0, cy1, cap_y, sw, show_dropdown)
    elif selected_tab == "Board":
        _draw_board_content(d, cy0, cy1, cap_y, sw)
    elif selected_tab == "Analysis":
        _draw_analysis_content(d, cy0, cy1, cap_y, sw)
    elif selected_tab == "Engine":
        _draw_engine_content(d, cy0, cy1, cap_y, sw)
    elif selected_tab == "View":
        _draw_view_content(d, cy0, cy1, cap_y, sw)

    return img.resize((W, H), Image.LANCZOS)


# ══════════════════════════════════════════════════════════════════════════════
# File backstage panel renderer
# ══════════════════════════════════════════════════════════════════════════════

FILE_PANEL_H = 180   # logical px for the file-backstage panel render

def render_file_panel():
    """Render the File backstage panel (full-width floating panel).

    In the real app this overlays the entire ribbon.  Here we show it as a
    standalone panel at full ribbon width, file-panel height.
    """
    fp_h = FILE_PANEL_H
    sw, sh = S(W), S(fp_h)
    img = Image.new("RGB", (sw, sh), BG)
    d   = ImageDraw.Draw(img)

    # Left column: File tab blue + title
    SIDE_W = S(120)
    d.rectangle([0, 0, SIDE_W, sh], fill=FILE_BLUE)
    d.text((S(8), S(10)), "File", font=F_TAB, fill=FILE_TEXT)
    d.text((S(8), S(30)), "Caissa Fritz", font=F_SM, fill="#a0c4e0")

    # Right panel: white area with menu items
    px0 = SIDE_W + S(1)
    d.rectangle([px0, 0, sw-1, sh], fill="#ffffff")
    d.line([(px0, 0), (px0, sh-1)], fill=DROP_BORDER, width=S(1))

    items = [
        ("New Game…",    draw_pawn,        ICON_BLUE,  False),
        ("Open…",        draw_back_arrow,  ICON_DARK,  False),
        ("Recent ▶",    None,             ICON_DARK,  False),
        ("Save",         None,             ICON_DARK,  False),
        ("Save As…",     None,             ICON_DARK,  False),
        (None,           None,             None,       True),   # separator
        ("Options…",     draw_gear,        ICON_DARK,  False),
        ("Engines…",     draw_cpu_chip,    ICON_BLUE,  False),
        ("Quit",         draw_flag,        ICON_RED,   False),
    ]
    ITEM_H = S(16)
    iy = S(8)
    ICON_R = S(7)
    for label, fn, color, is_sep in items:
        if is_sep:
            d.line([(px0 + S(8), iy + ITEM_H//2), (sw - S(8), iy + ITEM_H//2)],
                   fill=SEP_LINE, width=1)
            iy += ITEM_H // 2
            continue
        if fn:
            fn(d, px0 + S(16), iy + ITEM_H//2, ICON_R, color)
        d.text((px0 + S(32), iy + (ITEM_H - S(9))//2), label, font=F_SM, fill=TAB_TEXT)
        iy += ITEM_H + S(2)

    return img.resize((W, fp_h), Image.LANCZOS)


# ══════════════════════════════════════════════════════════════════════════════
# All-tabs sheet
# ══════════════════════════════════════════════════════════════════════════════

def all_tabs_sheet(out_path):
    """Render all 6 panels (File + 5 tabs) stacked vertically with labels.

    Saves the result to *out_path* and returns the output path.
    """
    LABEL_H  = 22    # logical px per section label
    GAP      = 6
    BORDER   = 2

    panels = []
    # File backstage first
    panels.append(("FILE  (backstage panel)", render_file_panel()))
    # Then each content tab
    for tab in TABS:
        show_drop = (tab == "Home")
        panels.append((f"{tab.upper()}  tab", render_tab(tab, show_dropdown=show_drop)))

    total_h = sum(LABEL_H + p.height + GAP for _, p in panels) + BORDER * 2
    canvas = Image.new("RGB", (W + BORDER * 2, total_h), "#e8e8ec")
    dc = ImageDraw.Draw(canvas)

    y = BORDER
    for label_text, panel in panels:
        # Label bar
        dc.rectangle([BORDER, y, W + BORDER, y + LABEL_H], fill="#2a4a6a")
        dc.text((BORDER + 8, y + (LABEL_H - 12)//2), label_text,
                font=F_LBL, fill="#ffffff")
        y += LABEL_H
        canvas.paste(panel, (BORDER, y))
        y += panel.height + GAP

    canvas.save(out_path)
    print(f"Saved all-tabs sheet → {out_path}  ({canvas.size})")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# Legacy render() — kept for backward-compat / side_by_side()
# ══════════════════════════════════════════════════════════════════════════════

def render(show_dropdown=True):
    """Render the Home tab (backward-compat alias for render_tab)."""
    return render_tab("Home", show_dropdown=show_dropdown)


def side_by_side(ref_path, out_path):
    """Composite Fritz reference on top, Caissa Home-tab mockup on bottom."""
    ref  = Image.open(ref_path)
    mock = render()

    LABEL_H = 24
    GAP     = 8
    fw = max(ref.width, mock.width)
    fh = LABEL_H + ref.height + GAP + LABEL_H + H

    canvas = Image.new("RGB", (fw, fh), "#f0f0f2")
    d = ImageDraw.Draw(canvas)
    fl = _font(10)

    d.text((8, 4), "Fritz 18 reference  (Board tab shown)", font=fl, fill="#333333")
    canvas.paste(ref, (0, LABEL_H))

    y2 = LABEL_H + ref.height + GAP
    d.text((8, y2 + 4), "Caissa Fritz target  (Home tab — Levels dropdown open)", font=fl,
           fill=SEL_ACCENT)
    canvas.paste(mock, (0, y2 + LABEL_H))

    canvas.save(out_path)
    print(f"Saved {out_path}  ({canvas.size})")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    _ref_dir = Path(os.environ.get(
        "FRITZ_REF", Path.home() / "Pictures" / "fritz-reference"))
    _out_dir = _ref_dir if _ref_dir.is_dir() else Path(tempfile.gettempdir())

    # Always produce the all-tabs sheet
    _sheet = _out_dir / "caissa_all_tabs.png"
    all_tabs_sheet(str(_sheet))

    # Also produce the side-by-side comparison if a reference image exists
    _ref = _ref_dir / "ribbon_home.png"
    _cmp = _out_dir / "caissa_ribbon_comparison.png"
    if _ref.exists():
        side_by_side(str(_ref), str(_cmp))
    else:
        print(f"NOTE: no reference at {_ref}; set FRITZ_REF env var for side-by-side")
        render().save(str(_out_dir / "caissa_home_only.png"))
        print(f"Saved home-tab-only mockup → {_out_dir / 'caissa_home_only.png'}")
