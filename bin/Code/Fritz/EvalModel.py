"""
bin/Code/Fritz/EvalModel.py — Pure evaluation model.

Converts a ``MultiEngineResponse`` (or raw values) into an :class:`EvalSummary`
with a verbal assessment, NAG number, formatted centipawn score, and search info.

Centipawn convention: ``cp_white`` is from White's perspective
(positive = White is better).  Use ``±_MATE_CP`` for decisive mate positions.

:spec: §5.3 (EvalModel), FR-31
"""

from __future__ import annotations

import logging

from Code.Fritz.Types import EvalSummary

_log = logging.getLogger(__name__)

# Absolute cp thresholds — from White's perspective.
_EQUAL_CP: int = 25       # |cp| ≤ this  →  equal
_SLIGHT_CP: int = 100     # |cp| ≤ this  →  slightly better
_BETTER_CP: int = 300     # |cp| ≤ this  →  better (moderate advantage)
# |cp| > _BETTER_CP         →  winning (decisive advantage)

# Mirrors WFritzEvalGraph._MATE_CP: centipawn encoding for a mating position.
_MATE_CP: int = 30_000

# NAG numbers (match Nags.py declarations).
_NAG_EQUAL = 10        # "="
_NAG_UNCLEAR = 13      # "∞"
_NAG_SLIGHT_W = 14     # "⩲"
_NAG_SLIGHT_B = 15     # "⩱"
_NAG_BETTER_W = 16     # "±"
_NAG_BETTER_B = 17     # "∓"
_NAG_WIN_W = 18        # "+-"
_NAG_WIN_B = 19        # "-+"


def _assessment(cp_white: int | None) -> tuple[str, int]:
    """Return ``(text, nag)`` for a given cp_white value.

    :param cp_white: Centipawns from White's perspective, ``+_MATE_CP`` for White
        mates, ``-_MATE_CP`` for Black mates, or ``None`` for truly unknown.
    """
    if cp_white is None:
        return ("Position is unclear", _NAG_UNCLEAR)
    if abs(cp_white) >= _MATE_CP:
        if cp_white > 0:
            return ("White is winning", _NAG_WIN_W)
        return ("Black is winning", _NAG_WIN_B)
    if abs(cp_white) <= _EQUAL_CP:
        return ("Position is equal", _NAG_EQUAL)
    white_better = cp_white > 0
    if abs(cp_white) <= _SLIGHT_CP:
        return ("White is slightly better", _NAG_SLIGHT_W) if white_better else ("Black is slightly better", _NAG_SLIGHT_B)
    if abs(cp_white) <= _BETTER_CP:
        return ("White is better", _NAG_BETTER_W) if white_better else ("Black is better", _NAG_BETTER_B)
    return ("White is winning", _NAG_WIN_W) if white_better else ("Black is winning", _NAG_WIN_B)


def describe_values(
    cp_white: int | None,
    depth: int,
    seldepth: int,
    nodes: int,
    ms: int,
) -> EvalSummary:
    """Pure evaluation summary from raw values.

    :param cp_white: Centipawns from White's perspective.  Use ``±_MATE_CP``
        for mate positions.  ``None`` → unclear.
    :param depth:    Search depth reached.
    :param seldepth: Selective search depth.
    :param nodes:    Nodes searched.
    :param ms:       Elapsed time in milliseconds.
    :returns: Fully populated :class:`~Code.Fritz.Types.EvalSummary`.
    :spec: FR-31
    """
    text, nag = _assessment(cp_white)
    # EvalSummary.cp stores None for mate positions (no meaningful cp to display).
    display_cp = None if (cp_white is not None and abs(cp_white) >= _MATE_CP) else cp_white
    return EvalSummary(
        text=text,
        nag=nag,
        cp=display_cp,
        depth=depth,
        seldepth=seldepth,
        nodes=nodes,
        ms=ms,
    )


def describe(mrm) -> EvalSummary | None:
    """Build an :class:`EvalSummary` from a live ``MultiEngineResponse``.

    :param mrm: A ``MultiEngineResponse`` (or duck-typed equivalent).
    :returns: :class:`EvalSummary`, or ``None`` if *mrm* is ``None`` / has no moves.
    :spec: FR-31
    """
    if mrm is None:
        return None
    li = getattr(mrm, "li_rm", None)
    if not li:
        return None
    rm = li[0]

    puntos: int = getattr(rm, "puntos", 0)
    mate: int = getattr(rm, "mate", 0)
    is_white: bool = getattr(rm, "is_white", True)

    if mate:
        # Positive mate from moving side's POV means they are mating the opponent.
        white_mates = (mate > 0) == is_white
        cp_white: int | None = _MATE_CP if white_mates else -_MATE_CP
    else:
        # Convert from moving-side perspective to White's perspective.
        cp_white = puntos if is_white else -puntos

    return describe_values(
        cp_white=cp_white,
        depth=getattr(mrm, "depth", 0),
        seldepth=getattr(rm, "seldepth", 0),
        nodes=getattr(mrm, "nodes", 0),
        ms=getattr(rm, "time", 0),
    )
