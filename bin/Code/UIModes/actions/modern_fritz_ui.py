"""
modern_fritz_ui.py — mode lifecycle hook for the Modern Fritz skin.

Called by Procesador.start() / reset() when the active mode is "Modern Fritz".
Enables the side eval bar, the move-list panel, and injects the Fritz engine
analysis panel into the main splitter.

Layout after on_mode_enter:
    MainWindow.splitter[0]  — WBase (board + toolbar + side eval bar)
    MainWindow.splitter[1]  — WFritzEnginePanel  (NEW — engine info)
    MainWindow.splitter[2]  — pgn_information    (move list)
"""
import logging

_log = logging.getLogger(__name__)


def on_mode_enter(procesador):
    """Activate Fritz layout: eval bar + engine panel + move list."""
    mw = procesador.main_window

    # Enable the side eval bar (starts the analyzer engine automatically)
    mw.activate_analysis_bar(True)

    # Show the PGN / move list panel on the right
    mw.active_information_pgn(True)

    # Inject the Fritz engine panel at splitter index 1 (before pgn_information)
    try:
        from Code.UIModes.WFritzEnginePanel import WFritzEnginePanel
        panel = WFritzEnginePanel(mw, mw.base.analysis_bar)
        mw.splitter.insertWidget(1, panel)
        panel.show()
        panel.start()
        mw._fritz_panel = panel
    except Exception:
        _log.error("Failed to inject WFritzEnginePanel", exc_info=True)


def on_mode_exit(procesador):
    """Remove Fritz-specific widgets before the standard reset wipes state."""
    mw = procesador.main_window
    panel = getattr(mw, "_fritz_panel", None)
    if panel is not None:
        try:
            panel.stop()
            panel.hide()
            panel.setParent(None)
        except Exception:
            _log.debug("Error removing WFritzEnginePanel", exc_info=True)
        finally:
            try:
                del mw._fritz_panel
            except AttributeError:
                pass
