"""
WFritzAnalysisTable — multi-PV engine analysis panel for Modern Fritz mode.

Displays up to N engine lines in a Fritz-style table:

    Stockfish 18                              depth 29  [−] [+]
    ────────────────────────────────────────────────────────────
    #1  +2.40   d29   Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7…
    #2  +2.15   d27   d4 d5 c4 c6 Nf3 Nf6 Nc3 e6…
    #3  +1.95   d25   e4 e5 Nf3 Nc6 Bb5 a6 Ba4…

Data source: polls ``analysis_bar.mrm`` every 250 ms; does NOT start a second engine.
The analysis bar must be activated (``activate_analysis_bar(True)``) before this widget
starts — handled by ``modern_fritz_ui.on_mode_enter``.
"""
import logging

from PySide6 import QtCore, QtGui, QtWidgets

import Code
from Code.Base import Game

_log = logging.getLogger(__name__)

_BG = "#252526"
_SURFACE = "#2d2d2d"
_BORDER = "#505050"
_TEXT = "#d4d4d4"
_DIM = "#9e9e9e"
_BLUE = "#0078d4"
_RED = "#d16969"
_HEADER_H = 28
_ROW_H = 22


class WFritzAnalysisTable(QtWidgets.QWidget):
    """Fritz-style multi-PV engine analysis table.

    :param parent:       Parent widget (MainWindow).
    :param analysis_bar: Running :class:`~Code.Main.WAnalysisBar.AnalysisBar` instance.
    """

    _MIN_PV = 1
    _MAX_PV = 5

    def __init__(self, parent, analysis_bar):
        super().__init__(parent)
        self.setObjectName("WFritzAnalysisTable")
        self.analysis_bar = analysis_bar
        self._n_pv = 3
        self._multipv_applied = False

        self._build_ui()
        self.setMinimumWidth(220)
        self.setMinimumHeight(80)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row: engine name (left) | depth (centre) | ± (right)
        hdr = QtWidgets.QWidget(self)
        hdr.setFixedHeight(_HEADER_H)
        hdr.setStyleSheet(f"background:{_SURFACE}; border-bottom:1px solid {_BORDER};")
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(8, 0, 4, 0)
        hl.setSpacing(4)

        self._lb_engine = QtWidgets.QLabel("", hdr)
        self._lb_engine.setStyleSheet(f"color:{_DIM}; font-size:11px; background:transparent;")

        self._lb_depth = QtWidgets.QLabel("", hdr)
        self._lb_depth.setStyleSheet(f"color:{_DIM}; font-size:11px; background:transparent;")
        self._lb_depth.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        def _btn(symbol):
            b = QtWidgets.QToolButton(hdr)
            b.setText(symbol)
            b.setFixedSize(20, 20)
            b.setStyleSheet(
                f"QToolButton{{color:{_TEXT};background:{_BG};border:1px solid {_BORDER};"
                f"font-size:13px;font-weight:bold;}}"
                f"QToolButton:hover{{background:{_BORDER};}}"
                f"QToolButton:pressed{{background:{_BLUE};}}"
            )
            return b

        self._btn_minus = _btn("−")
        self._btn_plus = _btn("+")
        self._btn_minus.clicked.connect(self._dec_pv)
        self._btn_plus.clicked.connect(self._inc_pv)

        hl.addWidget(self._lb_engine, stretch=1)
        hl.addWidget(self._lb_depth)
        hl.addWidget(self._btn_minus)
        hl.addWidget(self._btn_plus)
        outer.addWidget(hdr)

        # PV rows: QTableWidget, no headers, read-only
        self._table = QtWidgets.QTableWidget(self)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["#", "Score", "d", "Principal Variation"])
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_H)
        self._table.setStyleSheet(
            f"QTableWidget{{"
            f"background:{_BG}; color:{_TEXT}; font-size:11px;"
            f"border:none; gridline-color:transparent;"
            f"}}"
            f"QTableWidget::item{{padding:0px 4px; border:none;}}"
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 24)
        self._table.setColumnWidth(1, 46)
        self._table.setColumnWidth(2, 30)

        outer.addWidget(self._table, stretch=1)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)

        self._rebuild_rows()

    # ── public API ─────────────────────────────────────────────────────────────

    def start(self):
        """Begin polling the analysis bar for engine data."""
        self._multipv_applied = False
        self._timer.start()

    def stop(self):
        """Stop polling."""
        self._timer.stop()

    # ── private ────────────────────────────────────────────────────────────────

    def _inc_pv(self):
        if self._n_pv < self._MAX_PV:
            self._n_pv += 1
            self._rebuild_rows()
            self._request_multipv()

    def _dec_pv(self):
        if self._n_pv > self._MIN_PV:
            self._n_pv -= 1
            self._rebuild_rows()
            self._request_multipv()

    def _request_multipv(self):
        bar = self.analysis_bar
        if not bar or not bar.activated:
            return
        try:
            if bar.engine_manager:
                if hasattr(bar.engine_manager, "change_multipv"):
                    bar.engine_manager.change_multipv(self._n_pv)
                elif hasattr(bar.engine_manager, "set_multipv"):
                    bar.engine_manager.set_multipv(self._n_pv)
        except Exception:
            _log.debug("change_multipv failed", exc_info=True)

    def _rebuild_rows(self):
        self._table.setRowCount(self._n_pv)
        for r in range(self._n_pv):
            for c in range(4):
                item = QtWidgets.QTableWidgetItem("")
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(r, c, item)
        self._btn_minus.setEnabled(self._n_pv > self._MIN_PV)
        self._btn_plus.setEnabled(self._n_pv < self._MAX_PV)

    def _refresh(self):
        bar = self.analysis_bar
        if not bar or not bar.activated:
            return

        mrm = bar.mrm
        if mrm is None:
            return

        # First time we see real data: request MultiPV=n_pv so subsequent
        # positions analyzed include all PV lines (takes effect on next go).
        if not self._multipv_applied:
            self._multipv_applied = True
            self._request_multipv()

        # Update header
        engine_name = ""
        try:
            if bar.engine_manager and hasattr(bar.engine_manager, "name"):
                engine_name = bar.engine_manager.name or ""
        except Exception:
            pass
        self._lb_engine.setText(engine_name)

        depth_txt = f"depth {mrm.depth}" if mrm.depth else ""
        self._lb_depth.setText(depth_txt)

        # Get FEN for PGN conversion
        fen = None
        try:
            if bar.game:
                fen = bar.game.last_position.fen()
        except Exception:
            pass

        li = mrm.li_rm or []
        for row in range(self._n_pv):
            if row < len(li):
                rm = li[row]
                self._fill_row(row, row + 1, rm, fen)
            else:
                self._clear_row(row)

    def _fill_row(self, row, rank, rm, fen):
        try:
            score_txt = rm.abbrev_text_base1()
        except Exception:
            score_txt = ""
        depth_txt = str(rm.depth) if rm.depth else ""

        pv_txt = ""
        try:
            if fen and rm.pv:
                pgn = Game.pv_pgn(fen, rm.pv)
                tokens = pgn.split()
                pv_txt = " ".join(tokens[:14])
                if len(tokens) > 14:
                    pv_txt += "…"
        except Exception:
            pass

        positive = not score_txt.startswith("-") and not score_txt.startswith("M-")
        score_color = _BLUE if positive else _RED

        def _set(col, txt, color=_TEXT, bold=False):
            item = self._table.item(row, col)
            if item is None:
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(row, col, item)
            else:
                item.setText(txt)
            item.setForeground(QtGui.QColor(color))
            font = item.font()
            font.setBold(bold)
            item.setFont(font)

        _set(0, f"#{rank}", _DIM)
        _set(1, score_txt, score_color, bold=True)
        _set(2, depth_txt, _DIM)
        _set(3, pv_txt, _TEXT)

    def _clear_row(self, row):
        for col in range(4):
            item = self._table.item(row, col)
            if item:
                item.setText("")
