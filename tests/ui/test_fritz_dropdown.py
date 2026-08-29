"""
tests/ui/test_fritz_dropdown.py — In-process Qt tests for WDropdownPanel and WRibbon toggle.

Test IDs
────────
T-RIB-01  test_dropdown_panel_opens_below_button
T-RIB-02  test_dropdown_panel_dismisses_on_outside_click
T-RIB-03  test_dropdown_panel_checkmark_on_active_item
T-RIB-04  test_toggle_button_is_checkable
T-RIB-05  test_toggle_button_sync_with_app_state

:spec: FR-16, FR-17, §5.2 (feature_spec.md fritz-mode)
"""

from __future__ import annotations

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

pytestmark = pytest.mark.ui


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_actions(*keys: str) -> dict:
    """Return a dic_toolbar mapping each string key to a fresh QAction."""
    return {k: QtGui.QAction(k) for k in keys}


_TOGGLE_RIBBON = {
    "$schema_version": 1,
    "default_tab": "home",
    "missing_key_policy": "disable",
    "quick_access": [],
    "tabs": [
        {
            "id": "home",
            "label": "Home",
            "groups": [
                {
                    "id": "home.play",
                    "label": "Play",
                    "slots": [
                        {"key": "TB_STOP", "size": "large", "label": "Play Now", "toggle": True},
                        {"key": "TB_RESIGN", "size": "small"},
                    ],
                }
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# T-RIB-01  WDropdownPanel is positioned below its anchor button
# ---------------------------------------------------------------------------

def test_dropdown_panel_opens_below_button(qt_app):
    """T-RIB-01: popup() positions the panel immediately below the anchor button.

    :spec: §5.2 (WDropdownPanel.popup), FR-16
    """
    from Code.Fritz.WDropdownPanel import WDropdownPanel

    parent = QtWidgets.QWidget()
    parent.setGeometry(200, 200, 400, 60)
    parent.show()

    anchor = QtWidgets.QPushButton("New Game\n▼", parent)
    anchor.setGeometry(10, 10, 120, 40)

    clicked: list[str] = []
    panel = WDropdownPanel(
        parent=None,
        title="Choose Level",
        items=[
            ("Easy", lambda: clicked.append("easy")),
            ("Medium", lambda: clicked.append("medium")),
        ],
    )

    panel.popup(anchor)

    assert panel.isVisible(), "T-RIB-01: panel should be visible after popup()"

    expected_global = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))
    actual_pos = panel.pos()
    # Allow ±3px — the offscreen platform may report position with a small
    # frame-decoration offset that does not occur on a real WM.
    dx = abs(actual_pos.x() - expected_global.x())
    dy = abs(actual_pos.y() - expected_global.y())
    assert dx <= 3 and dy <= 3, (
        f"T-RIB-01: panel top-left {actual_pos} differs from "
        f"anchor bottom-left {expected_global} by ({dx},{dy})px"
    )

    panel.hide()
    parent.hide()


# ---------------------------------------------------------------------------
# T-RIB-02  WDropdownPanel has Qt.Popup window flag (dismisses on outside click)
# ---------------------------------------------------------------------------

def test_dropdown_panel_dismisses_on_outside_click(qt_app):
    """T-RIB-02: Panel uses Qt.Popup window type so it auto-dismisses on outside click.

    Qt.Popup is the semantic contract; the actual focus-loss event cannot be
    simulated offscreen without a real WM, so we verify the flag is set correctly.

    :spec: §5.2 (WDropdownPanel — Qt.Popup semantics), FR-16
    """
    from Code.Fritz.WDropdownPanel import WDropdownPanel

    panel = WDropdownPanel(
        parent=None,
        title="Test",
        items=[("Item A", lambda: None)],
    )

    flags = panel.windowFlags()
    assert flags & QtCore.Qt.WindowType.Popup, (
        "T-RIB-02: WDropdownPanel must have Qt.Popup window type "
        "so it dismisses on outside click"
    )


# ---------------------------------------------------------------------------
# T-RIB-03  WDropdownPanel set_checked() shows checkmark on correct item
# ---------------------------------------------------------------------------

def test_dropdown_panel_checkmark_on_active_item(qt_app):
    """T-RIB-03: set_checked(label) prefixes the matching item with '✓' and clears others.

    :spec: §5.2 (WDropdownPanel.set_checked), FR-16
    """
    from Code.Fritz.WDropdownPanel import WDropdownPanel

    labels = ["Easy", "Medium", "Hard"]
    panel = WDropdownPanel(
        parent=None,
        title="Choose Level",
        items=[(lbl, lambda: None) for lbl in labels],
    )

    panel.set_checked("Medium")

    assert panel._buttons["Medium"].text() == "✓  Medium", (
        "T-RIB-03: active item should have '✓  ' prefix"
    )
    assert panel._buttons["Easy"].text() == "Easy", (
        "T-RIB-03: non-active items should have no prefix"
    )
    assert panel._buttons["Hard"].text() == "Hard", (
        "T-RIB-03: non-active items should have no prefix"
    )

    # Clearing the checkmark
    panel.set_checked(None)
    for lbl in labels:
        assert panel._buttons[lbl].text() == lbl, (
            f"T-RIB-03: set_checked(None) should clear prefix on {lbl!r}"
        )


# ---------------------------------------------------------------------------
# T-RIB-04  WRibbon builds a checkable button for "toggle": true slots
# ---------------------------------------------------------------------------

def test_toggle_button_is_checkable(qt_app):
    """T-RIB-04: A slot with "toggle": true produces a checkable QToolButton.

    :spec: FR-17, §5.1 (WRibbon toggle support)
    """
    from Code.Fritz.WRibbon import WRibbon

    ribbon = WRibbon(
        spec=_TOGGLE_RIBBON,
        dic_toolbar=_make_actions("TB_STOP", "TB_RESIGN"),
    )
    ribbon.show()

    toggle_btn = ribbon._toggle_btns.get("TB_STOP")
    assert toggle_btn is not None, (
        "T-RIB-04: TB_STOP with 'toggle': true should be in _toggle_btns"
    )
    assert toggle_btn.isCheckable(), (
        "T-RIB-04: toggle button must be checkable"
    )

    non_toggle_btn = ribbon._toggle_btns.get("TB_RESIGN")
    assert non_toggle_btn is None, (
        "T-RIB-04: TB_RESIGN without 'toggle' must not appear in _toggle_btns"
    )


# ---------------------------------------------------------------------------
# T-RIB-05  WRibbon.sync() reflects toggle state from set_toggle_api()
# ---------------------------------------------------------------------------

def test_toggle_button_sync_with_app_state(qt_app):
    """T-RIB-05: sync() calls the toggle-get function and updates button checked state.

    :spec: FR-17, §5.1 (WRibbon.sync + set_toggle_api)
    """
    from Code.Fritz.WRibbon import WRibbon

    ribbon = WRibbon(
        spec=_TOGGLE_RIBBON,
        dic_toolbar=_make_actions("TB_STOP", "TB_RESIGN"),
    )
    ribbon.show()

    state = {"TB_STOP": True}
    ribbon.set_toggle_api(lambda key: state.get(key, False))

    ribbon.sync(li_acciones=["TB_STOP", "TB_RESIGN"])

    btn = ribbon._toggle_btns["TB_STOP"]
    assert btn.isChecked() is True, (
        "T-RIB-05: sync() should set checked=True when toggle_get returns True"
    )

    state["TB_STOP"] = False
    ribbon.sync(li_acciones=["TB_STOP", "TB_RESIGN"])
    assert btn.isChecked() is False, (
        "T-RIB-05: sync() should set checked=False when toggle_get returns False"
    )
