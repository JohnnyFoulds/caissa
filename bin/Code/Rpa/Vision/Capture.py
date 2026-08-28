"""
bin/Code/Rpa/Vision/Capture.py — Widget-to-ndarray capture for the Caissa RPA layer.

This module is **Qt-touching** — it may import PySide6.  All other Vision modules
import only ``numpy`` and ``cv2``.

The ``Screenshot`` dataclass wraps a NumPy RGB ndarray and carries the device pixel
ratio (DPR) so that callers can normalise to logical (DPR-1) coordinates.

Two implementation notes that would surprise a reader:

* **``bytesPerLine()`` row padding** — Qt pads each scanline to a 4-byte boundary.
  A naïve ``frombuffer(…).reshape(h, w, 3)`` shears the image for odd widths.  The
  fix is to reshape on ``bytesPerLine`` and slice out the live pixels afterwards.

* **Channel order** — Qt's ``Format_RGB888`` is already R-G-B, so no ``cvtColor``
  call is needed.  Everything inside ``Vision/`` must stay RGB; callers that need
  BGR for ``cv2`` functions are responsible for converting at the call site.

:spec: FR-7, §9 (feature_spec.md) — N-RPA-2 (only Qt-touching class in Vision/).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)


@dataclass
class Screenshot:
    """A widget capture expressed as a NumPy RGB ndarray.

    :param rgb: H×W×3 uint8 array in **RGB** channel order at physical (DPR) resolution.
    :param dpr: Device pixel ratio of the source widget.
    """

    rgb: "numpy.ndarray"  # noqa: F821 — forward reference; numpy imported lazily below
    dpr: float

    def logical(self) -> "numpy.ndarray":
        """Return the screenshot resized to logical (DPR-1) coordinates.

        Uses ``INTER_AREA`` — the correct filter for downscaling — so the output
        matches what a DPR-1 capture would look like.  When ``dpr == 1.0`` the
        original array is returned unchanged.

        :returns: H×W×3 uint8 RGB ndarray at logical pixel resolution.
        """
        import cv2
        import numpy as np

        if abs(self.dpr - 1.0) < 1e-6:
            return self.rgb

        h, w = self.rgb.shape[:2]
        lw = max(1, round(w / self.dpr))
        lh = max(1, round(h / self.dpr))
        return cv2.resize(self.rgb, (lw, lh), interpolation=cv2.INTER_AREA)


def grab(widget) -> Screenshot:
    """Capture *widget* as an RGB :class:`Screenshot`.

    Handles ``bytesPerLine()`` row padding and guarantees RGB channel order.

    :param widget: A :class:`PySide6.QtWidgets.QWidget` instance.
    :returns: :class:`Screenshot` at the widget's physical (DPR) resolution.
    :raises ImportError: If ``numpy`` is not installed.
    """
    import numpy as np

    pixmap = widget.grab()
    dpr = pixmap.devicePixelRatio()

    # Convert to Format_RGB888 — guaranteed no alpha, no padding quirks
    qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)

    w = qimage.width()
    h = qimage.height()
    bpl = qimage.bytesPerLine()  # may be > w * 3 on odd widths (4-byte alignment)

    ptr = qimage.constBits()
    # frombuffer wraps the Qt memory; copy() makes it independent (Qt may free it)
    buf = np.frombuffer(ptr, dtype=np.uint8).copy()

    if bpl == w * 3:
        rgb = buf.reshape(h, w, 3)
    else:
        # Reshape on bpl, then slice to remove padding bytes from each row
        rgb = buf.reshape(h, bpl)[:, : w * 3].reshape(h, w, 3)

    return Screenshot(rgb=rgb, dpr=float(dpr))
