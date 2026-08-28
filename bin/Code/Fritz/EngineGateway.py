"""
bin/Code/Fritz/EngineGateway.py — Adapter over ``WAnalysisBar.mrm``.

The only impure module in the Fritz eval path: it reads Qt widget state from
``Code.procesador``.  Every caller that needs current engine data should go
through this rather than accessing ``analysis_bar.mrm`` directly.

:spec: §5.3 (EngineGateway)
"""

from __future__ import annotations

import logging

import Code

_log = logging.getLogger(__name__)


def latest_analysis():
    """Return the current ``MultiEngineResponse``, or ``None``.

    Traverses ``Code.procesador → main_window → base → analysis_bar → mrm``.
    Returns ``None`` if any segment of that chain is absent or raises.

    :returns: A ``MultiEngineResponse`` instance, or ``None``.
    :spec: §5.3 (EngineGateway)
    """
    try:
        mw = Code.procesador.main_window
        bar = mw.base.analysis_bar
        if not getattr(bar, "activated", False):
            return None
        return getattr(bar, "mrm", None)
    except Exception:
        _log.debug("EngineGateway.latest_analysis: access failed", exc_info=True)
        return None
