"""
tests/unit/fritz/test_ribbon_model.py — Unit tests for Code.Fritz.RibbonModel (no Qt).

Test IDs
────────
T-RM-01  test_load_returns_valid_spec            load() parses and validates a good JSON
T-RM-02  test_load_raises_on_missing_file        load() raises RibbonSpecError for missing path
T-RM-03  test_load_raises_on_bad_json            load() raises RibbonSpecError for invalid JSON
T-RM-04  test_load_raises_on_wrong_schema_version load() rejects schema_version != 1
T-RM-05  test_load_raises_on_duplicate_tab_id     _validate() catches duplicate tab ids
T-RM-06  test_load_raises_on_duplicate_group_id   _validate() catches duplicate group ids
T-RM-07  test_load_raises_on_missing_tab_id       _validate() catches tab with no id
T-RM-08  test_load_raises_on_missing_group_id     _validate() catches group with no id
T-RM-09  test_all_slot_keys_deduplicates          all_slot_keys() returns first-seen unique keys
T-RM-10  test_state_enabled_for_active_keys       state() marks present keys as enabled
T-RM-11  test_state_disabled_for_missing_keys     state() marks absent keys as disabled
T-RM-12  test_overflow_returns_uncovered_keys     overflow() returns keys not in any slot
T-RM-13  test_overflow_empty_when_all_covered     overflow() is empty when all keys in spec
T-RM-14  test_best_tab_scores_by_intersection     best_tab() returns tab with most matching keys
T-RM-15  test_best_tab_falls_back_to_default      best_tab() returns default_tab when no match
T-RM-16  test_compact_above_threshold             compact() returns True above threshold
T-RM-17  test_compact_below_threshold             compact() returns False at/below threshold

:spec: Phase 7 (feature_spec.md §2.2, §5)
"""

from __future__ import annotations

import json
import os
import tempfile

