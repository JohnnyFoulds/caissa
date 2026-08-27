"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador.start() / reset() when the active mode is "Modern Fritz".

Target layout (after home panel is dismissed)
─────────────────────────────────────────────
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase                — board + toolbar + side eval bar
    └─ [1]  _fritz_right_col  (QSplitter, Vertical)
               ├─ [0]  WFritzHome OR WFritzAnalysisTable  — home / engine table
               ├─ [1]  WFritzEvalGraph (80 px fixed)       — eval profile graph
               └─ [2]  pgn_information                     — move list (reparented)

On mode entry, WFritzHome is shown.  After the user picks an action the home
panel is swapped for WFritzAnalysisTable + WFritzEvalGraph and the chosen
flow starts (new game, load, analyze).

Cleanup (on_mode_exit) restores pgn_information to the main splitter and
removes the sub-splitter before Procesador.reset() clears the rest of the state.
"""
import logging

from PySide6 import QtCore, QtWidgets

_log = logging.getLogger(__name__)


def on_mode_enter(procesador):
    """Activate Fritz layout: home panel + move list in a vertical right column."""
    mw = procesador.main_window

    from Code.UIModes.WFritzHome import WFritzHome

    # Build the vertical right column
    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)

    # Start with the home panel (eval graph + table added later, on action)
    home = WFritzHome(mw)
    right_col.addWidget(home)
    # Reparent move list into right column
    right_col.addWidget(mw.pgn_information)
    right_col.setSizes([280, 500])

    mw.splitter.addWidget(right_col)
    right_col.show()
    home.show()

    # Start analysis bar (engine fires up in background)
    mw.activate_analysis_bar(True)
    mw.active_information_pgn(True)

    mw._fritz_home = home
    mw._fritz_analysis_table = None
    mw._fritz_eval_graph = None
    mw._fritz_right_col = right_col

    # Connect home panel signal — swap to analysis view when user picks action
    home.action_chosen.connect(lambda action: _on_home_action(procesador, action))

    _log.debug("Modern Fritz layout activated (home screen)")


def _on_home_action(procesador, action: str):
    """Swap home panel → analysis table + eval graph, then dispatch the action."""
    mw = procesador.main_window

    home = getattr(mw, "_fritz_home", None)
    right_col = getattr(mw, "_fritz_right_col", None)
    if home is None or right_col is None:
        return

    bar = mw.base.analysis_bar

    # Build analysis table
    from Code.UIModes.WFritzAnalysisTable import WFritzAnalysisTable
    table = WFritzAnalysisTable(mw, bar)

    # Build eval graph (fixed 80 px, inserted between table and move list)
    from Code.UIModes.WFritzEvalGraph import WFritzEvalGraph
    eval_graph = WFritzEvalGraph(mw, bar)

    # Swap: replace home (index 0) with the analysis table
    right_col.replaceWidget(0, table)
    # Insert eval graph at index 1; pgn_information shifts to index 2
    right_col.insertWidget(1, eval_graph)
    right_col.setSizes([200, 80, 400])

    table.show()
    eval_graph.show()
    table.start()
    eval_graph.start()

    home.hide()
    home.setParent(None)
    mw._fritz_home = None
    mw._fritz_analysis_table = table
    mw._fritz_eval_graph = eval_graph

    _log.debug("Modern Fritz: home → analysis table + eval graph")

    # Dispatch the chosen action
    _dispatch_action(procesador, action)


def _dispatch_action(procesador, action: str):
    """Route a home-screen action into the existing Lucas Chess handlers."""
    from Code.Shortcuts import Shortcuts
    sh = Shortcuts.Shortcuts(procesador)

    try:
        if action == "new_game":
            _fritz_new_game(procesador)
        elif action == "load_game":
            sh.tools_menu().run_exec("openPGN")
        elif action == "analyze":
            sh.play_menu().run_exec("voyager2")
    except Exception:
        _log.debug("Fritz home action dispatch failed: %s", action, exc_info=True)


def _fritz_new_game(procesador):
    """Show a Fritz-style level picker and start the game directly — no PAE popup."""
    mw = procesador.main_window
    from Code.UIModes.WFritzNewGame import WFritzNewGame
    dlg = WFritzNewGame(mw)
    if not dlg.exec():
        return

    dic = dlg.get_dic()
    if dic is None:
        return

    # Reset eval graph for the new game
    eval_graph = getattr(mw, "_fritz_eval_graph", None)
    if eval_graph is not None:
        eval_graph.reset()

    from Code.PlayAgainstEngine import ManagerPlayAgainstEngine
    manager = ManagerPlayAgainstEngine.ManagerPlayAgainstEngine(procesador)
    manager.start(dic)


def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window

    table = getattr(mw, "_fritz_analysis_table", None)
    eval_graph = getattr(mw, "_fritz_eval_graph", None)
    home = getattr(mw, "_fritz_home", None)
    right_col = getattr(mw, "_fritz_right_col", None)

    for widget, attr in [(table, "_fritz_analysis_table"),
                         (eval_graph, "_fritz_eval_graph"),
                         (home, "_fritz_home")]:
        if widget is not None:
            try:
                if hasattr(widget, "stop"):
                    widget.stop()
            except Exception:
                _log.debug("Fritz widget stop error (%s)", attr, exc_info=True)

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

    for widget, attr in [(table, "_fritz_analysis_table"),
                         (eval_graph, "_fritz_eval_graph"),
                         (home, "_fritz_home")]:
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

    _log.debug("Modern Fritz layout removed")
