"""
WFritzEvalGraph — Fritz-style evaluation profile graph.

Shows a per-half-move evaluation history bar chart, similar to Fritz 15–18's
"evaluation profile" that sits above the move list.  White advantage is drawn
above the centre line in Fritz blue; black advantage is drawn below in red.

Design values arrive via ``qproperty-`` on the ``WFritzEvalGraph`` selector
in the active ``.qss``; see ``docs/fritz/qss-contract.md`` for the full E1
property table.  Python defaults equal the ``Modern Fritz`` dark-theme values.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

_log = logging.getLogger(__name__)

_CAP_CP = 600     # centipawns shown at full height
_MATE_CP = 30000  # centipawns_abs() value for mate


class WFritzEvalGraph(QtWidgets.QWidget):
    """Fritz-style evaluation profile graph.

    Design values (colours, height) arrive from the QSS via ``qproperty-``
    properties; Python defaults equal the ``Modern Fritz`` dark-theme values.

    :param parent:       Parent widget (MainWindow).
    :param analysis_bar: Running ``AnalysisBar`` instance.

    :spec: §5.3, Phase 1 (feature_spec.md)
    """

    # ── E1: qproperty- contract ────────────────────────────────────────────────

    def _get_bgColor(self) -> QtGui.QColor:
        return self._bgColor

    def _set_bgColor(self, v: QtGui.QColor) -> None:
        self._bgColor = v
        self.update()

    bgColor = QtCore.Property(QtGui.QColor, _get_bgColor, _set_bgColor)

    def _get_dividerColor(self) -> QtGui.QColor:
        return self._dividerColor

    def _set_dividerColor(self, v: QtGui.QColor) -> None:
        self._dividerColor = v
        self.update()

    dividerColor = QtCore.Property(QtGui.QColor, _get_dividerColor, _set_dividerColor)

    def _get_whiteBarColor(self) -> QtGui.QColor:
        return self._whiteBarColor

    def _set_whiteBarColor(self, v: QtGui.QColor) -> None:
        self._whiteBarColor = v
        self.update()

    whiteBarColor = QtCore.Property(QtGui.QColor, _get_whiteBarColor, _set_whiteBarColor)

    def _get_blackBarColor(self) -> QtGui.QColor:
        return self._blackBarColor

    def _set_blackBarColor(self, v: QtGui.QColor) -> None:
        self._blackBarColor = v
        self.update()

    blackBarColor = QtCore.Property(QtGui.QColor, _get_blackBarColor, _set_blackBarColor)

    def _get_currentBarColor(self) -> QtGui.QColor:
        return self._currentBarColor

    def _set_currentBarColor(self, v: QtGui.QColor) -> None:
        self._currentBarColor = v
        self.update()

    currentBarColor = QtCore.Property(QtGui.QColor, _get_currentBarColor, _set_currentBarColor)

    def _get_graphHeight(self) -> int:
        return self._graphHeight

    def _set_graphHeight(self, v: int) -> None:
        self._graphHeight = v
        self.setFixedHeight(v)

    graphHeight = QtCore.Property(int, _get_graphHeight, _set_graphHeight)

    # ── constructor ────────────────────────────────────────────────────────────

    def __init__(self, parent, analysis_bar):
        super().__init__(parent)
        self.setObjectName("WFritzEvalGraph")
        self.analysis_bar = analysis_bar

        # E1 property defaults (Modern Fritz dark values)
        self._bgColor = QtGui.QColor("#1e1e1e")
        self._dividerColor = QtGui.QColor("#505050")
        self._whiteBarColor = QtGui.QColor("#0078d4")
        self._blackBarColor = QtGui.QColor("#d16969")
        self._currentBarColor = QtGui.QColor("#ffffff")
        self._graphHeight = 80

        self.setFixedHeight(self._graphHeight)
        self.setMinimumWidth(80)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        self._evals: list[int] = []
        self._last_ply: int = -1
        self._current_ply: int = -1
        self._last_mrm_cp: int = 0

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)

    # ── public API ─────────────────────────────────────────────────────────────

    def start(self):
        """Begin polling and accumulating evaluations."""
        self._timer.start()

    def stop(self):
        """Stop polling."""
        self._timer.stop()

    def reset(self):
        """Clear accumulated evaluation history (call when a new game starts)."""
        self._evals = []
        self._last_ply = -1
        self._current_ply = -1
        self._last_mrm_cp = 0
        self.update()

    # ── private ────────────────────────────────────────────────────────────────

    def _refresh(self):
        bar = self.analysis_bar
        if not bar or not bar.activated:
            return

        try:
            import Code
            mgr = Code.procesador.manager if Code.procesador else None
            game = getattr(mgr, "game", None) if mgr else None
            if game is None:
                game = getattr(bar, "game", None)
            ply = len(game.li_moves) if game else 0
        except Exception:
            return

        mrm = bar.mrm
        if mrm:
            rm = mrm.rm_best()
            if rm:
                cp_abs = rm.centipawns_abs()
                if cp_abs >= _MATE_CP:
                    cp_abs = _CAP_CP * 2
                signed = cp_abs if rm.is_white else -cp_abs
                self._last_mrm_cp = signed

        self._current_ply = ply

        if ply > self._last_ply:
            while len(self._evals) < ply:
                self._evals.append(self._last_mrm_cp)
            self._last_ply = ply
            self.update()
        elif ply < len(self._evals):
            self._evals = self._evals[:ply]
            self._last_ply = ply
            self.update()

    # ── painting ───────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        p = QtGui.QPainter(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()
        mid = h // 2

        p.fillRect(0, 0, w, h, self._bgColor)

        n = len(self._evals)
        if n == 0:
            p.setPen(self._dividerColor)
            p.drawLine(0, mid, w, mid)
            p.end()
            return

        bar_w = max(2, w // max(n, 1))
        if bar_w * n < w:
            bar_w = max(2, w // n)

        for i, cp in enumerate(self._evals):
            x = i * bar_w
            clamped = max(-_CAP_CP, min(_CAP_CP, cp))
            height_px = int(abs(clamped) / _CAP_CP * (mid - 2))
            height_px = max(1, height_px)

            is_current = (i == self._current_ply - 1)
            if is_current:
                color = self._currentBarColor
            elif cp >= 0:
                color = self._whiteBarColor
            else:
                color = self._blackBarColor

            if cp >= 0:
                rect = QtCore.QRect(x, mid - height_px, bar_w - 1, height_px)
            else:
                rect = QtCore.QRect(x, mid, bar_w - 1, height_px)

            p.fillRect(rect, color)

        p.setPen(self._dividerColor)
        p.drawLine(0, mid, w, mid)
        p.end()
