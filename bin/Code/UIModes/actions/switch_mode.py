"""
switch_mode.py — "caissa:switch_mode" action.

Opens a simple dialog letting the user pick any available mode.
This action is injected non-filterably into every toolbar and the Options menu
by the framework, so no mode is ever a dead end.
"""


def register(reg):
    from Code.QT import Iconos
    reg(
        "caissa:switch_mode",
        _("Switch mode…"),
        Iconos.Vista(),
        _handler,
    )


def _handler():
    import Code
    from Code.UIModes import UIModes
    from Code.QT import QTDialogs

    modes = UIModes.load_modes()
    if not modes:
        return

    current = getattr(Code.configuration, "x_ui_mode", "classical")
    menu = QTDialogs.LCMenu(Code.procesador.main_window)
    for mode in modes:
        name = mode.get("name", "")
        if not name:
            continue
        label = f"✓  {name}" if name.lower() == current.lower() else f"    {name}"
        from Code.QT import Iconos
        menu.opcion(name, label, Iconos.Vista())

    resp = menu.lanza()
    if resp is None:
        return

    dic_previo = Code.configuration.read_dic_x()
    Code.configuration.x_ui_mode = resp
    Code.configuration.graba()

    if Code.configuration.needs_reinit(dic_previo):
        Code.procesador.main_window.final_processes()
        from Code.QT import QTUtils
        from Code.Base.Constantes import ExitProgram
        Code.procesador.main_window.accept()
        QTUtils.exit_application(ExitProgram.REINIT)
    else:
        # Mode change doesn't require restart — rebuild toolbar and menus live
        from Code.Main import InitApp
        InitApp.apply_live_style(Code.configuration)
        if Code.procesador and hasattr(Code.procesador, "main_window"):
            mw = Code.procesador.main_window
            if hasattr(mw, "base") and hasattr(mw.base, "pon_toolbar"):
                tb_keys = mw.base.get_toolbar()
                mw.base.pon_toolbar(tb_keys)
