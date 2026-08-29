"""
tests/test_ribbon_map.py — Ribbon content map validation tests (T-RMAP-01..08).

:spec: Phase 7 (feature_spec.md)
"""

from __future__ import annotations

import glob
import json
import os
import re

import pytest

pytestmark = pytest.mark.unit

_RIBBONS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "Resources", "Ribbons")
)
_MODES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "Resources", "Modes")
)


def _load_all_ribbons() -> list[tuple[str, dict]]:
    """Return [(basename, parsed_dict)] for every *.json in Resources/Ribbons/."""
    files = glob.glob(os.path.join(_RIBBONS_DIR, "*.json"))
    result = []
    for f in sorted(files):
        with open(f, encoding="utf-8") as fh:
            result.append((os.path.basename(f), json.load(fh)))
    return result


def _all_slot_keys(data: dict) -> list[str]:
    """Flat list of every key in slots + quick_access + backstage items (with duplicates preserved)."""
    keys: list[str] = []
    for key in data.get("quick_access", []):
        keys.append(key)
    for tab in data.get("tabs", []):
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                k = slot.get("key", "")
                if k:
                    keys.append(k)
        # backstage tabs use "items" instead of groups/slots
        for item in tab.get("items", []):
            k = item.get("key", "")
            if k:
                keys.append(k)
    return keys


def _non_backstage_slot_keys(data: dict) -> list[str]:
    """Keys in regular-tab slots + quick_access only (excluding backstage items).

    Backstage items (File menu) legitimately duplicate regular slots — e.g.
    "New Game" appears in File backstage AND in Home > Play, like every Office ribbon app.
    """
    keys: list[str] = []
    for key in data.get("quick_access", []):
        keys.append(key)
    for tab in data.get("tabs", []):
        if tab.get("kind") == "backstage":
            continue
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                k = slot.get("key", "")
                if k:
                    keys.append(k)
    return keys


def _tab_only_slot_keys(data: dict) -> list[str]:
    """Keys in regular-tab slots only — excludes quick_access and backstage.

    Use this for duplicate detection: QAT items intentionally mirror their home
    tab slot (Office ribbon pattern), so QAT/tab overlap is not a defect.
    """
    keys: list[str] = []
    for tab in data.get("tabs", []):
        if tab.get("kind") == "backstage":
            continue
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                k = slot.get("key", "")
                if k:
                    keys.append(k)
    return keys


def _backstage_slot_keys(data: dict) -> set[str]:
    """Keys that appear in any backstage tab's items list."""
    keys: set[str] = set()
    for tab in data.get("tabs", []):
        if tab.get("kind") != "backstage":
            continue
        for item in tab.get("items", []):
            k = item.get("key", "")
            if k:
                keys.add(k)
    return keys


def test_all_ribbon_jsons_valid_schema():
    """T-RMAP-01: Every Resources/Ribbons/*.json is valid with $schema_version == 1."""
    ribbons = _load_all_ribbons()
    assert ribbons, (
        "T-RMAP-01 FAIL: No *.json files found in Resources/Ribbons/ — "
        f"looked in {_RIBBONS_DIR}"
    )
    for basename, data in ribbons:
        assert data.get("$schema_version") == 1, (
            f"T-RMAP-01 FAIL: {basename} has $schema_version={data.get('$schema_version')!r}, expected 1"
        )
        assert "tabs" in data, f"T-RMAP-01 FAIL: {basename} missing 'tabs' key"
        assert "quick_access" in data, f"T-RMAP-01 FAIL: {basename} missing 'quick_access' key"


def test_unique_tab_and_group_ids():
    """T-RMAP-02: All tab and group IDs within a ribbon JSON are unique."""
    for basename, data in _load_all_ribbons():
        tab_ids: list[str] = []
        group_ids: list[str] = []
        for tab in data.get("tabs", []):
            tid = tab.get("id", "")
            tab_ids.append(tid)
            for group in tab.get("groups", []):
                group_ids.append(group.get("id", ""))
        dup_tabs = {t for t in tab_ids if tab_ids.count(t) > 1}
        dup_groups = {g for g in group_ids if group_ids.count(g) > 1}
        assert not dup_tabs, (
            f"T-RMAP-02 FAIL: {basename} has duplicate tab ids: {sorted(dup_tabs)}"
        )
        assert not dup_groups, (
            f"T-RMAP-02 FAIL: {basename} has duplicate group ids: {sorted(dup_groups)}"
        )


def test_no_duplicate_slot_keys():
    """T-RMAP-03: No key appears more than once within regular-tab slots.

    Two kinds of duplication are intentional and explicitly excluded:
    - Backstage items (File menu) may duplicate regular tab slots — Office pattern.
    - QAT items may duplicate their home tab slot — QAT is a pinning shortcut,
      not an independent placement.

    Only true within-tab duplicates (the same key in two different non-backstage
    tab groups) are considered defects.
    """
    for basename, data in _load_all_ribbons():
        all_keys = _tab_only_slot_keys(data)
        seen: set[str] = set()
        dups: list[str] = []
        for k in all_keys:
            if k in seen:
                dups.append(k)
            seen.add(k)
        assert not dups, (
            f"T-RMAP-03 FAIL: {basename} has duplicate keys within tab slots: {sorted(set(dups))}"
        )


