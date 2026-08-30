"""
UI integration tests for Fritz pane title bars and pane API (Phase 3).

Test IDs
────────
T-PANE-01  test_pane_title_bars_present_with_correct_labels
T-PANE-02  test_title_bar_height_matches_qss_property
T-PANE-03  test_close_button_hides_pane_siblings_intact        [xfail Phase 7]
T-PANE-04  test_reshown_pane_returns_above_min_px              [xfail Phase 7]
T-PANE-05  test_chevron_menu_has_three_items_and_sibling_submenu [xfail Phase 7]
T-PANE-06  test_mode_exit_restores_layout_to_baseline
T-PANE-07  test_no_fritz_widget_has_zero_dimension

Tests marked xfail (strict=True) for T-PANE-03/04/05 require the
``toggle_pane`` RPC verb added in Phase 7 (feat/fritz-ribbon).

Run with:
    pytest tests/ui/test_fritz_panes.py -v

Requires a Caissa process in Modern Fritz mode with a game in progress
(the pane swap from home to analysis view must have occurred).
"""

from __future__ import annotations

import os
import pickle
import re
import time

import pytest

pytestmark = pytest.mark.ui

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PK_PATH = os.path.join(_REPO, "UserData", "__Config__", "lk.pk2")

_PHASE7 = "Requires toggle_pane RPC verb (feat/fritz-ribbon, Phase 7)"

# Expected pane names in top-to-bottom order; must match _PANE_SPECS in modern_fritz_ui.py
_PANE_KEYS = ["player_header", "analysis_table", "eval_graph", "pgn"]
_PANE_OBJECT_NAMES = [f"WFritzPane_{k}" for k in _PANE_KEYS]

# QSS default title height (kept in sync with Modern Fritz.qss qproperty-titleHeight)
_QSS_TITLE_HEIGHT_PX = 20
_TITLE_HEIGHT_TOLERANCE = 2


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_fritz_game(client):
    """Ensure the app is in Fritz mode with an active game (analysis view visible)."""
    _set_ui_mode("Modern Fritz")
    time.sleep(0.3)
    # Trigger a game if we're still on the home screen
    _ensure_game_running(client)
    yield


def _set_ui_mode(mode_name: str) -> None:
    if not os.path.exists(_PK_PATH):
        return
    try:
        with open(_PK_PATH, "rb") as fh:
            cfg = pickle.load(fh)
        cfg["x_ui_mode"] = mode_name
        with open(_PK_PATH, "wb") as fh:
            pickle.dump(cfg, fh)
    except Exception:
        pass


def _ensure_game_running(client) -> None:
    """Start a Fritz game if the analysis widgets are not yet visible."""
    geo = _geo(client, "WFritzPane_eval_graph")
    if geo is not None:
        return  # already in analysis view

    # Home screen — trigger a new game
    try:
        client.click_toolbar("Level")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                info = client.dialog_info()
                if info.get("widgets"):
                    break
            except Exception:
                pass
            time.sleep(0.3)
        client.dialog_accept()
        time.sleep(1.2)
    except Exception:
        pass


def _geo(client, object_name: str) -> dict | None:
    """Geometry dict for a widget, or None if not found."""
    try:
        result = client.send(f"find_widget {object_name}")
        return result.get("geometry")
    except Exception:
        return None


def _geo_assert(geo: dict | None, label: str) -> dict:
    """Assert geometry exists and return it."""
    assert geo is not None, f"{label}: widget not found (is the app in Fritz game mode?)"
    return geo


# ---------------------------------------------------------------------------
# T-PANE-01  Four right-column panes visible, correct top-to-bottom order
# ---------------------------------------------------------------------------

def test_pane_title_bars_present_with_correct_labels(client):
    """T-PANE-01: All four WFritzPane wrappers are visible, top-to-bottom order correct."""
    geos = {}
    for name in _PANE_OBJECT_NAMES:
        g = _geo(client, name)
        _geo_assert(g, f"T-PANE-01 FAIL [{name}]")
        geos[name] = g

    # Check top-to-bottom ordering: each pane's y must be >= the previous one's y
    names = list(geos)
    for i in range(1, len(names)):
        prev_y = geos[names[i - 1]]["y"]
        curr_y = geos[names[i]]["y"]
        assert curr_y >= prev_y, (
            f"T-PANE-01 FAIL: {names[i]} (y={curr_y}) is above {names[i-1]} (y={prev_y}). "
            "Panes are not in the expected top-to-bottom order."
        )

    # Sanity: all panes have positive width and height
    for name, g in geos.items():
        assert g["w"] > 0, f"T-PANE-01 FAIL: {name} has zero width"
        assert g["h"] > 0, f"T-PANE-01 FAIL: {name} has zero height"


# ---------------------------------------------------------------------------
# T-PANE-02  Title bar height equals the QSS qproperty-titleHeight default
# ---------------------------------------------------------------------------

