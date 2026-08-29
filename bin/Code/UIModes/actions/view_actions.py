"""
view_actions.py — caissa:std_layout, caissa:fullscreen, caissa:play_now,
                  caissa:select_engine actions.
"""


def register(reg):
    from Code.QT import Iconos
    reg("caissa:std_layout",     _("Standard Layouts"), Iconos.Themes(),    _std_layout)
    reg("caissa:fullscreen",     _("Full Screen"),      Iconos.ResizeAll(), _fullscreen)
    reg("caissa:play_now",       _("Play Now"),         Iconos.Play(),        _play_now)
    reg("caissa:select_engine",  _("Select Engine"),    Iconos.Engines(),     _select_engine)


def _std_layout():
    pass


def _fullscreen():
    import Code
    mw = getattr(Code, "procesador", None) and Code.procesador.main_window
    if mw:
        if mw.isFullScreen():
            mw.showNormal()
        else:
            mw.showFullScreen()


def _play_now():
    pass


def _select_engine():
    import Code
    if hasattr(Code, "procesador") and Code.procesador is not None:
        from Code.UIModes.actions.modern_fritz_ui import _fritz_new_game
        _fritz_new_game(Code.procesador)
