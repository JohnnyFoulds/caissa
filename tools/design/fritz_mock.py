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

    # Explicit digit geometry — fully independent width/height so proportions are correct
    DH = 38   # digit cell height
    DW = 20   # digit cell width  (roughly 1:2 ratio, tall and narrow like a real display)
    T  = 4    # bar thickness
    G  = 2    # gap at bar ends

    class _LCD(QtWidgets.QWidget):
        """Seven-segment LCD clock widget (prototype for WFritzLCD)."""

        LIT = QtGui.QColor("#30ff70")
        DIM = QtGui.QColor("#0a2010")
        BG  = QtGui.QColor("#000000")

        def __init__(self, text: str = "0:05:00"):
            super().__init__()
            self.setObjectName("WFritzLCDMock")
            self._text = text
            box_w = self._text_width(text) + 20
            box_h = DH + 16
            self.setFixedSize(box_w, box_h)

        def _text_width(self, text: str) -> int:
            w = 0
            for ch in text:
                w += (T + G * 2 + 2) if ch == ":" else (DW + G)
            return w

        def _seg_rect(self, sx, sy, seg):
            # Returns (x, y, w, h) for one segment bar
            if seg == 0:  # top horizontal
                return (sx + G, sy,              DW - 2*G, T)
            if seg == 6:  # bottom horizontal
                return (sx + G, sy + DH - T,     DW - 2*G, T)
            if seg == 3:  # middle horizontal
                return (sx + G, sy + (DH-T)//2,  DW - 2*G, T)
            half = DH // 2
            if seg == 1:  # top-left vertical
                return (sx,         sy + G + T,  T, half - G - T - 1)
            if seg == 2:  # top-right vertical
                return (sx + DW-T,  sy + G + T,  T, half - G - T - 1)
            if seg == 4:  # bot-left vertical
                return (sx,         sy + half+1, T, half - G - T - 1)
            if seg == 5:  # bot-right vertical
                return (sx + DW-T,  sy + half+1, T, half - G - T - 1)
            return (0, 0, 0, 0)

        def paintEvent(self, _event):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), self.BG)
            p.setPen(QtCore.Qt.PenStyle.NoPen)

            x = 10
            y = (self.height() - DH) // 2

            for ch in self._text:
                segs = _SEGS.get(ch)
                if segs is None:  # colon
                    dot = max(3, T)
                    cx = x + G
                    p.setBrush(self.LIT)
                    p.fillRect(cx, y + DH//3 - dot//2,   dot, dot, self.LIT)
                    p.fillRect(cx, y + 2*DH//3 - dot//2, dot, dot, self.LIT)
                    x += T + G * 2 + 2
                else:
                    for seg_i in range(7):
                        rx, ry, rw, rh = self._seg_rect(x, y, seg_i)
                        color = self.LIT if seg_i in segs else self.DIM
                        p.fillRect(rx, ry, rw, rh, color)
                    x += DW + G

            p.end()

    # Fritz layout: each player row has TWO black LCD boxes side by side
    # (main time left, increment/move time right), no player label in the clock pane
    container = QtWidgets.QWidget()
    container.setObjectName("WFritzClocksDemo")
    bg = "#1e1e1e" if variant == "dark" else "#d0d8e0"
    container.setStyleSheet(f"background:{bg};")
    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(12, 12, 12, 12)
    vly.setSpacing(8)

    # Black on top, White on bottom — two boxes per row
    for main_t, inc_t in [("0:05:00", "0:00:16"), ("0:05:00", "0:00:00")]:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(_LCD(main_t))
        row.addWidget(_LCD(inc_t))
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

@scene("nag_row")
def render_nag_row(out_dir: Path, variant: str, width: int) -> Path:
    """Two rows of NAG annotation symbol buttons (Phase 5 design)."""
    from PySide6 import QtWidgets

    qss = _load_qss(variant)

    # NAG symbols in standard two-row Fritz layout.
    # Row 1: tactical/evaluation  Row 2: positional
    ROW1 = ["‼", "!", "!?", "?!", "?", "??"]
    ROW2 = ["+−", "±", "∓", "=", "∞", "⩱", "⩲"]

    container = QtWidgets.QWidget()
    container.setObjectName("WFritzNagDemo")
    bg = "#1e1e1e" if variant == "dark" else "#f0f0f0"
    container.setStyleSheet(f"background:{bg}; padding:8px;")

    vly = QtWidgets.QVBoxLayout(container)
    vly.setContentsMargins(8, 8, 8, 8)
    vly.setSpacing(4)

    # NAG → (tooltip, colour)
    NAG_COLORS = {
        "‼": ("#66cc66", "Brilliant move"),
        "!":  ("#88cc44", "Good move"),
        "!?": ("#aabb44", "Interesting move"),
        "?!": ("#ccaa44", "Dubious move"),
        "?":  ("#cc7744", "Mistake"),
        "??": ("#cc4444", "Blunder"),
        "+−": ("#cc6666", "White is winning"),
        "±":  ("#99cc66", "White is better"),
        "∓":  ("#6699cc", "Black is better"),
        "=":  ("#888888", "Equal"),
        "∞":  ("#9988aa", "Unclear"),
        "⩱":  ("#88aacc", "White is slightly better"),
        "⩲":  ("#ccaa88", "Black is slightly better"),
    }

    btn_bg   = "#3c3c3c" if variant == "dark" else "#e0e8f0"
    btn_fg   = "#d4d4d4" if variant == "dark" else "#1a1a1a"
    btn_hover = "#505060" if variant == "dark" else "#c8d8e8"

    for row_syms in [ROW1, ROW2]:
        row_ly = QtWidgets.QHBoxLayout()
        row_ly.setSpacing(4)
        for sym in row_syms:
            color, tip = NAG_COLORS.get(sym, ("#888888", sym))
            btn = QtWidgets.QToolButton()
            btn.setText(sym)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 28)
            btn.setStyleSheet(
                f"QToolButton {{ background:{btn_bg}; color:{color}; "
                f"font-size:13px; font-weight:bold; border:1px solid #555; "
                f"border-radius:3px; }}"
                f"QToolButton:hover {{ background:{btn_hover}; }}"
            )
            row_ly.addWidget(btn)
        row_ly.addStretch()
        vly.addLayout(row_ly)

    vly.addStretch()

    px = _grab(container, width, 110, qss)
    out = out_dir / f"nag_row_{variant}.png"
    _save(px, out)
    return out


# ── scene: notation_tabs ──────────────────────────────────────────────────────

@scene("notation_tabs")
def render_notation_tabs(out_dir: Path, variant: str, width: int) -> Path:
    """Fritz notation tab strip mock (Phase 5 design).

    Six tabs: Notation / Training / Score sheet / LiveBook / Openings Book / My Moves
    Uses a bare QTabBar (not QTabWidget) to match the Phase 5 implementation.
    """
    from PySide6 import QtCore, QtWidgets

    qss = _load_qss(variant)

    TABS = ["Notation", "Training", "Score sheet", "LiveBook", "Openings Book", "My Moves"]

    container = QtWidgets.QWidget()
    container.setObjectName("WFritzNotationDemo")
    bg = "#1e1e1e" if variant == "dark" else "#f0f0f0"
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

    # Notation content area mock
    content = QtWidgets.QWidget()
    content.setObjectName("WFritzNotationContent")
    clr = "#2d2d2d" if variant == "dark" else "#ffffff"
    content.setStyleSheet(f"background:{clr}; border:1px solid #505050;")

    # Placeholder move grid rows
    grid_ly = QtWidgets.QGridLayout(content)
    grid_ly.setContentsMargins(4, 4, 4, 4)
    grid_ly.setSpacing(2)
    moves = [
        ("1.", "e4",  "e5"),
        ("2.", "Nf3", "Nc6"),
        ("3.", "Bc4", "Bc5"),
        ("4.", "O-O", "Nf6"),
        ("5.", "d3",  "d6"),
    ]
    tc = "#d4d4d4" if variant == "dark" else "#1a1a1a"
    hi = "#094771" if variant == "dark" else "#cce4ff"
    for r, (num, white, black) in enumerate(moves):
        for c, text in enumerate([num, white, black]):
            lbl = QtWidgets.QLabel(text)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            style = f"color:{tc}; font-size:11px; padding:2px 4px;"
            if r == 1 and c == 1:  # highlight current move
                style += f" background:{hi}; border-radius:2px;"
            lbl.setStyleSheet(style)
            grid_ly.addWidget(lbl, r, c)

    vly.addWidget(tabbar)
    vly.addWidget(content, 1)

    px = _grab(container, width, 200, qss)
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
    """Full Fritz right-column mock: player header + analysis + eval graph + notation.

    This is the 'Round 1' full-window scene — the one that determines layout
    direction and palette before any per-scene detail is reviewed.
    """
    from PySide6 import QtCore, QtWidgets

    qss = _load_qss(variant)

    # Colour palette
    bg        = "#252526" if variant == "dark" else "#f0f0f0"
    surface   = "#2d2d2d" if variant == "dark" else "#ffffff"
    border    = "#505050" if variant == "dark" else "#a0b4c8"
    tc        = "#d4d4d4" if variant == "dark" else "#1a1a1a"
    tc_dim    = "#858585" if variant == "dark" else "#5a6570"
    accent    = "#0078d4" if variant == "dark" else "#0060b0"
    grad_top  = "#3a3a3c" if variant == "dark" else "#dce6f0"
    grad_bot  = "#2d2d2f" if variant == "dark" else "#b8ccdf"

    outer = QtWidgets.QWidget()
    outer.setObjectName("WFritzRightColDemo")
    outer.setStyleSheet(f"background:{bg};")
    vly = QtWidgets.QVBoxLayout(outer)
    vly.setContentsMargins(0, 0, 0, 0)
    vly.setSpacing(1)

    def _pane(title: str, body_widget: QtWidgets.QWidget,
              title_h: int = 22) -> QtWidgets.QWidget:
        """Wrap body in a titled pane."""
        from PySide6 import QtGui

        pane = QtWidgets.QWidget()
        pane.setObjectName(f"WFritzPane_{title.replace(' ', '_')}")
        p_ly = QtWidgets.QVBoxLayout(pane)
        p_ly.setContentsMargins(0, 0, 0, 0)
        p_ly.setSpacing(0)

        class _TitleBar(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                self.setFixedHeight(title_h)
                self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
                ly = QtWidgets.QHBoxLayout(self)
                ly.setContentsMargins(8, 0, 4, 0)
                ly.setSpacing(0)
                lbl = QtWidgets.QLabel(title)
                f = QtGui.QFont()
                f.setPointSize(8)
                f.setBold(True)
                lbl.setFont(f)
                lbl.setStyleSheet(f"color:{tc}; background:transparent;")
                ly.addWidget(lbl, 1)
                for ch in ["▾", "✕"]:
                    btn = QtWidgets.QToolButton()
                    btn.setText(ch)
                    btn.setFixedSize(18, 18)
                    btn.setStyleSheet(
                        f"QToolButton {{ border:none; background:transparent; "
                        f"color:{tc_dim}; font-size:11px; }}"
                        f"QToolButton:hover {{ color:{accent}; }}"
                    )
                    ly.addWidget(btn)

            def paintEvent(self, event):
                p = QtGui.QPainter(self)
                grad = QtGui.QLinearGradient(0, 0, 0, self.height())
                grad.setColorAt(0.0, QtGui.QColor(grad_top))
                grad.setColorAt(1.0, QtGui.QColor(grad_bot))
                p.fillRect(self.rect(), grad)
                p.end()
                super().paintEvent(event)

        p_ly.addWidget(_TitleBar())
        body_widget.setStyleSheet(f"background:{surface}; border:1px solid {border};")
        p_ly.addWidget(body_widget, 1)
        return pane

    # ── Player header (no title bar — it IS the title) ────────────────────────
    player_hdr = QtWidgets.QWidget()
    player_hdr.setFixedHeight(62)
    player_hdr.setStyleSheet(f"background:{surface}; border-bottom:1px solid {border};")
    ph_ly = QtWidgets.QVBoxLayout(player_hdr)
    ph_ly.setContentsMargins(8, 4, 8, 4)
    ph_ly.setSpacing(2)
    for piece, name, clock in [("♛", "Stockfish 18", "01:27"), ("♙", "You", "04:55")]:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        p_lbl = QtWidgets.QLabel(f"{piece}  {name}")
        p_lbl.setStyleSheet(f"color:{tc}; font-size:11px; background:transparent;")
        c_lbl = QtWidgets.QLabel(clock)
        c_lbl.setStyleSheet(
            f"color:{accent}; font-size:12px; font-family:monospace; "
            f"background:#000; padding:1px 4px; border-radius:2px;"
        )
        c_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(p_lbl, 1)
        row.addWidget(c_lbl)
        ph_ly.addLayout(row)
    vly.addWidget(player_hdr)

    # ── Engine analysis pane ──────────────────────────────────────────────────
    analysis_body = QtWidgets.QWidget()
    ab_ly = QtWidgets.QVBoxLayout(analysis_body)
    ab_ly.setContentsMargins(4, 4, 4, 4)
    ab_ly.setSpacing(2)
    lines = [
        ("∓", "#6699cc", "Black slightly better: ∓ (-0.60)  Depth: 24/45  51157kN"),
        ("  ", tc_dim,   "  1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"),
        ("  ", tc_dim,   "  1. e4 c5 2. Nf3 d6 3. d4 cxd4"),
    ]
    for nag, color, text in lines:
        lbl = QtWidgets.QLabel(f"{nag}  {text}")
        lbl.setStyleSheet(
            f"color:{color}; font-size:10px; font-family:monospace; "
            f"background:transparent;"
        )
        ab_ly.addWidget(lbl)
    ab_ly.addStretch()
    analysis_body.setFixedHeight(80)
    vly.addWidget(_pane("Engine analysis", analysis_body))

    # ── Eval graph pane ────────────────────────────────────────────────────────
    from PySide6 import QtGui

    class _EvalGraphMock(QtWidgets.QWidget):
        def paintEvent(self, _ev):
            p = QtGui.QPainter(self)
            p.fillRect(self.rect(), QtGui.QColor(surface))
            # Draw a mock eval bar chart
            import math
            w, h = self.width(), self.height()
            n = 20
            bar_w = max(2, w // n - 1)
            evals = [0.2, 0.3, 0.1, -0.1, -0.3, -0.5, -0.4, -0.2, -0.6,
                     -0.5, -0.4, -0.3, -0.2, 0.0, 0.1, 0.2, 0.3, 0.1, -0.1, -0.2]
            mid = h // 2
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            for i, ev in enumerate(evals):
                x = i * (bar_w + 1) + 4
                bar_h = int(abs(ev) * h * 0.4)
                if ev >= 0:
                    p.setBrush(QtGui.QColor("#c8c8c8"))
                    p.drawRect(x, mid - bar_h, bar_w, bar_h)
                else:
                    p.setBrush(QtGui.QColor("#505050"))
                    p.drawRect(x, mid, bar_w, bar_h)
            # zero line
            p.setPen(QtGui.QColor(border))
            p.drawLine(0, mid, w, mid)
            p.end()

    eval_body = _EvalGraphMock()
    eval_body.setFixedHeight(70)
    vly.addWidget(_pane("Eval profile", eval_body))

    # ── Notation pane ──────────────────────────────────────────────────────────
    notation_body = QtWidgets.QWidget()
    nb_ly = QtWidgets.QVBoxLayout(notation_body)
    nb_ly.setContentsMargins(0, 0, 0, 0)
    nb_ly.setSpacing(0)

    tabbar = QtWidgets.QTabBar()
    tabbar.setObjectName("WFritzNotationTabBar")
    tabbar.setExpanding(False)
    tabbar.setDrawBase(False)
    for tab in ["Notation", "Training", "Score sheet", "LiveBook"]:
        tabbar.addTab(tab)

    grid = QtWidgets.QWidget()
    g_ly = QtWidgets.QGridLayout(grid)
    g_ly.setContentsMargins(4, 2, 4, 2)
    g_ly.setSpacing(1)
    hi = "#094771" if variant == "dark" else "#cce4ff"
    moves2 = [("1.", "e4", "e5"), ("2.", "Nf3", "Nc6"), ("3.", "Bc4", "Bc5"),
              ("4.", "O-O", "Nf6"), ("5.", "d3", "d6")]
    for r, (num, wm, bm) in enumerate(moves2):
        for c, text in enumerate([num, wm, bm]):
            lbl = QtWidgets.QLabel(text)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            st = f"color:{tc}; font-size:10px; padding:1px 3px;"
            if r == 1 and c == 1:
                st += f" background:{hi}; border-radius:2px;"
            lbl.setStyleSheet(st)
            g_ly.addWidget(lbl, r, c)

    nb_ly.addWidget(tabbar)
    nb_ly.addWidget(grid, 1)
    notation_body.setFixedHeight(120)
    vly.addWidget(_pane("Notation", notation_body))

    vly.addStretch()

    px = _grab(outer, width, 440, qss)
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
