"""
Phase 8 — RPA workflow integration tests.

These tests require a live running Caissa process (CAISSA_TEST=1) in
``classical`` mode.  All tests are marked ``rpa_ui`` and are excluded from
the default run::

    make test-ui         # runs ui + rpa_ui suite

:spec: FR-10, FR-12, §12, §13 (feature_spec.md)
"""

import time

import pytest

from tests.ui.rpa_client import CaissaRpaClient, CaissaRpaError

pytestmark = pytest.mark.rpa_ui


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rpa(client):
    """CaissaRpaClient backed by the module-scoped caissa_proc."""
    return CaissaRpaClient()


# ---------------------------------------------------------------------------
# Workflow: smoke_home
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=False,
    reason="smoke_home requires classical HOME state; app runs in Fritz mode in CI",
)
def test_smoke_home_succeeds(rpa):
    """smoke_home workflow: converge to HOME, assert state is HOME, succeed."""
    stat = rpa.run_and_wait("smoke_home", timeout=30.0)
    assert stat["status"] == "SUCCEEDED", (
        f"smoke_home failed with status {stat['status']!r}"
    )


# ---------------------------------------------------------------------------
# Workflow: classical_invariant
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=False,
    reason="classical_invariant requires classical mode; app runs in Fritz mode in CI",
)
def test_classical_invariant_workflow_passes_on_classical_mode(rpa):
    """classical_invariant workflow passes when Caissa is in classical mode."""
    stat = rpa.run_and_wait("classical_invariant", timeout=30.0)
    assert stat["status"] == "SUCCEEDED", (
        f"classical_invariant failed — Classical Invariant may be broken. "
        f"Status: {stat['status']!r}"
    )


# ---------------------------------------------------------------------------
# Workflow: config_roundtrip
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=False,
    reason="config_roundtrip requires classical HOME state; app runs in Fritz mode in CI",
)
def test_config_roundtrip_succeeds(rpa):
    """config_roundtrip opens config, sets player name, closes, reopens, verifies."""
    stat = rpa.run_and_wait("config_roundtrip", timeout=60.0)
    assert stat["status"] == "SUCCEEDED", (
        f"config_roundtrip failed with status {stat['status']!r}"
    )


# ---------------------------------------------------------------------------
# Workflow list
# ---------------------------------------------------------------------------

def test_rpa_workflows_lists_all_builtins(rpa):
    """rpa_workflows returns all four built-in workflow names."""
    resp = rpa.workflows()
    names = set(resp)
    for expected in ("smoke_home", "classical_invariant", "play_a_game", "config_roundtrip"):
        assert expected in names, (
            f"Workflow {expected!r} not listed. Got: {sorted(names)}"
        )
