"""
tools/design/fritz_mock.py — Offscreen Fritz UI scene renderer.

Renders one or more Fritz design scenes using PySide6 + the real .qss files,
then saves each as a PNG in CAISSA_DESIGN_OUT (default: /tmp/caissa-design/).

These are *design mockups* for Phases 3-7.  The widgets built here are the
design medium — approval of their appearance drives the implementation.

Usage
─────
    QT_QPA_PLATFORM=offscreen python3 tools/design/fritz_mock.py --scene all
    QT_QPA_PLATFORM=offscreen python3 tools/design/fritz_mock.py --scene clocks pane_titlebar
    QT_QPA_PLATFORM=offscreen python3 tools/design/fritz_mock.py --scene full --variant dark

Scenes
──────
    pane_titlebar   Gradient title bar with label and ▾ ✕ buttons
    clocks          Two LCD-style clock boxes (black with digital digits)
    eval_line       Dense single-line evaluation: assessment + NAG + depth
    nag_row         Two rows of NAG annotation symbol buttons
    notation_tabs   Six-tab QTabBar (Notation / Training / Score sheet / …)
    ribbon_home     Office-style ribbon mock: Home tab with Game + Panes groups
    full            Full right-column mock: header + analysis + eval + notation

Options
───────
    --scene SCENE [SCENE …]   Scenes to render; ``all`` renders every scene
    --variant dark|light       QSS variant to apply (default: dark / Modern Fritz)
    --out DIR                  Override CAISSA_DESIGN_OUT
    --width W                  Scene widget width in pixels (default: 420)

:spec: §0.4, Phase 0 (feature_spec.md)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── bootstrap ─────────────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[2]
_BIN  = _REPO / "bin"
os.chdir(_BIN)
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APP = None


def _init():
    """Bootstrap Qt + Code.configuration (idempotent, mirrors tests/conftest.py)."""
    global _APP
    if _APP is not None:
        return _APP
    # Code/__init__.py uses sys.argv[0] to chdir; point it at the real launcher
    # so it resolves to bin/, not tools/design/.
    sys.argv[0] = str(_BIN / "LucasR.py")
    from PySide6 import QtWidgets
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    import Code
    from Code.Config import Configuration
    from Code.QT import IconosBase
    from Code.Main import InitApp
    if not hasattr(Code, "configuration") or Code.configuration is None:
        Code.configuration = Configuration.Configuration("")
        Code.configuration.start()
        InitApp.init_app_style(_APP, Code.configuration)
        IconosBase.icons.reset(Code.configuration.x_style_icons)
        from Code.QT import Piezas
        Code.all_pieces = Piezas.AllPieces()
        from Code.Engines import ListEngineManagers
        Code.list_engine_managers = ListEngineManagers.ListEngineManagers()
    return _APP


# ── scene registry ─────────────────────────────────────────────────────────────

_SCENES: dict[str, "callable"] = {}


def scene(name: str):
    """Decorator: register a scene factory function."""
    def _dec(fn):
        _SCENES[name] = fn
        return fn
    return _dec


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_qss(variant: str) -> str:
    """Return the QSS text for the given variant.

    :param variant: ``"dark"`` → ``Modern Fritz.qss``, ``"light"`` → ``Fritz.qss``
                    (Fritz.qss ships in Phase 6; falls back to dark if absent).
    """
    styles_dir = _REPO / "Resources" / "Styles"
    if variant == "light":
        path = styles_dir / "Fritz.qss"
        if not path.exists():
            path = styles_dir / "Modern Fritz.qss"
    else:
        path = styles_dir / "Modern Fritz.qss"
    return path.read_text(encoding="utf-8")


def _apply_qss(widget, qss: str) -> None:
    """Apply the QSS to *widget* and ensure it is polished."""
    widget.setStyleSheet(qss)
    widget.ensurePolished()


def _grab(widget, w: int, h: int, qss: str) -> "QPixmap":
    """Size, show, polish, and grab *widget* offscreen."""
    from PySide6 import QtWidgets
    widget.resize(w, h)
    widget.show()
    QtWidgets.QApplication.processEvents()
    _apply_qss(widget, qss)
    QtWidgets.QApplication.processEvents()
    return widget.grab()


def _save(pixmap, path: Path) -> None:
    """Save a QPixmap to *path*, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))


# ── shared LCD widget ─────────────────────────────────────────────────────────
# Used by both the clocks scene and the full-window composition.

_LCD_SEGS = {
    "0": frozenset([0, 1, 2, 4, 5, 6]),
    "1": frozenset([2, 5]),
    "2": frozenset([0, 2, 3, 4, 6]),
    "3": frozenset([0, 2, 3, 5, 6]),
    "4": frozenset([1, 2, 3, 5]),
    "5": frozenset([0, 1, 3, 5, 6]),
    "6": frozenset([0, 1, 3, 4, 5, 6]),
    "7": frozenset([0, 2, 5]),
    "8": frozenset([0, 1, 2, 3, 4, 5, 6]),
    "9": frozenset([0, 1, 2, 3, 5, 6]),
    ":": None,
    " ": frozenset(),
}
_LCD_DH = 38   # digit cell height
_LCD_DW = 20   # digit cell width
_LCD_T  = 4    # bar thickness
_LCD_G  = 2    # gap at bar ends


