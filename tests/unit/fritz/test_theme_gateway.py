"""
tests/unit/fritz/test_theme_gateway.py — unit tests for ThemeGateway.

Uses a fake ``Code.dic_colors`` dict injected via monkeypatching so no
app initialisation is required.

:spec: §5.3, Phase 1 (feature_spec.md)
"""

from __future__ import annotations

import sys
import types

import pytest
from Code.Fritz import ThemeGateway

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — inject a fake Code module so the adapter can import it
# ---------------------------------------------------------------------------

def _make_fake_code(dic_colors: dict) -> types.ModuleType:
    """Return a minimal fake ``Code`` module with *dic_colors*."""
    fake = types.ModuleType("Code")
    fake.dic_colors = dic_colors

    class _FakeCfg:
        x_style_mode = "Modern Fritz"

    fake.configuration = _FakeCfg()
    return fake


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_color_returns_value_from_dic_colors(monkeypatch):
    """color() delegates to Code.dic_colors and returns the mapped hex."""
    fake = _make_fake_code({"CHROME_ACCENT": "#0078d4", "IS_DARK": "1"})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.color("CHROME_ACCENT") == "#0078d4"


def test_color_returns_fallback_for_missing_key(monkeypatch):
    """color() returns the fallback when the key is absent."""
    fake = _make_fake_code({})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.color("NONEXISTENT_KEY", "#abcdef") == "#abcdef"


def test_color_returns_default_fallback_for_missing_key(monkeypatch):
    """color() returns '#000000' when no fallback is supplied."""
    fake = _make_fake_code({})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.color("NONEXISTENT_KEY") == "#000000"


def test_is_dark_true_when_is_dark_equals_1(monkeypatch):
    """is_dark() returns True when IS_DARK=1 in dic_colors."""
    fake = _make_fake_code({"IS_DARK": "1"})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.is_dark() is True


def test_is_dark_false_when_is_dark_equals_0(monkeypatch):
    """is_dark() returns False when IS_DARK=0 in dic_colors."""
    fake = _make_fake_code({"IS_DARK": "0"})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.is_dark() is False


def test_is_dark_false_when_key_absent(monkeypatch):
    """is_dark() returns False when IS_DARK is not in dic_colors."""
    fake = _make_fake_code({})
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.is_dark() is False


def test_invalidate_clears_cache():
    """invalidate() empties the NAG hex cache so the next call re-reads."""
    ThemeGateway._nag_hex_cache[99] = "#112233"
    ThemeGateway.invalidate()
    assert 99 not in ThemeGateway._nag_hex_cache


def test_active_style_returns_configuration_value(monkeypatch):
    """active_style() returns the x_style_mode from Code.configuration."""
    fake = _make_fake_code({})
    fake.configuration.x_style_mode = "Modern Fritz"
    monkeypatch.setitem(sys.modules, "Code", fake)
    assert ThemeGateway.active_style() == "Modern Fritz"


def test_active_style_returns_empty_string_on_exception(monkeypatch):
    """active_style() returns '' when Code raises on attribute access."""
    fake = types.ModuleType("Code")
    # No configuration attribute at all
    monkeypatch.setitem(sys.modules, "Code", fake)
    result = ThemeGateway.active_style()
    assert isinstance(result, str)


def test_nag_color_returns_hex_from_cache():
    """nag_color() returns the cached value on repeated calls."""
    ThemeGateway.invalidate()
    ThemeGateway._nag_hex_cache[42] = "#aabbcc"
    result = ThemeGateway.nag_color(42)
    assert result == "#aabbcc"
    # Clean up
    ThemeGateway.invalidate()


def test_nag_color_returns_fallback_on_exception(monkeypatch):
    """nag_color() returns '#ffffff' when Code.Nags is unavailable."""
    ThemeGateway.invalidate()

    import builtins
    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if "Nags" in name:
            raise ImportError("no Nags")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    result = ThemeGateway.nag_color(999)
    assert result == "#ffffff"
    ThemeGateway.invalidate()


def test_invalidate_also_resets_nags_xdic_colors(monkeypatch):
    """invalidate() resets Nags.xdic_colors when the module is importable."""
    import types as _types

    fake_nags_mod = _types.ModuleType("Code.Nags.Nags")
    fake_nags_mod.xdic_colors = {"some_key": "#000"}

    fake_nags_pkg = _types.ModuleType("Code.Nags")

    monkeypatch.setitem(sys.modules, "Code.Nags", fake_nags_pkg)
    monkeypatch.setitem(sys.modules, "Code.Nags.Nags", fake_nags_mod)

    ThemeGateway._nag_hex_cache[1] = "#ff0000"
    ThemeGateway.invalidate()

    assert 1 not in ThemeGateway._nag_hex_cache
    assert fake_nags_mod.xdic_colors == {}
