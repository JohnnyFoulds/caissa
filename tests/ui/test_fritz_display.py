"""
tests/ui/test_fritz_display.py — Tests for Board Display checkbox wiring and
select-engine defect fix.

:spec: defect #6, defect #11 (Fritz Mode Behaviour SDD)
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.ui


def _make_ribbon_with_display(qt_app):
    """Build a WRibbon with a Board Display checkboxes group."""
    from Code.Fritz.WRibbon import WRibbon

    spec = {
        "$schema_version": 1,
        "default_tab": "board",
        "missing_key_policy": "disable",
        "quick_access": [],
        "tabs": [
            {
                "id": "board",
                "label": "Board",
                "groups": [
                    {
                        "id": "board.display",
                        "label": "Display",
                        "kind": "checkboxes",
                        "items": [
                            {"key": "caissa:board_coordinates", "label": "Coordinates", "default": True},
                            {"key": "caissa:board_arrows",      "label": "Show arrows", "default": True},
                            {"key": "caissa:board_hints",       "label": "Show hints",  "default": False},
                        ],
                    }
                ],
            }
        ],
    }
    ribbon = WRibbon(spec=spec, dic_toolbar={})
    ribbon.show()
    return ribbon


# ---------------------------------------------------------------------------
# T-DSP-01  display checkboxes render (no crash, visible)
# ---------------------------------------------------------------------------

def test_display_checkboxes_render(qt_app):
    """T-DSP-01: Board Display group renders without crash."""
    ribbon = _make_ribbon_with_display(qt_app)
    assert ribbon is not None, "T-DSP-01: WRibbon with checkboxes group must not be None"


# ---------------------------------------------------------------------------
# T-DSP-02  set_display_api routes toggle to callback
# ---------------------------------------------------------------------------

def test_display_api_routes_toggle_to_callback(qt_app):
    """T-DSP-02: set_display_api routes checkbox toggle to the registered callback."""
    ribbon = _make_ribbon_with_display(qt_app)

    calls: list[tuple[str, bool]] = []

    ribbon.set_display_api({
        "caissa:board_coordinates": lambda v: calls.append(("coords", v)),
        "caissa:board_arrows":      lambda v: calls.append(("arrows", v)),
        "caissa:board_hints":       lambda v: calls.append(("hints", v)),
    })

    # Re-build — the display_api is registered AFTER construction, so we test
    # by triggering the toggled signal on the checkbox widgets directly.
    from PySide6 import QtWidgets
    for cb in ribbon.findChildren(QtWidgets.QCheckBox):
        if "Coordinates" in cb.text():
            # Toggle it off then back on.
            cb.setChecked(False)
            cb.setChecked(True)
            break

    coord_calls = [v for k, v in calls if k == "coords"]
    assert len(coord_calls) >= 1, (
        "T-DSP-02: at least one 'coords' callback call expected after toggling Coordinates"
    )


# ---------------------------------------------------------------------------
# T-DSP-03  select-engine action does not call motores() (crash guard)
# ---------------------------------------------------------------------------

def test_select_engine_action_does_not_crash(qt_app, monkeypatch):
    """T-DSP-03: caissa:select_engine no longer calls non-existent procesador.motores().

    The action is routed to _fritz_pick_level; we monkeypatch that to a no-op
    so the test stays unit-level.
    """
    import Code.UIModes.actions.view_actions as va

    called: list[bool] = []

    import Code.UIModes.actions.modern_fritz_ui as mfu
    monkeypatch.setattr(mfu, "_fritz_pick_level", lambda proc: called.append(True))

    import Code
    original_proc = getattr(Code, "procesador", None)
    try:
        from unittest.mock import MagicMock
        Code.procesador = MagicMock(spec=[])  # has NO 'motores' attribute

        va._select_engine()

        assert called, (
            "T-DSP-03: _fritz_pick_level must be called when caissa:select_engine fires"
        )
    finally:
        Code.procesador = original_proc


# ---------------------------------------------------------------------------
# T-DSP-04  modern-fritz.json board display items have key fields
# ---------------------------------------------------------------------------

def test_ribbon_json_display_items_have_keys():
    """T-DSP-04: modern-fritz.json Board Display items all have 'key' fields."""
    repo = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "Resources", "Ribbons", "modern-fritz.json")
    )
    with open(repo, encoding="utf-8") as fh:
        spec = json.load(fh)

    display_items = []
    for tab in spec.get("tabs", []):
        for group in tab.get("groups", []):
            if group.get("kind") == "checkboxes":
                display_items.extend(group.get("items", []))

    assert display_items, "T-DSP-04: at least one checkbox group expected"
    for item in display_items:
        assert "key" in item, (
            f"T-DSP-04: checkbox item {item.get('label')!r} missing 'key' field"
        )
