"""
bin/Code/Retro/Cpus/Availability.py — Unicorn availability probe.

Provides a cheap import-time check so callers can give an actionable error
message before any emulation is attempted, rather than a bare ``ImportError``
buried in a traceback.

No ``Cpu`` import, no third-party imports at module level.

:spec: feature_spec.md §5
"""

from __future__ import annotations


def is_available() -> bool:
    """Return ``True`` if the ``unicorn`` package is importable.

    :return: ``True`` when unicorn is installed and importable; ``False`` otherwise.
    """
    try:
        import unicorn  # noqa: F401
        return True
    except ImportError:
        return False


def require() -> None:
    """Raise :class:`~Code.Retro.Errors.EmulatorUnavailableError` if unicorn is absent.

    Call this at the top of any function that requires the real emulator, so the
    user gets an actionable install message rather than a bare ``ImportError``.

    :raises EmulatorUnavailableError: When unicorn is not installed.
    """
    if not is_available():
        from Code.Retro.Errors import EmulatorUnavailableError
        raise EmulatorUnavailableError()
