"""
Actions.py — registry for named UI actions that mode JSON files can reference.

Actions let modes ADD functionality (toolbar buttons, menu entries) without
touching WBase, BaseMenu, or Constantes. Each action is a namespaced string
like "caissa:switch_mode".

Drop-in modules in Code/UIModes/actions/*.py each expose register(reg) and
are loaded once at first import of this module.
"""
import importlib
import os

_registry: dict = {}  # key -> {"label": str, "icon": QIcon|None, "handler": callable}


def register(key: str, label: str, icon, handler):
    _registry[key] = {"label": label, "icon": icon, "handler": handler}


def has(key: str) -> bool:
    _load_plugins()
    return key in _registry


def get(key: str) -> dict | None:
    _load_plugins()
    return _registry.get(key)


def all_items():
    _load_plugins()
    return _registry.items()


_plugins_loaded = False


def _load_plugins():
    global _plugins_loaded
    if _plugins_loaded:
        return
    _plugins_loaded = True
    actions_dir = os.path.join(os.path.dirname(__file__), "actions")
    for fname in sorted(os.listdir(actions_dir)):
        if fname.endswith(".py") and fname != "__init__.py":
            mod_name = f"Code.UIModes.actions.{fname[:-3]}"
            try:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, "register"):
                    mod.register(register)
            except Exception as exc:
                import Code
                if hasattr(Code, "informacion"):
                    Code.informacion(f"UIModes action load error ({mod_name}): {exc}")
