"""
bin/Code/Rpa/Vision/Availability.py — Capability probe for the CV/OCR vision layer.

Lazily and safely checks whether ``cv2`` and ``pytesseract`` (+ the ``tesseract``
binary) are importable/runnable.  The probe result is cached at the module level
so it is executed at most once per process; it never raises.

Usage::

    from Code.Rpa.Vision.Availability import probe, AvailabilityFlags

    flags = probe()
    if flags.cv_available:
        ...

:spec: NFR-9, §9 (feature_spec.md)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_INSTALL_CV = "pip install -r requirements-rpa.txt"
_INSTALL_TESSERACT_MAC = "brew install tesseract"
_INSTALL_TESSERACT_LINUX = "apt install tesseract-ocr"


@dataclass(frozen=True)
class AvailabilityFlags:
    """Result of a capability probe.

    :param cv_available: ``True`` if ``cv2`` (OpenCV) is importable.
    :param ocr_available: ``True`` if both ``pytesseract`` and the ``tesseract``
        binary are available.
    :param reason: Human-readable explanation when either flag is ``False``,
        including the literal install command.
    """

    cv_available: bool
    ocr_available: bool
    reason: str = field(default="")


_cached: AvailabilityFlags | None = None


def probe() -> AvailabilityFlags:
    """Return cached capability flags; never raises.

    The probe is run at most once.  Subsequent calls return the same object.

    :returns: :class:`AvailabilityFlags` describing what is available.
    """
    global _cached
    if _cached is not None:
        return _cached

    cv_ok = False
    ocr_ok = False
    reasons: list[str] = []

    try:
        import cv2  # noqa: F401
        cv_ok = True
    except ImportError:
        reasons.append(f"cv2 not installed — {_INSTALL_CV}")
        logger.debug("cv2 not available: %s", _INSTALL_CV)

    if cv_ok:
        try:
            import pytesseract  # noqa: F401
            # Verify the binary is on PATH by asking for the version
            pytesseract.get_tesseract_version()
            ocr_ok = True
        except ImportError:
            reasons.append(f"pytesseract not installed — {_INSTALL_CV}")
            logger.debug("pytesseract not available: %s", _INSTALL_CV)
        except Exception as exc:
            # Binary missing or not executable
            reasons.append(
                f"tesseract binary not found — {_INSTALL_TESSERACT_MAC}"
                f" / {_INSTALL_TESSERACT_LINUX} (detail: {exc})"
            )
            logger.debug("tesseract binary unavailable: %s", exc)

    _cached = AvailabilityFlags(
        cv_available=cv_ok,
        ocr_available=ocr_ok,
        reason="; ".join(reasons),
    )
    return _cached


def _reset_cache() -> None:
    """Reset the probe cache.  For testing only."""
    global _cached
    _cached = None
