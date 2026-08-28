"""
tests/unit/fritz/test_clock_model.py — Unit tests for ClockModel (no Qt).

Test IDs
────────
T-CLK-01  test_parse_mmss_form
T-CLK-02  test_parse_hmmss_form
T-CLK-03  test_parse_html_two_line_form
T-CLK-04  test_parse_returns_none_for_garbage
T-CLK-05  test_format_tenths_below_threshold
T-CLK-06  test_format_no_tenths_above_threshold
T-CLK-07  test_negative_seconds_clamp_to_zero

:spec: §5.3 (ClockModel), FR-29
"""

from __future__ import annotations

import pytest

from Code.Fritz.ClockModel import digits, format, parse

pytestmark = pytest.mark.unit


def test_parse_mmss_form():
    """T-CLK-01: MM:SS strings parse to correct seconds."""
    assert parse("05:00") == 300.0
    assert parse("01:30") == 90.0
    assert parse("00:00") == 0.0
    assert parse("59:59") == 3599.0


def test_parse_hmmss_form():
    """T-CLK-02: H:MM:SS strings parse to correct seconds."""
    assert parse("1:00:00") == 3600.0
    assert parse("1:30:00") == 5400.0
    assert parse("2:05:03") == 7503.0


def test_parse_html_two_line_form():
    """T-CLK-03: HTML two-line form (from WBase.set_clock_*) parses correctly."""
    # This is the actual string WBase.set_clock_white produces when tm2 is not None.
    html = '05:00<br><FONT SIZE="-4">0.0'
    assert parse(html) == 300.0

    html2 = '01:23<br><FONT SIZE="-4">0.5'
    assert parse(html2) == 83.0


def test_parse_returns_none_for_garbage():
    """T-CLK-04: Unrecognised strings return None instead of raising."""
    assert parse("") is None
    assert parse("not a clock") is None
    assert parse("abc:xyz") is None
    assert parse(None) is None  # type: ignore[arg-type]


def test_format_tenths_below_threshold():
    """T-CLK-05: With show_tenths=True, tenths are appended when seconds < 20."""
    result = format(19.3, show_tenths=True)
    assert result == "00:19.3"

    result = format(0.7, show_tenths=True)
    assert result == "00:00.7"


def test_format_no_tenths_above_threshold():
    """T-CLK-06: Tenths are suppressed at or above the 20-second threshold."""
    result = format(20.0, show_tenths=True)
    assert "." not in result

    result = format(300.0, show_tenths=True)
    assert result == "05:00"
    assert "." not in result


def test_negative_seconds_clamp_to_zero():
    """T-CLK-07: Negative input is silently clamped to 0."""
    assert format(-5.0) == "00:00"
    assert digits(-100.0) == "00:00"
    assert format(-5.0, show_tenths=True) == "00:00.0"
