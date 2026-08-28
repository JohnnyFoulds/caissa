"""
fritz_level.py — "caissa:fritz_level" action.

Opens the Fritz-style level/time-control picker and restarts the current game
with the new settings.  Registered as a toolbar-inject action in modern-fritz.json
so it appears as "Level" in the Fritz mode in-game toolbar.
"""


def register(reg):
    from Code.QT import Iconos
    reg("caissa:fritz_level", _("Level"), Iconos.Configurar(), _handler)


def _handler():
    import Code
    from Code.UIModes.actions.modern_fritz_ui import _fritz_new_game
    _fritz_new_game(Code.procesador)
