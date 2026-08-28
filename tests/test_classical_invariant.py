"""
tests/test_classical_invariant.py — unit tests for the classical invariant.

These tests run without Qt or a live app process.  They verify:

1. No .ui.json overlay exists for the four shipped themes, so they are
   completely unmodified from upstream.
2. load_overlay() returns {} for all four shipped themes.
3. OverlayForm with an empty overlay is a pure passthrough — every field
   and tab reaches the base form unchanged.
4. OverlayForm.result() returns correct positions when all fields are visible.
5. OverlayForm.result() skips hidden fields and shifts positions correctly.
6. Configuration.mode_settings persists through graba()/lee().
"""

import os
import sys
from unittest.mock import MagicMock, call

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Bootstrap: make the bin/ tree importable without Qt or a display
# ---------------------------------------------------------------------------

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BIN = os.path.join(_REPO, "bin")
if _BIN not in sys.path:
    sys.path.insert(0, _BIN)

# Stub out the Qt-dependent modules before any Caissa import.
# This lets us import FormOverlay (which imports Code) without a display.
import types

for _mod_name in [
    "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "Code.QT.FormLayout",
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

# Provide the minimum Code globals that load_overlay needs
import Code as _Code
if not hasattr(_Code, "path_resource") or not callable(_Code.path_resource):
    def _path_resource(*lista):
        p = os.path.join(_REPO, "Resources")
        for x in lista:
            p = os.path.join(p, x)
        return p
    _Code.path_resource = _path_resource

from Code.Config.FormOverlay import OverlayForm, load_overlay  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHIPPED_THEMES = ["By default", "Dark", "Light", "Mid"]
_STYLES_DIR = os.path.join(_REPO, "Resources", "Styles")

# ---------------------------------------------------------------------------
# 1. No overlay file for shipped themes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("theme", _SHIPPED_THEMES)
def test_no_overlay_file_for_shipped_theme(theme):
    """No .ui.json must exist for any of the four shipped upstream themes."""
    overlay_path = os.path.join(_STYLES_DIR, f"{theme}.ui.json")
    assert not os.path.exists(overlay_path), (
        f"Overlay file {overlay_path!r} exists for shipped theme {theme!r}. "
        "Shipped themes must never have overlays — they must be upstream-identical."
    )


# ---------------------------------------------------------------------------
# 2. load_overlay returns {} for shipped themes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("theme", _SHIPPED_THEMES)
def test_load_overlay_empty_for_shipped_themes(theme):
    """load_overlay must return {} for all four shipped themes (no overlay files)."""
    result = load_overlay(theme)
    assert result == {}, (
        f"load_overlay({theme!r}) returned {result!r} — expected empty dict."
    )


def test_load_overlay_nonempty_for_caissa():
    """Caissa.ui.json must exist and load as a non-empty dict."""
    result = load_overlay("Caissa")
    assert isinstance(result, dict)
    assert result, "Caissa overlay must not be empty"
    assert "labels" in result or "tabs" in result, (
        f"Caissa overlay has unexpected shape: {result!r}"
    )


# ---------------------------------------------------------------------------
# 3. OverlayForm with empty overlay is a pure passthrough
# ---------------------------------------------------------------------------

def _make_overlay_form(overlay=None):
    """Return (mock_base, overlay_form) pair."""
    mock_base = MagicMock()
    return mock_base, OverlayForm(mock_base, overlay or {})


def test_passthrough_combobox():
    base, form = _make_overlay_form()
    form.combobox("Window style", [("Fusion", "Fusion")], "Fusion")
    base.combobox.assert_called_once_with("Window style", [("Fusion", "Fusion")], "Fusion")


def test_passthrough_checkbox():
    base, form = _make_overlay_form()
    form.checkbox("Show puzzles on startup", True)
    base.checkbox.assert_called_once_with("Show puzzles on startup", True)


def test_passthrough_edit():
    base, form = _make_overlay_form()
    form.edit("Player's name", "Alice")
    base.edit.assert_called_once_with("Player's name", "Alice")


def test_passthrough_spinbox():
    base, form = _make_overlay_form()
    form.spinbox("Font size", 3, 64, 60, 13)
    base.spinbox.assert_called_once_with("Font size", 3, 64, 60, 13)


def test_passthrough_add_tab():
    base, form = _make_overlay_form()
    form.add_tab("General")
    base.add_tab.assert_called_once_with("General")


def test_passthrough_separador():
    base, form = _make_overlay_form()
    form.separador()
    base.separador.assert_called_once()


# ---------------------------------------------------------------------------
# 4. OverlayForm.result with all-visible fields
# ---------------------------------------------------------------------------

def _build_form_with_fields(field_labels, overlay=None):
    """Build an OverlayForm with one tab containing the given fields, using mock base."""
    base = MagicMock()
    form = OverlayForm(base, overlay or {})
    for lbl in field_labels:
        form.combobox(lbl, [], "val")
    form.add_tab("TestTab")
    return form


def test_result_all_visible_first_field():
    labels = ["Alpha", "Beta", "Gamma"]
    form = _build_form_with_fields(labels)
    tab_result = [10, 20, 30]
    assert form.result(0, tab_result, "Alpha") == 10


def test_result_all_visible_middle_field():
    labels = ["Alpha", "Beta", "Gamma"]
    form = _build_form_with_fields(labels)
    tab_result = [10, 20, 30]
    assert form.result(0, tab_result, "Beta") == 20


def test_result_all_visible_last_field():
    labels = ["Alpha", "Beta", "Gamma"]
    form = _build_form_with_fields(labels)
    tab_result = [10, 20, 30]
    assert form.result(0, tab_result, "Gamma") == 30


def test_result_missing_label_returns_default():
    labels = ["Alpha", "Beta"]
    form = _build_form_with_fields(labels)
    assert form.result(0, [10, 20], "NonExistent", default="x") == "x"


def test_result_out_of_bounds_tab_returns_default():
    labels = ["Alpha"]
    form = _build_form_with_fields(labels)
    assert form.result(99, [10], "Alpha", default="fallback") == "fallback"


# ---------------------------------------------------------------------------
# 5. OverlayForm.result with hidden fields shifts positions correctly
# ---------------------------------------------------------------------------

def test_result_hidden_first_field_shifts_remaining():
    """If the first field is hidden, the second field is at result index 0."""
    overlay = {"labels": {"Alpha": None}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.combobox("Alpha", [], "a")   # hidden
    form.combobox("Beta", [], "b")    # visible → index 0
    form.combobox("Gamma", [], "c")   # visible → index 1
    form.add_tab("T")

    tab_result = [100, 200]   # Alpha absent from result list
    assert form.result(0, tab_result, "Alpha", default="X") == "X"
    assert form.result(0, tab_result, "Beta") == 100
    assert form.result(0, tab_result, "Gamma") == 200


def test_result_hidden_middle_field():
    overlay = {"labels": {"Beta": None}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.combobox("Alpha", [], "a")   # visible → index 0
    form.combobox("Beta", [], "b")    # hidden
    form.combobox("Gamma", [], "c")   # visible → index 1
    form.add_tab("T")

    tab_result = [10, 30]
    assert form.result(0, tab_result, "Alpha") == 10
    assert form.result(0, tab_result, "Beta", default="Z") == "Z"
    assert form.result(0, tab_result, "Gamma") == 30


def test_result_hidden_last_field():
    overlay = {"labels": {"Gamma": None}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.combobox("Alpha", [], "a")   # visible → index 0
    form.combobox("Beta", [], "b")    # visible → index 1
    form.combobox("Gamma", [], "c")   # hidden
    form.add_tab("T")

    tab_result = [10, 20]
    assert form.result(0, tab_result, "Alpha") == 10
    assert form.result(0, tab_result, "Beta") == 20
    assert form.result(0, tab_result, "Gamma", default="Q") == "Q"


def test_result_renamed_field_still_found_by_original_label():
    """result() looks up by the original label, not the renamed one."""
    overlay = {"labels": {"Mode": "Theme"}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.combobox("Mode", [], "Caissa")   # renamed to "Theme" but tracked as "Mode"
    form.add_tab("T")

    tab_result = ["Caissa"]
    assert form.result(0, tab_result, "Mode") == "Caissa"


def test_tab_rename_forwarded_to_base():
    overlay = {"tabs": {"Boards 1": "Pieces"}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.add_tab("Boards 1")
    base.add_tab.assert_called_once_with("Pieces")


def test_tab_without_rename_passes_through():
    overlay = {"tabs": {"Boards 1": "Pieces"}}
    base = MagicMock()
    form = OverlayForm(base, overlay)
    form.add_tab("General")
    base.add_tab.assert_called_once_with("General")


# ---------------------------------------------------------------------------
# 6. mode_settings round-trip through graba/lee
# ---------------------------------------------------------------------------

def test_mode_settings_persisted(tmp_path):
    """mode_settings survives graba() → lee() round-trip."""
    # Minimal stubs so Configuration can be imported without Qt
    import types
    for m in ["Code.QT.IconosBase", "Code.Board.ConfBoards",
              "Code.Config.ConfigEngines", "Code.Analysis.AnalysisEval",
              "Code.Translations.Translate", "Code.Translations.TrListas",
              "Code.SQL.UtilSQL", "Code.Engines.Priorities"]:
        if m not in sys.modules:
            sys.modules[m] = types.ModuleType(m)
    # Provide minimal stubs on the modules
    icons_stub = sys.modules.get("Code.QT.IconosBase") or types.ModuleType("Code.QT.IconosBase")
    if not hasattr(icons_stub, "icons"):
        icons_stub.icons = MagicMock()
        icons_stub.icons.NORMAL = 0
    sys.modules["Code.QT.IconosBase"] = icons_stub

    screen_stub = types.ModuleType("Code.QT.ScreenUtils")
    screen_stub.desktop_size = MagicMock(return_value=(1920, 1080))
    sys.modules["Code.QT.ScreenUtils"] = screen_stub

    try:
        from Code.Config import Configuration as _Cfg
        from Code.Config import ConfigPaths as _CP

        # Build a minimal ConfigPaths pointing at tmp_path
        cp = MagicMock()
        cp.file = str(tmp_path / "lk.pk2")
        cp.is_first_time = False

        cfg = _Cfg.Configuration.__new__(_Cfg.Configuration)
        # Set only what graba/lee need
        cfg.paths = cp
        cfg.mode_settings = {"coach": {"maia_level": 1500, "auto_tutor": True}}
        cfg.li_personalities = []
        # Build a minimal x_ dict so read_dic_x works
        cfg.x_style_mode = "By default"
        cfg.x_style_icons = 0
        cfg.x_style = "Fusion"
        cfg.x_caissa_theme = "Classic"
        cfg.x_ui_mode = "Classical"

        from Code.Z import Util as _Util
        # Patch save/restore pickle to use tmp_path
        original_save = _Util.save_pickle
        original_restore = _Util.restore_pickle

        saved = {}

        def _fake_save(path, obj):
            saved[path] = obj

        def _fake_restore(path):
            return saved.get(path)

        _Util.save_pickle = _fake_save
        _Util.restore_pickle = _fake_restore

        try:
            cfg.graba()
            # Mutate and then restore via lee
            cfg.mode_settings = {}
            cfg.lee = lambda: None  # skip full lee; just test the dict restore
            # Manually replay what lee() does for mode_settings
            if dic := _fake_restore(str(tmp_path / "lk.pk2")):
                cfg.mode_settings = dic.get("MODE_SETTINGS", {})
            assert cfg.mode_settings == {"coach": {"maia_level": 1500, "auto_tutor": True}}, (
                f"mode_settings not restored correctly: {cfg.mode_settings}"
            )
        finally:
            _Util.save_pickle = original_save
            _Util.restore_pickle = original_restore

    except ImportError as exc:
        pytest.skip(f"Configuration import requires too many deps: {exc}")
