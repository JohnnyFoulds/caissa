"""
WFritzEvalGraph — Fritz-style evaluation profile graph.

Shows a per-half-move evaluation history bar chart, similar to Fritz 15–18's
"evaluation profile" that sits above the move list.  White advantage is drawn
above the centre line in Fritz blue; black advantage is drawn below in red.

Architecture
────────────
The widget accumulates evaluations by polling the ``AnalysisBar.mrm`` object
at 250 ms intervals.  Each time the game gains a new half-move, the current
centipawn value is locked in for that ply.  If the user navigates backwards
(ply count drops) the trailing entries are trimmed so the graph matches the
visible board position.

Bars are capped at ± :data:`_CAP_CP` centipawns for visual scaling; mate
values (±30000 from ``centipawns_abs()``) are rendered at the cap boundary.

The widget has a fixed height of 80 px and expands horizontally.
"""
import logging

from PySide6 import QtCore, QtGui, QtWidgets

_log = logging.getLogger(__name__)

_BG = "#1e1e1e"
_DIVIDER = "#505050"
_WHITE_BAR = "#0078d4"
_BLACK_BAR = "#d16969"
_CURRENT = "#ffffff"
_H = 80           # fixed height in px
_CAP_CP = 600     # centipawns shown at full height
_MATE_CP = 30000  # centipawns_abs() value for mate


class WFritzEvalGraph(QtWidgets.QWidget):
    """Fritz-style evaluation profile graph.

    :param parent:       Parent widget (MainWindow).
    :param analysis_bar: Running :class:`~Code.Main.WAnalysisBar.AnalysisBar` instance.
    """

    def __init__(self, parent, analysis_bar):
        super().__init__(parent)
        self.setObjectName("WFritzEvalGraph")
        self.analysis_bar = analysis_bar

        self.setFixedHeight(_H)
        self.setMinimumWidth(80)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)

        # _evals: list of signed centipawn values, one per half-move played.
        # Positive = white advantage; negative = black advantage.
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

        # Derive current ply from the game object
        try:
            import Code
            mgr = Code.procesador.manager if Code.procesador else None
            game = getattr(mgr, "game", None) if mgr else None
            if game is None:
                game = getattr(bar, "game", None)
            ply = len(game.li_moves) if game else 0
        except Exception:
            return

        # Read current analysis value (signed centipawns, white perspective)
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

        # If ply grew: lock in evaluation for the position just reached
        if ply > self._last_ply:
            # Fill any gap (shouldn't happen except on resume)
            while len(self._evals) < ply:
                self._evals.append(self._last_mrm_cp)
            self._last_ply = ply
            self.update()

        # If ply shrank (user navigated back): trim
        elif ply < len(self._evals):
            self._evals = self._evals[:ply]
            self._last_ply = ply
            self.update()

    # ── painting ───────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()
        mid = h // 2

        # Background
        p.fillRect(0, 0, w, h, QtGui.QColor(_BG))

        n = len(self._evals)
        if n == 0:
            # Draw centre line only
            p.setPen(QtGui.QColor(_DIVIDER))
            p.drawLine(0, mid, w, mid)
            p.end()
            return

        bar_w = max(2, w // max(n, 1))
        # When bars are very thin, render them pixel-tight
        if bar_w * n < w:
            bar_w = max(2, w // n)

        col_white = QtGui.QColor(_WHITE_BAR)
        col_black = QtGui.QColor(_BLACK_BAR)
        col_curr = QtGui.QColor(_CURRENT)

        for i, cp in enumerate(self._evals):
            x = i * bar_w
            clamped = max(-_CAP_CP, min(_CAP_CP, cp))
            height_px = int(abs(clamped) / _CAP_CP * (mid - 2))
            height_px = max(1, height_px)

            is_current = (i == self._current_ply - 1)
            if is_current:
                color = col_curr
            elif cp >= 0:
                color = col_white
            else:
                color = col_black

            if cp >= 0:
                rect = QtCore.QRect(x, mid - height_px, bar_w - 1, height_px)
            else:
                rect = QtCore.QRect(x, mid, bar_w - 1, height_px)

            p.fillRect(rect, color)

        # Centre divider
        p.setPen(QtGui.QColor(_DIVIDER))
        p.drawLine(0, mid, w, mid)
        p.end()
