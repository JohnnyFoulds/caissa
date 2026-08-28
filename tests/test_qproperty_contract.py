"""
tests/test_qproperty_contract.py — Offscreen qproperty- contract checks (T-QPR-01..05).

These tests require a running QApplication and are therefore offscreen tests.
They are xfail stubs until Phase 1 populates the Fritz .qss with WFritz* selectors.

:spec: §4, §5.3 (feature_spec.md), N-FRITZ-4
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 (refactor/fritz-widget-qss) — no WFritz* qproperty- blocks yet")
def test_qproperty_names_resolve_to_declared_properties():
    """T-QPR-01: every qproperty-<name> in Fritz .qss files resolves to a declared Qt Property."""
    pytest.fail("not yet implemented — requires Phase 1 widget qproperty- blocks")


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 (refactor/fritz-widget-qss)")
def test_property_defaults_are_valid_colors_or_positive_ints():
    """T-QPR-02: every widget's Python Property default is a valid colour or positive int."""
    pytest.fail("not yet implemented — requires Phase 1")


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 (refactor/fritz-widget-qss) and Phase 6 (feat/fritz-light-theme)")
def test_fritz_and_dark_yield_different_resolved_values():
    """T-QPR-03: instantiating each widget under Fritz and Modern Fritz yields different colour values."""
    pytest.fail("not yet implemented — requires Phase 1 + Phase 6")


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 (refactor/fritz-widget-qss)")
def test_widget_renders_with_no_stylesheet_using_defaults():
    """T-QPR-04: a widget whose .qss block is absent still renders with its documented defaults."""
    pytest.fail("not yet implemented — requires Phase 1")


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 (refactor/fritz-widget-qss)")
def test_wa_styled_background_set_on_all_custom_painted_widgets():
    """T-QPR-05: WA_StyledBackground is set on every custom-painted Fritz widget."""
    pytest.fail("not yet implemented — requires Phase 1")
