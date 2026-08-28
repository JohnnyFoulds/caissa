"""
UI integration tests for the classical invariant.

When the app runs with the 'By default' theme (no overlay), the Configuration
dialog must show all original labels and all original tab names exactly as
upstream Lucas Chess R6.

T-CLS-01: All original General-tab labels are present.
T-CLS-02: All original tab names are present.

Run with: pytest tests/ui/test_classical.py -v
"""

import time

import pytest

pytestmark = pytest.mark.ui


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_config(client):
    """Open the General Configuration dialog and wait for it to appear."""
    client.send("open_config")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            info = client.dialog_info()
            if "General configuration" in info.get("title", "") or info.get("widgets"):
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError("General Configuration dialog did not appear within 5s")


def _close_config(client):
    """Cancel the configuration dialog if open."""
    try:
        client.dialog_cancel()
        time.sleep(0.3)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# T-CLS-01  All original General-tab labels present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", [
    "Mode",
    "UI mode",
    "Window style",
    "Menu Play",
    "Preventing system crashes when playing",
])
def test_cls_01_original_labels_present(client, config_theme, label):
    """T-CLS-01: In 'By default' theme, all original labels are present in the dialog."""
    config_theme("By default")
    _open_config(client)
    try:
        client.assert_dialog_field(label)
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-CLS-02  All original tab names present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tab_label", [
    "Boards 1",
    "Boards 2",
    "Appearance 1",
    "Appearance 2",
    "Change elos",
])
def test_cls_02_original_tabs_present(client, config_theme, tab_label):
    """T-CLS-02: In 'By default' theme, all original tab labels are present."""
    config_theme("By default")
    _open_config(client)
    try:
        client.assert_tab_exists(tab_label)
    finally:
        _close_config(client)
