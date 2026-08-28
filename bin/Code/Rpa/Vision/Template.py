"""
bin/Code/Rpa/Vision/Template.py — Template matching for the Caissa RPA layer.

Implements ``find_all()`` which locates all occurrences of a template PNG inside
a screenshot using OpenCV ``matchTemplate`` with ``TM_CCOEFF_NORMED``, greedy
non-maximum suppression (NMS) at IoU 0.3, and a multi-scale fallback.

**Channel order contract** — all arrays entering and leaving this module are in
**RGB** order.  ``cv2.matchTemplate`` is channel-agnostic (it computes a scalar
correlation), so channel order does not affect the match; but callers that pass BGR
inadvertently will still get correct bounding boxes, they just won't notice.

**Scale fallback** — matching runs at scale 1.0 first.  If the best score is below
``threshold``, it retries at `[0.95, 1.05, 0.90, 1.10]`.  A ``logger.warning`` is
emitted when a non-1.0 scale wins, indicating the stored template is stale.

:spec: FR-7, §9 (feature_spec.md)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_MULTI_SCALES = [0.95, 1.05, 0.90, 1.10]
_NMS_IOU_THRESHOLD = 0.3
_DEFAULT_THRESHOLD = 0.8


@dataclass(frozen=True)
class Match:
    """A single template match result in logical coordinates.

    :param rect: Bounding box in the logical-resolution screenshot coordinate space.
    :param confidence: Normalised match score in [0.0, 1.0].
    :param scale: The scale at which the template was matched (1.0 = exact size).
    """

    rect: "Code.Rpa.Types.Rect"  # type: ignore[name-defined]
    confidence: float
    scale: float = 1.0


def _iou(a, b) -> float:
    """Compute Intersection-over-Union of two ``(x, y, w, h)`` tuples."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _nms(candidates: list[tuple[float, tuple[int, int, int, int]]]) -> list[tuple[float, tuple[int, int, int, int]]]:
    """Greedy NMS: sort by score desc, suppress overlapping boxes at IoU > 0.3."""
    candidates = sorted(candidates, key=lambda c: c[0], reverse=True)
    kept = []
    for score, box in candidates:
        if all(_iou(box, kb) <= _NMS_IOU_THRESHOLD for _, kb in kept):
            kept.append((score, box))
    return kept


def _match_at_scale(
    haystack: "numpy.ndarray",
    needle: "numpy.ndarray",
    scale: float,
    threshold: float,
) -> list[tuple[float, tuple[int, int, int, int]]]:
    """Run ``matchTemplate`` at *scale*, returning ``(score, (x, y, w, h))`` pairs above threshold."""
    import cv2
    import numpy as np

    h_orig, w_orig = needle.shape[:2]
    if scale != 1.0:
        nw = max(1, round(w_orig * scale))
        nh = max(1, round(h_orig * scale))
        needle_s = cv2.resize(needle, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
    else:
        needle_s = needle
        nw, nh = w_orig, h_orig

    if haystack.shape[0] < nh or haystack.shape[1] < nw:
        return []

    result = cv2.matchTemplate(haystack, needle_s, cv2.TM_CCOEFF_NORMED)
    locs = np.where(result >= threshold)
    hits = []
    for y, x in zip(locs[0], locs[1]):
        hits.append((float(result[y, x]), (int(x), int(y), int(nw), int(nh))))
    return hits


def find_all(
    screenshot: "Code.Rpa.Vision.Capture.Screenshot",  # type: ignore[name-defined]
    template: "numpy.ndarray",
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[Match]:
    """Find all occurrences of *template* in *screenshot*.

    Runs ``matchTemplate`` at scale 1.0 first; if no match exceeds *threshold*,
    retries at ``[0.95, 1.05, 0.90, 1.10]`` and emits ``logger.warning`` when a
    non-unit scale wins.

    :param screenshot: Source :class:`~Code.Rpa.Vision.Capture.Screenshot`; matching
        runs on ``screenshot.logical()`` so all returned rects are in logical coords.
    :param template: H×W×3 uint8 RGB ndarray of the template, authored at DPR-1.
    :param threshold: Minimum ``TM_CCOEFF_NORMED`` score (default 0.8).
    :returns: List of :class:`Match` sorted by confidence descending.
    """
    from Code.Rpa.Types import Rect

    img = screenshot.logical()

    # Scale 1.0 first
    hits = _match_at_scale(img, template, 1.0, threshold)
    winning_scale = 1.0

    if not hits:
        for scale in _MULTI_SCALES:
            hits = _match_at_scale(img, template, scale, threshold)
            if hits:
                winning_scale = scale
                logger.warning(
                    "Template matched at scale %.2f — the stored template may be stale",
                    scale,
                )
                break

    if not hits:
        return []

    kept = _nms(hits)
    return [
        Match(
            rect=Rect(x=box[0], y=box[1], w=box[2], h=box[3]),
            confidence=round(score, 4),
            scale=winning_scale,
        )
        for score, box in sorted(kept, key=lambda c: c[0], reverse=True)
    ]
