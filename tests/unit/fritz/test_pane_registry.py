"""
tests/unit/fritz/test_pane_registry.py — Unit tests for ``Code.Fritz.PaneRegistry`` (T-PREG-01..04+).

xfail stubs until Phase 3 (feat/fritz-panes).

:spec: §5.3, Phase 3 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE3 = "Requires Phase 3 (feat/fritz-panes)"


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_restore_px_returns_default_from_zero():
    """T-PREG-01: restore_px returns default_px from zero."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_restore_px_returns_current_when_nonzero():
    """T-PREG-02: restore_px returns the current size when already non-zero."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_restore_px_floors_at_min_px():
    """T-PREG-03: restore_px floors at min_px."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE3)
def test_unknown_key_raises_pane_not_registered_error():
    """T-PREG-04: an unregistered key raises PaneNotRegisteredError."""
    pytest.fail("not yet implemented")
