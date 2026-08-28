"""
tests/unit/fritz/test_mode_gateway.py — Unit tests for ``Code.Fritz.ModeGateway``.

Tests:

- ``test_load_modes_parses_once_across_100_calls``  cache hit across 100 calls
- ``test_invalidate_forces_exactly_one_reparse``    ``invalidate()`` forces a re-read

:spec: §5.4 (feature_spec.md)
"""

from __future__ import annotations

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
