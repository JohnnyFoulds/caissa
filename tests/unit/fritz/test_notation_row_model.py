"""
tests/unit/fritz/test_notation_row_model.py — Unit tests for ``Code.Fritz.NotationRowModel``.

xfail stubs until Phase 5 (feat/fritz-notation).

:spec: §5.3, Phase 5 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE5 = "Requires Phase 5 (feat/fritz-notation)"


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_row_returns_correct_figurine_glyph():
    """row() returns the correct figurine glyph for a piece move."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_row_returns_correct_nag_nums():
    """row() returns the correct NAG numbers for an annotated move."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_row_indent_level_for_variation():
    """row() indent_level > 0 for a move inside a variation."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE5)
def test_row_is_current_flag():
    """row() is_current is True exactly for the current move."""
    pytest.fail("not yet implemented")
