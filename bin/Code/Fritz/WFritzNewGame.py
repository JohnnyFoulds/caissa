"""
WFritzNewGame — Fritz-style simplified game-setup dialog.

Replaces the full Play-Against-Engine popup when the user clicks "New Game"
in Modern Fritz mode.  Three simple choices instead of 50+ options:

    Side:    [White]  [Black]  [Random]
    Level:   [Easy]  [Club]  [Active]  [Strong]  [Master]  [Grandmaster]
    Time:    [No limit]  [Blitz 5']  [Rapid 15']  [Classical 60']

Returns a ``dic`` compatible with ``ManagerPlayAgainstEngine.start()``.

All colour and geometry values come from the active ``.qss`` via standard
QSS selectors and E4 dynamic properties (``[selected="1"]``); no Python hex
constants are used.  See ``Modern Fritz.qss`` for the ``#WFritzNewGame*`` blocks.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import random
import logging

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

import Code
from Code.Base.Constantes import ADJUST_BETTER, ENG_INTERNAL, TIMEMODE_SUDDEN_DEATH
from Code.Engines import SelectEngines

_log = logging.getLogger(__name__)

_LEVELS = [
    ("Easy",        3,    10),
    ("Club",        8,    20),
    ("Active",      13,   30),
    ("Strong",      17,   50),
    ("Master",      20,   100),
    ("Grandmaster", 20,   0),
]

_TIMES = [
    ("No limit",      0,    0),
    ("Blitz 5'",      5,    0),
    ("Rapid 15'",     15,   0),
    ("Classical 60'", 60,   0),
]


class WFritzNewGame(QtWidgets.QDialog):
    """Fritz-style simplified game-start dialog.

    Toggle buttons use the E4 pattern: ``setProperty("selected", "1")`` +
    ``unpolish``/``polish`` so the ``.qss`` ``[selected="1"]`` selector applies.

    :param parent: Parent widget (main window).

    :spec: §5.3, Phase 1 (feature_spec.md)
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
        )
        self.setWindowTitle("Levels")
        self.setObjectName("WFritzNewGame")
        self.setMinimumWidth(440)

        self._side = "B"
        self._level_idx = 1
        self._time_idx = 0

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

    def _section(self, title: str) -> QtWidgets.QLabel:
        lb = QtWidgets.QLabel(title.upper(), self)
        lb.setObjectName("WFritzNewGameSection")
        return lb

    def _build_side_row(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._side_btns: dict[str, QtWidgets.QPushButton] = {}
        for label, key in [("White ♔", "B"), ("Black ♚", "N"), ("Random ⇄", "R")]:
            btn = self._toggle_btn(label)
            btn.clicked.connect(lambda _, k=key: self._pick_side(k))
            self._side_btns[key] = btn
            hl.addWidget(btn)
        hl.addStretch()
        self._refresh_btn_group(self._side_btns, "B")
        return row

    def _build_level_row(self):
        row = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._level_btns: dict[int, QtWidgets.QPushButton] = {}
        for i, (label, _skill, _time) in enumerate(_LEVELS):
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

        self._time_btns: dict[int, QtWidgets.QPushButton] = {}
        for i, (label, _mins, _sec_inc) in enumerate(_TIMES):
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
        cancel_btn.setObjectName("WFritzNewGameCancel")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QtWidgets.QPushButton("Start Game", row)
        ok_btn.setFixedHeight(32)
        ok_btn.setDefault(True)
        ok_btn.setObjectName("WFritzNewGameOk")
        ok_btn.clicked.connect(self.accept)

        hl.addWidget(cancel_btn)
        hl.addSpacing(8)
        hl.addWidget(ok_btn)
        return row

    # ── toggle buttons ─────────────────────────────────────────────────────────

    def _toggle_btn(self, label: str) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(label, self)
        btn.setFixedHeight(30)
        btn.setObjectName("WFritzNewGameToggle")
        btn.setProperty("selected", "0")
        return btn

    def _refresh_btn_group(self, btns: dict, selected_key) -> None:
        for key, btn in btns.items():
            val = "1" if key == selected_key else "0"
            btn.setProperty("selected", val)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── selection handlers ─────────────────────────────────────────────────────

    def _pick_side(self, key: str) -> None:
        self._side = key
        self._refresh_btn_group(self._side_btns, key)

    def _pick_level(self, idx: int) -> None:
        self._level_idx = idx
        self._refresh_btn_group(self._level_btns, idx)

    def _pick_time(self, idx: int) -> None:
        self._time_idx = idx
        self._refresh_btn_group(self._time_btns, idx)

    # ── result ─────────────────────────────────────────────────────────────────

    def get_dic(self) -> dict | None:
        """Build the ``dic_var`` for ``ManagerPlayAgainstEngine.start()``.

        :returns: Configuration dict, or ``None`` if no suitable engine found.
        """
        side = self._side
        if side == "R":
            side = "B" if random.randint(1, 2) == 1 else "N"

        try:
            engine = SelectEngines.busca_engine_default(ENG_INTERNAL, "stockfish", None)
            if engine is None:
                engine = SelectEngines.busca_engine_default(ENG_INTERNAL, Code.configuration.x_rival_inicial, None)
        except Exception:
            _log.error("Fritz new game: could not resolve engine", exc_info=True)
            return None
        if engine is None:
            _log.error("Fritz new game: no usable engine found")
            return None

        label, skill_level, time_tenths = _LEVELS[self._level_idx]
        time_label, minutes, _sec_inc = _TIMES[self._time_idx]
        with_time = minutes > 0

        li_uci = [("UCI_LimitStrength", "true"), ("UCI_Elo", str(800 + skill_level * 150))]

        dr = {
            "ENGINE": engine.key,
            "TYPE": ENG_INTERNAL,
            "ALIAS": engine.key,
            "LIUCI": li_uci,
            "ENGINE_TIME": time_tenths,
            "ENGINE_DEPTH": 0,
            "ENGINE_NODES": 0,
            "ENGINE_UNLIMITED": 3,
        }

        return {
            "SIDE": self._side,
            "ISWHITE": side == "B",
            "RIVAL": dr,
            "ADJUST": ADJUST_BETTER,
            "ANALYSIS_BAR": True,
            "HINTS": 3,
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
