"""
tests/unit/fritz/test_eval_model.py — Unit tests for ``Code.Fritz.EvalModel``.

xfail stubs until Phase 4 (feat/fritz-clocks-eval).

:spec: §5.3, Phase 4 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE4 = "Requires Phase 4 (feat/fritz-clocks-eval)"


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_assessment_ladder_slightly_better():
    """describe_values produces 'slightly better' for a small centipawn advantage."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_assessment_ladder_winning():
    """describe_values produces 'winning' for a large centipawn advantage."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_mate_score_produces_correct_nag():
    """A mate score produces the correct NAG number."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_none_cp_is_handled():
    """describe_values handles None cp (e.g. during a mate sequence)."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_sign_is_side_to_move_relative():
    """The verbal assessment sign is relative to the side to move."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_describe_values_produces_correct_summary():
    """describe_values produces a correctly formatted EvalSummary string."""
    pytest.fail("not yet implemented")
