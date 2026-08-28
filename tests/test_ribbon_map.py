"""
tests/test_ribbon_map.py — Ribbon content map validation tests (T-RMAP-01..08).

xfail stubs until Phase 7 (feat/fritz-ribbon).

:spec: Phase 7 (feature_spec.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_PHASE7 = "Requires Phase 7 (feat/fritz-ribbon)"


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_all_ribbon_jsons_valid_schema():
    """T-RMAP-01: Every Resources/Ribbons/*.json is valid with $schema_version == 1."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_unique_tab_and_group_ids():
    """T-RMAP-02: All tab and group IDs within a ribbon JSON are unique."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_no_duplicate_slot_keys():
    """T-RMAP-03: No key appears more than once across slots + quick_access."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_all_keys_resolve_in_constantes():
    """T-RMAP-04: Every slot key resolves to a TB_* name in Constantes or matches ^caissa:[a-z_]+$."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_all_fritz_toolbar_keys_in_slot_or_quick_access():
    """T-RMAP-05: Every key in modern-fritz.json's toolbar allowlist appears in some slot or quick_access."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_never_filter_keys_in_quick_access():
    """T-RMAP-06: All NEVER_FILTER_TOOLBAR members appear in quick_access."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_no_non_fritz_mode_has_ribbon_key():
    """T-RMAP-07: None of the six non-Fritz mode JSONs contains a ribbon key."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason=_PHASE7)
def test_no_ribbon_json_in_modes_directory():
    """T-RMAP-08: Resources/Modes/ contains no *.ribbon.json files."""
    pytest.fail("not yet implemented")
