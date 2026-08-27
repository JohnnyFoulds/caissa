"""
WFritzEnginePanel — Fritz-style engine analysis widget for the Modern Fritz mode.

Sits as the top section of the right column (inserted into MainWindow.splitter
at index 1, pushing pgn_information to index 2).  Displays engine name, search
depth, evaluation score, and best line — the elements Fritz 15–18 shows
prominently above the move list.

Data source: reads `analysis_bar.mrm` every 250 ms via a QTimer; no second
engine is started.  The Fritz panel reuses the same analyzer that powers the
side eval bar.
"""
import logging

from PySide6 import QtCore, QtWidgets

import Code
from Code.Base import Game

_log = logging.getLogger(__name__)


class WFritzEnginePanel(QtWidgets.QWidget):
    """Fritz-style engine analysis panel.

    :param parent:        Parent widget (MainWindow).
    :param analysis_bar:  The running AnalysisBar instance to read data from.
    """

    _STYLESHEET = """
WFritzEnginePanel
{
    background-color: #1f1f1f;
    border-bottom: 1px solid #3a3a3a;
}

QLabel#fritz_header
{
    color: #8a8a8a;
    font-size: 11px;
    padding: 4px 8px 0px 8px;
}

QLabel#fritz_score
{
    color: #0078d4;
    font-size: 14px;
    font-weight: bold;
    padding: 0px 8px;
}

QLabel#fritz_line
{
    color: #e8e8e8;
    font-size: 11px;
    padding: 2px 8px 6px 8px;
}

QProgressBar#fritz_evalbar
{
    border: none;
    border-radius: 0px;
    background-color: #1a1a1a;
    height: 10px;
    text-align: center;
}

QProgressBar#fritz_evalbar::chunk
{
    background-color: #d4d4d4;
    border-radius: 0px;
}
"""

    def __init__(self, parent, analysis_bar):
        super().__init__(parent)
        self.setObjectName("WFritzEnginePanel")
        self.analysis_bar = analysis_bar

        # --- Header row: engine name (left) + depth (right)
        self._lb_header = QtWidgets.QLabel("", self)
        self._lb_header.setObjectName("fritz_header")

        # --- Horizontal eval bar
        self._eval_bar = QtWidgets.QProgressBar(self)
        self._eval_bar.setObjectName("fritz_evalbar")
        self._eval_bar.setRange(0, 10000)
        self._eval_bar.setValue(5000)
        self._eval_bar.setTextVisible(False)
        self._eval_bar.setFixedHeight(10)

        # --- Score label
        self._lb_score = QtWidgets.QLabel("", self)
        self._lb_score.setObjectName("fritz_score")
        self._lb_score.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # --- Best line
        self._lb_line = QtWidgets.QLabel("", self)
        self._lb_line.setObjectName("fritz_line")
        self._lb_line.setWordWrap(True)
        self._lb_line.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._lb_header)
        layout.addWidget(self._eval_bar)
        layout.addWidget(self._lb_score)
        layout.addWidget(self._lb_line)
        layout.addStretch()
        self.setLayout(layout)

        self.setStyleSheet(self._STYLESHEET)
        self.setFixedHeight(110)
        self.setMinimumWidth(180)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)

    def start(self):
        """Begin polling the analysis bar for engine data."""
        self._timer.start()

    def stop(self):
        """Stop polling."""
        self._timer.stop()

    def _refresh(self):
        bar = self.analysis_bar
        if not bar or not bar.activated:
            return

        mrm = bar.mrm
        if mrm is None:
            return

        rm = mrm.rm_best()
        if rm is None:
            return

        try:
            # Header: engine name + depth
            engine_name = ""
            if bar.engine_manager and hasattr(bar.engine_manager, "name"):
                engine_name = bar.engine_manager.name or ""
            self._lb_header.setText(f"{engine_name}   depth: {rm.depth}")

            # Score
            score_txt = rm.abbrev_text_base1()
            self._lb_score.setText(score_txt)

            # Eval bar — reuse AnalysisBar's computed aeval value
            cp = rm.centipawns_abs()
            if not rm.is_white:
                cp = -cp
            ev = int(bar.aeval.lv(cp) * 100)
            ev = max(0, min(10000, ev))
            self._eval_bar.setValue(ev)

            # Best line — first 8 half-moves
            try:
                fen = bar.game.last_position.fen() if bar.game else None
                if fen:
                    pgn = Game.pv_pgn(fen, rm.pv)
                    tokens = pgn.split()[:12]
                    self._lb_line.setText(" ".join(tokens) + ("…" if len(pgn.split()) > 12 else ""))
                else:
                    self._lb_line.setText("")
            except Exception:
                self._lb_line.setText("")

        except Exception:
            _log.debug("WFritzEnginePanel refresh error", exc_info=True)
