"""
switch_theme.py — "caissa:switch_theme" action.

Lets the user pick any installed theme without opening the full Options dialog.
The choice is stored in x_style_mode and takes priority over the mode's built-in
style default — so selecting "Caissa" in Fritz mode gives the Caissa palette even
though Fritz mode defaults to the Fritz theme.  Selecting "By default" restores
the mode's built-in default.
"""

# Internal QSS files that are not user-selectable themes.
_SKIP = {"fritz-widgets"}


def register(reg):
    from Code.QT import Iconos
    reg(
        "caissa:switch_theme",
        _("Switch theme…"),
        Iconos.Colores(),
        _handler,
    )


def _handler():
    import os
    import Code
    from Code.QT import QTDialogs, Iconos
    from Code.Main import InitApp

    styles_dir = Code.path_resource("Styles")
    themes = sorted(
        f[:-4]
        for f in os.listdir(styles_dir)
        if f.endswith(".qss") and f[:-4] not in _SKIP
    )

    current = getattr(Code.configuration, "x_style_mode", "By default")
    menu = QTDialogs.LCMenu(Code.procesador.main_window)
    for theme in themes:
        label = f"✓  {theme}" if theme == current else f"    {theme}"
        menu.opcion(theme, label, Iconos.Colores())

    resp = menu.lanza()
    if resp is None:
        return

    Code.configuration.x_style_mode = resp
    Code.configuration.graba()
    InitApp.apply_live_style(Code.configuration)
