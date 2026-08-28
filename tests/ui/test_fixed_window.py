"""
tests/ui/test_fixed_window.py — Fixed-window behaviour tests (T-FIX-01..15).

xfail stubs until Phase 2 (feat/fritz-fixed-window).

:spec: Phase 2 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE2 = "Requires Phase 2 (feat/fritz-fixed-window)"


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_resize_window_reports_correct_size():
    """T-FIX-01: resize_window 1400 900 → window_info reports 1400×900 ±4px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_window_unchanged_after_game_start():
    """T-FIX-02: after startgame, window_info w/h are unchanged."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_window_unchanged_after_return_home():
    """T-FIX-03: returning home leaves w/h unchanged."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_board_grows_with_window():
    """T-FIX-04: board_info.ancho grows between small and large window sizes."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_min_size_small():
    """T-FIX-05: window_info.min_w/min_h ≤ 600×400 (board not driving the minimum)."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_maximize_restore_returns_original_size():
    """T-FIX-06: set_window_state maximized then normal returns to pre-maximize size ±4px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_fullscreen_round_trip():
    """T-FIX-07: fullscreen round-trip — ribbon/toolbar hidden then visible, board not clipped."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_width_piece_never_persisted_by_fit():
    """T-FIX-08: width_piece in UserData is unchanged across all resize/maximize/game operations."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_splitter_sizes_survive_restart():
    """T-FIX-09: splitter sizes survive app restart."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_no_runtime_error_on_repeated_mode_enter():
    """T-FIX-10: no RuntimeError in bug.log after entering/exiting Fritz mode 3 times."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_classical_adjust_size_still_runs():
    """T-FIX-11: classical mode — adjust_size still runs, window height tracks board."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_board_zoom_disabled_in_fritz_enabled_in_classical():
    """T-FIX-12: Ctrl+wheel over the board in Fritz leaves board unchanged; in classical it resizes."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_show_variations_does_not_change_window_size():
    """T-FIX-13: show_variations — window_info w/h unchanged before, during and after."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_no_basev_entry_created_by_fritz_mode():
    """T-FIX-14: Fritz mode creates no BASEV entry in UserData on a fresh profile."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE2)
def test_dispatch_size_path_guarded():
    """T-FIX-15: with _fit_board true, a board width change via width_changed leaves window size unchanged."""
    pytest.fail("not yet implemented")