def test_all_keys_resolve_in_constantes():
    """T-RMAP-04: Every slot key resolves to a TB_* name in Constantes or matches ^caissa:[a-z_]+$."""
    from Code.Base import Constantes

    tb_values: set = {v for k, v in vars(Constantes).items() if k.startswith("TB_")}
    caissa_re = re.compile(r"^caissa:[a-z_]+$")

    violations: list[str] = []
    for basename, data in _load_all_ribbons():
        for key in set(_all_slot_keys(data)):
            if isinstance(key, int):
                if key not in tb_values:
                    violations.append(f"{basename}: int key {key} not in Constantes TB_* range")
            elif isinstance(key, str):
                if caissa_re.match(key):
                    continue  # caissa: namespace is always valid
                # Must be a TB_* name
                if not hasattr(Constantes, key):
                    violations.append(f"{basename}: {key!r} not found in Constantes")

    assert not violations, (
        "T-RMAP-04 FAIL: unresolvable keys:\n" + "\n".join(violations)
    )


def test_all_fritz_toolbar_keys_in_slot_or_quick_access():
    """T-RMAP-05: Every key in modern-fritz.json's toolbar allowlist appears in some slot or quick_access."""
    fritz_path = os.path.join(_MODES_DIR, "modern-fritz.json")
    assert os.path.isfile(fritz_path), f"T-RMAP-05 FAIL: {fritz_path} not found"

    with open(fritz_path, encoding="utf-8") as fh:
        fritz_mode = json.load(fh)

    ribbon_name = fritz_mode.get("ribbon")
    assert ribbon_name, "T-RMAP-05 FAIL: modern-fritz.json has no 'ribbon' key"

    ribbon_path = os.path.join(_RIBBONS_DIR, f"{ribbon_name}.json")
    assert os.path.isfile(ribbon_path), (
        f"T-RMAP-05 FAIL: ribbon file {ribbon_path} not found"
    )
    with open(ribbon_path, encoding="utf-8") as fh:
        ribbon_data = json.load(fh)

    covered = set(_all_slot_keys(ribbon_data))
    toolbar_keys = fritz_mode.get("toolbar", []) + fritz_mode.get("toolbar_inject", [])

    uncovered = [k for k in toolbar_keys if k not in covered]
    assert not uncovered, (
        "T-RMAP-05 FAIL: keys in modern-fritz toolbar allowlist not covered by any slot or QAT:\n"
        + "\n".join(f"  {k!r}" for k in uncovered)
    )


def test_never_filter_keys_in_quick_access():
    """T-RMAP-06: Every NEVER_FILTER_TOOLBAR member is in quick_access or a backstage tab.

    TB_QUIT lives in the File backstage (not QAT) by approved design: it is an
    infrequent, destructive action that should not sit in the always-visible strip.
    All other NEVER_FILTER_TOOLBAR members must remain in QAT for one-key reachability.
    """
    from Code.Base import Constantes
    from Code.Base.Constantes import NEVER_FILTER_TOOLBAR

    # Resolve TB_* int values back to names for readable error messages
    int_to_name = {v: k for k, v in vars(Constantes).items() if k.startswith("TB_")}

    def _resolve_keys(raw_keys):
        result: set = set()
        for k in raw_keys:
            if isinstance(k, int):
                result.add(k)
            elif hasattr(Constantes, k):
                result.add(getattr(Constantes, k))
        return result

    for basename, data in _load_all_ribbons():
        qat_ints = _resolve_keys(data.get("quick_access", []))
        backstage_ints = _resolve_keys(_backstage_slot_keys(data))
        reachable = qat_ints | backstage_ints

        missing = NEVER_FILTER_TOOLBAR - reachable
        assert not missing, (
            f"T-RMAP-06 FAIL: {basename} has NEVER_FILTER_TOOLBAR members not in "
            f"quick_access or backstage: "
            + str({int_to_name.get(v, v) for v in missing})
        )


def test_overflow_group_exists():
    """T-RMAP-09: If a ribbon JSON specifies an overflow group, that group must exist."""
    for basename, data in _load_all_ribbons():
        overflow = data.get("overflow")
        if not overflow:
            continue
        tab_id = overflow.get("tab")
        group_id = overflow.get("group")
        if not tab_id or not group_id:
            continue
        # Find the target tab
        tab_data = next((t for t in data.get("tabs", []) if t.get("id") == tab_id), None)
        assert tab_data is not None, (
            f"T-RMAP-09 FAIL: {basename} overflow.tab={tab_id!r} names a tab that does not exist"
        )
        group_ids = {g.get("id") for g in tab_data.get("groups", [])}
        assert group_id in group_ids, (
            f"T-RMAP-09 FAIL: {basename} overflow.group={group_id!r} not found in tab {tab_id!r}. "
            f"Available groups: {sorted(group_ids)}"
        )


def test_no_non_fritz_mode_has_ribbon_key():
    """T-RMAP-07: None of the six non-Fritz mode JSONs contains a ribbon key."""
    fritz_names = {"modern fritz", "modern fritz dark"}
    mode_files = glob.glob(os.path.join(_MODES_DIR, "*.json"))
    violations: list[str] = []
    for path in sorted(mode_files):
        with open(path, encoding="utf-8") as fh:
            mode = json.load(fh)
        name = mode.get("name", "").lower()
        if name in fritz_names:
            continue
        if "ribbon" in mode and mode["ribbon"] is not None:
            violations.append(f"{os.path.basename(path)}: has ribbon={mode['ribbon']!r}")
    assert not violations, (
        "T-RMAP-07 FAIL: non-Fritz mode files with a ribbon key:\n"
        + "\n".join(violations)
    )


def test_no_ribbon_json_in_modes_directory():
    """T-RMAP-08: Resources/Modes/ contains no *.ribbon.json files."""
    ribbon_jsons = glob.glob(os.path.join(_MODES_DIR, "*.ribbon.json"))
    assert not ribbon_jsons, (
        "T-RMAP-08 FAIL: found *.ribbon.json files in Resources/Modes/:\n"
        + "\n".join(os.path.basename(f) for f in ribbon_jsons)
    )
