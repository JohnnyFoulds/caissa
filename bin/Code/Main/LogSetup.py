"""
bin/Code/Main/LogSetup.py — Application logging configuration.

Called **once** from the application entry point (``LucasChessGui.py``) before any
module logs.  RPA code and all other Caissa modules must never call
``logging.basicConfig`` or modify the root logger directly — they call
``logging.getLogger(__name__)`` and let the entry point decide the handler and level.

Usage::

    # In LucasChessGui.py (or equivalent entry point):
    from Code.Main.LogSetup import configure
    configure()

:spec: §3 (implementation_plan.md Session 1-B)
"""

import logging
import os

_configured = False

_DEFAULT_LEVEL = logging.WARNING
_ENV_VAR = "CAISSA_LOG_LEVEL"


def configure(level: str | int | None = None) -> None:
    """Configure the root logger.  No-op if called more than once.

    When *level* is ``None``, reads ``CAISSA_LOG_LEVEL`` from the environment.
    Falls back to ``WARNING`` if the variable is absent or invalid.

    A ``StreamHandler`` writing to stderr is added when no handlers are present on
    the root logger.  The format includes the logger name so per-module loggers are
    identifiable in the output.

    :param level: Explicit log level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
        ``"ERROR"``, ``"CRITICAL"``) or integer constant (``logging.DEBUG``, etc.).
        ``None`` reads ``CAISSA_LOG_LEVEL``.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()

    if level is None:
        env_val = os.environ.get(_ENV_VAR, "")
        if env_val:
            numeric = getattr(logging, env_val.upper(), None)
            if isinstance(numeric, int):
                level = numeric
            else:
                logging.getLogger(__name__).warning(
                    "Unknown CAISSA_LOG_LEVEL=%r; falling back to WARNING", env_val
                )
                level = _DEFAULT_LEVEL
        else:
            level = _DEFAULT_LEVEL

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)

    root.setLevel(level)
    _configured = True


def reset() -> None:
    """Reset the configured flag.  **Test-only** — do not call in production code.

    Allows unit tests to re-invoke ``configure()`` with different parameters without
    state leaking between tests.
    """
    global _configured
    _configured = False
