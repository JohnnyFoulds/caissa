"""bin/Code/Fritz/GeometryStore.py — Window and splitter geometry persistence for Fritz.

An adapter-tier module that owns all geometry saves/restores for the fixed-window
mode.  It wraps ``Code.configuration.save_video`` / ``restore_video`` with a
Fritz-specific key prefix so geometry never collides with the classical ``"maind"``
slot.

:spec: §2.6, Phase 2 (feature_spec.md)
:tier: adapter — may call upstream Code.*; no direct PySide6 import
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

#: Encoding stored in the ``_SIZE_`` slot to indicate the window was maximized
#: when geometry was saved.  Restored as ``showMaximized()`` rather than a pixel
#: size.
_MAXIMIZED_TOKEN = "_MAXIMIZED_"


def save_window(key: str, pos_x: int, pos_y: int, width: int, height: int,
                maximized: bool, fullscreen: bool) -> None:
    """Persist window geometry under *key*.

    Maximized windows store :data:`_MAXIMIZED_TOKEN` instead of the current
    screen-filling size so that a subsequent restore-down returns to the
    user's chosen size.  Fullscreen geometry is never saved.

    :param key: Video-save key (e.g. ``"fritzd"``).
    :param pos_x: Window left edge in screen pixels.
    :param pos_y: Window top edge in screen pixels.
    :param width: ``normalGeometry().width()`` — valid even when maximized.
    :param height: ``normalGeometry().height()``.
    :param maximized: ``True`` when the window is maximized (not fullscreen).
    :param fullscreen: ``True`` when fullscreen (F11).  If ``True`` the call
        is a no-op — we never persist fullscreen geometry.
    """
    if fullscreen:
        return

    import Code  # noqa: PLC0415 — adapter: upstream import
    dic = Code.configuration.restore_video(key) or {}

    dic["_POSICION_"] = "%d,%d" % (pos_x, pos_y)

    if maximized:
        # Persist the normal (pre-maximize) size so restore-down works.
        dic["_SIZE_"] = _MAXIMIZED_TOKEN
        dic["_NORMAL_SIZE_"] = "%d,%d" % (width, height)
    else:
        dic["_SIZE_"] = "%d,%d" % (width, height)
        dic.pop("_NORMAL_SIZE_", None)

    Code.configuration.save_video(key, dic)


def load_window(key: str) -> dict | None:
    """Return saved window geometry for *key*, or ``None`` if nothing is stored.

    The returned dict has string keys ``pos``, ``size`` (tuple ``(w, h)``),
    ``maximized`` (bool), and optionally ``normal_size`` (tuple ``(w, h)``).

    :param key: Video-save key.
    :returns: Geometry dict, or ``None``.
    """
    import Code  # noqa: PLC0415
    raw = Code.configuration.restore_video(key)
    if not raw:
        return None

    result: dict = {}

    pos_str = raw.get("_POSICION_")
    if pos_str:
        try:
            x, y = (int(v) for v in pos_str.split(",", 1))
            result["pos"] = (x, y)
        except (ValueError, TypeError):
            logger.warning("GeometryStore: bad _POSICION_ for key=%s: %r", key, pos_str,
                           exc_info=True)

    size_str = raw.get("_SIZE_")
    if size_str == _MAXIMIZED_TOKEN:
        result["maximized"] = True
        normal_str = raw.get("_NORMAL_SIZE_")
        if normal_str:
            try:
                w, h = (int(v) for v in normal_str.split(",", 1))
                result["normal_size"] = (w, h)
            except (ValueError, TypeError):
                logger.warning("GeometryStore: bad _NORMAL_SIZE_ for key=%s: %r",
                               key, normal_str, exc_info=True)
    elif size_str:
        try:
            w, h = (int(v) for v in size_str.split(",", 1))
            result["size"] = (w, h)
            result["maximized"] = False
        except (ValueError, TypeError):
            logger.warning("GeometryStore: bad _SIZE_ for key=%s: %r", key, size_str,
                           exc_info=True)

    return result if result else None


def save_splitters(key: str, splitter_sizes: dict[str, list[int]]) -> None:
    """Persist a mapping of splitter name → sizes list under *key*.

    :param key: Video-save key (typically the same as the window key).
    :param splitter_sizes: ``{name: [int, ...]}`` mapping.
    """
    import Code  # noqa: PLC0415
    dic = Code.configuration.restore_video(key) or {}
    for name, sizes in splitter_sizes.items():
        dic[f"SP_{name}"] = sizes
    Code.configuration.save_video(key, dic)


def load_splitters(key: str) -> dict[str, list[int]]:
    """Return saved splitter sizes for *key*.

    :param key: Video-save key.
    :returns: ``{name: [int, ...]}`` mapping; empty dict if nothing stored.
    """
    import Code  # noqa: PLC0415
    raw = Code.configuration.restore_video(key) or {}
    result: dict[str, list[int]] = {}
    for k, v in raw.items():
        if k.startswith("SP_") and isinstance(v, list):
            result[k[3:]] = v
    return result


def clamp_to_screens(x: int, y: int, w: int, h: int,
                     screens: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    """Return ``(x, y, w, h)`` adjusted so the window is at least partly visible.

    Each screen is a ``(sx, sy, sw, sh)`` tuple in logical pixels.  If no
    screen contains the top-left corner, the window is moved to the primary
    screen (first entry in *screens*).

    This is a pure function — it does not call Qt.

    :param x: Window left edge.
    :param y: Window top edge.
    :param w: Window width.
    :param h: Window height.
    :param screens: List of ``(sx, sy, sw, sh)`` screen geometries.
    :returns: ``(x, y, w, h)`` possibly adjusted.
    """
    if not screens:
        return x, y, w, h

    for sx, sy, sw, sh in screens:
        if sx <= x < sx + sw and sy <= y < sy + sh:
            return x, y, w, h

    # Top-left is off all screens: move to primary screen.
    sx, sy, sw, sh = screens[0]
    new_x = max(sx, min(x, sx + sw - w))
    new_y = max(sy, min(y, sy + sh - h))
    return new_x, new_y, w, h
