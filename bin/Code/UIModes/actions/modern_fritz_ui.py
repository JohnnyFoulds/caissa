"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador when the active mode is "Modern Fritz".

Target layout (after home panel is dismissed, game in progress)
───────────────────────────────────────────────────────────────
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase                    — board + toolbar + eval bar
    │          (internal right panel COLLAPSED — pgn reparented out)
    └─ [1]  _fritz_right_col  (QSplitter, Vertical)
               ├─ [0]  WFritzPlayerHeader (60 px fixed)  — player names/clocks
               ├─ [1]  WFritzAnalysisTable (flexible)    — multi-PV engine lines
               ├─ [2]  WFritzEvalGraph (80 px fixed)     — eval profile graph
               └─ [3]  WBase.pgn (flexible)              — game move list

Home-screen layout (on mode entry, before a game starts):
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase                    — board
    └─ [1]  _fritz_right_col
               ├─ [0]  WFritzHome                       — home/landing panel
               └─ [1]  pgn_information                   — hidden

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

# Tab labels in order; only "Notation" has live content initially.
_NOTATION_TAB_LABELS = [
    "Notation",
    "Training",
    "Score sheet",
    "LiveBook",
    "Openings Book",
    "My Moves",
]

# (label, NAG integer) pairs for the two NAG button rows.
_NAG_ROW_1 = [("‼", 3), ("!", 1), ("!?", 5), ("?!", 6), ("?", 2), ("??", 4)]
_NAG_ROW_2 = [("=", 10), ("∞", 13), ("⩲", 14), ("⩱", 15), ("±", 16), ("∓", 17), ("+−", 18)]


