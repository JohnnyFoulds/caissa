"""tests/unit/fritz/test_geometry_store.py — Unit tests for GeometryStore.

:spec: §2.6, Phase 2 (feature_spec.md)
"""

from __future__ import annotations

import sys
import types

import pytest

pytestmark = pytest.mark.unit

from Code.Fritz import GeometryStore


# ---------------------------------------------------------------------------
# Fake Code module
# ---------------------------------------------------------------------------

class _FakeConfig:
    """Minimal fake configuration that stores video dict in-memory."""

    def __init__(self):
        self._videos: dict = {}

    def save_video(self, key: str, dic: dict) -> None:
        self._videos[key] = dict(dic)

    def restore_video(self, key: str) -> dict | None:
        return dict(self._videos[key]) if key in self._videos else None


def _make_fake_code() -> tuple[types.ModuleType, _FakeConfig]:
    fake = types.ModuleType("Code")
    cfg = _FakeConfig()
    fake.configuration = cfg
    return fake, cfg


# ---------------------------------------------------------------------------
# Round-trip: save then load
# ---------------------------------------------------------------------------

def test_save_and_load_window_normal(monkeypatch):
    """save_window + load_window round-trips a normal (non-maximized) window."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    GeometryStore.save_window("fritzd", 100, 200, 1280, 860, maximized=False, fullscreen=False)
    result = GeometryStore.load_window("fritzd")

    assert result is not None
    assert result.get("maximized") is False
    assert result.get("size") == (1280, 860)
    assert result.get("pos") == (100, 200)


def test_save_maximized_stores_token_and_normal_size(monkeypatch):
    """save_window stores _MAXIMIZED_ token and normal geometry when maximized."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    GeometryStore.save_window("fritzd", 0, 0, 1280, 860, maximized=True, fullscreen=False)
    raw = cfg._videos.get("fritzd", {})

    assert raw.get("_SIZE_") == GeometryStore._MAXIMIZED_TOKEN
    assert raw.get("_NORMAL_SIZE_") == "1280,860"


def test_load_maximized_returns_normal_size(monkeypatch):
    """load_window returns maximized=True and normal_size when token is present."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    GeometryStore.save_window("fritzd", 50, 50, 1024, 768, maximized=True, fullscreen=False)
    result = GeometryStore.load_window("fritzd")

    assert result is not None
    assert result.get("maximized") is True
    assert result.get("normal_size") == (1024, 768)
    assert "size" not in result


def test_fullscreen_save_is_noop(monkeypatch):
    """save_window in fullscreen is a no-op — geometry must never be saved."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    GeometryStore.save_window("fritzd", 0, 0, 1920, 1080, maximized=False, fullscreen=True)

    assert "fritzd" not in cfg._videos


def test_load_returns_none_when_nothing_stored(monkeypatch):
    """load_window returns None when no geometry has been saved."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    assert GeometryStore.load_window("fritzd") is None


# ---------------------------------------------------------------------------
# Splitters
# ---------------------------------------------------------------------------

def test_save_and_load_splitters_round_trip(monkeypatch):
    """save_splitters + load_splitters round-trips correctly."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    sizes = {"RightCol": [100, 200, 80, 180], "Main": [600, 420]}
    GeometryStore.save_splitters("fritzd", sizes)
    result = GeometryStore.load_splitters("fritzd")

    assert result == sizes


def test_load_splitters_empty_when_nothing_stored(monkeypatch):
    """load_splitters returns an empty dict when no splitters are stored."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    assert GeometryStore.load_splitters("fritzd") == {}


def test_splitters_do_not_collide_with_window_key(monkeypatch):
    """splitter keys (SP_*) and window keys (_POSICION_ etc.) coexist."""
    fake, cfg = _make_fake_code()
    monkeypatch.setitem(sys.modules, "Code", fake)

    GeometryStore.save_window("fritzd", 10, 20, 1280, 860, maximized=False, fullscreen=False)
    GeometryStore.save_splitters("fritzd", {"RightCol": [300, 100]})

    result_win = GeometryStore.load_window("fritzd")
    result_sp = GeometryStore.load_splitters("fritzd")

    assert result_win is not None
    assert result_win.get("size") == (1280, 860)
    assert result_sp == {"RightCol": [300, 100]}


# ---------------------------------------------------------------------------
# clamp_to_screens (pure function)
# ---------------------------------------------------------------------------

def test_clamp_to_screens_no_adjustment_when_on_screen():
    """clamp_to_screens returns coords unchanged when on a screen."""
    screens = [(0, 0, 1920, 1080)]
    assert GeometryStore.clamp_to_screens(100, 100, 1280, 800, screens) == (100, 100, 1280, 800)


def test_clamp_to_screens_moves_offscreen_window_to_primary():
    """clamp_to_screens moves an off-screen window to the primary screen."""
    screens = [(0, 0, 1920, 1080)]
    # x=2000 is off the only screen
    result = GeometryStore.clamp_to_screens(2000, 100, 1280, 800, screens)
    sx, sy, sw, sh = screens[0]
    rx, ry, rw, rh = result
    assert sx <= rx < sx + sw
    assert sy <= ry < sy + sh
    assert rw == 1280
    assert rh == 800


def test_clamp_to_screens_multi_monitor_stays_on_second():
    """clamp_to_screens leaves the window on the second monitor when it's valid."""
    screens = [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)]
    # top-left on second screen
    result = GeometryStore.clamp_to_screens(2000, 100, 1280, 800, screens)
    assert result == (2000, 100, 1280, 800)


def test_clamp_to_screens_empty_screens_returns_unchanged():
    """clamp_to_screens returns coords unchanged when screens list is empty."""
    assert GeometryStore.clamp_to_screens(100, 100, 800, 600, []) == (100, 100, 800, 600)
