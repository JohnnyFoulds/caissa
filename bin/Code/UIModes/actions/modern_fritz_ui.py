"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador when the active mode is "Modern Fritz".

On mode entry the board boots directly into Infinite Analysis (manual §000128):
engine analyses but never replies.  No landing screen.

Layout:
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase                    — board + toolbar
    │          (internal right panel COLLAPSED — pgn reparented out)
    └─ [1]  _fritz_right_col  (QSplitter, Vertical)
               ├─ [0]  WFritzPlayerHeader (60 px)   — player names/clocks
               ├─ [1]  WFritzAnalysisTable (flexible) — multi-PV engine lines
               ├─ [2]  WFritzEvalGraph (80 px)       — eval profile graph
               └─ [3]  WBase.pgn (flexible)          — game move list

On mode exit, every widget is restored to its original parent and constraints
so Classical mode renders identically to upstream Lucas Chess R6.
"""
import logging

from PySide6 import QtCore, QtGui, QtWidgets

_log = logging.getLogger(__name__)

# ── pane specifications (order = top-to-bottom in the right column) ────────────

from Code.Fritz.Types import PaneSpec  # noqa: E402 — after logging setup

_PANE_SPECS = [
    PaneSpec("player_header",  "Players",         60,  40),
    PaneSpec("analysis_table", "Engine analysis", 280, 60),
    PaneSpec("eval_graph",     "Eval profile",     80, 40),
    PaneSpec("pgn",            "Notation",        220, 60),
    PaneSpec("eval_bar",       "Eval bar",         30, 30),
]

# NAG colours come from dic_colors via ThemeGateway — no hardcoded hex here.
def _nag_colors() -> dict:
    import Code
    from Code.Nags.Nags import NAG_1, NAG_2, NAG_3, NAG_4, NAG_5, NAG_6
    dc = Code.dic_colors
    return {
        NAG_3: QtGui.QColor(dc.get("NAG_BRILLIANT", "#1d4f1d")),
        NAG_1: QtGui.QColor(dc.get("NAG_GOOD",      "#183018")),
        NAG_5: QtGui.QColor(dc.get("NAG_INTERESTING","#1a2d3d")),
        NAG_6: QtGui.QColor(dc.get("NAG_DUBIOUS",   "#3d2a00")),
        NAG_2: QtGui.QColor(dc.get("NAG_MISTAKE",   "#4d2200")),
        NAG_4: QtGui.QColor(dc.get("NAG_BLUNDER",   "#5c0000")),
    }


def _install_fritz_pgn_coloring(base):
    colors = _nag_colors()

    def grid_color_fondo(_grid, row, col):
        if col.key == "NUMBER":
            return None
        mgr = getattr(base, "manager", None)
        if mgr is None:
            return None
        pgn_ctrl = getattr(mgr, "pgn", None)
        if pgn_ctrl is None or not hasattr(pgn_ctrl, "only_move"):
            return None
        move = pgn_ctrl.only_move(row, col.key)
        if move is None:
            return None
        return colors.get(move.get_nag())

    base.grid_color_fondo = grid_color_fondo
    try:
        base.pgn.cg.siColorFondo = True
    except AttributeError:
        pass


def _uninstall_fritz_pgn_coloring(base):
    try:
        del base.grid_color_fondo
    except AttributeError:
        pass
    try:
        base.pgn.cg.siColorFondo = False
    except AttributeError:
        pass


# ── notation tab strip + NAG palette ───────────────────────────────────────────

# Fritz notation tab strip (manual §000067).
# Notation and Score sheet have live content; the rest show the flowing
# notation view (better than blank) until those features are implemented.
_NOTATION_TAB_LABELS = [
    "Notation",
    "Training",
    "Score sheet",
    "LiveBook",
    "Openings Book",
    "My Moves",
]
_SCORE_SHEET_TAB = 2  # index of the Score sheet tab

# (label, NAG integer) pairs for the two NAG button rows.
_NAG_ROW_1 = [("‼", 3), ("!", 1), ("!?", 5), ("?!", 6), ("?", 2), ("??", 4)]
_NAG_ROW_2 = [("=", 10), ("∞", 13), ("⩲", 14), ("⩱", 15), ("±", 16), ("∓", 17), ("+−", 18)]


class _FlowingNotation(QtWidgets.QTextEdit):
    """Flowing move-text view — "1. e4 e5 2. Nf3 Nc6..." (manual §000067).

    Polls the active manager's game at 400 ms intervals and renders it as
    plain flowing notation text.  Shown on the Notation tab; the Score sheet
    tab shows the standard N./White/Black grid instead.
    """

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self._mw = mw
        self.setObjectName("WFritzFlowingNotation")
        self.setReadOnly(True)
        self.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._refresh)
        self._last_text = ""

    def start(self):
        self._refresh()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _refresh(self):
        mgr = getattr(getattr(self._mw, "base", None), "manager", None)
        if mgr is None:
            return
        game = getattr(mgr, "game", None)
        if game is None:
            return
        try:
            text = game.pgn_base_raw() or ""
        except Exception:
            return
        if text != self._last_text:
            self._last_text = text
            self.setPlainText(text)
            # Scroll to end so latest move is visible
            c = self.textCursor()
            c.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.setTextCursor(c)


def _build_notation_widget(mw) -> QtWidgets.QWidget:
    """Notation pane: flowing text (Notation tab) and grid table (Score sheet tab).

    Widget tree::

        WFritzNotationContainer  (QWidget)
        ├─ WFritzNotationTabBar  (QTabBar)  — "Notation" | "Score sheet"
        ├─ WFritzNagBar          (QWidget)  — NAG palette (Notation tab only)
        ├─ WFritzFlowingNotation (QTextEdit)— flowing "1. e4 e5…" (Notation tab)
        └─ mw.base.pgn           (Grid)     — N./White/Black table (Score sheet tab)

    :spec: §5.2 / manual §000067
    """
    container = QtWidgets.QWidget(mw)
    container.setObjectName("WFritzNotationContainer")
    vbox = QtWidgets.QVBoxLayout(container)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.setSpacing(0)

    # ── tab bar ──────────────────────────────────────────────────────────────
    tab_bar = QtWidgets.QTabBar(container)
    tab_bar.setObjectName("WFritzNotationTabBar")
    tab_bar.setExpanding(False)
    tab_bar.setDrawBase(False)
    for label in _NOTATION_TAB_LABELS:
        tab_bar.addTab(label)
    vbox.addWidget(tab_bar)

    # ── flowing notation (Notation tab) ──────────────────────────────────────
    flowing = _FlowingNotation(mw, container)
    vbox.addWidget(flowing)

    # ── score-sheet grid (Score sheet tab) ───────────────────────────────────
    vbox.addWidget(mw.base.pgn)
    mw.base.pgn.hide()   # Score sheet hidden by default; Notation tab is default

    # Store so _build_fritz_right_col can start/stop the timer
    mw._fritz_notation_flowing = flowing

    # ── tab switching ────────────────────────────────────────────────────────
    # Score sheet tab shows the N./White/Black grid; all other tabs show the
    # flowing notation text.
    def _on_tab_change(idx, _flow=flowing, _pgn=mw.base.pgn):
        is_score = idx == _SCORE_SHEET_TAB
        _flow.setVisible(not is_score)
        _pgn.setVisible(is_score)

    tab_bar.currentChanged.connect(_on_tab_change)
    # Force initial state — currentChanged does not fire for the default tab 0.
    _on_tab_change(tab_bar.currentIndex())

    # Store refs so on_mode_enter can re-apply after ManagerSolo re-shows pgn.
    mw._fritz_notation_tab_bar = tab_bar
    mw._fritz_notation_on_tab_change = _on_tab_change

    return container


def _apply_nag(mw, nag_num: int) -> None:
    """Apply *nag_num* to the currently selected move in the notation grid.

    :spec: §5.2
    """
    mgr = getattr(mw.base, "manager", None)
    if mgr is None:
        return
    pgn_ctrl = getattr(mgr, "pgn", None)
    if pgn_ctrl is None or not hasattr(pgn_ctrl, "only_move"):
        return

    try:
        row, col = mw.base.pgn.current_position()
        move = pgn_ctrl.only_move(row, col.key)
        if move is None:
            return
        move.put_nag(nag_num)
        mw.base.pgn.refresh()
    except Exception:
        _log.debug("Fritz apply_nag failed", exc_info=True)


def _attach_fritz_delegates(pgn_grid) -> list:
    """Replace WHITE/BLACK column delegates with :class:`FritzEtiquetaPGN`.

    Returns the list of ``(col, original_delegate)`` pairs so the caller can
    restore them on mode exit.

    :spec: §5.5
    """
    from Code.Fritz.Delegates import FritzEtiquetaPGN

    o_columns = pgn_grid.o_columns
    restored = []
    for col_key, is_white in (("WHITE", True), ("BLACK", False)):
        col = o_columns.locate_column(col_key)
        if col is not None:
            restored.append((col, col.edicion))
            col.edicion = FritzEtiquetaPGN(is_white)
    pgn_grid.reread_columns()
    return restored


def _restore_delegates(pgn_grid, saved_delegates: list) -> None:
    """Restore delegate objects saved by :func:`_attach_fritz_delegates`.

    :spec: §5.5
    """
    for col, original in saved_delegates:
        col.edicion = original
    try:
        pgn_grid.reread_columns()
    except Exception:
        _log.debug("Fritz delegate restore error", exc_info=True)


# ── layout helpers ─────────────────────────────────────────────────────────────

def _find_widget_in_layout(top_layout, target):
    """Return (layout, index) where *target* is a direct child, else None.

    Searches the entire layout tree rooted at *top_layout* recursively.
    """
    if top_layout is None:
        return None
    for i in range(top_layout.count()):
        item = top_layout.itemAt(i)
        if item is None:
            continue
        if item.widget() is target:
            return top_layout, i
        child = item.layout()
        if child is not None:
            found = _find_widget_in_layout(child, target)
            if found is not None:
                return found
    return None


def _collapse_widget(widget):
    """Hide a widget and zero out its size constraints so it contributes zero to min-size."""
    orig_min = widget.minimumSize()
    orig_max = widget.maximumSize()
    widget.hide()
    widget.setMinimumSize(0, 0)
    widget.setMaximumSize(0, 0)
    return orig_min, orig_max


# ── mode entry ─────────────────────────────────────────────────────────────────

def on_mode_enter(procesador):
    """Boot Fritz mode directly into Infinite Analysis (manual §000128).

    Engine analyses but never replies.  No landing screen.
    """
    mw = procesador.main_window

    # Re-entry guard: remove stale Fritz right_col if mode is re-entered
    # (e.g. after force_cancel → proc.start()).
    old_rc = getattr(mw, "_fritz_right_col", None)
    _log.debug(
        "on_mode_enter: splitter.count()=%d  sizes=%s  old_rc=%s",
        mw.splitter.count(),
        mw.splitter.sizes(),
        old_rc,
    )
    if old_rc is not None:
        try:
            _restore_main_splitter_pre_fritz(mw)
        except Exception:
            _log.debug("Fritz on_mode_enter pre-cleanup failed", exc_info=True)

    # 1. Terminate presentacion manager (ManagerChallenge101) if it was started
    #    by Procesador.reset() before the mode hook ran.
    mgr = getattr(procesador, "manager", None)
    if mgr is not None and type(mgr).__name__ == "ManagerChallenge101":
        try:
            mgr.terminate()
        except Exception:
            _log.debug("Fritz: failed to terminate presentacion manager", exc_info=True)

    # 2. Activate analysis bar BEFORE building pane widgets.
    #    force_hidden prevents macOS QGraphicsDropShadowEffect crash on Qt6/Metal.
    mw.activate_analysis_bar(True)
    mw.base.analysis_bar.force_hidden = True
    mw.base.analysis_bar.setVisible(False)
    # Collapse layout space — setVisible alone still reserves ≈70 px in HBoxLayout.
    mw.base.analysis_bar.setMaximumWidth(0)
    mw.active_information_pgn(True)

    # 3. Build the right column with all panes (no landing screen).
    _build_fritz_right_col(mw)

    # 4. Restore last saved layout (manual §000078).
    try:
        from Code.Fritz import GeometryStore
        saved = GeometryStore.load_splitters("fritz")
        if saved:
            rc = getattr(mw, "_fritz_right_col", None)
            if rc is not None and "right_col" in saved:
                rc.setSizes(saved["right_col"])
            if "main" in saved:
                mw.splitter.setSizes(saved["main"])
    except Exception:
        _log.debug("Fritz: GeometryStore load failed", exc_info=True)

    # 5. Boot ManagerSolo in Infinite Analysis — engine analyses, never replies.
    from Code.Z.ManagerSolo import ManagerSolo as _ManagerSolo
    _ManagerSolo(procesador).start({"PLAY_AGAINST_ENGINE": False, "ANALYSIS_BAR": True})

    # 5b. ManagerSolo.start() triggers Qt layout events that collapse right_col to 0.
    #     Re-assert the sizes immediately, then again after the event loop drains.
    _reapply_fritz_right_col_sizes(mw)
    QtCore.QTimer.singleShot(150, lambda: _reapply_fritz_right_col_sizes(mw))
    # 5b2. Snap WBase width to actual board width (eliminates the dead-space gap).
    #      The board gets its final size during Qt paint events, so we need a delay.
    QtCore.QTimer.singleShot(400, lambda: _snap_wbase_to_board(mw))
    QtCore.QTimer.singleShot(700, lambda: _snap_wbase_to_board(mw))

    # 5c. ManagerSolo.active_game(True) calls pgn.setVisible(True), re-showing the
    #     pgn table.  Re-apply the current notation tab's visibility state to undo it.
    def _reapply_notation_visibility():
        if getattr(mw, "_fritz_right_col", None) is None:
            return
        fn = getattr(mw, "_fritz_notation_on_tab_change", None)
        tb = getattr(mw, "_fritz_notation_tab_bar", None)
        if fn and tb:
            fn(tb.currentIndex())

    _reapply_notation_visibility()
    QtCore.QTimer.singleShot(0,   _reapply_notation_visibility)
    QtCore.QTimer.singleShot(200, _reapply_notation_visibility)
    QtCore.QTimer.singleShot(600, _reapply_notation_visibility)

    # 6. Register ribbon dropdowns for has_dropdown buttons.
    _register_ribbon_dropdowns(mw, procesador)

    _log.debug("Modern Fritz layout activated (Infinite Analysis)")


# ── right column builder ───────────────────────────────────────────────────────

def _snap_wbase_to_board(mw) -> None:
    """Eliminate the dead-space gap between the board and the right panel.

    WBase contains [board (fixed size) | collapsed widgets | relleno() stretch].
    The stretch eats all WBase space to the right of the board.  Snapping the
    splitter so that WBase width == board width + margins removes that gap and
    gives the freed pixels to the right column.
    """
    rc = getattr(mw, "_fritz_right_col", None)
    if rc is None:
        return
    board = getattr(mw.base, "board", None)
    if board is None:
        return
    bw = board.width()
    if bw < 100:
        return
    total = mw.splitter.width()
    if total < 400:
        return
    wbase_w = bw + 6          # board + 2 px margin each side + 2 px slack
    rc_w = max(total - wbase_w, 360)
    wbase_w = total - rc_w    # recalculate in case rc_w hit the floor
    mw.splitter.setSizes([wbase_w, rc_w])


def _reapply_fritz_right_col_sizes(mw) -> None:
    """Re-assert right_col width if Qt collapsed it during ManagerSolo.start()."""
    rc = getattr(mw, "_fritz_right_col", None)
    if rc is None:
        return
    total = mw.splitter.width()
    if total < 400:
        return
    if mw.splitter.sizes()[-1] < 360:
        mw.splitter.setSizes([total - 380, 380])


def _build_fritz_right_col(mw) -> None:
    """Build the Fritz right column and wire pane API.

    Builds::

        _fritz_right_col (QSplitter, Vertical)
        ├─ [0]  WFritzPlayerHeader
        ├─ [1]  WFritzAnalysisTable
        ├─ [2]  WFritzEvalGraph
        └─ [3]  notation widget (tab strip + NAG bar + mw.base.pgn)

    Parks ``mw.pgn_information`` inside right_col so it is removed from the main
    splitter (keeps the main splitter at 2 items), then hides it.
    """
    main_sizes = mw.splitter.sizes()
    wbase_width = main_sizes[0] if main_sizes else 800
    pgn_width = main_sizes[1] if len(main_sizes) > 1 else 300

    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)
    right_col.setObjectName("WFritzRightCol")

    # Park pgn_information so it leaves the main splitter (→ 2-item main splitter).
    right_col.addWidget(mw.pgn_information)
    mw.pgn_information.hide()

    bar = mw.base.analysis_bar

    # ── 1. Find pgn's position in WBase's layout tree BEFORE reparenting it ──
    pgn_layout_info = _find_widget_in_layout(mw.base.layout(), mw.base.pgn)

    # ── 2. Build content widgets ──────────────────────────────────────────────
    from Code.Fritz.WFritzPlayerHeader import WFritzPlayerHeader
    from Code.Fritz.WFritzAnalysisTable import WFritzAnalysisTable
    from Code.Fritz.WFritzEvalGraph import WFritzEvalGraph
    from Code.Fritz.PaneRegistry import PaneRegistry
    from Code.Fritz.WFritzPane import WFritzPane

    player_header = WFritzPlayerHeader(mw, mw.base)
    table = WFritzAnalysisTable(mw, bar)
    eval_graph = WFritzEvalGraph(mw, bar)

    # ── 3. Wrap in WFritzPane ─────────────────────────────────────────────────
    reg = PaneRegistry()
    for s in _PANE_SPECS:
        reg.register(s)

    ph_pane  = WFritzPane(_PANE_SPECS[0], player_header)
    tbl_pane = WFritzPane(_PANE_SPECS[1], table)
    eg_pane  = WFritzPane(_PANE_SPECS[2], eval_graph)
    notation_widget = _build_notation_widget(mw)
    pgn_pane = WFritzPane(_PANE_SPECS[3], notation_widget)

    # ── 4. Populate right_col ─────────────────────────────────────────────────
    # pgn_information is at index 0 (parked above).  Replace it with ph_pane,
    # then append the remaining panes.
    old_pgi = right_col.replaceWidget(0, ph_pane)
    if old_pgi is not None:
        old_pgi.hide()
    right_col.addWidget(tbl_pane)
    right_col.addWidget(eg_pane)
    right_col.addWidget(pgn_pane)

    # ── 5. Restructure layout: ribbon above [board | right_col] (Fritz 9 style) ──
    # Extract the toolbar from WBase and place it above the horizontal splitter
    # so it spans the full window width.  Then [board | right_col] sit below it,
    # both starting at the same y — exactly the Fritz 9/18 layout.
    wbase_layout = mw.base.layout()
    if wbase_layout is not None:
        wbase_layout.removeWidget(mw.base.tb)

    fritz_container = QtWidgets.QWidget(mw)
    fritz_container.setObjectName("WFritzOuterContainer")
    fritz_vbox = QtWidgets.QVBoxLayout(fritz_container)
    fritz_vbox.setContentsMargins(0, 0, 0, 0)
    fritz_vbox.setSpacing(0)
    fritz_vbox.addWidget(mw.base.tb)       # toolbar spans full width at top

    _mw_layout = mw.layout()
    _splitter_idx = 0
    if _mw_layout is not None:
        for _i in range(_mw_layout.count()):
            _item = _mw_layout.itemAt(_i)
            if _item is not None and _item.widget() is mw.splitter:
                _splitter_idx = _i
                break
        _mw_layout.removeWidget(mw.splitter)
    fritz_vbox.addWidget(mw.splitter, 1)   # board + right_col below toolbar
    if _mw_layout is not None:
        _mw_layout.insertWidget(_splitter_idx, fritz_container)

    mw._fritz_container    = fritz_container
    mw._fritz_splitter_idx = _splitter_idx

    mw.splitter.addWidget(right_col)
    fritz_col_width = max(pgn_width, 380)
    mw.splitter.setSizes([max(wbase_width - (fritz_col_width - pgn_width), 600),
                          fritz_col_width])
    mw.splitter.setChildrenCollapsible(False)
    right_col.setMinimumWidth(360)

    right_col.setSizes([_PANE_SPECS[0].default_px, _PANE_SPECS[1].default_px,
                        _PANE_SPECS[2].default_px, _PANE_SPECS[3].default_px])
    right_col.show()

    # ── 6. Wire pane API ──────────────────────────────────────────────────────
    pane_dict = {
        "player_header":  ph_pane,
        "analysis_table": tbl_pane,
        "eval_graph":     eg_pane,
        "pgn":            pgn_pane,
    }
    mw._fritz_panes         = pane_dict
    mw._fritz_pane_registry = reg
    mw._fritz_pane_sizes    = {}

    _api = {
        "names": [s.key for s in _PANE_SPECS],
        "get":   lambda key: bool(pane_dict.get(key) and pane_dict[key].isVisible()),
        "set":   lambda key, vis: _set_pane_visible(mw, key, vis),
    }
    for _pane in pane_dict.values():
        _pane.wire_pane_api(_api, _PANE_SPECS)

    # ── 7. Attach FritzEtiquetaPGN delegates ──────────────────────────────────
    saved_delegates = _attach_fritz_delegates(mw.base.pgn)
    mw._fritz_saved_delegates = saved_delegates

    # ── 8. Collapse WBase internal right-panel widgets ─────────────────────────
    _right_panel_widgets = [
        mw.base.lb_player_white,
        mw.base.lb_player_black,
        mw.base.lb_clock_white,
        mw.base.lb_clock_black,
        mw.base.lb_rotulo1,
        mw.base.lb_rotulo2,
        mw.base.lb_rotulo3,
        mw.base.bt_active_tutor,
        mw.base.lb_capt_white,
        mw.base.lb_capt_black,
        mw.base.bt_capt,
        mw.base.wsolve,
        mw.base.wmessage,
    ]
    constraints = []
    for w in _right_panel_widgets:
        orig_min, orig_max = _collapse_widget(w)
        constraints.append((w, orig_min, orig_max))
    mw._fritz_wbase_constraints = constraints

    # ── 9. Show and start live widgets ────────────────────────────────────────
    for _p in pane_dict.values():
        _p.show()
    player_header.start()
    table.start()
    eval_graph.start()
    flowing = getattr(mw, "_fritz_notation_flowing", None)
    if flowing is not None:
        flowing.start()

    # ── 10. Store state attrs ─────────────────────────────────────────────────
    mw._fritz_right_col      = right_col
    mw._fritz_home           = None
    mw._fritz_player_header  = player_header
    mw._fritz_analysis_table = table
    mw._fritz_eval_graph     = eval_graph
    mw._fritz_pgn_restore    = pgn_layout_info

    _log.debug("Fritz right col built")


def _register_ribbon_dropdowns(mw, procesador) -> None:
    """Register WDropdownPanel instances for every has_dropdown ribbon button.

    Called at the end of on_mode_enter so the ribbon exists and procesador
    is fully set up.  Silently skips if no ribbon is installed.
    """
    ribbon = getattr(getattr(mw, "base", None), "ribbon", None)
    if ribbon is None:
        return

    # ── New Game ▼ (caissa:fritz_level) ─────────────────────────────────────
    def _new_game():
        _fritz_new_game(procesador)

    ribbon.set_dropdown(
        "caissa:fritz_level",
        _("New Game"),
        [(_("New Game…"), _new_game)],
    )

    # ── Piece Style ▼ (caissa:piece_style) ───────────────────────────────────
    from Code.UIModes.actions.board_actions import apply_piece_style as _apply_piece

    _PIECES = [
        "Alpha", "Berlin", "Cburnett", "Leipzig", "Merida", "Regular", "Staunton 3D",
    ]

    def _make_piece_cb(name: str):
        def _cb():
            _apply_piece(name)
        return _cb

    def _config_board():
        import Code
        if hasattr(Code, "procesador") and Code.procesador is not None:
            Code.procesador.config_board()

    piece_items = [(n, _make_piece_cb(n)) for n in _PIECES]
    piece_items.append((_("More…"), _config_board))

    ribbon.set_dropdown("caissa:piece_style", _("Piece Style"), piece_items)

    # ── Square Color ▼ (caissa:sq_color) ─────────────────────────────────────
    ribbon.set_dropdown(
        "caissa:sq_color",
        _("Square Color"),
        [(_("Configure…"), _config_board)],
    )

    # ── Standard Layouts ▼ (caissa:std_layout) ───────────────────────────────
    from Code.Fritz.Layouts import apply_preset as _apply_layout, preset_names as _preset_names

    def _make_layout_cb(preset_name: str):
        def _cb():
            rc = getattr(mw, "_fritz_right_col", None)
            if rc is not None:
                _apply_layout(preset_name, mw.splitter, rc)
        return _cb

    def _factory_reset():
        from Code.Fritz.Layouts import factory_name
        _make_layout_cb(factory_name())()

    layout_items = [(n, _make_layout_cb(n)) for n in _preset_names()]
    layout_items.append((_("Factory Settings"), _factory_reset))

    ribbon.set_dropdown("caissa:std_layout", _("Standard Layouts"), layout_items)

    # ── Select Engine ▼ (caissa:select_engine) ───────────────────────────────
    # Engine selection is part of the level/game setup dialog for now.
    def _select_engine():
        _fritz_pick_level(procesador)

    ribbon.set_dropdown(
        "caissa:select_engine",
        _("Select Engine"),
        [(_("Choose Engine…"), _select_engine)],
    )

    # ── Board Display API (caissa:board_coordinates, caissa:board_arrows) ─────
    def _get_board():
        rc = getattr(mw, "base", None)
        return rc.board if rc is not None and hasattr(rc, "board") else None

    def _set_coordinates(visible: bool) -> None:
        board = _get_board()
        if board is not None:
            board.show_coordinates(visible)

    def _set_arrows(visible: bool) -> None:
        import Code
        Code.configuration.x_show_bestmove = visible

    ribbon.set_display_api({
        "caissa:board_coordinates": _set_coordinates,
        "caissa:board_arrows":      _set_arrows,
        "caissa:board_hints":       lambda _: None,
    })

    # ── Toggle API: caissa:infinite_analysis checked = currently in analysis mode ──
    # Checked means play_against_engine is False (engine analyses, never replies).
    # The toggle_get is re-called on every ribbon.sync() so it tracks live state.
    def _get_toggle(key):
        import Code
        mgr = getattr(getattr(Code, "procesador", None), "manager", None)
        if key == "caissa:infinite_analysis" and mgr and hasattr(mgr, "play_against_engine"):
            return not mgr.play_against_engine  # checked when in analysis mode
        return None

    ribbon.set_toggle_api(_get_toggle)


_FRITZ_GAME_DIC_KEY = "FRITZ_LAST_GAME_DIC"


def _fritz_new_game(procesador):
    """New Game — restart immediately with last-used settings (no dialog).

    Fritz behaviour: New Game never shows a dialog.  On first run, when no
    level has been configured yet, it is a no-op — the board stays in
    Infinite Analysis.  Use Levels to pick a level before starting a game.
    """
    import Code
    stored = Code.configuration.read_variables(_FRITZ_GAME_DIC_KEY)
    if stored and "RIVAL" in stored:
        _start_fritz_engine_game(procesador, stored)


def _fritz_pick_level(procesador):
    """Levels — open the Fritz level/time-control picker dialog.

    After the user confirms, the selected settings are saved and the game
    starts immediately.  This is the only place the WFritzNewGame dialog
    is shown.
    """
    mw = procesador.main_window
    from Code.Fritz.WFritzNewGame import WFritzNewGame
    dlg = WFritzNewGame(mw)
    if not dlg.exec():
        return

    dic = dlg.get_dic()
    if dic is None:
        return

    import Code
    Code.configuration.write_variables(_FRITZ_GAME_DIC_KEY, dic)
    _start_fritz_engine_game(procesador, dic)


def _start_fritz_engine_game(procesador, dic):
    """Start a Fritz engine game from a fully-formed game-setup dic."""
    mw = procesador.main_window
    eval_graph = getattr(mw, "_fritz_eval_graph", None)
    if eval_graph is not None:
        eval_graph.reset()

    from Code.PlayAgainstEngine import ManagerPlayAgainstEngine
    manager = ManagerPlayAgainstEngine.ManagerPlayAgainstEngine(procesador)
    manager.start(dic)


# ── pane visibility helper ────────────────────────────────────────────────────

def _set_pane_visible(mw, key: str, visible: bool) -> None:
    """Show or hide a Fritz pane, restoring its height from the registry.

    :spec: §5.3
    """
    pane = getattr(mw, "_fritz_panes", {}).get(key)
    if pane is None:
        return
    reg = getattr(mw, "_fritz_pane_registry", None)
    right_col = getattr(mw, "_fritz_right_col", None)
    if right_col is None:
        pane.setVisible(visible)
        return

    pane_sizes = getattr(mw, "_fritz_pane_sizes", {})

    # Locate pane index in the splitter
    idx = None
    for i in range(right_col.count()):
        if right_col.widget(i) is pane:
            idx = i
            break

    if visible:
        stored = pane_sizes.get(key, 0)
        restored_h = reg.restore_px(key, stored) if reg else pane.spec.default_px
        pane.show()
        if idx is not None:
            sizes = right_col.sizes()
            new_sizes = list(sizes)
            new_sizes[idx] = restored_h
            right_col.setSizes(new_sizes)
    else:
        if idx is not None:
            sizes = right_col.sizes()
            if idx < len(sizes):
                pane_sizes[key] = sizes[idx]
                mw._fritz_pane_sizes = pane_sizes
        pane.hide()


def pane_api(mw) -> dict:
    """Return the pane capability dict consumed by ``WFritzPane.wire_pane_api``.

    :returns: ``{"names": [...], "get": callable, "set": callable}``
    :spec: §5.3
    """
    pane_dict = getattr(mw, "_fritz_panes", {})
    return {
        "names": [s.key for s in _PANE_SPECS],
        "get":   lambda key: bool(pane_dict.get(key) and pane_dict[key].isVisible()),
        "set":   lambda key, vis: _set_pane_visible(mw, key, vis),
    }


# ── mode exit ──────────────────────────────────────────────────────────────────

def _restore_fritz_structural_layout(mw):
    """Reverse the Fritz layout restructure: return toolbar to WBase, splitter to mw."""
    fritz_container = getattr(mw, "_fritz_container", None)
    if fritz_container is None:
        return
    _mw_layout = mw.layout()
    wbase_layout = mw.base.layout()
    saved_idx = getattr(mw, "_fritz_splitter_idx", 0)
    fritz_vbox = fritz_container.layout()

    # Detach splitter from fritz_container and restore it to mw's layout
    if fritz_vbox is not None:
        fritz_vbox.removeWidget(mw.splitter)
    mw.splitter.setParent(mw)
    if _mw_layout is not None:
        _mw_layout.removeWidget(fritz_container)
        _mw_layout.insertWidget(saved_idx, mw.splitter)

    # Detach toolbar from fritz_container and restore it to WBase's layout at position 0
    if fritz_vbox is not None:
        fritz_vbox.removeWidget(mw.base.tb)
    mw.base.tb.setParent(mw.base)
    if wbase_layout is not None:
        wbase_layout.insertWidget(0, mw.base.tb)

    fritz_container.hide()
    fritz_container.setParent(None)
    try:
        del mw._fritz_container
    except AttributeError:
        pass
    try:
        del mw._fritz_splitter_idx
    except AttributeError:
        pass


def _restore_main_splitter_pre_fritz(mw):
    """Remove the Fritz right_col from mw.splitter and restore pgn_information.

    Called by on_mode_enter when Fritz mode is re-entered (e.g. after
    force_cancel → proc.start()).  Without this, mw.splitter accumulates extra
    panes and setSizes([a, b]) leaves the third pane at 0px.
    """
    right_col = getattr(mw, "_fritz_right_col", None)
    if right_col is None:
        return
    try:
        mw.splitter.addWidget(mw.pgn_information)
        right_col.hide()
        right_col.setParent(None)
    except Exception:
        _log.debug("_restore_main_splitter_pre_fritz error", exc_info=True)
    _restore_fritz_structural_layout(mw)
    # Clear all Fritz state attrs so on_mode_enter starts fresh.
    for attr in ("_fritz_right_col", "_fritz_home",
                 "_fritz_analysis_table", "_fritz_eval_graph", "_fritz_player_header",
                 "_fritz_pgn_restore"):
        try:
            delattr(mw, attr)
        except AttributeError:
            pass


def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window

    # ── Persist current splitter layout (manual §000078) ─────────────────────
    try:
        from Code.Fritz import GeometryStore
        rc = getattr(mw, "_fritz_right_col", None)
        splitter_sizes: dict[str, list[int]] = {}
        if rc is not None:
            splitter_sizes["right_col"] = rc.sizes()
        main_sizes = mw.splitter.sizes()
        if main_sizes:
            splitter_sizes["main"] = main_sizes
        if splitter_sizes:
            GeometryStore.save_splitters("fritz", splitter_sizes)
    except Exception:
        _log.debug("Fritz: GeometryStore save failed", exc_info=True)

    # Restore FritzEtiquetaPGN → original EtiquetaPGN delegates.
    saved = getattr(mw, "_fritz_saved_delegates", None)
    if saved is not None:
        _restore_delegates(mw.base.pgn, saved)
        try:
            del mw._fritz_saved_delegates
        except AttributeError:
            pass

    table = getattr(mw, "_fritz_analysis_table", None)
    eval_graph = getattr(mw, "_fritz_eval_graph", None)
    home = getattr(mw, "_fritz_home", None)
    player_header = getattr(mw, "_fritz_player_header", None)
    right_col = getattr(mw, "_fritz_right_col", None)
    flowing = getattr(mw, "_fritz_notation_flowing", None)

    # Stop live widgets
    for widget in (table, eval_graph, player_header, home, flowing):
        if widget is not None:
            try:
                if hasattr(widget, "stop"):
                    widget.stop()
            except Exception:
                _log.debug("Fritz widget stop error", exc_info=True)

    # ── Restore mw.base.pgn to WBase's layout ────────────────────────────────
    pgn_restore = getattr(mw, "_fritz_pgn_restore", None)
    if pgn_restore is not None:
        pgn_layout, pgn_idx = pgn_restore
        try:
            pgn_layout.insertWidget(pgn_idx, mw.base.pgn)
        except Exception:
            _log.debug("Fritz pgn restore error", exc_info=True)
        try:
            del mw._fritz_pgn_restore
        except AttributeError:
            pass

    # ── Restore WBase widget constraints ─────────────────────────────────────
    for widget, orig_min, orig_max in getattr(mw, "_fritz_wbase_constraints", []):
        try:
            widget.setMinimumSize(orig_min)
            widget.setMaximumSize(orig_max)
        except Exception:
            pass
    try:
        del mw._fritz_wbase_constraints
    except AttributeError:
        pass

    # Restore WBase's right panel visibility (show anything that was visible before)
    try:
        mw.base.show_replay()
    except Exception:
        _log.debug("Fritz show_replay error", exc_info=True)

    # ── Restore right_col / pgn_information to main splitter ─────────────────
    if right_col is not None:
        try:
            mw.splitter.addWidget(mw.pgn_information)
            right_col.hide()
            right_col.setParent(None)
        except Exception:
            _log.debug("Fritz right_col removal error", exc_info=True)
        finally:
            try:
                del mw._fritz_right_col
            except AttributeError:
                pass

    # Restore structural layout: ribbon back into WBase, splitter back to mw
    _restore_fritz_structural_layout(mw)

    # ── Destroy remaining Fritz widgets ───────────────────────────────────────
    for widget, attr in [
        (table, "_fritz_analysis_table"),
        (eval_graph, "_fritz_eval_graph"),
        (player_header, "_fritz_player_header"),
        (home, "_fritz_home"),
    ]:
        if widget is not None:
            try:
                widget.hide()
                widget.setParent(None)
            except Exception:
                pass
            try:
                delattr(mw, attr)
            except AttributeError:
                pass

    # Restore analysis bar visibility control so other modes work normally
    try:
        mw.base.analysis_bar.force_hidden = False
        mw.base.analysis_bar.setMaximumWidth(16777215)  # Qt QWIDGETSIZE_MAX
    except Exception:
        pass

    # Clean up pane-wrapper attrs
    for _attr in ("_fritz_panes", "_fritz_pane_registry", "_fritz_pane_sizes",
                  "_fritz_notation_flowing", "_fritz_notation_tab_bar",
                  "_fritz_notation_on_tab_change"):
        try:
            delattr(mw, _attr)
        except AttributeError:
            pass

    _log.debug("Modern Fritz layout removed")
