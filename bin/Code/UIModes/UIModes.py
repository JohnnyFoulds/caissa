"""
UIModes.py — load and apply UI mode definitions from Resources/Modes/*.json.

A mode JSON specifies:
  - menu_keys:  list of allowed Option.key strings/prefixes, or null (allow all)
                prefix entries end with "*", e.g. "person_*" matches person_irina etc.
  - toolbar:    list of allowed TB_* constant names, or null (allow all)
  - style, icons: optional overrides applied on mode entry

The "classical" mode is the safety net: null allowlists leave everything intact.
"""
import json
import os

import Code
from Code.Base import Constantes
from Code.Menus import BaseMenu

# Resolve TB_* name → int once at import time
_TB_BY_NAME = {k: v for k, v in vars(Constantes).items() if k.startswith("TB_")}

NEVER_FILTER_TOOLBAR = Constantes.NEVER_FILTER_TOOLBAR


def _modes_folder() -> str:
    return Code.path_resource("Modes")


def load_modes() -> list:
    folder = _modes_folder()
    modes = []
    if not os.path.isdir(folder):
        return modes
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(folder, fname), encoding="utf-8") as f:
                    modes.append(json.load(f))
            except Exception:
                pass
    return modes


def find_mode(name: str) -> dict | None:
    for m in load_modes():
        if m.get("name", "").lower() == name.lower():
            return m
    return None


def active_mode() -> dict:
    name = getattr(Code.configuration, "x_ui_mode", "classical")
    return find_mode(name) or {"name": "classical", "menu_keys": None, "toolbar": None}


# ── toolbar filtering ─────────────────────────────────────────────────────────

def _resolve_toolbar_set(mode: dict) -> frozenset | None:
    """Return frozenset of allowed TB_* int values, or None if mode allows all."""
    raw = mode.get("toolbar")
    if raw is None:
        return None
    result = set(NEVER_FILTER_TOOLBAR)
    for entry in raw:
        if isinstance(entry, str):
            val = _TB_BY_NAME.get(entry)
            if val is not None:
                result.add(val)
        elif isinstance(entry, int):
            result.add(entry)
    return frozenset(result)


def allows_toolbar(key) -> bool:
    # Extension keys (caissa: prefix) are never filtered — they are not TB_* int keys.
    if isinstance(key, str) and key.startswith("caissa:"):
        return True
    if key in NEVER_FILTER_TOOLBAR:
        return True
    mode = active_mode()
    tb_set = _resolve_toolbar_set(mode)
    if tb_set is None:
        return True
    return key in tb_set


def allows_all_toolbar() -> bool:
    return active_mode().get("toolbar") is None


def toolbar_inject() -> list:
    """Return action keys the active mode wants prepended to every toolbar."""
    return active_mode().get("toolbar_inject", [])


# ── menu filtering ────────────────────────────────────────────────────────────

def _build_menu_filter(mode: dict):
    """Return (literal_set, prefix_list) or (None, None) if mode allows all."""
    raw = mode.get("menu_keys")
    if raw is None:
        return None, None
    literals = set()
    prefixes = []
    for entry in raw:
        if entry.endswith("*"):
            prefixes.append(entry[:-1])
        else:
            literals.add(entry)
    return literals, prefixes


def _key_allowed(key: str, literals, prefixes) -> bool:
    if key in literals:
        return True
    for p in prefixes:
        if key.startswith(p):
            return True
    return False


def load_mode_hook(mode_name: str, hook: str | None = None):
    """
    Load the optional UI hook module for a mode.

    :param mode_name: Mode name string (e.g. ``"Coach"``).
    :param hook:      Optional explicit hook basename (without ``_ui.py``) from the
                      mode JSON's ``"hook"`` key.  When present it overrides the
                      name-derived path, so ``"Modern Fritz Dark"`` with
                      ``"hook": "modern_fritz"`` resolves to ``modern_fritz_ui.py``
                      rather than ``modern_fritz_dark_ui.py``.
    :returns:         The loaded module, or ``None`` if the hook file does not exist
                      or fails to load.

    The hook file is ``bin/Code/UIModes/actions/<safe_name>_ui.py``.
    It may expose any of:

    * ``patch_config_form(form, configuration, overlay)``
    * ``on_mode_enter(main_window)``
    * ``on_mode_exit(main_window)``
    """
    import importlib.util
    import logging as _logging

    actions_dir = os.path.join(os.path.dirname(__file__), "actions")
    if hook:
        # Explicit hook override: normalise and use directly.
        safe_name = hook.lower().replace(" ", "_").replace("-", "_")
    else:
        # Normalise to a valid Python module filename: lower-case, spaces and hyphens → underscores
        safe_name = mode_name.lower().replace(" ", "_").replace("-", "_")
    path = os.path.join(actions_dir, f"{safe_name}_ui.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"_caissa_mode_{safe_name}_ui", path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        _logging.getLogger(__name__).error(
            "Failed to load mode hook %s", path, exc_info=True
        )
        return None


def filter_menu_options(menu: BaseMenu.RootMenuBase):
    """Prune menu.li_options in-place to only allowed keys. Removes empty submenus."""
    mode = active_mode()
    literals, prefixes = _build_menu_filter(mode)
    if literals is None:
        return  # classical / allow-all

    def _filter(items):
        result = []
        for item in items:
            if isinstance(item, BaseMenu.SubMenu):
                item.li_options = _filter(item.li_options)
                if item.li_options:
                    result.append(item)
            elif isinstance(item, BaseMenu.Option):
                if _key_allowed(item.key, literals, prefixes):
                    result.append(item)
        return result

    menu.li_options = _filter(menu.li_options)
