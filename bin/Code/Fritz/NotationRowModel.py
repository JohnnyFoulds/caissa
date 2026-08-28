"""
NotationRowModel.py — pure model for a single notation-grid cell.

Produces :class:`NotationRow` from a duck-typed move object without importing
Qt or any upstream Qt-tainted module.  The *colors* parameter is injectable so
callers in the live app pass ``Code.dic_colors`` explicitly and test code can
pass a plain dict.

:spec: §5.1
"""
from __future__ import annotations

from dataclasses import dataclass

# Maps the six quality-NAG integers to their dic_colors key.
_NAG_COLOR_KEYS: dict[int, str] = {
    3: "NAG_BRILLIANT",
    1: "NAG_GOOD",
    5: "NAG_INTERESTING",
    6: "NAG_DUBIOUS",
    2: "NAG_MISTAKE",
    4: "NAG_BLUNDER",
}

_FIGURINE_CHARS: frozenset[str] = frozenset("PQBKRN")


@dataclass(frozen=True, slots=True)
class NotationRow:
    """Immutable snapshot of everything a Fritz notation cell needs to render.

    :param text:           PGN move text, e.g. ``"Nf3"`` or ``"O-O"``.
    :param figurine_glyph: Piece letter (``'P'``..``'N'``) for ChessMerida glyph,
                           or ``None`` for pawn/castling moves.
    :param nag_nums:       Raw NAG integers from ``move.li_nags``.
    :param chip_color:     Hex colour string for the left-margin NAG chip, or
                           ``None`` when *colors* was not provided or no quality
                           NAG is present.
    :param indent_level:   0 = main line, ≥1 = variation depth.
    :param is_current:     True when this is the board's current position.
    """

    text: str
    figurine_glyph: str | None
    nag_nums: tuple
    chip_color: str | None
    indent_level: int
    is_current: bool


def row(
    move,
    *,
    is_current: bool = False,
    indent_level: int = 0,
    colors=None,
) -> NotationRow:
    """Build a :class:`NotationRow` from a duck-typed move object.

    The function is intentionally duck-typed: it reads ``move.base_pgn()``
    (or falls back to ``str(move)``) and ``move.li_nags``.  This keeps the
    module import-free w.r.t. ``Code.Base.Move`` (which is Qt-tainted via
    ``Nags → QtGui``), so the AST purity check passes.

    :param move:         Any object with ``base_pgn() -> str`` and ``li_nags: list[int]``.
    :param is_current:   True when this is the board's current position.
    :param indent_level: 0 = main line, ≥1 = variation depth.
    :param colors:       Mapping of colour-key → hex string (e.g. ``Code.dic_colors``).
                         Pass ``None`` to suppress chip colouring (unit-test default).
    :returns:            A frozen :class:`NotationRow`.
    :spec: §5.1
    """
    pgn_text: str
    if callable(getattr(move, "base_pgn", None)):
        pgn_text = move.base_pgn()
    else:
        pgn_text = str(move)

    figurine_glyph: str | None = (
        pgn_text[0] if (pgn_text and pgn_text[0] in _FIGURINE_CHARS) else None
    )

    nag_nums: tuple = tuple(move.li_nags) if hasattr(move, "li_nags") else ()

    chip_color: str | None = None
    if colors is not None:
        for nag in nag_nums:
            key = _NAG_COLOR_KEYS.get(int(nag) if isinstance(nag, (int, str)) and str(nag).isdigit() else -1)
            if key:
                chip_color = colors.get(key)
                if chip_color:
                    break

    return NotationRow(
        text=pgn_text,
        figurine_glyph=figurine_glyph,
        nag_nums=nag_nums,
        chip_color=chip_color,
        indent_level=indent_level,
        is_current=is_current,
    )
