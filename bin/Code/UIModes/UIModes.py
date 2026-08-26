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
from typing import Optional

import Code
from Code.Menus import BaseMenu
from Code.Base import Constantes

# Resolve TB_* name → int once at import time
_TB_BY_NAME = {k: v for k, v in vars(Constantes).items() if k.startswith("TB_")}

# TB_* values that must NEVER be filtered — closeEvent depends on them.
NEVER_FILTER_TOOLBAR = frozenset({
    Constantes.TB_QUIT, Constantes.TB_CLOSE, Constantes.TB_CANCEL,
    Constantes.TB_STOP, Constantes.TB_TUTOR_STOP, Constantes.TB_END_REPLAY,
})


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


def find_mode(name: str) -> Optional[dict]:
    for m in load_modes():
        if m.get("name", "").lower() == name.lower():
            return m
    return None


def active_mode() -> dict:
    name = getattr(Code.configuration, "x_ui_mode", "classical")
    return find_mode(name) or {"name": "classical", "menu_keys": None, "toolbar": None}


# ── toolbar filtering ─────────────────────────────────────────────────────────

def _resolve_toolbar_set(mode: dict) -> Optional[frozenset]:
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
    if key in NEVER_FILTER_TOOLBAR:
        return True
    mode = active_mode()
    tb_set = _resolve_toolbar_set(mode)
    if tb_set is None:
        return True
    return key in tb_set


def allows_all_toolbar() -> bool:
    return active_mode().get("toolbar") is None


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
