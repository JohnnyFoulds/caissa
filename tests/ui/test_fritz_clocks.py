"""
tests/ui/test_fritz_clocks.py — Fritz LCD clock and eval line tests.

xfail stubs until Phase 4 (feat/fritz-clocks-eval).

:spec: Phase 4 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE4 = "Requires Phase 4 (feat/fritz-clocks-eval)"


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_lcd_widgets_present_and_visible():
    """WFritzLCD widgets present and visible for both sides in Fritz mode."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_lcd_renders_nonbackground_pixels():
    """WFritzLCD renders a non-trivial number of non-background pixels."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_lcd_parses_both_input_forms():
    """WFritzLCD parses both MM:SS and HTML two-line forms correctly."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_classical_shows_qlabel_not_lcd():
    """Classical mode shows a QLabel[type='clock'] and no WFritzLCD."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_eval_summary_line_format():
    """Eval summary line matches expected format after 3 seconds of engine time."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE4)
def test_three_reachable_clocks_agree():
    """The three reachable clock display sites agree on seconds mid-game."""
    pytest.fail("not yet implemented")
