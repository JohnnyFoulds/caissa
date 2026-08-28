"""
bin/Code/Fritz/ModeGateway.py — Cached adapter over the mode JSON files.

This is the single reader of ``Resources/Modes/`` for Fritz-layer purposes.
It caches the parsed mode list at module level so ``allows_toolbar`` (called
once per toolbar key per screen change) does not re-parse all 9 JSONs on every
invocation.

Public API
----------
``modes() -> dict[str, dict]``
    All loaded modes keyed by name.  Cached; call ``invalidate()`` in tests.

``active() -> dict``
    The currently active mode dict (reads ``Code.configuration.x_ui_mode``).

``layout() -> dict``
    The ``layout`` sub-dict of the active mode, or ``{}`` when absent/null.

``ribbon_name() -> str | None``
    The ``ribbon`` key of the active mode, or ``None`` when absent.

``hook_module_name(mode_name) -> str``
    Derives the hook module path from a mode name or its explicit ``"hook"``
    override, e.g. ``"modern fritz"`` → ``"Code.UIModes.actions.modern_fritz_ui"``.

``invalidate()``
    Clear the cache.  Call after writing test fixtures or switching profiles.

:spec: §5.4 (feature_spec.md)
"""

from __future__ import annotations

import json
import logging
import os

import Code

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_cache: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    """Load all mode JSONs from ``Resources/Modes/`` and return a name-keyed dict.

    Errors in individual files are logged and skipped.
    """
    folder = Code.path_resource("Modes")
    result: dict[str, dict] = {}
    if not os.path.isdir(folder):
        logger.warning("Mode folder not found: %s", folder)
        return result
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(folder, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            name = data.get("name", "")
            if name:
                result[name] = data
        except Exception as exc:
            logger.warning("Could not load mode file %s: %s", path, exc, exc_info=True)
    return result


def modes() -> dict[str, dict]:
    """Return all loaded modes keyed by name.

    The result is cached for the lifetime of the process.  Call
    ``invalidate()`` to force a re-read (tests, profile switches).

    :return: ``{mode_name: mode_dict}``

    :spec: §5.4
    """
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def invalidate() -> None:
    """Clear the mode cache.

    The next call to ``modes()`` will re-read ``Resources/Modes/``.

    :spec: §5.4
    """
    global _cache
    _cache = None


def active() -> dict:
    """Return the currently active mode dict.

    Reads ``Code.configuration.x_ui_mode``; falls back to a minimal
    ``classical`` dict when the mode is unrecognised.

    :return: Mode dict with at minimum ``{"name": ..., "toolbar": None, "menu_keys": None}``.

    :spec: §5.4
    """
    name = getattr(Code.configuration, "x_ui_mode", "classical")
    found = modes().get(name)
    if found is not None:
        return found
    # Exact match failed — try case-insensitive
    lower = name.lower()
    for mode_name, mode_dict in modes().items():
        if mode_name.lower() == lower:
            return mode_dict
    return {"name": "classical", "toolbar": None, "menu_keys": None}


def layout() -> dict:
    """Return the ``layout`` sub-dict of the active mode.

    Both an absent key and an explicit ``null`` value return ``{}``, so callers
    can use ``layout().get("fit_board_to_window", False)`` unconditionally.

    :return: Layout sub-dict, never ``None``.

    :spec: §5.4
    """
    return active().get("layout") or {}


def ribbon_name() -> str | None:
    """Return the ``ribbon`` key of the active mode, or ``None`` when absent.

    :return: Ribbon name string (used to locate ``Resources/Ribbons/<name>.json``)
        or ``None`` when the active mode has no ribbon.

    :spec: §5.4
    """
    return active().get("ribbon")


def hook_module_name(mode_name: str) -> str:
    """Derive the Python module path for a mode's UI hook.

    Uses the explicit ``"hook"`` key when present; otherwise derives from
    *mode_name* by lower-casing and replacing spaces with underscores.

    Example: ``"Modern Fritz Dark"`` → ``"Code.UIModes.actions.modern_fritz_ui"``
    (via ``"hook": "modern_fritz"`` in the mode JSON).

    :param mode_name: Mode name as it appears in the mode JSON ``"name"`` field.
    :return: Fully-qualified Python module path string.

    :spec: §5.4
    """
    mode_dict = modes().get(mode_name, {})
    hook_key = mode_dict.get("hook")
    if hook_key:
        base = hook_key
    else:
        base = mode_name.lower().replace(" ", "_")
    return f"Code.UIModes.actions.{base}_ui"
