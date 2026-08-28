"""
WFritzHome — Fritz-style home/landing screen for Modern Fritz mode.

Shown as a full-panel overlay when Fritz mode is entered and no game is
in progress.  The user picks an action (New Game, Load Game, Analyze)
from large labelled buttons and the panel dismisses itself immediately,
handing control back to the normal flow.

This gives the distinctive Fritz "one screen" feel: the board is always
there, the home state is just the board at the starting position with a
large action panel overlaid on the right column, instead of the default
Lucas Chess menu / empty-board view.

Architecture
────────────
``WFritzHome`` is a ``QWidget`` (not a dialog) reparented into the
right column of the Fritz layout.  ``modern_fritz_ui.on_mode_enter``
adds it as the top pane of the vertical right-column QSplitter and
connects to its ``action_chosen`` signal to dismiss it and show the
analysis panel instead.
"""
import logging

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

_log = logging.getLogger(__name__)


class WFritzHome(QtWidgets.QWidget):
    """Fritz-style home panel.

    :param parent: Parent widget (MainWindow).

    Emits :attr:`action_chosen` ``(str)`` when the user picks an action:
    ``"new_game"``, ``"load_game"``, or ``"analyze"``.
    """

    action_chosen = QtCore.Signal(str)

    _BG = "#252526"
    _SURFACE = "#2d2d2d"
    _BORDER = "#505050"
    _TEXT = "#d4d4d4"
    _DIM = "#9e9e9e"
    _BLUE = "#0078d4"
    _BLUE_HOVER = "#1a88e0"

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("WFritzHome")
        self.setStyleSheet(f"WFritzHome{{background:{self._BG};}}")
        self._build_ui()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(12)

        # Title
        title = QtWidgets.QLabel("Modern Fritz", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{self._TEXT}; font-size:18px; font-weight:bold;"
            f" background:transparent;"
        )
        root.addWidget(title)

        subtitle = QtWidgets.QLabel("Chess Analysis & Play", self)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{self._DIM}; font-size:11px; background:transparent;"
        )
        root.addWidget(subtitle)

        # Separator
        sep = QtWidgets.QFrame(self)
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{self._BORDER};")
        root.addWidget(sep)
        root.addSpacing(4)

        # Action buttons
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

        # Footer hint
        hint = QtWidgets.QLabel("Analysis panel will appear after a game starts", self)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color:{self._DIM}; font-size:10px; background:transparent;"
        )
        root.addWidget(hint)

    def _make_button(self, title, subtitle, primary=False):
        btn = QtWidgets.QPushButton(self)
        btn.setFixedHeight(52)
        bg = self._BLUE if primary else self._SURFACE
        bg_hover = self._BLUE_HOVER if primary else self._BORDER
        text_color = "#ffffff" if primary else self._TEXT

        btn.setStyleSheet(
            f"QPushButton{{"
            f"background:{bg}; color:{text_color};"
            f"border:1px solid {self._BORDER};"
            f"border-radius:4px; text-align:left; padding:4px 12px;"
            f"font-size:12px;"
            f"}}"
            f"QPushButton:hover{{"
            f"background:{bg_hover};"
            f"}}"
        )

        layout = QtWidgets.QVBoxLayout(btn)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        lb_title = QtWidgets.QLabel(title, btn)
        lb_title.setStyleSheet(
            f"color:{text_color}; font-size:12px; font-weight:bold;"
            f" background:transparent; pointer-events:none;"
        )
        lb_sub = QtWidgets.QLabel(subtitle, btn)
        lb_sub.setStyleSheet(
            f"color:{'rgba(255,255,255,0.75)' if primary else self._DIM};"
            f" font-size:10px; background:transparent; pointer-events:none;"
        )

        layout.addWidget(lb_title)
        layout.addWidget(lb_sub)

        return btn

    # ── private ─────────────────────────────────────────────────────────────────

    def _pick(self, action: str):
        self.action_chosen.emit(action)
