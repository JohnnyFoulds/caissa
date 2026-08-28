"""
tests/unit/fritz/test_notation_row_model.py — unit tests for Fritz/NotationRowModel.

The tests use simple duck-typed stubs for Move objects; no real Move is imported
because Move is Qt-tainted (Move → Nags → QtGui).  The bootstrap still runs so
that Code.configuration is available if any test needs it, but the Qt application
is not constructed.

Test IDs
─────────
test_row_returns_correct_figurine_glyph
test_row_returns_correct_nag_nums
test_row_indent_level_for_variation
test_row_is_current_flag

:spec: §5.1
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Duck-typed move stub
# ---------------------------------------------------------------------------

class _Move:
    """Minimal duck-typed stub for Code.Base.Move."""

    def __init__(self, pgn: str, li_nags=None):
        self._pgn = pgn
        self.li_nags = list(li_nags or [])

    def base_pgn(self) -> str:
        return self._pgn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_row_returns_correct_figurine_glyph():
    """NotationRow.figurine_glyph is the first char when it is a piece letter."""
    from Code.Fritz.NotationRowModel import row

    assert row(_Move("Nf3")).figurine_glyph == "N", (
        "T-NRM-01 FAIL: piece move should extract 'N' as figurine_glyph"
    )
    assert row(_Move("e4")).figurine_glyph is None, (
        "T-NRM-01 FAIL: pawn push should have figurine_glyph=None"
    )
    assert row(_Move("O-O")).figurine_glyph is None, (
        "T-NRM-01 FAIL: castling should have figurine_glyph=None"
    )
    assert row(_Move("Qa4")).figurine_glyph == "Q"
    assert row(_Move("Bb5")).figurine_glyph == "B"


def test_row_returns_correct_nag_nums():
    """NotationRow.nag_nums is a tuple of the move's li_nags."""
    from Code.Fritz.NotationRowModel import row

    r = row(_Move("d4", li_nags=[1]))
    assert r.nag_nums == (1,), f"T-NRM-02 FAIL: expected (1,), got {r.nag_nums}"

    r2 = row(_Move("c4", li_nags=[3, 14]))
    assert r2.nag_nums == (3, 14), f"T-NRM-02 FAIL: expected (3, 14), got {r2.nag_nums}"

    r3 = row(_Move("e5"))
    assert r3.nag_nums == (), f"T-NRM-02 FAIL: expected (), got {r3.nag_nums}"


def test_row_indent_level_for_variation():
    """indent_level propagates from the keyword argument."""
    from Code.Fritz.NotationRowModel import row

    r_main = row(_Move("e4"))
    assert r_main.indent_level == 0, (
        f"T-NRM-03 FAIL: default indent_level should be 0, got {r_main.indent_level}"
    )

    r_var = row(_Move("d5"), indent_level=1)
    assert r_var.indent_level == 1, (
        f"T-NRM-03 FAIL: expected indent_level=1, got {r_var.indent_level}"
    )

    r_deep = row(_Move("Nf6"), indent_level=2)
    assert r_deep.indent_level == 2


def test_row_is_current_flag():
    """is_current propagates from the keyword argument."""
    from Code.Fritz.NotationRowModel import row

    r = row(_Move("e4"))
    assert r.is_current is False, (
        f"T-NRM-04 FAIL: default is_current should be False, got {r.is_current}"
    )

    r_cur = row(_Move("e4"), is_current=True)
    assert r_cur.is_current is True, (
        f"T-NRM-04 FAIL: expected is_current=True, got {r_cur.is_current}"
    )


def test_row_chip_color_with_nag_and_colors():
    """chip_color is a hex string from the colors dict when a quality NAG is present."""
    from Code.Fritz.NotationRowModel import row

    colors = {
        "NAG_BRILLIANT": "#1d4f1d",
        "NAG_GOOD":      "#183018",
        "NAG_MISTAKE":   "#4d2200",
    }

    # NAG_3 = brilliant
    r = row(_Move("Rxf7", li_nags=[3]), colors=colors)
    assert r.chip_color == "#1d4f1d", (
        f"T-NRM-05 FAIL: expected '#1d4f1d', got {r.chip_color!r}"
    )

    # NAG_2 = mistake
    r2 = row(_Move("Nd7", li_nags=[2]), colors=colors)
    assert r2.chip_color == "#4d2200"

    # No quality NAG → None
    r3 = row(_Move("e4", li_nags=[14]), colors=colors)
    assert r3.chip_color is None


def test_row_chip_color_none_when_colors_absent():
    """chip_color is None when colors=None regardless of NAGs."""
    from Code.Fritz.NotationRowModel import row

    r = row(_Move("Nf3", li_nags=[1, 3]), colors=None)
    assert r.chip_color is None, (
        f"T-NRM-06 FAIL: chip_color should be None when colors=None, got {r.chip_color!r}"
    )