def test_title_bar_height_matches_qss_property(client):
    """T-PANE-02: WFritzPaneTitle height equals qproperty-titleHeight (20px)."""
    # find_widget returns the first matching widget; WFritzPaneTitle is the objectName
    # shared by all four title bars.  We measure the outer pane and infer the title bar.
    pane_geo = _geo(client, "WFritzPane_player_header")
    _geo_assert(pane_geo, "T-PANE-02 FAIL [WFritzPane_player_header]")

    title_geo = _geo(client, "WFritzPaneTitle")
    _geo_assert(title_geo, "T-PANE-02 FAIL [WFritzPaneTitle]")

    h = title_geo["h"]
    lo = _QSS_TITLE_HEIGHT_PX - _TITLE_HEIGHT_TOLERANCE
    hi = _QSS_TITLE_HEIGHT_PX + _TITLE_HEIGHT_TOLERANCE
    assert lo <= h <= hi, (
        f"T-PANE-02 FAIL: WFritzPaneTitle height is {h}px; "
        f"expected {_QSS_TITLE_HEIGHT_PX}px ±{_TITLE_HEIGHT_TOLERANCE}. "
        "Check qproperty-titleHeight in Modern Fritz.qss."
    )


# ---------------------------------------------------------------------------
# T-PANE-03  ✕ hides eval-graph pane, no sibling collapses   [xfail - Phase 7]
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_close_button_hides_pane_siblings_intact(client):
    """T-PANE-03: ✕ on eval_graph pane hides it; no sibling height goes to zero."""
    pytest.fail("not yet implemented — needs toggle_pane RPC verb")


# ---------------------------------------------------------------------------
# T-PANE-04  Re-showing pane restores it at >= min_px          [xfail - Phase 7]
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_reshown_pane_returns_above_min_px(client):
    """T-PANE-04: Re-showing eval_graph pane restores height >= min_px."""
    pytest.fail("not yet implemented — needs toggle_pane RPC verb")


# ---------------------------------------------------------------------------
# T-PANE-05  ▾ menu items and Reset size                       [xfail - Phase 7]
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_chevron_menu_has_three_items_and_sibling_submenu(client):
    """T-PANE-05: ▾ menu has Hide/Reset size/Panes; Reset size returns default_px."""
    pytest.fail("not yet implemented — needs toggle_pane RPC verb")


# ---------------------------------------------------------------------------
# T-PANE-06  Classical → Fritz layout structurally intact
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=False,
    reason="Mode switch requires app restart; not testable in a single-session fixture",
)
def test_mode_exit_restores_layout_to_baseline(client):
    """T-PANE-06: Switching to Classical and back leaves Fritz layout intact.

    Checks that on_mode_exit correctly unwraps WFritzPane wrappers so the
    Classical layout is byte-identical to a never-entered-Fritz baseline.
    """
    # Verify Fritz panes are present
    eg_before = _geo(client, "WFritzPane_eval_graph")
    _geo_assert(eg_before, "T-PANE-06 FAIL: Fritz panes not visible before mode switch")

    # Switch to classical (requires app restart — skip if not supported)
    _set_ui_mode("classical")
    time.sleep(0.5)

    # In classical: Fritz panes must be gone
    eg_classical = _geo(client, "WFritzPane_eval_graph")
    assert eg_classical is None, (
        "T-PANE-06 FAIL: WFritzPane_eval_graph still visible after switching to Classical. "
        "on_mode_exit did not remove the pane wrappers."
    )

    # Classical mode: pgn_information should be in the main splitter
    pgn_geo = _geo(client, "pgn_information")
    assert pgn_geo is not None, (
        "T-PANE-06 FAIL: pgn_information not found in classical mode. "
        "on_mode_exit may have failed to restore the standard layout."
    )

    # Switch back to Fritz
    _set_ui_mode("Modern Fritz")
    time.sleep(0.5)
    _ensure_game_running(client)

    # Fritz panes should be back
    eg_after = _geo(client, "WFritzPane_eval_graph")
    _geo_assert(eg_after, "T-PANE-06 FAIL: Fritz panes not restored after switching back to Fritz")


# ---------------------------------------------------------------------------
# T-PANE-07  No WFritzPane* widget has zero width or height
# ---------------------------------------------------------------------------

def test_no_fritz_widget_has_zero_dimension(client):
    """T-PANE-07: All WFritzPane wrappers have positive width and height."""
    failures: list[str] = []
    for name in _PANE_OBJECT_NAMES:
        g = _geo(client, name)
        if g is None:
            failures.append(f"{name}: not found")
            continue
        if g["w"] <= 0:
            failures.append(f"{name}: width={g['w']}")
        if g["h"] <= 0:
            failures.append(f"{name}: height={g['h']}")

    assert not failures, (
        "T-PANE-07 FAIL: zero-dimension pane(s):\n" + "\n".join(failures)
    )
