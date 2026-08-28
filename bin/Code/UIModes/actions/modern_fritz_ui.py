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

# Fritz-palette NAG background colours
_NAG_COLORS: dict = {}


def _nag_colors() -> dict:
    if not _NAG_COLORS:
        from Code.Nags.Nags import NAG_1, NAG_2, NAG_3, NAG_4, NAG_5, NAG_6
        _NAG_COLORS.update({
            NAG_3: QtGui.QColor("#1d4f1d"),  # !! brilliant  — bright green
            NAG_1: QtGui.QColor("#183018"),  # !  good       — subtle green
            NAG_5: QtGui.QColor("#1a2d3d"),  # !? interesting — teal
            NAG_6: QtGui.QColor("#3d2a00"),  # ?! dubious    — amber
            NAG_2: QtGui.QColor("#4d2200"),  # ?  mistake    — orange
            NAG_4: QtGui.QColor("#5c0000"),  # ?? blunder    — red
        })
    return _NAG_COLORS


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

    from Code.UIModes.WFritzHome import WFritzHome

    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)
    right_col.setObjectName("WFritzRightCol")

    home = WFritzHome(mw)
    right_col.addWidget(home)
    right_col.addWidget(mw.pgn_information)
    right_col.setSizes([320, 400])

    main_sizes = mw.splitter.sizes()
    wbase_width = main_sizes[0] if main_sizes else 800
    pgn_width = main_sizes[1] if len(main_sizes) > 1 else 300

    mw.splitter.addWidget(right_col)
    fritz_col_width = max(pgn_width, 380)
    mw.splitter.setSizes([max(wbase_width - (fritz_col_width - pgn_width), 600),
                          fritz_col_width])
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

    _install_fritz_pgn_coloring(mw.base)
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

    # ── 3. Restructure right_col ─────────────────────────────────────────────
    # Current right_col: [home(0), pgn_information(1)]
    # Target:            [player_header(0), table(1), eval_graph(2), pgn(3)]

    # Replace home(0) with player_header
    old_home = right_col.replaceWidget(0, player_header)
    if old_home is not None:
        old_home.hide()
        old_home.setParent(None)

    # Insert table at position 1 (pushes pgn_information to 2)
    right_col.insertWidget(1, table)

    # Insert eval_graph at position 2 (pushes pgn_information to 3)
    right_col.insertWidget(2, eval_graph)

    # Replace pgn_information(3) with mw.base.pgn
    old_pgi = right_col.replaceWidget(3, mw.base.pgn)

    # Put pgn_information back in main splitter (hidden)
    if old_pgi is not None:
        mw.splitter.addWidget(old_pgi)
        old_pgi.hide()

    right_col.setSizes([60, 280, 80, 220])

    # ── 4. Show and start the new widgets ────────────────────────────────────
    player_header.show()
    table.show()
    eval_graph.show()
    mw.base.pgn.show()

    player_header.start()
    table.start()
    eval_graph.start()

    # ── 5. Collapse WBase's internal right-panel widgets ─────────────────────
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


# ── mode exit ──────────────────────────────────────────────────────────────────

def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window
    _uninstall_fritz_pgn_coloring(mw.base)

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
    except Exception:
        pass

    _log.debug("Modern Fritz layout removed")
