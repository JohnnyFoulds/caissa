"""
Adapter: read/write access to Fritz-relevant ``Code.configuration`` keys.

All Fritz widgets that previously read ``configuration.x_*`` directly now use
this module so that the pure models can be tested against a fake config.

Purity tier: **Adapter** — imports ``Code.*`` but no Qt.

:spec: §5.3, Phase 1 (feature_spec.md)
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def pgn_width() -> int:
    """Return the persisted right-column PGN panel width.

    :returns: Width in pixels.
    :spec: §5.3 — ConfigGateway.pgn_width()
    """
    import Code
    return int(Code.configuration.x_pgn_width or 400)


def with_figurines() -> bool:
    """Return whether figurine glyphs are enabled in the notation column.

    :returns: Boolean.
    :spec: §5.3 — ConfigGateway.with_figurines()
    """
    import Code
    return bool(Code.configuration.x_pgn_withfigurines)


def width_piece() -> int:
    """Return the persisted board square side in pixels.

    :returns: Integer, typically 12–200.
    :spec: §5.3 — ConfigGateway.width_piece()
    """
    import Code
    return int(Code.configuration.x_anchoPieza or 48)


def ui_mode() -> str:
    """Return the active UI mode name.

    :returns: Mode name string, e.g. ``"Modern Fritz"``.
    :spec: §5.3 — ConfigGateway.ui_mode()
    """
    import Code
    return str(Code.configuration.x_ui_mode or "")


def set_width_piece(value: int, *, persist: bool = False) -> None:
    """Set the board square side in pixels.

    :param value:   New width in pixels.
    :param persist: When ``True`` writes ``guardaEnDisco()``.  The Fritz
                    fit path always passes ``False`` so the persisted user
                    preference is never overwritten by a window resize.
    :spec: §5.3 — ConfigGateway.set_width_piece()
    """
    import Code
    Code.configuration.x_anchoPieza = value
    if persist:
        try:
            Code.configuration.guardaEnDisco()
        except Exception:
            _log.error("ConfigGateway.set_width_piece: guardaEnDisco failed", exc_info=True)
