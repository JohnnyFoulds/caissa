"""
WFritzHome — Fritz-style home/landing screen for Modern Fritz mode.

Shown as a full-panel overlay when Fritz mode is entered and no game is
in progress.  The user picks an action (New Game, Load Game, Analyze)
from large labelled buttons and the panel dismisses itself immediately,
handing control back to the normal flow.

All colour and geometry values come from the active ``.qss`` via standard
QSS selectors on the widget's object names; no Python hex constants are
used.  See ``Modern Fritz.qss`` for the ``#WFritzHome*`` blocks.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

_log = logging.getLogger(__name__)


class WFritzHome(QtWidgets.QWidget):
    """Fritz-style home panel.

    :param parent: Parent widget (MainWindow).

    Emits :attr:`action_chosen` ``(str)`` when the user picks an action:
    ``"new_game"``, ``"load_game"``, or ``"analyze"``.

    :spec: §5.3, Phase 1 (feature_spec.md)
    """

    action_chosen = QtCore.Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("WFritzHome")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(12)

        title = QtWidgets.QLabel("Modern Fritz", self)
        title.setObjectName("WFritzHomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QtWidgets.QLabel("Chess Analysis & Play", self)
        subtitle.setObjectName("WFritzHomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        sep = QtWidgets.QFrame(self)
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setObjectName("WFritzHomeSep")
        root.addWidget(sep)
        root.addSpacing(4)

        btn_new = self._make_button("New Game", "Start a new game", primary=True)
        btn_load = self._make_button("Load Game", "Open a saved game or PGN")
        btn_analyze = self._make_button("Enter & Analyze", "Set up position for analysis")

        btn_new.clicked.connect(lambda: self._pick("new_game"))
        btn_load.clicked.connect(lambda: self._pick("load_game"))
        btn_analyze.clicked.connect(lambda: self._pick("analyze"))

        root.addWidget(btn_new)
        root.addWidget(btn_load)
        root.addWidget(btn_analyze)

        root.addStretch()

        hint = QtWidgets.QLabel("Analysis panel will appear after a game starts", self)
        hint.setObjectName("WFritzHomeHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

    def _make_button(self, title: str, subtitle: str, primary: bool = False) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(self)
        btn.setFixedHeight(52)
        btn.setObjectName("WFritzHomeBtnPrimary" if primary else "WFritzHomeBtnSecondary")

        layout = QtWidgets.QVBoxLayout(btn)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(1)

        lb_title = QtWidgets.QLabel(title, btn)
        lb_title.setObjectName("WFritzHomeBtnTitle")
        lb_sub = QtWidgets.QLabel(subtitle, btn)
        lb_sub.setObjectName("WFritzHomeBtnSub")

        layout.addWidget(lb_title)
        layout.addWidget(lb_sub)

        return btn

    # ── private ─────────────────────────────────────────────────────────────────

    def _pick(self, action: str):
        self.action_chosen.emit(action)
