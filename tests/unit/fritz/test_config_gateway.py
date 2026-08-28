"""
tests/unit/fritz/test_config_gateway.py — unit tests for ConfigGateway.

Uses a fake ``Code.configuration`` object injected via monkeypatching so
no app initialisation is required.

:spec: §5.3, Phase 1 (feature_spec.md)
"""

from __future__ import annotations

import sys
import types

import pytest

from Code.Fritz import ConfigGateway

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — inject a fake Code module
# ---------------------------------------------------------------------------

class _FakeConfig:
    x_pgn_width = 400
    x_pgn_withfigurines = True
    x_anchoPieza = 48
    x_ui_mode = "Modern Fritz"
    _saved = False

    def guardaEnDisco(self):
        self._saved = True


def _make_fake_code(cfg: _FakeConfig | None = None) -> types.ModuleType:
    fake = types.ModuleType("Code")
    fake.configuration = cfg or _FakeConfig()
    return fake


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pgn_width_returns_configured_value(monkeypatch):
    """pgn_width() returns x_pgn_width from Code.configuration."""
    cfg = _FakeConfig()
    cfg.x_pgn_width = 320
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.pgn_width() == 320


def test_pgn_width_fallback_when_zero(monkeypatch):
    """pgn_width() returns 400 when x_pgn_width is falsy."""
    cfg = _FakeConfig()
    cfg.x_pgn_width = 0
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.pgn_width() == 400


def test_with_figurines_true(monkeypatch):
    """with_figurines() returns True when x_pgn_withfigurines is truthy."""
    cfg = _FakeConfig()
    cfg.x_pgn_withfigurines = True
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.with_figurines() is True


def test_with_figurines_false(monkeypatch):
    """with_figurines() returns False when x_pgn_withfigurines is falsy."""
    cfg = _FakeConfig()
    cfg.x_pgn_withfigurines = False
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.with_figurines() is False


def test_width_piece_returns_configured_value(monkeypatch):
    """width_piece() returns x_anchoPieza from Code.configuration."""
    cfg = _FakeConfig()
    cfg.x_anchoPieza = 64
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.width_piece() == 64


def test_ui_mode_returns_configured_value(monkeypatch):
    """ui_mode() returns x_ui_mode from Code.configuration."""
    cfg = _FakeConfig()
    cfg.x_ui_mode = "Fritz Dark"
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))
    assert ConfigGateway.ui_mode() == "Fritz Dark"


def test_set_width_piece_without_persist_does_not_call_guardaendisco(monkeypatch):
    """set_width_piece(..., persist=False) never calls guardaEnDisco."""
    cfg = _FakeConfig()
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))

    ConfigGateway.set_width_piece(72, persist=False)

    assert cfg.x_anchoPieza == 72
    assert not cfg._saved, "guardaEnDisco must not be called when persist=False"


def test_set_width_piece_with_persist_calls_guardaendisco(monkeypatch):
    """set_width_piece(..., persist=True) calls guardaEnDisco exactly once."""
    cfg = _FakeConfig()
    monkeypatch.setitem(sys.modules, "Code", _make_fake_code(cfg))

    ConfigGateway.set_width_piece(80, persist=True)

    assert cfg.x_anchoPieza == 80
    assert cfg._saved, "guardaEnDisco must be called when persist=True"
