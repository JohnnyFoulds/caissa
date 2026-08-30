"""
WFritzAnalysisTable — multi-PV engine analysis panel for Modern Fritz mode.

Displays up to N engine lines in a Fritz-style table:

    Stockfish 18                              depth 29  [−] [+]
    ────────────────────────────────────────────────────────────
    #1  +2.40   d29   Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7…
    #2  +2.15   d27   d4 d5 c4 c6 Nf3 Nf6 Nc3 e6…
    #3  +1.95   d25   e4 e5 Nf3 Nc6 Bb5 a6 Ba4…

Data source: polls ``analysis_bar.mrm`` every 250 ms.

Design values arrive via ``qproperty-`` on the ``WFritzAnalysisTable``
selector and from QSS for the standard widget children.  Python defaults
equal the ``Modern Fritz`` dark-theme values.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

import Code
from Code.Base import Game
from Code.Fritz.EvalModel import describe as _eval_describe

_log = logging.getLogger(__name__)

_ACCENT_DEFAULT = "#0078d4"
_DANGER_DEFAULT = "#d16969"
_HEADER_H_DEFAULT = 28
_ROW_H_DEFAULT = 22


class WFritzAnalysisTable(QtWidgets.QWidget):
    """Fritz-style multi-PV engine analysis table.

    :param parent:       Parent widget (MainWindow).
    :param analysis_bar: Running ``AnalysisBar`` instance.

    :spec: §5.3, Phase 1 (feature_spec.md)
    """

    _MIN_PV = 1
    _MAX_PV = 5

    # ── E1: qproperty- contract ────────────────────────────────────────────────

    def _get_dangerColor(self) -> QtGui.QColor:
        return self._dangerColor

    def _set_dangerColor(self, v: QtGui.QColor) -> None:
        self._dangerColor = v
        self.update()

    dangerColor = QtCore.Property(QtGui.QColor, _get_dangerColor, _set_dangerColor)

    def _get_accentColor(self) -> QtGui.QColor:
        return self._accentColor

    def _set_accentColor(self, v: QtGui.QColor) -> None:
        self._accentColor = v
        self.update()

    accentColor = QtCore.Property(QtGui.QColor, _get_accentColor, _set_accentColor)

    def _get_headerHeight(self) -> int:
        return self._headerHeight

    def _set_headerHeight(self, v: int) -> None:
        self._headerHeight = v
        if hasattr(self, "_hdr"):
            self._hdr.setFixedHeight(v)

    headerHeight = QtCore.Property(int, _get_headerHeight, _set_headerHeight)

    def _get_rowHeight(self) -> int:
        return self._rowHeight

    def _set_rowHeight(self, v: int) -> None:
        self._rowHeight = v
        if hasattr(self, "_table"):
            self._table.verticalHeader().setDefaultSectionSize(v)

    rowHeight = QtCore.Property(int, _get_rowHeight, _set_rowHeight)

    # ── constructor ────────────────────────────────────────────────────────────

    def __init__(self, parent, analysis_bar):
        super().__init__(parent)
        self.setObjectName("WFritzAnalysisTable")
        self.analysis_bar = analysis_bar
        self._n_pv = 3
        self._multipv_applied = False

        # E1 property defaults
        self._dangerColor = QtGui.QColor(_DANGER_DEFAULT)
        self._accentColor = QtGui.QColor(_ACCENT_DEFAULT)
        self._headerHeight = _HEADER_H_DEFAULT
        self._rowHeight = _ROW_H_DEFAULT

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self.setMinimumWidth(220)
        self.setMinimumHeight(80)

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._hdr = QtWidgets.QWidget(self)
        self._hdr.setObjectName("WFritzAnalysisHeader")
        self._hdr.setFixedHeight(self._headerHeight)
        hl = QtWidgets.QHBoxLayout(self._hdr)
        hl.setContentsMargins(8, 0, 4, 0)
        hl.setSpacing(4)

        self._lb_engine = QtWidgets.QLabel("", self._hdr)
        self._lb_engine.setObjectName("WFritzAnalysisEngineLabel")

        self._lb_depth = QtWidgets.QLabel("", self._hdr)
        self._lb_depth.setObjectName("WFritzAnalysisDepthLabel")
        self._lb_depth.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self._btn_minus = QtWidgets.QToolButton(self._hdr)
        self._btn_minus.setText("−")
        self._btn_minus.setFixedSize(20, 20)
        self._btn_minus.setObjectName("WFritzAnalysisDecBtn")

        self._btn_plus = QtWidgets.QToolButton(self._hdr)
        self._btn_plus.setText("+")
        self._btn_plus.setFixedSize(20, 20)
        self._btn_plus.setObjectName("WFritzAnalysisIncBtn")

        self._btn_minus.clicked.connect(self._dec_pv)
        self._btn_plus.clicked.connect(self._inc_pv)

        hl.addWidget(self._lb_engine, stretch=1)
        hl.addWidget(self._lb_depth)
        hl.addWidget(self._btn_minus)
        hl.addWidget(self._btn_plus)
        outer.addWidget(self._hdr)

        # Dense one-line eval summary: "Black is slightly better: ⩱ (-0.60) Depth: 24/45 …"
        self._lb_eval_summary = QtWidgets.QLabel("", self)
        self._lb_eval_summary.setObjectName("WFritzEvalSummary")
        outer.addWidget(self._lb_eval_summary)

        self._table = QtWidgets.QTableWidget(self)
        self._table.setObjectName("WFritzAnalysisGrid")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["#", "Score", "d", "Principal Variation"])
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(self._rowHeight)

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

        if not self._multipv_applied:
            self._multipv_applied = True
            self._request_multipv()

        engine_name = ""
        try:
            if bar.engine_manager and hasattr(bar.engine_manager, "name"):
                engine_name = bar.engine_manager.name or ""
        except Exception:
            pass
        self._lb_engine.setText(engine_name)

        depth_txt = f"depth {mrm.depth}" if mrm.depth else ""
        self._lb_depth.setText(depth_txt)

        fen = None
        try:
            if bar.game:
                fen = bar.game.last_position.fen()
        except Exception:
            pass
        if not fen:
            # bar.game not yet set (engine fired before put_view).  Fall back
            # to the board's current position which is always up to date.
            try:
                fen = bar.board.last_position.fen()
            except Exception:
                pass

        self._update_eval_summary(mrm)

        li = mrm.li_rm or []
        for row in range(self._n_pv):
            if row < len(li):
                rm = li[row]
                self._fill_row(row, row + 1, rm, fen)
            else:
                self._clear_row(row)

    def _update_eval_summary(self, mrm) -> None:
        """Populate the one-line dense eval label from *mrm*.

        Format: ``"Black is slightly better: ⩱ (-0.60) Depth: 24/45 00:00:16 51157kN"``

        :param mrm: Live ``MultiEngineResponse``.
        :spec: FR-31
        """
        summary = _eval_describe(mrm)
        if summary is None:
            self._lb_eval_summary.setText("")
            return

        try:
            from Code.Nags.Nags import dic_symbol_nags
            nag_sym = dic_symbol_nags(summary.nag) if summary.nag is not None else ""
        except Exception:
            nag_sym = ""

        cp_str = f"({summary.cp / 100.0:+.2f})" if summary.cp is not None else ""
        depth_str = (
            f"{summary.depth}/{summary.seldepth}" if summary.seldepth else str(summary.depth)
        )

        # Format elapsed time as HH:MM:SS or MM:SS
        total_s = summary.ms // 1000
        h, rem = divmod(total_s, 3600)
        m, s = divmod(rem, 60)
        time_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        # Format node count (e.g. 51157kN)
        if summary.nodes >= 1_000_000:
            nodes_str = f"{summary.nodes // 1000}kN"
        elif summary.nodes >= 1_000:
            nodes_str = f"{summary.nodes // 1000}kN"
        else:
            nodes_str = f"{summary.nodes}N" if summary.nodes else ""

        parts = [summary.text]
        if nag_sym:
            parts.append(f": {nag_sym}")
        if cp_str:
            parts.append(f" {cp_str}")
        if depth_str:
            parts.append(f" Depth: {depth_str}")
        if time_str:
            parts.append(f" {time_str}")
        if nodes_str:
            parts.append(f" {nodes_str}")

        self._lb_eval_summary.setText("".join(parts))

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
        score_color = self._accentColor if positive else self._dangerColor

        dim = QtGui.QColor(self.palette().color(self.palette().ColorRole.Mid))

        def _set(col, txt, color, bold=False):
            item = self._table.item(row, col)
            if item is None:
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(row, col, item)
            else:
                item.setText(txt)
            item.setForeground(color)
            font = item.font()
            font.setBold(bold)
            item.setFont(font)

        _set(0, f"#{rank}", dim)
        _set(1, score_txt, score_color, bold=True)
        _set(2, depth_txt, dim)
        _set(3, pv_txt, self.palette().color(self.palette().ColorRole.Text))

    def _clear_row(self, row):
        for col in range(4):
            item = self._table.item(row, col)
            if item:
                item.setText("")
