"""
tests/unit/fritz/test_mode_gateway.py — Unit tests for ``Code.Fritz.ModeGateway``.

Tests:

- ``test_load_modes_parses_once_across_100_calls``  cache hit across 100 calls
- ``test_invalidate_forces_exactly_one_reparse``    ``invalidate()`` forces a re-read
- ``test_active_returns_matching_mode``             active() finds exact-match mode
- ``test_active_case_insensitive_fallback``         active() tries case-insensitive lookup
- ``test_active_fallback_to_classical``             active() returns classical stub when unknown
- ``test_layout_returns_sub_dict``                  layout() returns the layout block
- ``test_layout_returns_empty_for_null``            layout() returns {} when layout is null
- ``test_layout_returns_empty_when_absent``         layout() returns {} when key missing
- ``test_ribbon_name_returns_value``                ribbon_name() returns the ribbon key
- ``test_ribbon_name_returns_none_when_absent``     ribbon_name() returns None when key absent
- ``test_hook_module_name_with_explicit_hook``      hook_module_name() uses explicit hook key
- ``test_hook_module_name_derived_from_name``       hook_module_name() derives from mode name
- ``test_load_handles_missing_folder``              _load() handles non-existent Modes dir
- ``test_load_skips_broken_json``                   _load() skips files with parse errors

:spec: §5.4 (feature_spec.md)
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_load_modes_parses_once_across_100_calls():
    """ModeGateway.modes() must hit disk exactly once across 100 calls.

    :spec: §5.4
    """
    from Code.Fritz import ModeGateway

    ModeGateway.invalidate()

    call_count = 0
    original_load = ModeGateway._load

    def counting_load() -> dict:
        nonlocal call_count
        call_count += 1
        return original_load()

    ModeGateway._load = counting_load
    try:
        for _ in range(100):
            ModeGateway.modes()
        assert call_count == 1, (
            f"test_load_modes_parses_once_across_100_calls FAIL: "
            f"_load() called {call_count} times across 100 modes() calls (expected 1)"
        )
    finally:
        ModeGateway._load = original_load
        ModeGateway.invalidate()


def test_invalidate_forces_exactly_one_reparse():
    """ModeGateway.invalidate() must cause exactly one re-read on the next modes() call.

    :spec: §5.4
    """
    from Code.Fritz import ModeGateway

    ModeGateway.invalidate()

    call_count = 0
    original_load = ModeGateway._load

    def counting_load() -> dict:
        nonlocal call_count
        call_count += 1
        return original_load()

    ModeGateway._load = counting_load
    try:
        ModeGateway.modes()           # populates cache (call 1)
        ModeGateway.invalidate()      # clears cache
        ModeGateway.modes()           # re-reads (call 2)
        ModeGateway.modes()           # still cached (no new call)

        assert call_count == 2, (
            f"test_invalidate_forces_exactly_one_reparse FAIL: "
            f"_load() called {call_count} times (expected exactly 2)"
        )
    finally:
        ModeGateway._load = original_load
        ModeGateway.invalidate()


# ---------------------------------------------------------------------------
# active() / layout() / ribbon_name() / hook_module_name() — coverage tests
# ---------------------------------------------------------------------------

def test_active_returns_matching_mode(monkeypatch):
    """active() returns the mode dict when x_ui_mode matches exactly."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "Modern Fritz"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        result = MG.active()
        assert result is mode
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_active_case_insensitive_fallback(monkeypatch):
    """active() falls through to a case-insensitive scan when exact match fails."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "modern fritz"   # lowercase — no exact match

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        result = MG.active()
        assert result is mode
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_active_fallback_to_classical(monkeypatch):
    """active() returns a minimal classical stub when mode is completely unknown."""
    import Code
    import Code.Fritz.ModeGateway as MG

    monkeypatch.setattr(MG, "_cache", {})

    class _Cfg:
        x_ui_mode = "completely_unknown_mode"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        result = MG.active()
        assert result["name"] == "classical"
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_layout_returns_sub_dict(monkeypatch):
    """layout() returns the layout block from the active mode."""
    import Code
    import Code.Fritz.ModeGateway as MG

    layout_block = {"fit_board_to_window": True, "default_size": [1280, 860]}
    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None, "layout": layout_block}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "Modern Fritz"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        result = MG.layout()
        assert result is layout_block
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_layout_returns_empty_for_null(monkeypatch):
    """layout() returns {} when the active mode has layout=null."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None, "layout": None}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "Modern Fritz"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        assert MG.layout() == {}
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_layout_returns_empty_when_absent(monkeypatch):
    """layout() returns {} when the active mode has no layout key."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "Modern Fritz"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        assert MG.layout() == {}
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_ribbon_name_returns_value(monkeypatch):
    """ribbon_name() returns the ribbon key from the active mode."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz", "toolbar": [], "menu_keys": None, "ribbon": "modern-fritz"}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})

    class _Cfg:
        x_ui_mode = "Modern Fritz"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        assert MG.ribbon_name() == "modern-fritz"
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_ribbon_name_returns_none_when_absent(monkeypatch):
    """ribbon_name() returns None when the active mode has no ribbon key."""
    import Code
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "classical", "toolbar": None, "menu_keys": None}
    monkeypatch.setattr(MG, "_cache", {"classical": mode})

    class _Cfg:
        x_ui_mode = "classical"

    original = getattr(Code, "configuration", None)
    Code.configuration = _Cfg()
    try:
        assert MG.ribbon_name() is None
    finally:
        if original is None:
            del Code.configuration
        else:
            Code.configuration = original
    MG.invalidate()


def test_hook_module_name_with_explicit_hook(monkeypatch):
    """hook_module_name() uses the explicit 'hook' key when present."""
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz Dark", "hook": "modern_fritz"}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz Dark": mode})
    result = MG.hook_module_name("Modern Fritz Dark")
    assert result == "Code.UIModes.actions.modern_fritz_ui"
    MG.invalidate()


def test_hook_module_name_derived_from_name(monkeypatch):
    """hook_module_name() derives the module path from the mode name when no hook key."""
    import Code.Fritz.ModeGateway as MG

    mode = {"name": "Modern Fritz"}
    monkeypatch.setattr(MG, "_cache", {"Modern Fritz": mode})
    result = MG.hook_module_name("Modern Fritz")
    assert result == "Code.UIModes.actions.modern_fritz_ui"
    MG.invalidate()


def test_load_handles_missing_folder(tmp_path):
    """_load() logs a warning and returns {} when the Modes directory is missing."""
    import Code
    import Code.Fritz.ModeGateway as MG

    nonexistent = str(tmp_path / "NoSuchDir")
    original_path_resource = Code.path_resource
    Code.path_resource = lambda *_a: nonexistent
    MG.invalidate()
    try:
        result = MG._load()
        assert result == {}
    finally:
        Code.path_resource = original_path_resource
        MG.invalidate()


def test_load_skips_broken_json(tmp_path):
    """_load() skips files that contain invalid JSON (logs warning, continues)."""
    import Code
    import Code.Fritz.ModeGateway as MG

    modes_dir = tmp_path / "Modes"
    modes_dir.mkdir()
    (modes_dir / "broken.json").write_text("{not json", encoding="utf-8")
    (modes_dir / "good.json").write_text(
        json.dumps({"name": "TestMode", "toolbar": [], "menu_keys": None}),
        encoding="utf-8",
    )

    original_path_resource = Code.path_resource
    Code.path_resource = lambda *_a: str(modes_dir)
    MG.invalidate()
    try:
        result = MG._load()
        assert "TestMode" in result
    finally:
        Code.path_resource = original_path_resource
        MG.invalidate()
