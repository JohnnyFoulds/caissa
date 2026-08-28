"""
WFritzPlayerHeader — player name / clock strip for Fritz mode.

Displays both players at the top of the Fritz right column, matching Fritz 18's
player-info bar:

    ♛  Stockfish 18                     00:00
    ♙  Johannes Foulds                  00:00

Black player is shown at the top (they sit at the far side of the board),
white player below.  Data is polled from WBase's existing labels at 500 ms
so no reparenting is required and the manager keeps full control of updates.

Design values arrive via ``qproperty-`` on the ``WFritzPlayerHeader`` selector
in the active ``.qss``; see ``docs/fritz/qss-contract.md`` for the full E1
property table.  Python defaults equal the ``Modern Fritz`` dark-theme values.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from Code.Fritz.WFritzLCD import WFritzLCD

_log = logging.getLogger(__name__)


class _PlayerRow(QtWidgets.QWidget):
    """One player row: piece icon + name (left) and clock (right)."""

    def __init__(self, parent, piece_char: str, icon_color: str):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._icon_color = icon_color

        ly = QtWidgets.QHBoxLayout(self)
        ly.setContentsMargins(8, 2, 8, 2)
        ly.setSpacing(6)

        icon_lbl = QtWidgets.QLabel(piece_char, self)
        icon_lbl.setFixedWidth(16)
        f_icon = QtGui.QFont()
        f_icon.setPointSize(14)
        icon_lbl.setFont(f_icon)
        icon_lbl.setStyleSheet(f"color:{icon_color}; background:transparent;")

        self._name = QtWidgets.QLabel("", self)
        self._name.setObjectName("WFritzPlayerName")

        self._clock = WFritzLCD(self)
        self._clock.setObjectName("WFritzPlayerClock")

        ly.addWidget(icon_lbl)
        ly.addWidget(self._name, 1)
        ly.addWidget(self._clock)

    def update_text(self, name: str, clock: str):
        self._name.setText(name)
        self._clock.set_time_text(clock)

    def paintEvent(self, event):
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()
        super().paintEvent(event)


class WFritzPlayerHeader(QtWidgets.QWidget):
    """Fritz-style player info strip.

    Design values (colours, row height) arrive from the QSS via
    ``qproperty-`` properties; Python defaults equal the ``Modern Fritz``
    dark-theme values so the widget renders correctly with no stylesheet.

    :param parent: Parent widget (MainWindow).
    :param base:   WBase instance — polled for player/clock label text.

    :spec: §5.3, Phase 1 (feature_spec.md)
    """

    # ── E1: qproperty- contract ────────────────────────────────────────────────
    # Default values = Modern Fritz dark theme.  Qt sets these at polish time.

    def _get_bgColor(self) -> QtGui.QColor:
        return self._bgColor

    def _set_bgColor(self, v: QtGui.QColor) -> None:
        self._bgColor = v
        self.update()

    bgColor = QtCore.Property(QtGui.QColor, _get_bgColor, _set_bgColor)

    def _get_borderColor(self) -> QtGui.QColor:
        return self._borderColor

    def _set_borderColor(self, v: QtGui.QColor) -> None:
        self._borderColor = v
        self.update()

    borderColor = QtCore.Property(QtGui.QColor, _get_borderColor, _set_borderColor)

    def _get_rowHeight(self) -> int:
        return self._rowHeight

    def _set_rowHeight(self, v: int) -> None:
        self._rowHeight = v
        self.setFixedHeight(v * 2 + 1)

    rowHeight = QtCore.Property(int, _get_rowHeight, _set_rowHeight)

    # ── constructor ────────────────────────────────────────────────────────────

    def __init__(self, parent, base):
        super().__init__(parent)
        self.setObjectName("WFritzPlayerHeader")
        self._base = base

        # E1 property defaults (Modern Fritz dark values)
        self._bgColor = QtGui.QColor("#1e1e1e")
        self._borderColor = QtGui.QColor("#505050")
        self._rowHeight = 30

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(self._rowHeight * 2 + 1)
        self.setMinimumWidth(180)

        ly = QtWidgets.QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        self._black_row = _PlayerRow(self, "♛", "#b0b0b0")
        self._white_row = _PlayerRow(self, "♙", "#ffffff")

        sep = QtWidgets.QFrame(self)
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setObjectName("WFritzPlayerHeaderSep")

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

    def paintEvent(self, event):
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        # bottom border
        p.setPen(self._borderColor)
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()
        super().paintEvent(event)
