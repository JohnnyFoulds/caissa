"""
WFritzNewGame — Fritz-style simplified game-setup dialog.

Replaces the full Play-Against-Engine popup when the user clicks "New Game"
in Modern Fritz mode.  Three simple choices instead of 50+ options:

    Side:    [White]  [Black]  [Random]
    Level:   [Easy]  [Club]  [Active]  [Strong]  [Master]  [Grandmaster]
    Time:    [No limit]  [Blitz 5']  [Rapid 15']  [Classical 60']

Returns a ``dic`` compatible with ``ManagerPlayAgainstEngine.start()``.
"""
import random
import logging

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

import Code
from Code.Base.Constantes import ADJUST_BETTER, ENG_INTERNAL, TIMEMODE_SUDDEN_DEATH
from Code.Engines import SelectEngines

_log = logging.getLogger(__name__)

_BG = "#252526"
_SURFACE = "#2d2d2d"
_BORDER = "#505050"
_TEXT = "#d4d4d4"
_DIM = "#9e9e9e"
_BLUE = "#0078d4"
_BLUE_HOVER = "#1a88e0"
_SELECTED_BG = "#0078d4"
_SELECTED_FG = "#ffffff"
_BTN_FG = "#d4d4d4"

_LEVELS = [
    ("Easy",        5,    0),    # (label, depth, time_tenths)
    ("Club",        10,   0),
    ("Active",      15,   0),
    ("Strong",      20,   0),
    ("Master",      0,    50),   # 5s per move
    ("Grandmaster", 0,    0),    # unlimited
]

_TIMES = [
    ("No limit",      0,    0),   # (label, minutes, seconds_inc)
    ("Blitz 5'",      5,    0),
    ("Rapid 15'",     15,   0),
    ("Classical 60'", 60,   0),
]


