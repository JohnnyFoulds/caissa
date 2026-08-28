"""
tests/unit/fritz/test_pane_registry.py — Unit tests for ``Code.Fritz.PaneRegistry``.

Test IDs: T-PREG-01..06
:spec: §5.3, Phase 3 (feature_spec.md)
"""

from __future__ import annotations

import pytest

from Code.Fritz.Errors import PaneNotRegisteredError
from Code.Fritz.PaneRegistry import PaneRegistry
from Code.Fritz.Types import PaneSpec

pytestmark = pytest.mark.unit

_SPEC = PaneSpec(key="eval_graph", label="Eval profile", default_px=80, min_px=24)
_SPEC_B = PaneSpec(key="pgn", label="Notation", default_px=220, min_px=40)


def _reg(*specs: PaneSpec) -> PaneRegistry:
    r = PaneRegistry()
    for s in specs:
        r.register(s)
    return r


def test_restore_px_returns_default_from_zero():
    """T-PREG-01: restore_px(key, 0) returns default_px."""
    reg = _reg(_SPEC)
    result = reg.restore_px(_SPEC.key, 0)
    assert result == _SPEC.default_px, (
        f"T-PREG-01 FAIL: expected {_SPEC.default_px}, got {result}"
    )


def test_restore_px_returns_current_when_nonzero():
    """T-PREG-02: restore_px returns current_px when it is already >= min_px."""
    reg = _reg(_SPEC)
    current = 150
    assert current >= _SPEC.min_px
    result = reg.restore_px(_SPEC.key, current)
    assert result == current, (
        f"T-PREG-02 FAIL: expected {current}, got {result}"
    )


def test_restore_px_floors_at_min_px():
    """T-PREG-03: restore_px floors at min_px when current_px is positive but too small."""
    reg = _reg(_SPEC)
    current = 5
    assert current < _SPEC.min_px
    result = reg.restore_px(_SPEC.key, current)
    assert result == _SPEC.min_px, (
        f"T-PREG-03 FAIL: expected {_SPEC.min_px}, got {result}"
    )


def test_unknown_key_raises_pane_not_registered_error():
    """T-PREG-04: spec() and restore_px() raise PaneNotRegisteredError for unknown keys."""
    reg = _reg(_SPEC)
    with pytest.raises(PaneNotRegisteredError):
        reg.spec("does_not_exist")
    with pytest.raises(PaneNotRegisteredError):
        reg.restore_px("does_not_exist", 0)


def test_names_preserves_registration_order():
    """T-PREG-05: names() returns keys in the order they were registered."""
    reg = _reg(_SPEC, _SPEC_B)
    assert reg.names() == [_SPEC.key, _SPEC_B.key], (
        f"T-PREG-05 FAIL: expected {[_SPEC.key, _SPEC_B.key]}, got {reg.names()}"
    )


def test_register_same_key_twice_replaces_not_duplicates():
    """T-PREG-06: registering the same key twice replaces the entry, no duplicates."""
    updated = PaneSpec(key=_SPEC.key, label="Updated", default_px=100, min_px=30)
    reg = _reg(_SPEC)
    reg.register(updated)
    assert reg.names() == [_SPEC.key], (
        f"T-PREG-06 FAIL: names() should have one entry, got {reg.names()}"
    )
    assert reg.spec(_SPEC.key).label == "Updated", (
        f"T-PREG-06 FAIL: spec should reflect updated label"
    )