def _make_lcd_widget(text: str = "0:05:00"):
    """Return a QWidget rendering seven-segment LCD digits for *text*."""
    from PySide6 import QtCore, QtGui, QtWidgets

    DH, DW, T, G = _LCD_DH, _LCD_DW, _LCD_T, _LCD_G

    class _LCD(QtWidgets.QWidget):
        LIT = QtGui.QColor("#30ff70")
        DIM = QtGui.QColor("#0a2010")
        BG  = QtGui.QColor("#000000")

        def __init__(self, t):
            super().__init__()
            self._text = t
            box_w = self._text_width(t) + 20
            box_h = DH + 16
            self.setFixedSize(box_w, box_h)

        def _text_width(self, t):
            w = 0
            for ch in t:
                w += (T + G * 2 + 2) if ch == ":" else (DW + G)
            return w

        def _seg_rect(self, sx, sy, seg):
            if seg == 0:
                return (sx + G, sy,             DW - 2*G, T)
            if seg == 6:
                return (sx + G, sy + DH - T,    DW - 2*G, T)
            if seg == 3:
                return (sx + G, sy + (DH-T)//2, DW - 2*G, T)
            half = DH // 2
            if seg == 1:
                return (sx,        sy + G + T,  T, half - G - T - 1)
            if seg == 2:
                return (sx + DW-T, sy + G + T,  T, half - G - T - 1)
            if seg == 4:
                return (sx,        sy + half+1, T, half - G - T - 1)
            if seg == 5:
                return (sx + DW-T, sy + half+1, T, half - G - T - 1)
            return (0, 0, 0, 0)

        def paintEvent(self, _ev):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), self.BG)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            x, y = 10, (self.height() - DH) // 2
            for ch in self._text:
                segs = _LCD_SEGS.get(ch)
                if segs is None:
                    dot = max(3, T)
                    cx = x + G
                    p.fillRect(cx, y + DH//3 - dot//2,   dot, dot, self.LIT)
                    p.fillRect(cx, y + 2*DH//3 - dot//2, dot, dot, self.LIT)
                    x += T + G * 2 + 2
                else:
                    for si in range(7):
                        rx, ry, rw, rh = self._seg_rect(x, y, si)
                        p.fillRect(rx, ry, rw, rh, self.LIT if si in segs else self.DIM)
                    x += DW + G
            p.end()

    return _LCD(text)


# ── scene: pane_titlebar ───────────────────────────────────────────────────────

@scene("pane_titlebar")
def render_pane_titlebar(out_dir: Path, variant: str, width: int) -> Path:
    """Mock WFritzPane title bar — gradient header with label and ▾ ✕ buttons.

    This is the design prototype for ``bin/Code/Fritz/WFritzPane.py`` (Phase 3).
    The gradient, dimensions, font and button style here are what Phase 3
    implements.
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    qss = _load_qss(variant)

    class _PaneTitleMock(QtWidgets.QWidget):
        """Stand-alone pane title bar mock."""

        TITLE_H = 22
        PAD_X   = 8
        GRAD_TOP    = "#dce6f0" if variant == "light" else "#3a3a3c"
        GRAD_BOTTOM = "#b8ccdf" if variant == "light" else "#2d2d2f"
        TEXT_COLOR  = "#1a1a1a" if variant == "light" else "#d4d4d4"
        BTN_COLOR   = "#555566" if variant == "light" else "#888899"

        def __init__(self):
            super().__init__()
            self.setObjectName("WFritzPaneTitleMock")
            self.setFixedHeight(self.TITLE_H)

            ly = QtWidgets.QHBoxLayout(self)
            ly.setContentsMargins(self.PAD_X, 0, 4, 0)
            ly.setSpacing(0)

            self._label = QtWidgets.QLabel("Engine analysis")
            self._label.setObjectName("WFritzPaneTitle")
            f = QtGui.QFont()
            f.setPointSize(8)
            f.setBold(True)
            self._label.setFont(f)
            self._label.setStyleSheet(f"color:{self.TEXT_COLOR}; background:transparent;")

            ly.addWidget(self._label, 1)

            for ch, tip in [("▾", "Options"), ("✕", "Hide")]:
                btn = QtWidgets.QToolButton()
                btn.setText(ch)
                btn.setToolTip(tip)
                btn.setFixedSize(18, 18)
                btn.setStyleSheet(
                    f"QToolButton {{ border:none; background:transparent; "
                    f"color:{self.BTN_COLOR}; font-size:11px; }}"
                    f"QToolButton:hover {{ color:#0078d4; }}"
                )
                ly.addWidget(btn)

        def paintEvent(self, event):
            p = QtGui.QPainter(self)
            grad = QtGui.QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, QtGui.QColor(self.GRAD_TOP))
            grad.setColorAt(1.0, QtGui.QColor(self.GRAD_BOTTOM))
            p.fillRect(self.rect(), grad)
            p.end()
            super().paintEvent(event)

    # Render four panes stacked to show the real right-column appearance.
    container = QtWidgets.QWidget()
    container.setObjectName("WFritzPaneTitleDemo")
    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(0, 0, 0, 0)
    vly.setSpacing(1)

    bg = "#ffffff" if variant == "light" else "#252526"
    for label_text in ["Players", "Engine analysis", "Eval profile", "Notation"]:
        row = QtWidgets.QWidget()
        rly = QtWidgets.QVBoxLayout(row)
        rly.setContentsMargins(0, 0, 0, 0)
        rly.setSpacing(0)

        title = _PaneTitleMock()
        title._label.setText(label_text)

        body = QtWidgets.QWidget()
        body.setFixedHeight(60)
        body.setStyleSheet(f"background:{bg};")

        rly.addWidget(title)
        rly.addWidget(body)
        vly.addWidget(row)

    vly.addStretch()

    px = _grab(container, width, 380, qss)
    out = out_dir / f"pane_titlebar_{variant}.png"
    _save(px, out)
    return out


# ── scene: clocks ──────────────────────────────────────────────────────────────

@scene("clocks")
def render_clocks(out_dir: Path, variant: str, width: int) -> Path:
    """Mock WFritzLCD clock box — black box with seven-segment style digits.

    This is the design prototype for ``bin/Code/Fritz/WFritzLCD.py`` (Phase 4).
    Uses QPainterPath polygons to draw seven-segment digits (D11).
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    qss = _load_qss(variant)

    # Seven-segment segment definitions.
    # Each digit 0-9 maps to a frozenset of segment indices:
    #   0=top  1=top-left  2=top-right  3=middle  4=bot-left  5=bot-right  6=bottom
    _SEGS = {
        "0": frozenset([0, 1, 2, 4, 5, 6]),
        "1": frozenset([2, 5]),
        "2": frozenset([0, 2, 3, 4, 6]),
        "3": frozenset([0, 2, 3, 5, 6]),
        "4": frozenset([1, 2, 3, 5]),
        "5": frozenset([0, 1, 3, 5, 6]),
        "6": frozenset([0, 1, 3, 4, 5, 6]),
        "7": frozenset([0, 2, 5]),
        "8": frozenset([0, 1, 2, 3, 4, 5, 6]),
        "9": frozenset([0, 1, 2, 3, 5, 6]),
        ":": None,  # rendered as two dots
        " ": frozenset(),
    }

    container = QtWidgets.QWidget()
    container.setObjectName("WFritzClocksDemo")
    bg = "#1e1e1e" if variant == "dark" else "#d0d8e0"
    container.setStyleSheet(f"background:{bg};")
    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(12, 12, 12, 12)
    vly.setSpacing(8)

    for main_t, inc_t in [("0:05:00", "0:00:16"), ("0:05:00", "0:00:00")]:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(_make_lcd_widget(main_t))
        row.addWidget(_make_lcd_widget(inc_t))
        row.addStretch()
        vly.addLayout(row)

    vly.addStretch()

    px = _grab(container, width, 160, qss)
    out = out_dir / f"clocks_{variant}.png"
    _save(px, out)
    return out


# ── scene: eval_line ──────────────────────────────────────────────────────────

@scene("eval_line")
def render_eval_line(out_dir: Path, variant: str, width: int) -> Path:
    """Dense single-line evaluation summary (Phase 4 design).

    Format: ``Black is slightly better: ∓ (-0.60) Depth: 24/45 00:00:16 51157kN``
    """
    from PySide6 import QtCore, QtWidgets

    qss = _load_qss(variant)

    container = QtWidgets.QWidget()
    container.setObjectName("WFritzEvalLineDemo")
    bg = "#1e1e1e" if variant == "dark" else "#f0f0f0"
    container.setStyleSheet(f"background:{bg};")

    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(8, 8, 8, 8)
    vly.setSpacing(4)

    examples = [
        ("∓", "#6699cc", "Black is slightly better: ∓ (-0.60)  Depth: 24/45  00:00:16  51157kN"),
        ("±", "#99cc66", "White is slightly better: ± (+0.45)  Depth: 21/38  00:00:09  38421kN"),
        ("+−", "#cc6666", "White is winning: +− (+3.20)  Depth: 18/32  00:00:05  21034kN"),
        ("=", "#888888", "Equal position: = (0.00)  Depth: 26/48  00:00:22  61200kN"),
    ]

    tc = "#d4d4d4" if variant == "dark" else "#1a1a1a"
    tc_dim = "#858585" if variant == "dark" else "#5a6570"

    for nag, nag_color, text in examples:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        nag_lbl = QtWidgets.QLabel(nag)
        nag_lbl.setFixedWidth(22)
        nag_lbl.setStyleSheet(
            f"color:{nag_color}; font-size:13px; font-weight:bold; "
            f"background:transparent;"
        )
        nag_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        eval_lbl = QtWidgets.QLabel(text)
        eval_lbl.setStyleSheet(
            f"color:{tc}; font-size:10px; font-family:monospace; background:transparent;"
        )
        eval_lbl.setWordWrap(False)

        row.addWidget(nag_lbl)
        row.addWidget(eval_lbl, 1)
        vly.addLayout(row)

    # Separator + PV line below
    sep_style = f"color:{tc_dim}; font-size:10px; background:transparent;"
    pv = QtWidgets.QLabel("  1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O Nf6 5. d3")
    pv.setStyleSheet(sep_style)
    vly.addWidget(pv)
    vly.addStretch()

    px = _grab(container, width, 160, qss)
    out = out_dir / f"eval_line_{variant}.png"
    _save(px, out)
    return out


# ── scene: nag_row ────────────────────────────────────────────────────────────

def _make_nag_toolbar(variant: str, parent=None):
    """Build the two-row Fritz NAG toolbar widget.

    Row 1 — piece-insertion buttons (wP bP wB bB wN bN wR bR wQ bQ).
            Fritz uses rendered piece icons; we use short labels for the mockup.
    Row 2 — navigation (↑ X ]) + tactical (!! ! !? ?! ? ??) +
             positional (+- +/- -/+ = ~).

    Lives at the bottom of the notation pane, not as a separate pane.
    Sized to fit inside a 420 px column.
    """
    from PySide6 import QtWidgets

    bg     = "#2d2d2d" if variant == "dark" else "#e8eef4"
    btn_bg = "#3a3a3a" if variant == "dark" else "#dce8f4"
    border = "#505050" if variant == "dark" else "#a0b4c8"
    tc     = "#cccccc" if variant == "dark" else "#222222"

    # Symbols with dedicated colours (NAG semantics)
    NAG_COLORS = {
        "!!": "#55cc55", "!":  "#88cc44", "!?": "#aaaa33",
        "?!": "#ccaa22", "?":  "#cc7733", "??": "#cc3333",
        "+-": "#cc5555", "+/-":"#88bb44", "-/+":"#5588cc",
        "=":  "#888888", "~":  "#9977aa",
    }

    w = QtWidgets.QWidget(parent)
    w.setObjectName("WFritzNagToolbar")
    w.setStyleSheet(f"background:{bg}; border-top:1px solid {border};")
    vly = QtWidgets.QVBoxLayout(w)
    vly.setContentsMargins(3, 2, 3, 2)
    vly.setSpacing(2)

    def _btn(text, color=None, w_px=24, h_px=22):
        from PySide6 import QtCore
        b = QtWidgets.QLabel(text)
        b.setFixedSize(w_px, h_px)
        b.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        col = color or tc
        b.setStyleSheet(
            f"QLabel {{ background:{btn_bg}; color:{col}; "
            f"font-size:10px; font-weight:bold; "
            f"border:1px solid {border}; border-radius:2px; }}"
        )
        return b

    def _sep():
        s = QtWidgets.QFrame()
        s.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        s.setFixedWidth(5)
        s.setStyleSheet(f"color:{border};")
        return s

    # Row 1 — piece pair buttons  (10 × 22px + 9 × 2px = 238px → fits)
    r1 = QtWidgets.QHBoxLayout(); r1.setSpacing(2)
    for label in ["wP", "bP", "wB", "bB", "wN", "bN", "wR", "bR", "wQ", "bQ"]:
        r1.addWidget(_btn(label, tc))
    r1.addStretch()
    vly.addLayout(r1)

    # Row 2 — nav (3) + sep + tactical (6) + sep + positional (5)
    # 14 buttons × 22px + 13 × 2px + 2 seps × 5px = 308 + 26 + 10 = 344px → fits
    r2 = QtWidgets.QHBoxLayout(); r2.setSpacing(2)
    for sym in ["<<", "X", "]"]:
        r2.addWidget(_btn(sym, tc))
    r2.addWidget(_sep())
    for sym in ["!!", "!", "!?", "?!", "?", "??"]:
        r2.addWidget(_btn(sym, NAG_COLORS.get(sym, tc)))
    r2.addWidget(_sep())
    for sym in ["+-", "+/-", "-/+", "=", "~"]:
        r2.addWidget(_btn(sym, NAG_COLORS.get(sym, tc), w_px=28))
    r2.addStretch()
    vly.addLayout(r2)

    return w


@scene("nag_row")
def render_nag_row(out_dir: Path, variant: str, width: int) -> Path:
    """Fritz NAG toolbar as it appears inside the notation pane (Phase 5 design).

    Two rows: piece figurines on top, navigation + annotation symbols below.
    In the real layout this sits at the bottom of the notation pane — not a
    separate pane.
    """
    from PySide6 import QtWidgets

    qss = _load_qss(variant)
    container = QtWidgets.QWidget()
    container.setObjectName("WFritzNagDemo")
    bg = "#1e1e1e" if variant == "dark" else "#f0f0f0"
    container.setStyleSheet(f"background:{bg};")
    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(0, 0, 0, 0)
    vly.setSpacing(0)
    vly.addWidget(_make_nag_toolbar(variant))
    vly.addStretch()

    px = _grab(container, width, 68, qss)
    out = out_dir / f"nag_row_{variant}.png"
    _save(px, out)
    return out


# ── scene: notation_tabs ──────────────────────────────────────────────────────

def _make_notation_content(variant: str) -> "QtWidgets.QWidget":
    """Build the flowing-text notation content area + embedded NAG toolbar.

    Matches the real Fritz Notation tab layout:
      ┌─────────────────────────────┐
      │  flowing move text          │ ← inline moves, current highlighted
      │  (variations indented)      │
      │  commentary in italics      │
      │─────────────────────────────│
      │  figurine row               │ ← NAG toolbar row 1
      │  nav + annotation symbols   │ ← NAG toolbar row 2
      └─────────────────────────────┘
    The Score sheet tab would instead show a Move/White/Black grid — this is
    the Notation tab view only.
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    bg_content = "#ffffff" if variant == "light" else "#1e1e1e"
    tc         = "#1a1a1a" if variant == "light" else "#d4d4d4"
    tc_dim     = "#5a6570" if variant == "light" else "#858585"
    hi_bg      = "#1a5276" if variant == "dark"  else "#cce4ff"
    hi_fg      = "#ffffff" if variant == "dark"  else "#000000"
    var_col    = "#7a9bbf" if variant == "dark"  else "#1a5276"

    outer = QtWidgets.QWidget()
    outer.setObjectName("WFritzNotationContent")
    outer.setStyleSheet(f"background:{bg_content};")
    vly = QtWidgets.QVBoxLayout(outer)
    vly.setContentsMargins(0, 0, 0, 0)
    vly.setSpacing(0)

    # ── Flowing notation text area ────────────────────────────────────────────
    text_area = QtWidgets.QTextBrowser()
    text_area.setObjectName("WFritzNotationText")
    text_area.setStyleSheet(
        f"QTextBrowser {{ background:{bg_content}; color:{tc}; "
        f"border:none; font-size:11px; }}"
    )
    text_area.setOpenLinks(False)
    text_area.setReadOnly(True)

    # Build rich-text notation mimicking Fritz inline move display.
    hi_span  = f'<span style="background:{hi_bg}; color:{hi_fg}; padding:0 3px; border-radius:2px;">'
    dim_span = f'<span style="color:{tc_dim}; font-size:10px;">'
    var_span = f'<span style="color:{var_col}; font-size:10px;">'

    html = (
        f'<p style="margin:4px 6px; color:{tc_dim}; font-size:10px;">'
        f'Paulsen,L – Morphy,P  C48  New York 1857</p>'
        f'<p style="margin:4px 6px;">'
        # variation line above current
        f'{var_span}( 20.Qe2 Bb6 21.Bg4 Rxe3 22.Bxf5 Rxe2 23.Bxd7= )</span><br>'
        f'{var_span}( 20.Qa5? Rg6 21.Kh1 Qxf3 22.gxf3 Bc6-+ )</span><br>'
        f'<span style="color:{tc};">20...Bd6 &nbsp; 21.c4± &nbsp; </span>'
        # current move highlighted
        f'{hi_span}16...Rae8</span>'
        f'<span style="color:{tc};"> &nbsp; 17.Qa6 </span>'
        f'{dim_span}[#]</span>'
        f'<br>'
        f'{var_span}[ 17.Qd1 &nbsp; c5 &nbsp; ♗s...♟d7-b5 ]</span><br>'
        f'<span style="color:{tc};">18.♗xg5± &nbsp; ♛a5 &nbsp; </span>'
        f'{dim_span}1.50/13</span>'
        f'</p>'
        f'<p style="margin:4px 6px; color:{tc_dim}; font-style:italic; font-size:10px;">'
        f'Johnson,C.F.: "Morphy deliberated half an hour"'
        f'</p>'
    )
    text_area.setHtml(html)

    vly.addWidget(text_area, 1)

    # ── NAG toolbar (embedded at bottom of notation pane) ─────────────────────
    vly.addWidget(_make_nag_toolbar(variant))

    return outer


@scene("notation_tabs")
def render_notation_tabs(out_dir: Path, variant: str, width: int) -> Path:
    """Fritz notation pane mock (Phase 5 design).

    Tab strip (bare QTabBar, not QTabWidget) over a flowing-text notation area
    with the NAG annotation toolbar embedded at the bottom.  The Score sheet
    tab would show a grid; only the Notation tab is mocked here.
    """
    from PySide6 import QtWidgets

    qss = _load_qss(variant)

    TABS = ["Notation", "Training", "Score sheet", "LiveBook", "Openings Book", "My Moves"]

    container = QtWidgets.QWidget()
    container.setObjectName("WFritzNotationDemo")
    bg = "#1e1e1e" if variant == "dark" else "#f4f8fc"
    container.setStyleSheet(f"background:{bg};")

    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(0, 0, 0, 0)
    vly.setSpacing(0)

    tabbar = QtWidgets.QTabBar()
    tabbar.setObjectName("WFritzNotationTabBar")
    tabbar.setExpanding(False)
    tabbar.setDrawBase(False)
    for tab in TABS:
        tabbar.addTab(tab)
    tabbar.setCurrentIndex(0)

    vly.addWidget(tabbar)
    vly.addWidget(_make_notation_content(variant), 1)

    px = _grab(container, width, 260, qss)
    out = out_dir / f"notation_tabs_{variant}.png"
    _save(px, out)
    return out


# ── scene: ribbon_home ────────────────────────────────────────────────────────

@scene("ribbon_home")
def render_ribbon_home(out_dir: Path, variant: str, width: int) -> Path:
    """Fritz Office-style ribbon mock — Home tab (Phase 7 design).

    Shows: tab strip (Home / Board / Training / Analysis / Opening / Engine),
    Game group (New Game large + Resign/Draw/Takeback small),
    Panes group (checkbox list).
    """
    from PySide6 import QtCore, QtWidgets

    qss = _load_qss(variant)

    bg_ribbon  = "#e8eef4" if variant == "light" else "#2d2d2d"
    bg_page    = "#f4f8fc" if variant == "light" else "#333333"
    bg_group   = "#eef2f8" if variant == "light" else "#3a3a3a"
    tc         = "#1a1a1a" if variant == "light" else "#d4d4d4"
    tc_cap     = "#555566" if variant == "light" else "#888899"
    sep_color  = "#a0b4c8" if variant == "light" else "#505050"
    btn_bg     = "#dce8f4" if variant == "light" else "#3c3c3c"
    btn_hover  = "#c0d4e8" if variant == "light" else "#505060"
    accent     = "#0060b0" if variant == "light" else "#0078d4"

    TABS = ["Home", "Board", "Training", "Analysis", "Opening", "Engine"]

    container = QtWidgets.QWidget()
    container.setObjectName("WRibbonDemo")
    container.setFixedHeight(120)
    container.setStyleSheet(f"background:{bg_ribbon};")

    outer = QtWidgets.QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # ── Tab strip + quick-access ──────────────────────────────────────────────
    header = QtWidgets.QWidget()
    header.setFixedHeight(26)
    header.setStyleSheet(f"background:{bg_ribbon};")
    hly = QtWidgets.QHBoxLayout(header)
    hly.setContentsMargins(4, 0, 4, 0)
    hly.setSpacing(0)

    tabbar = QtWidgets.QTabBar()
    tabbar.setObjectName("WRibbonTabBar")
    tabbar.setExpanding(False)
    tabbar.setDrawBase(False)
    for tab in TABS:
        tabbar.addTab(tab)
    tabbar.setCurrentIndex(0)

    hly.addWidget(tabbar, 1)

    # Quick-access strip (right side of header)
    for icon_text in ["✕", "↩", "⏸"]:
        qab = QtWidgets.QToolButton()
        qab.setText(icon_text)
        qab.setFixedSize(20, 20)
        qab.setStyleSheet(
            f"QToolButton {{ border:none; background:transparent; color:{tc_cap}; }}"
            f"QToolButton:hover {{ color:{accent}; }}"
        )
        hly.addWidget(qab)

    outer.addWidget(header)

    # ── Rule ──────────────────────────────────────────────────────────────────
    rule = QtWidgets.QFrame()
    rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    rule.setFixedHeight(1)
    rule.setStyleSheet(f"color:{sep_color};")
    outer.addWidget(rule)

    # ── Page ──────────────────────────────────────────────────────────────────
    page = QtWidgets.QWidget()
    page.setStyleSheet(f"background:{bg_page};")
    page_ly = QtWidgets.QHBoxLayout(page)
    page_ly.setContentsMargins(6, 4, 6, 4)
    page_ly.setSpacing(8)

    # ── Game group ────────────────────────────────────────────────────────────
    game_grp = QtWidgets.QWidget()
    game_grp.setStyleSheet(
        f"background:{bg_group}; border:1px solid {sep_color}; border-radius:3px;"
    )
    gg_ly = QtWidgets.QVBoxLayout(game_grp)
    gg_ly.setContentsMargins(6, 4, 6, 2)
    gg_ly.setSpacing(2)

    # Large "New Game" button
    new_game = QtWidgets.QToolButton()
    new_game.setText("New\nGame")
    new_game.setFixedSize(56, 52)
    new_game.setStyleSheet(
        f"QToolButton {{ background:{btn_bg}; color:{tc}; font-size:10px; "
        f"border:1px solid {sep_color}; border-radius:3px; }}"
        f"QToolButton:hover {{ background:{btn_hover}; }}"
    )

    small_row = QtWidgets.QHBoxLayout()
    small_row.setSpacing(3)
    for label in ["Resign", "Draw", "Takeback"]:
        sb = QtWidgets.QToolButton()
        sb.setText(label)
        sb.setFixedHeight(20)
        sb.setStyleSheet(
            f"QToolButton {{ background:{btn_bg}; color:{tc}; font-size:9px; "
            f"border:1px solid {sep_color}; border-radius:2px; }}"
            f"QToolButton:hover {{ background:{btn_hover}; }}"
        )
        small_row.addWidget(sb)

    gg_top = QtWidgets.QHBoxLayout()
    gg_top.addWidget(new_game)
    gg_top.addLayout(small_row)
    gg_ly.addLayout(gg_top)

    cap_game = QtWidgets.QLabel("Game")
    cap_game.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    cap_game.setStyleSheet(f"color:{tc_cap}; font-size:8px; background:transparent; border:none;")
    gg_ly.addWidget(cap_game)

    page_ly.addWidget(game_grp)

    # ── Vertical separator ─────────────────────────────────────────────────────
    vsep = QtWidgets.QFrame()
    vsep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    vsep.setStyleSheet(f"color:{sep_color};")
    page_ly.addWidget(vsep)

    # ── Panes group ────────────────────────────────────────────────────────────
    panes_grp = QtWidgets.QWidget()
    panes_grp.setStyleSheet(
        f"background:{bg_group}; border:1px solid {sep_color}; border-radius:3px;"
    )
    pg_ly = QtWidgets.QVBoxLayout(panes_grp)
    pg_ly.setContentsMargins(6, 4, 6, 2)
    pg_ly.setSpacing(1)

    PANES = ["Players", "Engine analysis", "Eval profile", "Notation", "Eval bar"]
    for pane in PANES:
        cb = QtWidgets.QCheckBox(pane)
        cb.setChecked(True)
        cb.setStyleSheet(
            f"QCheckBox {{ color:{tc}; font-size:9px; background:transparent; border:none; }}"
        )
        pg_ly.addWidget(cb)

    cap_panes = QtWidgets.QLabel("Panes")
    cap_panes.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    cap_panes.setStyleSheet(f"color:{tc_cap}; font-size:8px; background:transparent; border:none;")
    pg_ly.addWidget(cap_panes)

    page_ly.addWidget(panes_grp)
    page_ly.addStretch()

    outer.addWidget(page, 1)

    px = _grab(container, width, 120, qss)
    out = out_dir / f"ribbon_home_{variant}.png"
    _save(px, out)
    return out


# ── scene: full ───────────────────────────────────────────────────────────────

@scene("full")
def render_full(out_dir: Path, variant: str, width: int) -> Path:
    """Full Fritz window composition: board placeholder + complete right column.

    This is the 'Round 1' full-window scene used in the design approval gate.
    Rendered at 1100×700 regardless of *width* so proportions match Fritz.
    """
    from PySide6 import QtCore, QtWidgets

    qss = _load_qss(variant)
    FULL_W, FULL_H = 1100, 700
    RIGHT_W = 420

    from PySide6 import QtGui

    bg       = "#252526" if variant == "dark" else "#eaeef2"
    surface  = "#2d2d2d" if variant == "dark" else "#ffffff"
    border   = "#505050" if variant == "dark" else "#a0b4c8"
    tc       = "#d4d4d4" if variant == "dark" else "#1a1a1a"
    tc_dim   = "#858585" if variant == "dark" else "#5a6570"
    accent   = "#0078d4" if variant == "dark" else "#0060b0"
    grad_top = "#3a3a3c" if variant == "dark" else "#dce6f0"
    grad_bot = "#2d2d2f" if variant == "dark" else "#b8ccdf"
    hi       = "#094771" if variant == "dark" else "#cce4ff"

    # ── helper: titled pane ────────────────────────────────────────────────────
    def _pane(title, body, body_h=None):
        pane = QtWidgets.QWidget()
        ply = QtWidgets.QVBoxLayout(pane)
        ply.setContentsMargins(0, 0, 0, 0)
        ply.setSpacing(0)

        class _TB(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                self.setFixedHeight(22)
                ly = QtWidgets.QHBoxLayout(self)
                ly.setContentsMargins(8, 0, 4, 0)
                ly.setSpacing(0)
                lbl = QtWidgets.QLabel(title)
                f = QtGui.QFont(); f.setPointSize(8); f.setBold(True)
                lbl.setFont(f)
                lbl.setStyleSheet(f"color:{tc}; background:transparent;")
                ly.addWidget(lbl, 1)
                for ch in ["▾", "✕"]:
                    b = QtWidgets.QToolButton()
                    b.setText(ch); b.setFixedSize(18, 18)
                    b.setStyleSheet(f"QToolButton{{border:none;background:transparent;"
                                    f"color:{tc_dim};font-size:11px;}}"
                                    f"QToolButton:hover{{color:{accent};}}")
                    ly.addWidget(b)
            def paintEvent(self, _ev):
                p = QtGui.QPainter(self)
                g = QtGui.QLinearGradient(0, 0, 0, self.height())
                g.setColorAt(0, QtGui.QColor(grad_top))
                g.setColorAt(1, QtGui.QColor(grad_bot))
                p.fillRect(self.rect(), g); p.end()
                super().paintEvent(_ev)

        body.setStyleSheet(f"background:{surface}; border:1px solid {border};")
        if body_h:
            body.setFixedHeight(body_h)
        ply.addWidget(_TB())
        ply.addWidget(body, 1)
        return pane

    # ── board placeholder ──────────────────────────────────────────────────────
    class _Board(QtWidgets.QWidget):
        def paintEvent(self, _ev):
            p = QtGui.QPainter(self)
            sz = min(self.width(), self.height())
            off_x = (self.width()  - sz) // 2
            off_y = (self.height() - sz) // 2
            sq = sz // 8
            light = QtGui.QColor("#f0d9b5")
            dark  = QtGui.QColor("#b58863")
            for r in range(8):
                for c in range(8):
                    col = light if (r + c) % 2 == 0 else dark
                    p.fillRect(off_x + c*sq, off_y + r*sq, sq, sq, col)
            p.end()

    board = _Board()

    # ── right column ───────────────────────────────────────────────────────────
    right = QtWidgets.QWidget()
    right.setFixedWidth(RIGHT_W)
    rly = QtWidgets.QVBoxLayout(right)
    rly.setContentsMargins(0, 0, 0, 0)
    rly.setSpacing(1)

    # Clock pane — two LCD rows
    clock_body = QtWidgets.QWidget()
    cl = QtWidgets.QVBoxLayout(clock_body)
    cl.setContentsMargins(8, 6, 8, 6)
    cl.setSpacing(6)
    for main_t, inc_t in [("0:05:00", "0:00:16"), ("0:05:00", "0:00:00")]:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(_make_lcd_widget(main_t))
        row.addWidget(_make_lcd_widget(inc_t))
        row.addStretch()
        cl.addLayout(row)
    rly.addWidget(_pane("Clocks: Blitz 5min", clock_body, 116))

    # Engine analysis pane
    analysis_body = QtWidgets.QWidget()
    ab = QtWidgets.QVBoxLayout(analysis_body)
    ab.setContentsMargins(4, 4, 4, 4); ab.setSpacing(2)
    for color, text in [
        (accent,  "Black is slightly better: ∓ (-0.60)  Depth: 24/45  00:00:16  51157kN"),
        (tc_dim,  "  1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"),
        (tc_dim,  "  1. e4 c5 2. Nf3 d6 3. d4 cxd4"),
    ]:
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(f"color:{color}; font-size:10px; font-family:monospace; background:transparent;")
        ab.addWidget(lbl)
    ab.addStretch()
    rly.addWidget(_pane("Engine: Fritz 18 Popcnt", analysis_body, 80))

    # Eval profile pane — bar chart of evaluation over move history
    class _EvalGraph(QtWidgets.QWidget):
        def paintEvent(self, _ev):
            import math
            p = QtGui.QPainter(self)
            p.fillRect(self.rect(), QtGui.QColor(surface.replace(";", "")))
            W, H = self.width(), self.height()
            mid = H // 2
            # draw centre line
            p.setPen(QtGui.QColor(border))
            p.drawLine(0, mid, W, mid)
            # synthetic eval curve (cp values over ~40 moves)
            import math
            cps = [
                0, 10, 25, 15, -20, -35, -15, 5, 30, 45, 60, 40, 20, 55, 80,
                65, 90, 120, 100, 85, 110, 95, 130, 150, 140, 120, 100, 80,
                60, 40, 20, 0, -10, -30, -20, 10, 30, 50, 40, 20,
            ]
            bar_w = max(2, W // len(cps))
            cap = 250  # cap at ±250 cp → full half-height
            white_col = QtGui.QColor("#99cc66")
            black_col = QtGui.QColor("#6699cc")
            for i, cp in enumerate(cps):
                bh = max(1, int(abs(cp) / cap * (mid - 2)))
                x = i * bar_w
                if cp >= 0:
                    p.fillRect(x, mid - bh, bar_w - 1, bh, white_col)
                else:
                    p.fillRect(x, mid, bar_w - 1, bh, black_col)
            # current position marker
            last_x = len(cps) * bar_w
            p.setPen(QtGui.QColor(accent))
            p.drawLine(last_x, 0, last_x, H)
            p.end()

    eval_graph_body = _EvalGraph()
    rly.addWidget(_pane("Eval profile", eval_graph_body, 80))

    # Notation pane — tab strip + flowing text + NAG toolbar embedded at bottom
    notation_body = QtWidgets.QWidget()
    nb = QtWidgets.QVBoxLayout(notation_body)
    nb.setContentsMargins(0, 0, 0, 0); nb.setSpacing(0)
    tabbar = QtWidgets.QTabBar()
    tabbar.setExpanding(False); tabbar.setDrawBase(False)
    for t in ["Notation", "Training", "Score sheet", "LiveBook", "Openings Book", "My Moves"]:
        tabbar.addTab(t)
    nb.addWidget(tabbar)
    nb.addWidget(_make_notation_content(variant), 1)
    rly.addWidget(_pane("Notation + Openings Book", notation_body), 1)

    # ── outer window ──────────────────────────────────────────────────────────
    window = QtWidgets.QWidget()
    window.setStyleSheet(f"background:{bg};")
    wly = QtWidgets.QHBoxLayout(window)
    wly.setContentsMargins(0, 0, 0, 0)
    wly.setSpacing(1)
    wly.addWidget(board, 1)
    wly.addWidget(right)

    px = _grab(window, FULL_W, FULL_H, qss)
    out = out_dir / f"full_{variant}.png"
    _save(px, out)
    return out


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Render Fritz UI design mockup scenes offscreen."
    )
    parser.add_argument(
        "--scene", nargs="+", default=["all"],
        help="Scene(s) to render, or 'all'.  Available: " + ", ".join(_SCENES),
    )
    parser.add_argument(
        "--variant", choices=["dark", "light"], default="dark",
        help="QSS variant (dark = Modern Fritz, light = Fritz [Phase 6]).",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output directory (overrides CAISSA_DESIGN_OUT).",
    )
    parser.add_argument(
        "--width", type=int, default=420,
        help="Scene widget width in pixels.",
    )
    args = parser.parse_args()

    # Ensure repo root is on sys.path so tools.design resolves
    _repo_str = str(_REPO)
    if _repo_str not in sys.path:
        sys.path.insert(0, _repo_str)
    from tools.design import DESIGN_OUT
    out_dir = args.out or DESIGN_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    scenes_to_render = list(_SCENES.keys()) if "all" in args.scene else args.scene
    for name in scenes_to_render:
        if name not in _SCENES:
            print(f"Unknown scene: {name!r}  (available: {', '.join(_SCENES)})")
            continue
        fn = _SCENES[name]
        _init()
        path = fn(out_dir, args.variant, args.width)
        print(f"  {name:20s}  →  {path}")


if __name__ == "__main__":
    # Must be run from repo root; chdir to bin/ so Code.__init__ finds its data.
    import os as _os
    _os.chdir(str(_REPO / "bin"))
    main()
