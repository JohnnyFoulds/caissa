"""
kibitzer.py — "caissa:kibitzer" action.

Opens the Kibitzers manager window to add/manage live engine analysis panels.
"""


def register(reg):
    from Code.QT import Iconos
    reg("caissa:kibitzer", _("Kibitzer"), Iconos.Kibitzer(), _handler)


def _handler():
    import Code
    if hasattr(Code, "procesador") and Code.procesador is not None:
        Code.procesador.kibitzers_manager.run(Code.procesador.main_window)
