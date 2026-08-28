"""
tests/ui/test_fritz_panes.py — Fritz pane title bar behaviour tests (T-PANE-01..07).

xfail stubs until Phase 3 (feat/fritz-panes).

:spec: Phase 3 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE3 = "Requires Phase 3 (feat/fritz-panes)"


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_pane_title_bars_present_with_correct_labels():
    """T-PANE-01: each right-column pane has a visible WFritzPaneTitle with the expected label."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_title_bar_height_matches_qss_property():
    """T-PANE-02: title bar height equals the qproperty-titleHeight in the active .qss."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_close_button_hides_pane_siblings_intact():
    """T-PANE-03: ✕ on the eval-graph pane hides it; no sibling's height goes to zero."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_reshown_pane_returns_above_min_px():
    """T-PANE-04: re-showing a hidden pane restores it at >= min_px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_chevron_menu_has_three_items_and_sibling_submenu():
    """T-PANE-05: ▾ opens a menu with three items and a sibling-panes submenu."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_mode_exit_restores_layout_to_baseline():
    """T-PANE-06: switching to classical and back leaves mw.base.layout() structurally identical to baseline."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_no_fritz_widget_has_zero_dimension():
    """T-PANE-07: no WFritz* widget reports zero width or zero height."""
    pytest.fail("not yet implemented")
