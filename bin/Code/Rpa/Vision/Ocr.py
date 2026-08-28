"""
bin/Code/Rpa/Vision/Ocr.py — OCR phrase location for the Caissa RPA layer.

Uses ``pytesseract.image_to_data`` to locate multi-word phrases in a screenshot.
Words are grouped by ``(block_num, par_num, line_num)`` and matched with a sliding
window over each line so that multi-word labels ("Player name", "Window style") are
found as contiguous units rather than individual words.

**Pre-processing** — upscale 2× with ``INTER_CUBIC`` and convert to grayscale.
Tesseract is unreliable on 11–13 px UI text without upscaling.

**Channel order** — the input ndarray is RGB (from ``Screenshot.logical()``).  The
module converts to grayscale internally; no BGR conversion is needed.

:spec: FR-7, §9 (feature_spec.md)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_UPSCALE_FACTOR = 2


def find_phrase(
    screenshot: "Code.Rpa.Vision.Capture.Screenshot",  # type: ignore[name-defined]
    phrase: str,
    confidence_threshold: float = 50.0,
) -> list["Code.Rpa.Vision.Template.Match"]:  # type: ignore[name-defined]
    """Find all occurrences of *phrase* in *screenshot* using OCR.

    Words within *phrase* must appear consecutively on the same line in the OCR
    output.  The returned bounding box covers the entire phrase, in logical
    (DPR-1) screenshot coordinates.

    :param screenshot: Source :class:`~Code.Rpa.Vision.Capture.Screenshot`.
    :param phrase: One or more words to locate (case-insensitive).
    :param confidence_threshold: Minimum per-word Tesseract confidence (0–100).
    :returns: List of :class:`~Code.Rpa.Vision.Template.Match` sorted by confidence
        descending.  Confidence is the mean per-word score normalised to [0, 1].
    """
    import cv2
    import numpy as np
    import pytesseract

    from Code.Rpa.Types import Rect
    from Code.Rpa.Vision.Template import Match

    img = screenshot.logical()

    # Pre-process: 2× upscale + grayscale
    h, w = img.shape[:2]
    upscaled = cv2.resize(img, (w * _UPSCALE_FACTOR, h * _UPSCALE_FACTOR), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_RGB2GRAY)

    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

    words_lower = [w.lower() for w in phrase.split()]
    if not words_lower:
        return []

    # Group words into lines keyed by (block_num, par_num, line_num)
    lines: dict[tuple[int, int, int], list[dict]] = {}
    n = len(data["text"])
    for i in range(n):
        conf = int(data["conf"][i])
        text = data["text"][i].strip()
        if not text or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append({
            "text": text,
            "conf": conf,
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
        })

    matches: list[Match] = []
    target_len = len(words_lower)
    scale = _UPSCALE_FACTOR  # upscaled coords → logical coords

    for line_words in lines.values():
        line_texts = [w["text"].lower() for w in line_words]
        # Sliding window
        for start in range(len(line_texts) - target_len + 1):
            window = line_texts[start:start + target_len]
            if window != words_lower:
                continue
            chunk = line_words[start:start + target_len]
            conf_values = [w["conf"] for w in chunk]
            if any(c < confidence_threshold for c in conf_values):
                continue
            mean_conf = sum(conf_values) / len(conf_values)

            # Bounding box in upscaled coords; convert back to logical
            x1 = min(w["left"] for w in chunk)
            y1 = min(w["top"] for w in chunk)
            x2 = max(w["left"] + w["width"] for w in chunk)
            y2 = max(w["top"] + w["height"] for w in chunk)

            lx = round(x1 / scale)
            ly = round(y1 / scale)
            lw = max(1, round((x2 - x1) / scale))
            lh = max(1, round((y2 - y1) / scale))

            matches.append(Match(
                rect=Rect(x=lx, y=ly, w=lw, h=lh),
                confidence=round(mean_conf / 100.0, 4),
                scale=1.0,
            ))

    return sorted(matches, key=lambda m: m.confidence, reverse=True)
