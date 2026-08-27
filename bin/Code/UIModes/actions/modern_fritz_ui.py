"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador.start() / reset() when the active mode is "Modern Fritz".

Target layout
─────────────
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase                — board + toolbar + side eval bar
    └─ [1]  _fritz_right_col  (QSplitter, Vertical)
               ├─ [0]  WFritzHome OR WFritzAnalysisTable  — home panel / engine table
               └─ [1]  pgn_information                    — move list (reparented)

On mode entry, WFritzHome is shown.  After the user picks "New Game" /
"Load Game" / "Analyze", the home panel is swapped out for WFritzAnalysisTable
and the normal play flow continues.

Cleanup (on_mode_exit) restores pgn_information to the main splitter and removes
the sub-splitter before Procesador.reset() clears the rest of the state.
"""
import logging

from PySide6 import QtCore, QtWidgets

_log = logging.getLogger(__name__)


def on_mode_enter(procesador):
    """Activate Fritz layout: home panel + move list in a vertical right column."""
    mw = procesador.main_window

    from Code.UIModes.WFritzHome import WFritzHome
    from Code.UIModes.WFritzAnalysisTable import WFritzAnalysisTable

    # Build the vertical right column
    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)

    # Start with the home panel
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
    mw._fritz_right_col = right_col

    # Connect home panel signal — swap to analysis view when user picks action
    home.action_chosen.connect(lambda action: _on_home_action(procesador, action))

    _log.debug("Modern Fritz layout activated (home screen)")


def _on_home_action(procesador, action: str):
    """Swap home panel → analysis table, then dispatch the chosen action."""
    mw = procesador.main_window

    home = getattr(mw, "_fritz_home", None)
    right_col = getattr(mw, "_fritz_right_col", None)
    if home is None or right_col is None:
        return

    # Build analysis table (replaces home panel)
    from Code.UIModes.WFritzAnalysisTable import WFritzAnalysisTable
    table = WFritzAnalysisTable(mw, mw.base.analysis_bar)

    # Swap: remove home, insert table at position 0
    right_col.replaceWidget(0, table)
    right_col.setSizes([200, 500])
    table.show()
    table.start()

    home.hide()
    home.setParent(None)
    mw._fritz_home = None
    mw._fritz_analysis_table = table

    _log.debug("Modern Fritz: swapped home → analysis table")

    # Dispatch the chosen action
    _dispatch_action(procesador, action)


def _dispatch_action(procesador, action: str):
    """Route a home-screen action into the existing Lucas Chess handlers."""
    import Code
    from Code.Shortcuts import Shortcuts
    sh = Shortcuts.Shortcuts(procesador)

    try:
        if action == "new_game":
            sh.play_menu().run_exec("free")
        elif action == "load_game":
            sh.tools_menu().run_exec("openPGN")
        elif action == "analyze":
            sh.play_menu().run_exec("voyager2")
    except Exception:
        _log.debug("Fritz home action dispatch failed: %s", action, exc_info=True)


def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window

    table = getattr(mw, "_fritz_analysis_table", None)
    home = getattr(mw, "_fritz_home", None)
    right_col = getattr(mw, "_fritz_right_col", None)

    if table is not None:
        try:
            table.stop()
        except Exception:
            _log.debug("Fritz table stop error", exc_info=True)

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

    for attr, widget in [("_fritz_analysis_table", table), ("_fritz_home", home)]:
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
