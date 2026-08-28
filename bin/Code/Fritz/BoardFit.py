"""bin/Code/Fritz/BoardFit.py — Pure board-sizing arithmetic.

Extracts the ``set_width``/``redraw`` geometry logic from ``Board`` so it can be
unit-tested without Qt and reused by the fixed-window fit mechanism (Phase 2).

:spec: §2.3, Phase 2 (feature_spec.md)
:tier: pure — no Qt, no third-party imports
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants mirroring Board.set_width / Board.redraw
# ---------------------------------------------------------------------------

#: Mapping of exact width-piece values to (puntos, margin_center_base) pairs.
#: Interpolation is used for values not in this table.
_D_TAM: dict[int, tuple[int, int]] = {
    16: (9, 23),
    24: (10, 29),
    32: (12, 33),
    48: (14, 38),
    64: (16, 42),
    80: (18, 46),
}

MIN_AP: int = 12   # minimum width-piece value
MIN_ANCHO: int = 150  # minimum board ancho (px)


@dataclass(frozen=True, slots=True)
class FitResult:
    """Result returned by :func:`fit`.

    :param width_piece: The chosen ``width_piece`` (piece pixel size).
    :param ancho: The resulting board size in pixels (square sides).
    :param clamped: ``True`` when ``MIN_ANCHO`` floor was applied.
    """

    width_piece: int
    ancho: int
    clamped: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _interpolate(ap: int) -> tuple[int, int]:
    """Return ``(puntos, margin_center_base)`` for *ap* via bucket interpolation.

    Exact matches return the table value directly.  Other values use the
    closest bucket (ties go to the lower bucket as the dict is iterated in
    insertion order).
    """
    if ap in _D_TAM:
        return _D_TAM[ap]
    mx = 10 ** 9
    kt = 0
    pt_kt = 0
    mc_kt = 0
    for k, (pt, mc) in _D_TAM.items():
        mt = abs(k - ap)
        if mt < mx:
            mx = mt
            kt = k
            pt_kt = pt
            mc_kt = mc
    return pt_kt * ap // kt, mc_kt * ap // kt


def _compute_geometry(
    ap: int,
    margin_pieces: int = 0,
    tam_recuadro_pct: int = 100,
    tam_frontera_pct: int = 100,
) -> tuple[int, int, int]:
    """Compute ``(width_square, margin_center, tam_frontera)`` for *ap*.

    Replicates ``Board.set_width`` (``Board.py:589-630``) exactly.

    :param ap: ``width_piece`` in pixels.
    :param margin_pieces: ``config.x_margin_pieces - 10`` (default 0).
    :param tam_recuadro_pct: ``config_board.tamRecuadro()`` (default 100).
    :param tam_frontera_pct: ``config_board.tamFrontera()`` (default 100).
    """
    _puntos, mc_base = _interpolate(ap)

    width_square = ap + margin_pieces * 2

    # tamFrontera is derived from the raw margin_center (before tamRecuadro scaling)
    tam_frontera = int(mc_base * 3.0 // 46.0)

    # margin_center is then scaled by tamRecuadro
    margin_center = mc_base * tam_recuadro_pct // 100

    # tamFrontera is scaled by tamFrontera_pct
    tam_frontera = int(tam_frontera * tam_frontera_pct // 100)
    if tam_frontera_pct > 0 and tam_frontera == 0:
        tam_frontera = 2
    if tam_frontera % 2 == 1:
        tam_frontera += 1

    return width_square, margin_center, tam_frontera


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ancho_for_width_piece(
    ap: int,
    margin_pieces: int = 0,
    tam_recuadro_pct: int = 100,
    tam_frontera_pct: int = 100,
) -> int:
    """Return the board ``ancho`` (px) for a given *ap* (``width_piece``).

    Replicates ``Board.redraw`` line 698-700:
    ``width_square * 8 + margin_center * 2 + tamFrontera * 2``.

    :param ap: ``width_piece`` in pixels.
    :param margin_pieces: ``config.x_margin_pieces - 10`` (default 0).
    :param tam_recuadro_pct: ``config_board.tamRecuadro()`` (default 100).
    :param tam_frontera_pct: ``config_board.tamFrontera()`` (default 100).
    :returns: Board width/height in pixels.
    """
    width_square, margin_center, tam_frontera = _compute_geometry(
        ap, margin_pieces, tam_recuadro_pct, tam_frontera_pct
    )
    return width_square * 8 + margin_center * 2 + tam_frontera * 2


def width_piece_for_ancho(
    target: int,
    margin_pieces: int = 0,
    tam_recuadro_pct: int = 100,
    tam_frontera_pct: int = 100,
) -> int:
    """Return the largest ``width_piece`` whose ``ancho`` does not exceed *target*.

    Uses a linear scan over ``[MIN_AP, 200]`` rather than bisection because
    ``ancho_for_width_piece`` is not strictly monotonic at bucket boundaries —
    the interpolation scheme can produce a smaller ``ancho`` at ``ap+1`` than at
    ``ap`` when the nearest bucket changes (e.g. ap=56→540, ap=57→534).  A
    linear scan is only 188 iterations and is always correct.

    If even ``MIN_AP`` exceeds *target*, ``MIN_AP`` is returned (the board clips
    rather than vanishing).

    :param target: Available pixels.
    :param margin_pieces: ``config.x_margin_pieces - 10`` (default 0).
    :param tam_recuadro_pct: ``config_board.tamRecuadro()`` (default 100).
    :param tam_frontera_pct: ``config_board.tamFrontera()`` (default 100).
    :returns: ``width_piece`` in pixels.
    """
    result = MIN_AP
    for ap in range(MIN_AP, 201):
        if ancho_for_width_piece(ap, margin_pieces, tam_recuadro_pct, tam_frontera_pct) <= target:
            result = ap
    return result


def fit(
    pane_w: int,
    pane_h: int,
    overhead_w: int,
    overhead_h: int,
    safety: int = 4,
    margin_pieces: int = 0,
    tam_recuadro_pct: int = 100,
    tam_frontera_pct: int = 100,
) -> FitResult:
    """Return the best ``FitResult`` for a board in a pane of size *pane_w* × *pane_h*.

    *overhead_w* / *overhead_h* are the non-board pixels already consumed in each
    dimension (toolbar, analysis bar, clock rows, margins).  The board is sized to
    ``min(pane_w - overhead_w, pane_h - overhead_h) - safety`` clamped to
    ``MIN_ANCHO`` from below.

    :param pane_w: Available pane width in pixels.
    :param pane_h: Available pane height in pixels.
    :param overhead_w: Non-board horizontal pixels.
    :param overhead_h: Non-board vertical pixels.
    :param safety: Extra pixel margin (default 4).
    :param margin_pieces: ``config.x_margin_pieces - 10`` (default 0).
    :param tam_recuadro_pct: ``config_board.tamRecuadro()`` (default 100).
    :param tam_frontera_pct: ``config_board.tamFrontera()`` (default 100).
    :returns: :class:`FitResult` with ``width_piece``, ``ancho``, and ``clamped``.
    """
    available = min(pane_w - overhead_w, pane_h - overhead_h) - safety
    clamped = available < MIN_ANCHO
    target = max(available, MIN_ANCHO)
    ap = width_piece_for_ancho(target, margin_pieces, tam_recuadro_pct, tam_frontera_pct)
    ancho = ancho_for_width_piece(ap, margin_pieces, tam_recuadro_pct, tam_frontera_pct)
    return FitResult(width_piece=ap, ancho=ancho, clamped=clamped)