import Code.Fritz.RibbonModel as rm
import pytest
from Code.Fritz.Errors import RibbonSpecError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ribbon(data: dict) -> str:
    """Write *data* to a temp JSON file and return the path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(data, fh)
    fh.close()
    return fh.name


_MINIMAL = {
    "$schema_version": 1,
    "default_tab": "home",
    "missing_key_policy": "disable",
    "quick_access": ["TB_CLOSE", "TB_QUIT"],
    "tabs": [
        {
            "id": "home",
            "label": "Home",
            "groups": [
                {
                    "id": "home.game",
                    "label": "Game",
                    "slots": [
                        {"key": "TB_RESIGN", "size": "large"},
                        {"key": "TB_DRAW",   "size": "small"},
                    ],
                }
            ],
        },
        {
            "id": "analysis",
            "label": "Analysis",
            "groups": [
                {
                    "id": "analysis.engine",
                    "label": "Engine",
                    "slots": [
                        {"key": "TB_CONFIG", "size": "small"},
                    ],
                }
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# T-RM-01  load() — happy path
# ---------------------------------------------------------------------------

def test_load_returns_valid_spec():
    """T-RM-01: load() returns the parsed dict for a valid JSON file."""
    path = _write_ribbon(_MINIMAL)
    try:
        spec = rm.load(path)
        assert spec["$schema_version"] == 1
        assert "tabs" in spec
        assert "quick_access" in spec
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-02  load() — missing file
# ---------------------------------------------------------------------------

def test_load_raises_on_missing_file():
    """T-RM-02: load() raises RibbonSpecError when the file does not exist."""
    with pytest.raises(RibbonSpecError, match="not found"):
        rm.load("/tmp/__nonexistent_ribbon__.json")


# ---------------------------------------------------------------------------
# T-RM-03  load() — invalid JSON
# ---------------------------------------------------------------------------

def test_load_raises_on_bad_json():
    """T-RM-03: load() raises RibbonSpecError for malformed JSON."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    fh.write("{not valid json")
    fh.close()
    try:
        with pytest.raises(RibbonSpecError, match="Invalid JSON"):
            rm.load(fh.name)
    finally:
        os.unlink(fh.name)


# ---------------------------------------------------------------------------
# T-RM-04  load() — wrong schema version
# ---------------------------------------------------------------------------

def test_load_raises_on_wrong_schema_version():
    """T-RM-04: load() raises RibbonSpecError when $schema_version != 1."""
    bad = dict(_MINIMAL, **{"$schema_version": 2})
    path = _write_ribbon(bad)
    try:
        with pytest.raises(RibbonSpecError, match="Unsupported"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-05  _validate() — duplicate tab id
# ---------------------------------------------------------------------------

def test_load_raises_on_duplicate_tab_id():
    """T-RM-05: _validate() raises when two tabs share the same id."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {"id": "home", "label": "Home", "groups": []},
            {"id": "home", "label": "Home2", "groups": []},
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="duplicate tab id"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-06  _validate() — duplicate group id
# ---------------------------------------------------------------------------

def test_load_raises_on_duplicate_group_id():
    """T-RM-06: _validate() raises when two groups share the same id."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {"id": "grp1", "label": "G1", "slots": []},
                    {"id": "grp1", "label": "G2", "slots": []},
                ],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="duplicate group id"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-07  _validate() — tab missing id
# ---------------------------------------------------------------------------

def test_load_raises_on_missing_tab_id():
    """T-RM-07: _validate() raises when a tab has no 'id' key."""
    data = {
        "$schema_version": 1,
        "tabs": [{"label": "NoID", "groups": []}],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="tab missing 'id'"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-08  _validate() — group missing id
# ---------------------------------------------------------------------------

def test_load_raises_on_missing_group_id():
    """T-RM-08: _validate() raises when a group has no 'id' key."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [{"label": "NoGroupID", "slots": []}],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="group missing 'id'"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RM-09  all_slot_keys() — deduplication
# ---------------------------------------------------------------------------

def test_all_slot_keys_deduplicates():
    """T-RM-09: all_slot_keys() returns unique keys, preserving first-seen order."""
    keys = rm.all_slot_keys(_MINIMAL)
    # quick_access: TB_CLOSE, TB_QUIT; tabs: TB_RESIGN, TB_DRAW, TB_CONFIG
    assert keys == ["TB_CLOSE", "TB_QUIT", "TB_RESIGN", "TB_DRAW", "TB_CONFIG"]
    # All unique — no repeats
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# T-RM-10  state() — keys in li_acciones are enabled
# ---------------------------------------------------------------------------

def test_state_enabled_for_active_keys():
    """T-RM-10: state() marks a key as enabled when it is in li_acciones."""
    st = rm.state(_MINIMAL, li_acciones=["TB_CLOSE", "TB_RESIGN"])
    vis, enabled, _tab = st["TB_CLOSE"]
    assert vis is True
    assert enabled is True
    vis, enabled, tab = st["TB_RESIGN"]
    assert vis is True
    assert enabled is True
    assert tab == "home"


# ---------------------------------------------------------------------------
# T-RM-11  state() — keys absent from li_acciones are disabled
# ---------------------------------------------------------------------------

def test_state_disabled_for_missing_keys():
    """T-RM-11: missing_key_policy=disable → absent keys are visible but disabled."""
    st = rm.state(_MINIMAL, li_acciones=[])
    for key in ["TB_CLOSE", "TB_QUIT", "TB_RESIGN", "TB_DRAW", "TB_CONFIG"]:
        vis, enabled, _tab = st[key]
        assert vis is True, f"{key} should be visible"
        assert enabled is False, f"{key} should be disabled when absent from li_acciones"


# ---------------------------------------------------------------------------
# T-RM-12  overflow() — uncovered keys returned
# ---------------------------------------------------------------------------

def test_overflow_returns_uncovered_keys():
    """T-RM-12: overflow() returns keys in li_acciones not covered by the spec."""
    extra = "TB_ADVICE"
    result = rm.overflow(_MINIMAL, li_acciones=["TB_RESIGN", extra])
    assert extra in result
    assert "TB_RESIGN" not in result


# ---------------------------------------------------------------------------
# T-RM-13  overflow() — empty when all covered
# ---------------------------------------------------------------------------

def test_overflow_empty_when_all_covered():
    """T-RM-13: overflow() is empty when every li_acciones key appears in the spec."""
    result = rm.overflow(_MINIMAL, li_acciones=["TB_RESIGN", "TB_CLOSE"])
    assert result == []


# ---------------------------------------------------------------------------
# T-RM-14  best_tab() — scores by intersection
# ---------------------------------------------------------------------------

def test_best_tab_scores_by_intersection():
    """T-RM-14: best_tab() returns the tab with the most matching slot keys."""
    # analysis tab has TB_CONFIG; home has TB_RESIGN + TB_DRAW
    tab = rm.best_tab(_MINIMAL, li_acciones=["TB_RESIGN", "TB_DRAW", "TB_CLOSE"])
    assert tab == "home"

    tab = rm.best_tab(_MINIMAL, li_acciones=["TB_CONFIG"])
    assert tab == "analysis"


# ---------------------------------------------------------------------------
# T-RM-15  best_tab() — falls back to default_tab
# ---------------------------------------------------------------------------

def test_best_tab_falls_back_to_default():
    """T-RM-15: best_tab() returns default_tab when no slot key matches."""
    tab = rm.best_tab(_MINIMAL, li_acciones=["TB_NONEXISTENT"])
    assert tab == "home"


# ---------------------------------------------------------------------------
# T-RM-16  compact() — above threshold
# ---------------------------------------------------------------------------

def test_compact_above_threshold():
    """T-RM-16: compact() returns True when ribbon_height > threshold."""
    assert rm.compact(1001, 1000) is True


# ---------------------------------------------------------------------------
# T-RM-17  compact() — at or below threshold
# ---------------------------------------------------------------------------

def test_compact_below_threshold():
    """T-RM-17: compact() returns False when ribbon_height <= threshold."""
    assert rm.compact(1000, 1000) is False
    assert rm.compact(800, 1000) is False


# ---------------------------------------------------------------------------
# T-RIB-06  _validate() — key with invalid format is rejected
# ---------------------------------------------------------------------------

def test_ribbon_model_rejects_unknown_tb_key():
    """T-RIB-06: _validate() raises for a slot key that is neither TB_* nor caissa:*."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {
                        "id": "home.game",
                        "label": "Game",
                        "slots": [
                            {"key": "INVALID_KEY_FORMAT", "size": "large"},
                        ],
                    }
                ],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="invalid format"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RIB-07  _validate() — duplicate slot key within a tab is rejected
