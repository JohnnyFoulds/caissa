"""
tests/unit/fritz/test_layouts.py — Unit tests for Fritz mode layout presets.

:spec: Phase 5 (feature_spec.md fritz-mode)
"""

from __future__ import annotations

import pytest
from Code.Fritz.Layouts import (
    PRESETS,
    apply_preset,
    factory_name,
    preset_names,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# T-LAY-01  preset_names returns a non-empty ordered list
# ---------------------------------------------------------------------------

def test_preset_names_returns_all_presets():
    """T-LAY-01: preset_names() returns one entry per PRESETS key."""
    names = preset_names()
    assert names == list(PRESETS), "T-LAY-01: preset_names() must match PRESETS key order"
    assert len(names) >= 4, "T-LAY-01: at least four named presets required"


# ---------------------------------------------------------------------------
# T-LAY-02  factory_name is a valid preset
# ---------------------------------------------------------------------------

def test_factory_name_is_in_presets():
    """T-LAY-02: factory_name() must be a key of PRESETS."""
    assert factory_name() in PRESETS, (
        f"T-LAY-02: factory_name={factory_name()!r} not found in PRESETS"
    )


# ---------------------------------------------------------------------------
# T-LAY-03  each preset has 'main' (len 2) and 'right_col' (len 4) lists
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(PRESETS))
def test_preset_structure(name):
    """T-LAY-03: each preset contains valid 'main' and 'right_col' int lists."""
    p = PRESETS[name]

    assert "main" in p, f"T-LAY-03: preset {name!r} missing 'main'"
    assert "right_col" in p, f"T-LAY-03: preset {name!r} missing 'right_col'"

    assert len(p["main"]) == 2, (
        f"T-LAY-03: preset {name!r} 'main' must have 2 entries (got {len(p['main'])})"
    )
    assert len(p["right_col"]) == 4, (
        f"T-LAY-03: preset {name!r} 'right_col' must have 4 entries (got {len(p['right_col'])})"
    )

    for v in p["main"] + p["right_col"]:
        assert isinstance(v, int) and v > 0, (
            f"T-LAY-03: preset {name!r} contains non-positive int: {v!r}"
        )


# ---------------------------------------------------------------------------
# T-LAY-04  apply_preset calls setSizes on both splitters
# ---------------------------------------------------------------------------

class _FakeSplitter:
    def __init__(self):
        self.last_sizes: list[int] | None = None

    def setSizes(self, sizes: list[int]) -> None:
        self.last_sizes = list(sizes)


def test_apply_preset_calls_set_sizes():
    """T-LAY-04: apply_preset() calls setSizes() on both splitters with correct values."""
    main_sp = _FakeSplitter()
    rc_sp = _FakeSplitter()

    name = preset_names()[0]
    apply_preset(name, main_sp, rc_sp)

    assert main_sp.last_sizes == PRESETS[name]["main"], (
        f"T-LAY-04: main splitter sizes mismatch for preset {name!r}"
    )
    assert rc_sp.last_sizes == PRESETS[name]["right_col"], (
        f"T-LAY-04: right_col splitter sizes mismatch for preset {name!r}"
    )


# ---------------------------------------------------------------------------
# T-LAY-05  apply_preset falls back to Standard on unknown name
# ---------------------------------------------------------------------------

def test_apply_preset_falls_back_to_factory():
    """T-LAY-05: apply_preset() with an unknown name uses the factory preset."""
    main_sp = _FakeSplitter()
    rc_sp = _FakeSplitter()

    apply_preset("NonexistentPreset", main_sp, rc_sp)

    fn = factory_name()
    assert main_sp.last_sizes == PRESETS[fn]["main"], (
        "T-LAY-05: fallback should use factory preset 'main'"
    )
    assert rc_sp.last_sizes == PRESETS[fn]["right_col"], (
        "T-LAY-05: fallback should use factory preset 'right_col'"
    )
