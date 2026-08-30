"""
tests/unit/rpa/test_design_spec.py — unit tests for Vision/DesignSpec.py (Phase 5).

Tests the canonical JSON spec, known-deviation machinery, and stale-deviation guard.

:spec: docs/features/rpa-design-vision/feature_spec.md §9 FR-13
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 — DesignSpec.py not yet written")
def test_ribbon_spec_json_is_canonical_source_of_truth():
    """Resources/Design/ribbon.spec.json must round-trip through DesignSpec.load()
    without loss. Loading then re-serialising must produce byte-identical JSON
    (after normalising key order). If it doesn't, the loader has dropped fields."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 — DesignSpec.py not yet written")
def test_assert_design_spec_known_deviation_warns_not_fails():
    """assert_design_spec with a known deviation (deviation_id registered in the spec)
    must emit a warning, not raise. A known deviation is an acknowledged gap."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 5 — DesignSpec.py not yet written")
def test_deviation_stale_fires_when_deviation_starts_passing():
    """When a previously registered deviation's finding is no longer present,
    assert_design_spec must raise DeviationStale. A stale entry means the workaround
    was fixed without retiring the deviation — the spec is now inconsistent."""
    raise NotImplementedError
