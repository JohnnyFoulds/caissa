"""
tests/test_fritz_qproperties.py — WFritz* widget qproperty- contract tests (T-FQP-01..09).

xfail stubs until Phase 1 (refactor/fritz-widget-qss).

:spec: §5.5 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui

_PHASE1 = "Requires Phase 1 (refactor/fritz-widget-qss)"


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_no_hardcoded_hex_outside_property_defaults():
    """T-FQP-01: every WFritz*.py module's remaining #RRGGBB literals appear only as Property defaults."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_every_python_property_has_qss_line_in_both_themes():
    """T-FQP-02: every Property declared in Python has a qproperty- line in both Fritz.qss and Modern Fritz.qss."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_every_qss_qproperty_has_python_property():
    """T-FQP-03: every qproperty- line in both themes resolves to a declared Python Property."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_different_themes_yield_different_resolved_values():
    """T-FQP-04: each widget instantiated under Fritz and Modern Fritz reports different resolved colours."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_no_stylesheet_renders_with_documented_defaults():
    """T-FQP-05: each widget instantiated with no stylesheet reports its documented defaults."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_player_header_height_not_less_than_content():
    """T-FQP-06: WFritzPlayerHeader.height() >= sum of child heights (the 61px clip bug)."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_player_header_font_family_not_menlo_under_qss():
    """T-FQP-07: WFritzPlayerHeader font family is not 'Menlo' when the QSS sets a different family."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_nag_keys_in_template_and_all_colors_files():
    """T-FQP-08: the six NAG_* keys exist in colors.template and in every .colors file."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE1)
def test_no_widget_reads_dic_colors_directly():
    """T-FQP-09: no WFritz* module reads Code.dic_colors directly (every colour via qproperty- or ThemeGateway)."""
    pytest.fail("not yet implemented")
