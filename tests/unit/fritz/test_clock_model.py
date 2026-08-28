"""
tests/unit/fritz/test_clock_model.py — Unit tests for ``Code.Fritz.ClockModel``.

xfail stubs until Phase 4 (feat/fritz-clocks-eval).

:spec: §5.3, Phase 4 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE4 = "Requires Phase 4 (feat/fritz-clocks-eval)"


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_parse_hmmss_form():
    """parse() accepts H:MM:SS form."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_parse_mmss_form():
    """parse() accepts MM:SS form."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_parse_html_two_line_form():
    """parse() accepts the HTML two-line form from set_clock_white."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_parse_returns_none_for_garbage():
    """parse() returns None for unrecognised input."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_format_tenths_below_threshold():
    """format() shows tenths when below the threshold."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_format_no_tenths_above_threshold():
    """format() omits tenths above the threshold."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_negative_seconds_clamp_to_zero():
    """format() clamps negative seconds to zero."""
    pytest.fail("not yet implemented")
