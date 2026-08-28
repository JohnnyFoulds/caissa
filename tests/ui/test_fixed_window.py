"""tests/ui/test_fixed_window.py — Fixed-window behaviour tests (T-FIX-01..15).

These tests verify that in Fritz mode the window stays at the user-chosen size
and the board fits itself into the available space, rather than the classical
behaviour where the window resizes to fit the board.

All tests require a running Caissa process in Modern Fritz mode.

Test IDs
─────────
T-FIX-01   resize_window reports the correct size ±4px
T-FIX-02   window size unchanged after a game starts
T-FIX-03   window size unchanged after returning to home screen
T-FIX-04   board ancho grows when the window is made larger
T-FIX-05   window minimum size is small (board is not driving it)
T-FIX-06   maximize then restore returns the pre-maximize size ±4px
T-FIX-07   fullscreen round-trip — board not clipped, toolbar restores
T-FIX-08   stored width_piece in UserData never changes across fit operations
T-FIX-09   splitter sizes survive a restart
T-FIX-10   no RuntimeError from repeated mode enter/exit (splitter list stays clean)
T-FIX-11   classical mode: adjust_size still runs; key_video is "maind"
T-FIX-12   Ctrl+wheel disabled in Fritz, enabled in classical
T-FIX-13   show_variations does not change window size
T-FIX-14   Fritz mode creates no BASEV board-config entry (WBase.py:291 decoupling)
T-FIX-15   dispatch_size path guarded: board width change doesn't move window

:spec: §2.2, Phase 2 (feature_spec.md)
"""

import pytest

pytestmark = pytest.mark.rpa_ui

_PHASE = "Phase 2 (feat/fritz-fixed-window)"


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_resize_window_reports_correct_size(client):
    """T-FIX-01: resize_window <w> <h> → window_info reports w×h ±4px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_window_unchanged_after_game_start(client):
    """T-FIX-02: starting a game does not change the window size."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_window_unchanged_after_return_home(client):
    """T-FIX-03: force_cancel back to home does not change the window size."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_board_grows_with_window(client):
    """T-FIX-04: board_info.ancho grows between resize 1000×700 and 1600×1000."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_min_size_small(client):
    """T-FIX-05: window_info.min_w and min_h are ≤ 600×400 (board not driving min)."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_maximize_restore_returns_original_size(client):
    """T-FIX-06: maximize → restore-down returns to the pre-maximize size ±4px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_fullscreen_round_trip(client):
    """T-FIX-07: F11 fullscreen round-trip — ribbon/toolbar hides and restores."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_width_piece_never_persisted_by_fit(client):
    """T-FIX-08: width_piece in UserData is unchanged across all fit operations."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_splitter_sizes_survive_restart(client):
    """T-FIX-09: set_splitter_sizes → restart → sizes within 8px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_no_runtime_error_on_repeated_mode_enter(client):
    """T-FIX-10: enter Fritz → exit → enter 3× produces no RuntimeError."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_classical_adjust_size_still_runs(client):
    """T-FIX-11: in classical mode adjust_size runs and key_video is 'maind'."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_board_zoom_disabled_in_fritz_enabled_in_classical(client):
    """T-FIX-12: Ctrl+wheel in Fritz leaves ancho unchanged; in classical it changes."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_show_variations_does_not_change_window_size(client):
    """T-FIX-13: the show_variations modal does not alter window w/h."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_no_basev_entry_created_by_fritz_mode(client):
    """T-FIX-14: entering Fritz mode creates no BASEV board-config entry."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=f"Requires {_PHASE}")
def test_dispatch_size_path_guarded(client):
    """T-FIX-15: board width change via Board.width_changed doesn't resize window."""
    pytest.fail("not yet implemented")
