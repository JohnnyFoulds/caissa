"""
Adapter: read-only view over ``Code.dic_colors`` for Fritz widgets.

All Fritz colour lookups go through this module so that (a) widgets never
read ``Code.dic_colors`` directly and (b) a theme swap can be detected and the
NAG colour memo invalidated.

Purity tier: **Adapter** — imports ``Code.*`` but no Qt.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NAG colour support
# ---------------------------------------------------------------------------
# Code.Nags.Nags.nag_color() is pure logic polluted by a QtGui.QColor wrapper.
# We call it and extract the hex string so callers stay Qt-free.
# The result is memoised here; invalidate() clears the memo on a theme swap.

_nag_hex_cache: dict[int, str] = {}


def invalidate() -> None:
    """Clear all cached values.  Call on every theme change.

    :spec: §5.3 — ThemeGateway.invalidate()
    """
    global _nag_hex_cache
    _nag_hex_cache = {}
    # Also reset Nags' own memo so nag_color() re-reads dic_colors.
    try:
        from Code.Nags import Nags as _Nags
        _Nags.xdic_colors = {}
    except Exception:
        _log.debug("ThemeGateway.invalidate: could not reset Nags.xdic_colors", exc_info=True)


def color(key: str, fallback: str = "#000000") -> str:
    """Return the hex colour for *key* from the active ``Code.dic_colors``.

    :param key:      Colour key, e.g. ``"CHROME_ACCENT"``.
    :param fallback: Returned when *key* is absent.
    :returns:        A ``#RRGGBB`` hex string.
    :spec: §5.3 — ThemeGateway.color()
    """
    import Code
    return Code.dic_colors.get(key, fallback)


def is_dark() -> bool:
    """Return ``True`` when the active theme declares ``IS_DARK=1``.

    :returns: Boolean dark-mode indicator.
    :spec: §5.3 — ThemeGateway.is_dark()
    """
    return color("IS_DARK", "0") == "1"


def nag_color(num: int) -> str:
    """Return the hex colour for NAG *num*.

    Delegates to ``Code.Nags.Nags.nag_color()`` but strips the ``QColor``
    wrapper and caches the result.  Calling this from a unit test that has
    populated ``Code.dic_colors`` is safe; calling it before app init is not.

    :param num: NAG number (1 = ``!``, 2 = ``?``, etc.).
    :returns:   A ``#RRGGBB`` hex string.
    :spec: §5.3 — ThemeGateway.nag_color()
    """
    if num in _nag_hex_cache:
        return _nag_hex_cache[num]
    try:
        from Code.Nags.Nags import nag_color as _nc
        qc = _nc(num)
        hex_val = qc.name() if hasattr(qc, "name") else str(qc)
        _nag_hex_cache[num] = hex_val
        return hex_val
    except Exception:
        _log.debug("ThemeGateway.nag_color(%d) failed", num, exc_info=True)
        return "#ffffff"


def active_style() -> str:
    """Return the active QSS style name from ``Code.configuration``.

    :returns: Style name string, e.g. ``"Modern Fritz"``.
    :spec: §5.3 — ThemeGateway.active_style()
    """
    try:
        import Code
        return Code.configuration.x_style_mode or ""
    except Exception:
        return ""