class WFritzNewGame(QtWidgets.QDialog):
    """Fritz-style simplified game-start dialog.

    :param parent: Parent widget (main window).
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
        )
        self.setWindowTitle("New Game")
        self.setMinimumWidth(440)
        self.setStyleSheet(
            f"QDialog{{background:{_BG}; color:{_TEXT};}}"
            f"QLabel{{background:transparent;}}"
        )

        self._side = "B"          # "B"=white, "N"=black, "R"=random
        self._level_idx = 1       # Club default
        self._time_idx = 0        # No limit default

        self._build_ui()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        root.addWidget(self._section("Side"))
        root.addWidget(self._build_side_row())
        root.addWidget(self._section("Level"))
        root.addWidget(self._build_level_row())
        root.addWidget(self._section("Time control"))
        root.addWidget(self._build_time_row())

        root.addSpacing(4)
        root.addWidget(self._build_buttons())

    def _section(self, title):
        lb = QtWidgets.QLabel(title.upper(), self)
        lb.setStyleSheet(
            f"color:{_DIM}; font-size:10px; letter-spacing:1px;"
            f" background:transparent;"
        )
        return lb

    def _build_side_row(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._side_btns = {}
        for label, key in [("White ♔", "B"), ("Black ♚", "N"), ("Random ⇄", "R")]:
            btn = self._toggle_btn(label)
            btn.clicked.connect(lambda _, k=key: self._pick_side(k))
            self._side_btns[key] = btn
            hl.addWidget(btn)
        hl.addStretch()
        self._side_btns["B"].setProperty("selected", True)
        self._refresh_btn_group(self._side_btns, "B")
        return row

    def _build_level_row(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._level_btns = {}
        for i, (label, depth, time_tenths) in enumerate(_LEVELS):
            btn = self._toggle_btn(label)
            btn.clicked.connect(lambda _, idx=i: self._pick_level(idx))
            self._level_btns[i] = btn
            hl.addWidget(btn)
        self._refresh_btn_group(self._level_btns, self._level_idx)
        return row

    def _build_time_row(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._time_btns = {}
        for i, (label, mins, sec_inc) in enumerate(_TIMES):
            btn = self._toggle_btn(label)
            btn.clicked.connect(lambda _, idx=i: self._pick_time(idx))
            self._time_btns[i] = btn
            hl.addWidget(btn)
        hl.addStretch()
        self._refresh_btn_group(self._time_btns, self._time_idx)
        return row

    def _build_buttons(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel", row)
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:{_SURFACE};color:{_TEXT};"
            f"border:1px solid {_BORDER};border-radius:3px;padding:0 16px;}}"
            f"QPushButton:hover{{background:{_BORDER};}}"
        )
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QtWidgets.QPushButton("Start Game", row)
        ok_btn.setFixedHeight(32)
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet(
            f"QPushButton{{background:{_BLUE};color:#fff;"
            f"border:none;border-radius:3px;padding:0 20px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{_BLUE_HOVER};}}"
        )
        ok_btn.clicked.connect(self.accept)

        hl.addWidget(cancel_btn)
        hl.addSpacing(8)
        hl.addWidget(ok_btn)
        return row

    # ── toggle buttons ─────────────────────────────────────────────────────────

    def _toggle_btn(self, label):
        btn = QtWidgets.QPushButton(label, self)
        btn.setFixedHeight(30)
        btn.setStyleSheet(self._btn_style(False))
        return btn

    @staticmethod
    def _btn_style(selected: bool) -> str:
        if selected:
            return (
                f"QPushButton{{background:{_SELECTED_BG};color:{_SELECTED_FG};"
                f"border:1px solid {_SELECTED_BG};border-radius:3px;padding:0 10px;}}"
            )
        return (
            f"QPushButton{{background:{_SURFACE};color:{_BTN_FG};"
            f"border:1px solid {_BORDER};border-radius:3px;padding:0 10px;}}"
            f"QPushButton:hover{{background:{_BORDER};}}"
        )

    def _refresh_btn_group(self, btns: dict, selected_key):
        for key, btn in btns.items():
            btn.setStyleSheet(self._btn_style(key == selected_key))

    # ── selection handlers ─────────────────────────────────────────────────────

    def _pick_side(self, key):
        self._side = key
        self._refresh_btn_group(self._side_btns, key)

    def _pick_level(self, idx):
        self._level_idx = idx
        self._refresh_btn_group(self._level_btns, idx)

    def _pick_time(self, idx):
        self._time_idx = idx
        self._refresh_btn_group(self._time_btns, idx)

    # ── result ─────────────────────────────────────────────────────────────────

    def get_dic(self) -> dict:
        """Build the ``dic_var`` for ``ManagerPlayAgainstEngine.start()``.

        :returns: Configuration dict, or ``None`` if no suitable engine found.
        """
        side = self._side
        if side == "R":
            side = "B" if random.randint(1, 2) == 1 else "N"

        try:
            engine_key = Code.configuration.x_rival_inicial
            engine = SelectEngines.busca_engine_default(ENG_INTERNAL, engine_key, None)
        except Exception:
            _log.error("Fritz new game: could not resolve default engine", exc_info=True)
            return None

        label, depth, time_tenths = _LEVELS[self._level_idx]
        time_label, minutes, _sec_inc = _TIMES[self._time_idx]
        with_time = minutes > 0

        dr = {
            "ENGINE": engine.key,
            "TYPE": ENG_INTERNAL,
            "ALIAS": engine.key,
            "LIUCI": list(getattr(engine, "liUCI", [])),
            "ENGINE_TIME": time_tenths,
            "ENGINE_DEPTH": depth,
            "ENGINE_NODES": 0,
            "ENGINE_UNLIMITED": 3,
        }

        return {
            "SIDE": self._side,
            "ISWHITE": side == "B",
            "RIVAL": dr,
            "ADJUST": ADJUST_BETTER,
            "HINTS": 0,
            "THOUGHTTT": -1,
            "ARROWSTT": 0,
            "2CHANCE": True,
            "ARROWS": 0,
            "THOUGHTOP": -1,
            "BOXHEIGHT": 24,
            "SUMMARY": False,
            "TAKEBACK": True,
            "WITH_LIMIT_PWW": False,
            "LIMIT_PWW": 90,
            "OPENIGSFAVORITES": [],
            "OPENING": None,
            "OPENING_LINE": None,
            "FEN": "",
            "BOOKR": None,
            "BOOKP": None,
            "RESIGN": -800,
            "WITHTIME": with_time,
            "TIME_MODE": TIMEMODE_SUDDEN_DEATH,
            "MINUTES": float(minutes),
            "SECONDS": 0,
            "MINEXTRA": 0.0,
            "DISABLEUSERTIME": False,
            "ZEITNOT": 0,
            "LEVEL_HUMANIZE": 0,
        }
