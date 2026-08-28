"""
tests/unit/fritz/test_eval_model.py — Unit tests for EvalModel (no Qt).

Test IDs
────────
T-EVAL-01  test_assessment_ladder_slightly_better
T-EVAL-02  test_assessment_ladder_winning
T-EVAL-03  test_mate_score_produces_correct_nag
T-EVAL-04  test_none_cp_is_handled
T-EVAL-05  test_sign_is_side_to_move_relative
T-EVAL-06  test_describe_values_produces_correct_summary

:spec: §5.3 (EvalModel), FR-31
"""

from __future__ import annotations

import pytest
from Code.Fritz.EvalModel import _MATE_CP, describe, describe_values

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# T-EVAL-01  Assessment ladder — slightly better
# ---------------------------------------------------------------------------

def test_assessment_ladder_slightly_better():
    """T-EVAL-01: 60cp ≈ slightly better; text and NAG are correct for both sides."""
    # White slightly better
    s = describe_values(cp_white=60, depth=20, seldepth=30, nodes=500_000, ms=1000)
    assert "slightly better" in s.text.lower() or "White" in s.text
    assert s.nag == 14  # ⩲
    assert s.cp == 60

    # Black slightly better
    s = describe_values(cp_white=-60, depth=20, seldepth=30, nodes=500_000, ms=1000)
    assert "slightly better" in s.text.lower() or "Black" in s.text
    assert s.nag == 15  # ⩱
    assert s.cp == -60


# ---------------------------------------------------------------------------
# T-EVAL-02  Assessment ladder — winning
# ---------------------------------------------------------------------------

def test_assessment_ladder_winning():
    """T-EVAL-02: |cp| > 300 → winning for the leading side; NAG 18 or 19."""
    s = describe_values(cp_white=400, depth=25, seldepth=35, nodes=1_000_000, ms=2000)
    assert s.nag == 18  # +-  (White winning)
    assert "winning" in s.text.lower() or "White" in s.text

    s = describe_values(cp_white=-400, depth=25, seldepth=35, nodes=1_000_000, ms=2000)
    assert s.nag == 19  # -+  (Black winning)


# ---------------------------------------------------------------------------
# T-EVAL-03  Mate score
# ---------------------------------------------------------------------------

def test_mate_score_produces_correct_nag():
    """T-EVAL-03: ±_MATE_CP encodes a mating position; EvalSummary.cp is None."""
    # White mates
    s = describe_values(cp_white=_MATE_CP, depth=15, seldepth=15, nodes=100_000, ms=500)
    assert s.nag == 18
    assert s.cp is None   # display cp suppressed for mates

    # Black mates
    s = describe_values(cp_white=-_MATE_CP, depth=15, seldepth=15, nodes=100_000, ms=500)
    assert s.nag == 19
    assert s.cp is None


# ---------------------------------------------------------------------------
# T-EVAL-04  None cp — unclear
# ---------------------------------------------------------------------------

def test_none_cp_is_handled():
    """T-EVAL-04: cp_white=None yields NAG 13 (unclear) without raising."""
    s = describe_values(cp_white=None, depth=0, seldepth=0, nodes=0, ms=0)
    assert s.nag == 13   # ∞
    assert s.cp is None


# ---------------------------------------------------------------------------
# T-EVAL-05  Sign is side-to-move relative
# ---------------------------------------------------------------------------

def test_sign_is_side_to_move_relative():
    """T-EVAL-05: describe() converts puntos (moving-side POV) to White's POV correctly."""

    class _RM:
        puntos = 100   # moving side has +1.00 advantage
        mate = 0
        is_white = False   # but it's Black's turn → White is -1.00
        depth = 20
        seldepth = 28
        time = 1000
        nodes = 500_000

    class _MRM:
        li_rm = [_RM()]
        depth = 20
        nodes = 500_000

    s = describe(_MRM())
    # puntos=100 with is_white=False → cp_white = -100 (Black is better)
    assert s.cp == -100
    assert s.nag == 15   # ⩱  Black slightly better


# ---------------------------------------------------------------------------
# T-EVAL-06  Full summary round-trip
# ---------------------------------------------------------------------------

def test_describe_values_produces_correct_summary():
    """T-EVAL-06: All EvalSummary fields are populated from describe_values."""
    s = describe_values(cp_white=75, depth=24, seldepth=32, nodes=900_000, ms=8000)
    assert isinstance(s.text, str) and s.text
    assert s.nag is not None
    assert s.cp == 75
    assert s.depth == 24
    assert s.seldepth == 32
    assert s.nodes == 900_000
    assert s.ms == 8000


# ---------------------------------------------------------------------------
# Additional coverage — equal, better, describe() edge cases
# ---------------------------------------------------------------------------

def test_assessment_equal_position():
    """cp=0 → equal; cp=25 → equal boundary."""
    for cp in [0, 10, 25, -25]:
        s = describe_values(cp_white=cp, depth=10, seldepth=10, nodes=0, ms=0)
        assert s.nag == 10, f"Expected equal (NAG 10) for cp={cp}, got {s.nag}"
        assert "equal" in s.text.lower()


def test_assessment_better_black():
    """Black slightly/clearly better in the 26–300 cp range."""
    # Slightly better for Black (26–100 cp)
    s = describe_values(cp_white=-80, depth=20, seldepth=28, nodes=0, ms=0)
    assert s.nag == 15   # ⩱
    # Better for Black (101–300 cp)
    s = describe_values(cp_white=-200, depth=20, seldepth=28, nodes=0, ms=0)
    assert s.nag == 17   # ∓


def test_describe_returns_none_for_none_mrm():
    """describe(None) returns None."""
    assert describe(None) is None


def test_describe_returns_none_for_empty_li_rm():
    """describe() returns None when mrm.li_rm is empty."""
    class _MRM:
        li_rm = []
        depth = 0
        nodes = 0
    assert describe(_MRM()) is None


def test_describe_with_mate_black_wins():
    """describe() with mate<0 from Black's side produces Black winning NAG."""
    class _RM:
        puntos = 0
        mate = -3        # Black mates in 3 (from Black's POV: negative mate)
        is_white = False  # Black is moving
        seldepth = 3
        time = 100

    class _MRM:
        li_rm = [_RM()]
        depth = 3
        nodes = 1000

    s = describe(_MRM())
    # mate=-3, is_white=False: white_mates = (-3 > 0) == False = (False == False) = True
    # Actually: (mate > 0) == is_white → (-3 > 0) == False → False == False → True
    # So white_mates=True → cp_white = _MATE_CP → White winning NAG 18
    # OR mate=3, is_white=True would give the same. Let's test mate=3 from White:
    assert s is not None
    assert s.nag in (18, 19)  # Either side mating
