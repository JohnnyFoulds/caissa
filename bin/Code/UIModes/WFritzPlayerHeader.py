"""
WFritzPlayerHeader — player name / clock strip for Fritz mode.

Displays both players at the top of the Fritz right column, matching Fritz 18's
player-info bar:

    ♛  Stockfish 18                     00:00
    ♙  Johannes Foulds                  00:00

Black player is shown at the top (they sit at the far side of the board),
white player below.  Data is polled from WBase's existing labels at 500 ms
so no reparenting is required and the manager keeps full control of updates.
"""
import logging

from PySide6 import QtCore, QtGui, QtWidgets

_log = logging.getLogger(__name__)

_BG = "#1e1e1e"
_SURFACE = "#2d2d2d"
_BORDER = "#505050"
_TEXT = "#d4d4d4"
_DIM = "#9e9e9e"
_CLOCK = "#0078d4"
_H = 60


class _PlayerRow(QtWidgets.QWidget):
    """One player row: piece icon + name (left) and clock (right)."""

    def __init__(self, parent, piece_char: str, color_hex: str):
        super().__init__(parent)
        self.setFixedHeight(_H // 2)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)

        ly = QtWidgets.QHBoxLayout(self)
        ly.setContentsMargins(8, 2, 8, 2)
        ly.setSpacing(6)

        icon_lbl = QtWidgets.QLabel(piece_char, self)
        icon_lbl.setFixedWidth(16)
        f_icon = QtGui.QFont()
        f_icon.setPointSize(14)
        icon_lbl.setFont(f_icon)
        icon_lbl.setStyleSheet(f"color:{color_hex}; background:transparent;")

        self._name = QtWidgets.QLabel("", self)
        f_name = QtGui.QFont()
        f_name.setPointSize(10)
        f_name.setBold(True)
        self._name.setFont(f_name)
        self._name.setStyleSheet(f"color:{_TEXT}; background:transparent;")

        self._clock = QtWidgets.QLabel("", self)
        f_clock = QtGui.QFont()
        f_clock.setPointSize(10)
        f_clock.setFamily("Menlo")
        self._clock.setFont(f_clock)
        self._clock.setStyleSheet(f"color:{_CLOCK}; background:transparent;")
        self._clock.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        ly.addWidget(icon_lbl)
        ly.addWidget(self._name, 1)
        ly.addWidget(self._clock)

    def update_text(self, name: str, clock: str):
        self._name.setText(name)
        self._clock.setText(clock)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(_BG))
        p.end()


class WFritzPlayerHeader(QtWidgets.QWidget):
    """Fritz-style player info strip.

    :param parent: Parent widget (MainWindow).
    :param base:   WBase instance — polled for player/clock label text.
    """

    def __init__(self, parent, base):
        super().__init__(parent)
        self.setObjectName("WFritzPlayerHeader")
        self._base = base
        self.setFixedHeight(_H)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumWidth(180)

        ly = QtWidgets.QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        self._black_row = _PlayerRow(self, "♛", "#b0b0b0")
        self._white_row = _PlayerRow(self, "♙", "#ffffff")

        # Separator line between rows
        sep = QtWidgets.QFrame(self)
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{_BORDER}; border:none;")

        ly.addWidget(self._black_row)
        ly.addWidget(sep)
        ly.addWidget(self._white_row)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._sync)

    # ── public API ─────────────────────────────────────────────────────────────

    def start(self):
        """Begin polling WBase labels."""
        self._sync()
        self._timer.start()

    def stop(self):
        """Stop polling."""
        self._timer.stop()

    # ── private ────────────────────────────────────────────────────────────────

    def _sync(self):
        base = self._base
        try:
            bname = base.lb_player_black.text()
            wname = base.lb_player_white.text()
            bclk = base.lb_clock_black.text()
            wclk = base.lb_clock_white.text()
        except Exception:
            return
        self._black_row.update_text(bname, bclk)
        self._white_row.update_text(wname, wclk)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(_BG))
        # Bottom border
        p.setPen(QtGui.QColor(_BORDER))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()