def _build_notation_widget(mw) -> QtWidgets.QWidget:
    """Wrap *mw.base.pgn* in a container that adds a tab strip and NAG palette.

    Widget tree::

        _FritzNotationContainer  (objectName WFritzNotationContainer)
        ├─ QTabBar               (objectName WFritzNotationTabBar)
        ├─ _nag_bar              (objectName WFritzNagBar)
        │  ├─ row-1  QWidget     (objectName WFritzNagRow1)
        │  └─ row-2  QWidget     (objectName WFritzNagRow2)
        └─ mw.base.pgn           (reparented here)

    :spec: §5.2
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

    # ── NAG palette ──────────────────────────────────────────────────────────
    nag_bar = QtWidgets.QWidget(container)
    nag_bar.setObjectName("WFritzNagBar")
    nag_vbox = QtWidgets.QVBoxLayout(nag_bar)
    nag_vbox.setContentsMargins(2, 2, 2, 2)
    nag_vbox.setSpacing(1)

    for row_idx, nag_row_def in enumerate((_NAG_ROW_1, _NAG_ROW_2), start=1):
        row_widget = QtWidgets.QWidget(nag_bar)
        row_widget.setObjectName(f"WFritzNagRow{row_idx}")
        row_hbox = QtWidgets.QHBoxLayout(row_widget)
        row_hbox.setContentsMargins(0, 0, 0, 0)
        row_hbox.setSpacing(2)
        for label, nag_num in nag_row_def:
            btn = QtWidgets.QToolButton(row_widget)
            btn.setText(label)
            btn.setObjectName(f"WFritzNagBtn_{nag_num}")
            btn.setFixedHeight(18)
            btn.setToolTip(f"NAG {nag_num}")
            # Capture nag_num in closure
            btn.clicked.connect(lambda _checked=False, n=nag_num, _mw=mw: _apply_nag(_mw, n))
            row_hbox.addWidget(btn)
        row_hbox.addStretch()
        nag_vbox.addWidget(row_widget)

    vbox.addWidget(nag_bar)

    # ── pgn grid ─────────────────────────────────────────────────────────────
    vbox.addWidget(mw.base.pgn)

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
    """Activate Fritz layout: home panel on the right, engine bar running."""
    mw = procesador.main_window

    # If re-entered (e.g. after force_cancel → proc.start()), remove the old
    # Fritz right_col before building a new one.  Without this, splitter ends up
    # with 3 children but setSizes only passes 2 values, leaving the third at 0px.
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
        _log.debug(
            "on_mode_enter: after cleanup splitter.count()=%d  sizes=%s",
            mw.splitter.count(),
            mw.splitter.sizes(),
        )

    from Code.UIModes.WFritzHome import WFritzHome

    # Read splitter sizes BEFORE addWidget so we see the 2-pane classical split.
    main_sizes = mw.splitter.sizes()
    _log.debug("on_mode_enter: main_sizes before addWidget = %s", main_sizes)
    wbase_width = main_sizes[0] if main_sizes else 800
    pgn_width = main_sizes[1] if len(main_sizes) > 1 else 300

    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)
    right_col.setObjectName("WFritzRightCol")

    home = WFritzHome(mw)
    right_col.addWidget(home)
    right_col.addWidget(mw.pgn_information)
    right_col.setSizes([320, 400])

    mw.splitter.addWidget(right_col)
    fritz_col_width = max(pgn_width, 380)
    _log.debug(
        "on_mode_enter: before setSizes splitter.count()=%d  computing sizes=[%d, %d]",
        mw.splitter.count(),
        max(wbase_width - (fritz_col_width - pgn_width), 600),
        fritz_col_width,
    )
    mw.splitter.setSizes([max(wbase_width - (fritz_col_width - pgn_width), 600),
                          fritz_col_width])
    _log.debug(
        "on_mode_enter: after setSizes splitter.sizes()=%s",
        mw.splitter.sizes(),
    )
    right_col.show()
    home.show()

    mw.activate_analysis_bar(True)
    # Keep the engine running but hide the widget — Fritz uses WFritzAnalysisTable.
    # force_hidden prevents activate() from calling setVisible(True) again when
    # Manager.show_info_extra() re-activates the bar during game start; a visible
    # AnalysisBar forces a board resize that triggers a QGraphicsDropShadowEffect
    # crash on macOS with Qt6/Metal.
    mw.base.analysis_bar.force_hidden = True
    mw.base.analysis_bar.setVisible(False)
    # Collapse the layout space — setVisible alone still reserves the widget's
    # preferred width (≈70 px) in the HBoxLayout, pushing the board rightward.
    mw.base.analysis_bar.setMaximumWidth(0)
    mw.active_information_pgn(True)
    # active_information_pgn(True) calls show() internally — hide it on home screen
    mw.pgn_information.hide()

    mw._fritz_home = home
    mw._fritz_analysis_table = None
    mw._fritz_eval_graph = None
    mw._fritz_player_header = None
    mw._fritz_right_col = right_col
    mw._fritz_pgn_restore = None
    mw._fritz_wbase_constraints = []

    home.action_chosen.connect(lambda action: _on_home_action(procesador, action))

    _log.debug("Modern Fritz layout activated (home screen)")


# ── home → analysis swap ───────────────────────────────────────────────────────

def _swap_home_to_analysis(procesador):
    """Replace WFritzHome with the full Fritz analysis panel.

    Builds the Fritz right column:
      [0] WFritzPlayerHeader (player names + clocks)
      [1] WFritzAnalysisTable (multi-PV engine lines)
      [2] WFritzEvalGraph (eval profile)
      [3] mw.base.pgn (game move list, reparented from WBase)

    Collapses WBase's internal right-panel widgets so the board fills WBase.
    Idempotent — safe to call even if already swapped.
    Returns True if the swap was performed, False if already in analysis view.
    """
    mw = procesador.main_window
    home = getattr(mw, "_fritz_home", None)
    right_col = getattr(mw, "_fritz_right_col", None)
    if home is None or right_col is None:
        return False

    bar = mw.base.analysis_bar

    # ── 1. Find pgn's position in WBase's layout tree BEFORE moving it ─────
    pgn_layout_info = _find_widget_in_layout(mw.base.layout(), mw.base.pgn)

    # ── 2. Build new right_col widgets ──────────────────────────────────────
    from Code.UIModes.WFritzPlayerHeader import WFritzPlayerHeader
    player_header = WFritzPlayerHeader(mw, mw.base)

    from Code.UIModes.WFritzAnalysisTable import WFritzAnalysisTable
    table = WFritzAnalysisTable(mw, bar)

    from Code.UIModes.WFritzEvalGraph import WFritzEvalGraph
    eval_graph = WFritzEvalGraph(mw, bar)

    # ── 3. Wrap content widgets in WFritzPane ────────────────────────────────
    from Code.Fritz.PaneRegistry import PaneRegistry
    from Code.Fritz.WFritzPane import WFritzPane

    reg = PaneRegistry()
    for s in _PANE_SPECS:
        reg.register(s)

    ph_pane  = WFritzPane(_PANE_SPECS[0], player_header)
    tbl_pane = WFritzPane(_PANE_SPECS[1], table)
    eg_pane  = WFritzPane(_PANE_SPECS[2], eval_graph)

    # Build the notation container (tab strip + NAG palette + pgn grid).
    notation_widget = _build_notation_widget(mw)
    pgn_pane = WFritzPane(_PANE_SPECS[3], notation_widget)

    # ── 4. Restructure right_col ─────────────────────────────────────────────
    # Current right_col: [home(0), pgn_information(1)]
    # Target:            [ph_pane(0), tbl_pane(1), eg_pane(2), pgn_pane(3)]

    old_home = right_col.replaceWidget(0, ph_pane)
    if old_home is not None:
        old_home.hide()
        old_home.setParent(None)

    right_col.insertWidget(1, tbl_pane)
    right_col.insertWidget(2, eg_pane)

    old_pgi = right_col.replaceWidget(3, pgn_pane)
    # replaceWidget() already detaches and hides old_pgi.  Do NOT add it back to
    # mw.splitter here — doing so creates a 3-item splitter, and the setSizes call
    # below only passes 2 values, leaving right_col at ~4px wide.
    if old_pgi is not None:
        old_pgi.hide()

    right_col.setSizes([60, 280, 80, 220])

    # ── 5. Wire pane API ─────────────────────────────────────────────────────
    _pane_dict = {
        "player_header":  ph_pane,
        "analysis_table": tbl_pane,
        "eval_graph":     eg_pane,
        "pgn":            pgn_pane,
    }
    mw._fritz_panes         = _pane_dict
    mw._fritz_pane_registry = reg
    mw._fritz_pane_sizes    = {}

    _api = {
        "names": [s.key for s in _PANE_SPECS],
        "get":   lambda key: bool(_pane_dict.get(key) and _pane_dict[key].isVisible()),
        "set":   lambda key, vis: _set_pane_visible(mw, key, vis),
    }
    for _pane in _pane_dict.values():
        _pane.wire_pane_api(_api, _PANE_SPECS)

    # ── Attach FritzEtiquetaPGN to notation columns (replaces monkey-patch) ────
    saved_delegates = _attach_fritz_delegates(mw.base.pgn)
    mw._fritz_saved_delegates = saved_delegates

    # ── 6. Show and start the new widgets ────────────────────────────────────
    for _p in _pane_dict.values():
        _p.show()
    player_header.start()
    table.start()
    eval_graph.start()

    # ── 7. Collapse WBase's internal right-panel widgets ─────────────────────
    # Zero out min/max size so the layout gives back all the space to the board.
    # We intentionally skip mw.base.pgn (already reparented) and track everything
    # else so we can restore on mode exit.
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

    # ── 6. Resize main splitter ───────────────────────────────────────────────
    total = sum(mw.splitter.sizes())
    fritz_width = 400
    mw.splitter.setSizes([max(total - fritz_width, 400), fritz_width])

    # ── 7. Store restoration info ─────────────────────────────────────────────
    mw._fritz_pgn_restore = pgn_layout_info
    mw._fritz_player_header = player_header
    mw._fritz_home = None
    mw._fritz_analysis_table = table
    mw._fritz_eval_graph = eval_graph

    _log.debug("Modern Fritz: home → player_header + analysis table + eval graph + pgn")
    return True


# ── home action routing ────────────────────────────────────────────────────────

def _on_home_action(procesador, action: str):
    if action == "new_game":
        _fritz_new_game(procesador, from_home=True)
    else:
        _swap_home_to_analysis(procesador)
        _dispatch_non_game_action(procesador, action)


def _dispatch_non_game_action(procesador, action: str):
    from Code.Shortcuts import Shortcuts
    sh = Shortcuts.Shortcuts(procesador)
    try:
        if action == "load_game":
            sh.tools_menu().run_exec("openPGN")
        elif action == "analyze":
            sh.play_menu().run_exec("voyager2")
    except Exception:
        _log.debug("Fritz home action dispatch failed: %s", action, exc_info=True)


def _fritz_new_game(procesador, from_home: bool = False):
    """Show the Fritz level picker and start a game without the PAE popup."""
    mw = procesador.main_window
    from Code.UIModes.WFritzNewGame import WFritzNewGame
    dlg = WFritzNewGame(mw)
    if not dlg.exec():
        return  # cancelled — home screen stays

    dic = dlg.get_dic()
    if dic is None:
        return

    _swap_home_to_analysis(procesador)  # no-op if already swapped

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
        # pgn_information may already be in mw.splitter (added by _swap_home_to_analysis
        # line 393) or still inside right_col; either way addWidget restores it.
        mw.splitter.addWidget(mw.pgn_information)
        right_col.hide()
        right_col.setParent(None)
    except Exception:
        _log.debug("_restore_main_splitter_pre_fritz error", exc_info=True)
    # Clear all Fritz state attrs so on_mode_enter starts fresh.
    for attr in ("_fritz_right_col", "_fritz_home", "_fritz_analysis_table",
                 "_fritz_eval_graph", "_fritz_player_header", "_fritz_pgn_restore"):
        try:
            delattr(mw, attr)
        except AttributeError:
            pass


def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window

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

    # Stop live widgets
    for widget in (table, eval_graph, player_header, home):
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
    for _attr in ("_fritz_panes", "_fritz_pane_registry", "_fritz_pane_sizes"):
        try:
            delattr(mw, _attr)
        except AttributeError:
            pass

    _log.debug("Modern Fritz layout removed")
