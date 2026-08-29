"""
fritz_level.py — "caissa:fritz_level" action.

Opens the Fritz-style level/time-control picker and restarts the current game
with the new settings.  Registered as a toolbar-inject action in modern-fritz.json
so it appears as "Level" in the Fritz mode in-game toolbar.
"""


def register(reg):
    from Code.QT import Iconos
    reg("caissa:fritz_level",         _("Level"),   Iconos.NuevaPartida(), _handler)
    reg("caissa:infinite_analysis",   _("Analyse"), Iconos.Kibitzers(),    _infinite_analysis_handler)


def _handler():
    import Code
    from Code.UIModes.actions.modern_fritz_ui import _fritz_new_game
    _fritz_new_game(Code.procesador)


def _infinite_analysis_handler():
    """Toggle between Infinite Analysis (ManagerSolo) and engine game (ManagerPlayAgainstEngine).

    When ManagerSolo is active: delegates to its run_action handler which
    switches play_against_engine on/off.  When any other manager is active,
    routes through it in case it also implements the key.
    """
    import Code
    mgr = getattr(getattr(Code, "procesador", None), "manager", None)
    if mgr is not None and hasattr(mgr, "run_action"):
        mgr.run_action("caissa:infinite_analysis")


def pick_level_handler():
    """Used by TB_LEVEL — always shows the picker."""
    import Code
    from Code.UIModes.actions.modern_fritz_ui import _fritz_pick_level
    _fritz_pick_level(Code.procesador)
