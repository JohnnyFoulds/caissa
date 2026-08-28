"""
tests/test_fritz_light_theme.py — Fritz light theme compliance tests.

xfail stubs until Phase 6 (feat/fritz-light-theme).

:spec: Phase 6 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui

_PHASE6 = "Requires Phase 6 (feat/fritz-light-theme)"


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_template_gaps_empty_for_all_eleven_colors_files():
    """T-LIT-01: template_gaps is empty for all 11 .colors files against colors.template."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_no_q1_or_q3_violation_in_fritz_qss():
    """T-LIT-02: scan_qss reports no Q1 or Q3 violations in Fritz.qss."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_geometry_parity_between_themes():
    """T-LIT-03: Fritz.qss and Modern Fritz.qss are identical once colour-bearing lines are stripped."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_same_qproperty_names_different_values():
    """T-LIT-04: Both theme files declare the same set of qproperty- names per selector with different values."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_board_static_dark_in_both_themes():
    """T-LIT-05: BOARD_STATIC key is dark in both Fritz.colors and Modern Fritz.colors."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_is_dark_differs_between_themes():
    """T-LIT-06: IS_DARK is 0 in Fritz.colors and 1 in Modern Fritz.colors."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_both_modes_resolve_to_modern_fritz_ui_hook():
    """T-LIT-07: load_mode_hook resolves both mode files to modern_fritz_ui.py."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE6)
def test_every_wfritz_selector_present_in_both_themes():
    """T-LIT-08: Every #WFritz*/#WRibbon* selector present in one theme file is present in the other."""
    pytest.fail("not yet implemented")
