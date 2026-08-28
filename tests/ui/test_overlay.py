"""
UI integration tests for the Caissa theme overlay system.

All tests require the app to be running and the Caissa theme active.
Run with: pytest tests/ui/test_overlay.py -v

Each test:
1. Switches to the Caissa theme (via config_theme fixture)
2. Opens the General Configuration dialog
3. Asserts on what is / isn't visible
4. Closes the dialog
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
# T-OVL-01  label rename: Mode → Theme
# ---------------------------------------------------------------------------

def test_ovl_01_mode_renamed_to_theme(client, config_theme):
    """T-OVL-01: In Caissa theme, the 'Mode' label is renamed to 'Theme'."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_dialog_field("Theme")
        client.assert_dialog_field_absent("Mode")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-02  label rename: UI mode → Mode
# ---------------------------------------------------------------------------

def test_ovl_02_ui_mode_renamed_to_mode(client, config_theme):
    """T-OVL-02: In Caissa theme, the 'UI mode' label is renamed to 'Mode'."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_dialog_field("Mode")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-03  field hidden: Window style
# ---------------------------------------------------------------------------

def test_ovl_03_window_style_hidden(client, config_theme):
    """T-OVL-03: In Caissa theme, the 'Window style' field is hidden."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_dialog_field_absent("Window style")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-04  field hidden: Menu Play
# ---------------------------------------------------------------------------

def test_ovl_04_menu_play_hidden(client, config_theme):
    """T-OVL-04: In Caissa theme, the 'Menu Play' field is hidden."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_dialog_field_absent("Menu Play")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-05  field hidden: Preventing system crashes when playing
# ---------------------------------------------------------------------------

def test_ovl_05_prevention_crashes_hidden(client, config_theme):
    """T-OVL-05: In Caissa theme, the 'Preventing system crashes' field is hidden."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_dialog_field_absent("Preventing system crashes")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-06  tab rename: Boards 1 → Pieces
# ---------------------------------------------------------------------------

def test_ovl_06_boards1_renamed_to_pieces(client, config_theme):
    """T-OVL-06: In Caissa theme, 'Boards 1' tab is renamed to 'Pieces'."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_tab_exists("Pieces")
        client.assert_tab_absent("Boards 1")
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-07  tab rename suite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("old_label,new_label", [
    ("Boards 2",     "Board"),
    ("Appearance 1", "Layout"),
    ("Appearance 2", "Colours"),
    ("Change elos",  "Rating"),
])
def test_ovl_07_tab_renames(client, config_theme, old_label, new_label):
    """T-OVL-07: In Caissa theme, tab labels are renamed per the overlay JSON."""
    config_theme("Caissa")
    _open_config(client)
    try:
        client.assert_tab_exists(new_label)
        client.assert_tab_absent(old_label)
    finally:
        _close_config(client)


# ---------------------------------------------------------------------------
# T-OVL-08  values survive round-trip
# ---------------------------------------------------------------------------

def test_ovl_08_player_name_round_trip(client, config_theme):
    """T-OVL-08: Changing the player name in Caissa theme and accepting saves it."""
    config_theme("Caissa")

    # Read current name
    info_before = client.info()

    _open_config(client)
    try:
        # Set player name to a known value via set_field (Player's name field)
        test_name = "CaissaTestPlayer"
        client.set_field("Player", test_name)
        client.dialog_accept()
        time.sleep(0.5)  # allow config to be saved
    except Exception:
        _close_config(client)
        raise

    # Verify by opening the dialog again and reading the field value
    _open_config(client)
    try:
        dlg = client.dialog_info()
        player_widget = next(
            (w for w in dlg.get("widgets", [])
             if w.get("class") == "QLineEdit" and test_name in (w.get("value", "") or "")),
            None
        )
        assert player_widget is not None, (
            f"Expected player name {test_name!r} in QLineEdit after round-trip, "
            f"but did not find it in dialog widgets."
        )
    finally:
        _close_config(client)
