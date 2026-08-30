"""
bin/Code/Fritz/Ribbon.py — Ribbon installation wiring for WBase.

:spec: Phase 7 (feature_spec.md §2.2, §5)

Purity tier: **Qt allowlist** (imports PySide6 indirectly via WRibbon).
"""

from __future__ import annotations

import logging
from typing import Any

import Code

_logger = logging.getLogger(__name__)


def spec_path_for_name(ribbon_name: str) -> str:
    """
    Resolve *ribbon_name* to an absolute filesystem path.

    :param ribbon_name: The bare name from the mode JSON's ``"ribbon"`` key,
        e.g. ``"modern-fritz"``.
    :returns: Absolute path to the corresponding ``Resources/Ribbons/<name>.json``.
    """
    return Code.path_resource("Ribbons", f"{ribbon_name}.json")


def install(
    base: Any,
    ribbon_name: str | None,
) -> Any | None:
    """
    Build a :class:`~Code.Fritz.WRibbon.WRibbon` and attach it to *base*'s toolbar.

    Returns ``None`` (logging a warning) rather than raising on any failure, so
    a malformed ribbon JSON degrades gracefully to the plain toolbar.

    :param base: The ``WBase`` instance (must have ``tb`` and ``dic_toolbar``).
    :param ribbon_name: Bare ribbon name from the active mode JSON's ``"ribbon"``
        key.  ``None`` means no ribbon — returns ``None`` immediately.
    :returns: The installed :class:`~Code.Fritz.WRibbon.WRibbon`, or ``None``.
    """
    if not ribbon_name:
        return None

    try:
        from PySide6 import QtWidgets

        from Code.Fritz import RibbonModel
        from Code.Fritz.WRibbon import WRibbon

        path = spec_path_for_name(ribbon_name)
        spec = RibbonModel.load(path)

        # Fetch pane_api from the active mode hook if available.
        # Defer main_window lookup to each call — at install time main_window
        # may not yet be assigned on Procesador, so _fritz_panes would be
        # missing and all pane checkboxes would be permanently inert.
        pane_api: dict | None = None
        try:
            from Code.UIModes import UIModes
            mode_dict = UIModes.active_mode()
            hook_override = mode_dict.get("hook")
            hook = UIModes.load_mode_hook(
                base.manager.configuration.x_ui_mode,
                hook=hook_override,
            )
            if hook and hasattr(hook, "pane_api"):
                _hook, _base = hook, base
                pane_api = {
                    "names": _hook.pane_api(None).get("names", []),
                    "get": lambda key: _hook.pane_api(_base.manager.main_window)["get"](key),
                    "set": lambda key, vis: _hook.pane_api(_base.manager.main_window)["set"](key, vis),
                }
        except Exception:
            pass

        ribbon = WRibbon(spec, base.dic_toolbar, pane_api=pane_api, parent=base.tb)
        ribbon.ensurePolished()

        action = QtWidgets.QWidgetAction(base.tb)
        action.setDefaultWidget(ribbon)
        base.tb.addAction(action)
        base.tb.setFixedHeight(ribbon.height() + 4)

        return ribbon

    except Exception as exc:
        _logger.warning("Ribbon.install failed for %r: %s", ribbon_name, exc, exc_info=True)
        return None
