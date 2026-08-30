"""
board_actions.py — caissa:flip_board, caissa:piece_style, caissa:sq_color actions.
"""


def register(reg):
    from Code.QT import Iconos
    reg("caissa:flip_board",  _("Flip Board"),   Iconos.ResizeBoard(), _flip_board)
    reg("caissa:piece_style", _("Piece Style"),  Iconos.Knight(),      _piece_style)
    reg("caissa:sq_color",    _("Square Color"), Iconos.Colores(),     _sq_color)


def _flip_board():
    import Code
    mw = getattr(Code, "procesador", None) and Code.procesador.main_window
    if mw:
        # rotate_board() repositions coordinates, arrows, captures panel, and
        # space_layer — direct is_white_bottom mutation + redraw() misses all that.
        mw.base.board.rotate_board()


def _piece_style():
    import Code
    if hasattr(Code, "procesador") and Code.procesador is not None:
        Code.procesador.config_board()


def _sq_color():
    import Code
    if hasattr(Code, "procesador") and Code.procesador is not None:
        Code.procesador.config_board()


def apply_piece_style(name: str) -> None:
    """Apply a piece style by name without opening the config dialog.

    :param name: Folder name from ``Resources/Pieces/``.
    """
    import Code
    mw = getattr(Code, "procesador", None) and Code.procesador.main_window
    if mw:
        mw.board.change_the_pieces(name)
