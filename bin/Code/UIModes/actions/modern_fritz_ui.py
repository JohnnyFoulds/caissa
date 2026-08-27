"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador.start() / reset() when the active mode is "Modern Fritz".

Target layout
─────────────
    MainWindow.splitter (horizontal)
    ├─ [0]  WBase          — board + toolbar + side eval bar
    └─ [1]  _fritz_right_col  (QSplitter, Vertical)  ← inserted by this hook
               ├─ [0]  WFritzEnginePanel  — engine name / depth / eval bar / best line
               └─ [1]  pgn_information   — move list (reparented from main splitter)

Cleanup (on_mode_exit) restores pgn_information to the main splitter and removes
the sub-splitter before Procesador.reset() clears the rest of the state.
"""
import logging

from PySide6 import QtCore, QtWidgets

_log = logging.getLogger(__name__)


def on_mode_enter(procesador):
    """Activate Fritz layout: eval bar + right column (engine panel + move list)."""
    mw = procesador.main_window

    # Start the side eval bar (also starts the analyzer engine)
    mw.activate_analysis_bar(True)

    # Build the Fritz engine panel
    try:
        from Code.UIModes.WFritzEnginePanel import WFritzEnginePanel
        fritz_panel = WFritzEnginePanel(mw, mw.base.analysis_bar)
    except Exception:
        _log.error("Could not create WFritzEnginePanel", exc_info=True)
        mw.active_information_pgn(True)
        return

    # Build a vertical sub-splitter: fritz panel (top) + move list (bottom)
    right_col = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, mw)
    right_col.setChildrenCollapsible(False)
    right_col.addWidget(fritz_panel)
    # Reparenting pgn_information into right_col (Qt removes it from mw.splitter)
    right_col.addWidget(mw.pgn_information)
    right_col.setSizes([110, 500])

    # Add the right column to the main horizontal splitter
    mw.splitter.addWidget(right_col)
    right_col.show()
    fritz_panel.show()
    fritz_panel.start()

    # Activate the move-list panel (operates on pgn_information's internal splitter)
    mw.active_information_pgn(True)

    mw._fritz_panel = fritz_panel
    mw._fritz_right_col = right_col

    _log.debug("Modern Fritz layout activated")


def on_mode_exit(procesador):
    """Restore the standard layout before Procesador.reset() wipes state."""
    mw = procesador.main_window

    fritz_panel = getattr(mw, "_fritz_panel", None)
    right_col = getattr(mw, "_fritz_right_col", None)

    if fritz_panel is not None:
        try:
            fritz_panel.stop()
        except Exception:
            _log.debug("Fritz panel stop error", exc_info=True)

    if right_col is not None:
        try:
            # Move pgn_information back to the main splitter before destroying right_col
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

    if fritz_panel is not None:
        try:
            fritz_panel.hide()
            fritz_panel.setParent(None)
        except Exception:
            pass
        finally:
            try:
                del mw._fritz_panel
            except AttributeError:
                pass

    _log.debug("Modern Fritz layout removed")
