"""
bin/Code/Fritz/RibbonModel.py — Pure ribbon content-map loader and state machine.

:spec: Phase 7 (feature_spec.md §2.2, §5)

Purity tier: **pure** — imports only stdlib + Fritz/Types, Fritz/Errors.
"""

from __future__ import annotations

import json
import re
from typing import Any

from Code.Fritz.Errors import RibbonSpecError

# ─────────────────────────── public helpers ──────────────────────────────────


def load(path: str) -> dict[str, Any]:
    """
    Load and validate a ribbon JSON at *path*.

    :param path: Filesystem path to a ``Resources/Ribbons/<name>.json`` file.
    :returns: The validated ribbon spec dict.
    :raises RibbonSpecError: When the file is missing, not valid JSON, or fails
        schema validation (``$schema_version != 1``).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise RibbonSpecError(f"Ribbon file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RibbonSpecError(f"Invalid JSON in {path}: {exc}") from exc

    if data.get("$schema_version") != 1:
        raise RibbonSpecError(
            f"Unsupported $schema_version in {path}: {data.get('$schema_version')!r}"
        )
    _validate(data, path)
    return data


def all_slot_keys(spec: dict[str, Any]) -> list[str]:
    """
    Return every action key referenced in slots + quick_access (no duplicates,
    preserving first-seen order).

    :param spec: A validated ribbon spec as returned by :func:`load`.
    """
    seen: set[str] = set()
    result: list[str] = []
    for key in spec.get("quick_access", []):
        if key not in seen:
            seen.add(key)
            result.append(key)
    for tab in spec.get("tabs", []):
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                key = slot.get("key", "")
                if key and key not in seen:
                    seen.add(key)
                    result.append(key)
        # backstage tabs use "items" instead of groups/slots
        for item in tab.get("items", []):
            key = item.get("key", "")
            if key and key not in seen:
                seen.add(key)
                result.append(key)
    return result


def state(
    spec: dict[str, Any],
    li_acciones: list[int | str],
) -> dict[str, tuple[bool, bool, str]]:
    """
    Compute per-slot state given the current ``li_acciones`` list.

    :param spec: A validated ribbon spec.
    :param li_acciones: The toolbar action keys currently active (as integers
        or caissa: strings, matching ``WBase.tb.li_acciones``).
    :returns: Mapping ``{key: (visible, enabled, tab_id)}`` for every slot and
        quick_access entry.  Keys absent from *li_acciones* get
        ``(True, False, tab_id)`` when ``missing_key_policy`` is ``"disable"``
        (the only policy currently defined).
    """
    active: set = set(li_acciones)
    policy = spec.get("missing_key_policy", "disable")
    result: dict[str, tuple[bool, bool, str]] = {}

    for key in spec.get("quick_access", []):
        enabled = (key in active) if policy == "disable" else True
        result[key] = (True, enabled, "")

    for tab in spec.get("tabs", []):
        tab_id = tab.get("id", "")
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                key = slot.get("key", "")
                if not key:
                    continue
                enabled = (key in active) if policy == "disable" else True
                result[key] = (True, enabled, tab_id)
        # backstage tabs use "items" instead of groups/slots
        for item in tab.get("items", []):
            key = item.get("key", "")
            if not key:
                continue
            enabled = (key in active) if policy == "disable" else True
            result[key] = (True, enabled, tab_id)

    return result


def overflow(
    spec: dict[str, Any],
    li_acciones: list[int | str],
) -> list[str]:
    """
    Return keys present in *li_acciones* but not covered by any slot or quick_access.

    :param spec: A validated ribbon spec.
    :param li_acciones: Current toolbar action keys.
    :returns: List of uncovered keys (order preserved from li_acciones).
    """
    covered = set(all_slot_keys(spec))
    return [k for k in li_acciones if k not in covered]


def best_tab(
    spec: dict[str, Any],
    li_acciones: list[int | str],
) -> str:
    """
    Return the tab id with the most intersection against *li_acciones*.

    Ties are broken by tab order.  Falls back to ``default_tab`` when every
    tab scores zero.

    :param spec: A validated ribbon spec.
    :param li_acciones: Current toolbar action keys.
    :returns: A tab id string.
    """
    active: set = set(li_acciones)
    best_id = spec.get("default_tab", "home")
    best_score = -1
    for tab in spec.get("tabs", []):
        score = 0
        for group in tab.get("groups", []):
            for slot in group.get("slots", []):
                if slot.get("key", "") in active:
                    score += 1
        if score > best_score:
            best_score = score
            best_id = tab.get("id", best_id)
    return best_id


def compact(ribbon_height: int, threshold: int) -> bool:
    """
    Return ``True`` when *ribbon_height* is above *threshold* and the ribbon
    should switch to its compact (small-slot) layout.

    :param ribbon_height: Current ribbon pixel height.
    :param threshold: The ``compact_below_height`` value from the mode JSON
        layout block.
    """
    return ribbon_height > threshold


# ─────────────────────────── internal validation ─────────────────────────────

_CAISSA_KEY_RE = re.compile(r"^caissa:[a-z_]+$")


def _validate(data: dict[str, Any], path: str) -> None:
    """Raise :class:`RibbonSpecError` if the spec has structural problems."""
    tab_ids: set[str] = set()
    group_ids: set[str] = set()
    all_keys: list[str] = []

    for key in data.get("quick_access", []):
        all_keys.append(key)

    for tab in data.get("tabs", []):
        tid = tab.get("id", "")
        if not tid:
            raise RibbonSpecError(f"{path}: tab missing 'id'")
        if tid in tab_ids:
            raise RibbonSpecError(f"{path}: duplicate tab id {tid!r}")
        tab_ids.add(tid)
        for group in tab.get("groups", []):
            gid = group.get("id", "")
            if not gid:
                raise RibbonSpecError(f"{path}: group missing 'id' in tab {tid!r}")
            if gid in group_ids:
                raise RibbonSpecError(f"{path}: duplicate group id {gid!r}")
            group_ids.add(gid)
            for slot in group.get("slots", []):
                key = slot.get("key", "")
                if key:
                    all_keys.append(key)