# ---------------------------------------------------------------------------

def test_ribbon_model_rejects_duplicate_slot_keys_within_tab():
    """T-RIB-07: _validate() raises when the same key appears twice in one tab."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {
                        "id": "home.g1",
                        "label": "G1",
                        "slots": [{"key": "TB_RESIGN", "size": "large"}],
                    },
                    {
                        "id": "home.g2",
                        "label": "G2",
                        "slots": [{"key": "TB_RESIGN", "size": "small"}],
                    },
                ],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="duplicate slot key"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RIB-08  _validate() — invalid size value is rejected
# ---------------------------------------------------------------------------

def test_ribbon_model_rejects_invalid_size():
    """T-RIB-08: _validate() raises when a slot has an unrecognised size value."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {
                        "id": "home.game",
                        "label": "Game",
                        "slots": [{"key": "TB_RESIGN", "size": "huge"}],
                    }
                ],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="invalid size"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RIB-09  _validate() — invalid kind value is rejected
# ---------------------------------------------------------------------------

def test_ribbon_model_rejects_invalid_kind():
    """T-RIB-09: _validate() raises when a group has an unrecognised kind value."""
    data = {
        "$schema_version": 1,
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {
                        "id": "home.game",
                        "label": "Game",
                        "kind": "list",
                        "slots": [],
                    }
                ],
            }
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="invalid kind"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RIB-10  _validate() — default_tab naming a non-existent tab is rejected
# ---------------------------------------------------------------------------

def test_ribbon_model_rejects_unknown_default_tab():
    """T-RIB-10: _validate() raises when default_tab does not match any tab id."""
    data = {
        "$schema_version": 1,
        "default_tab": "nonexistent",
        "tabs": [
            {"id": "home", "label": "Home", "groups": []},
        ],
        "quick_access": [],
    }
    path = _write_ribbon(data)
    try:
        with pytest.raises(RibbonSpecError, match="default_tab"):
            rm.load(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# T-RIB-11  _validate() — same key in QAT and a tab slot is accepted
# ---------------------------------------------------------------------------

def test_ribbon_model_accepts_qat_tab_overlap():
    """T-RIB-11: A key appearing in quick_access AND a tab slot is valid (Office pattern)."""
    data = {
        "$schema_version": 1,
        "default_tab": "home",
        "quick_access": ["TB_CLOSE"],
        "tabs": [
            {
                "id": "home",
                "label": "Home",
                "groups": [
                    {
                        "id": "home.game",
                        "label": "Game",
                        # TB_CLOSE also in quick_access — must not raise
                        "slots": [{"key": "TB_CLOSE", "size": "small"}],
                    }
                ],
            }
        ],
    }
    path = _write_ribbon(data)
    try:
        spec = rm.load(path)
        assert spec is not None
    finally:
        os.unlink(path)
