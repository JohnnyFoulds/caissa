"""
tests/ui/test_fritz_ribbon.py — Fritz Office-style ribbon tests (T-RIB-01..11).

xfail stubs until Phase 7 (feat/fritz-ribbon).

:spec: Phase 7 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE7 = "Requires Phase 7 (feat/fritz-ribbon)"


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_ribbon_present_correct_height():
    """T-RIB-01: Ribbon present in Fritz mode, height 60-140px, WRibbonTabBar visible."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_tab_labels_in_order_each_tab_has_groups():
    """T-RIB-02: Tab labels are exactly the expected set in order; every tab has >= 1 group with >= 1 slot."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_group_captions_below_controls():
    """T-RIB-03: Every group caption is non-empty and positioned below its controls."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_resign_disabled_at_home_geometry_stable():
    """T-RIB-04: TB_RESIGN is visible+disabled at home, visible+enabled in game; x,y unchanged."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_overflow_empty_across_screen_states():
    """T-RIB-05: Overflow is empty at every step of home/in-game/tutor-thinking/engine-thinking/paused."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_close_keys_in_quick_access():
    """T-RIB-06: All six closeEvent keys are in quick_access and >= 1 is enabled."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_click_ribbon_new_game_opens_dialog():
    """T-RIB-07: click_ribbon home 'New Game' opens WFritzNewGame; dialog_cancel returns to home intact."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_toggle_pane_hides_and_restores():
    """T-RIB-08: toggle_pane eval_graph off hides WFritzEvalGraph; on restores it at height > 20px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_user_tab_pin_respected():
    """T-RIB-09: current_tab stays on user-selected tab after a move."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_classical_mode_no_ribbon():
    """T-RIB-10: In classical mode: ribbon_info.present is false, toolbar height < 80px, WRibbon not findable."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_resize_with_ribbon_board_fits():
    """T-RIB-11: With ribbon installed, resize_window 1200x800 keeps window at 1200x800 and board fits pane."""
    pytest.fail("not yet implemented")
