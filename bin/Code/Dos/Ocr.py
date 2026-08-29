"""
bin/Code/Dos/Ocr.py — OCR utilities for DOSBox-X screen images.

Wraps Tesseract to locate text in low-resolution DOS screens.  DOS games
render large, blocky fonts on uniform backgrounds; pre-scaling the image 2×
before OCR improves recognition significantly.

All public functions accept :class:`PIL.Image.Image` objects and return
coordinates in the **original image's** pixel space (not the scaled space).

Typical usage::

    from Code.Dos.Ocr import find_text_bounds, find_all_text

    img = driver.screenshot()
    bounds = find_text_bounds(img, "2D Board")
    if bounds:
        cx, cy = bounds[0] + bounds[2] // 2, bounds[1] + bounds[3] // 2
        # cx, cy are window-relative for the driver

**Purity tier: adapter** — imports stdlib + pytesseract + PIL.  No Qt.

:purity: adapter
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)

# Tesseract PSM 11 = sparse text with OSD; works well for single menu items.
# PSM 6 = uniform block of text; better for multi-line menus.
_PSM_SPARSE = "11"
_PSM_BLOCK = "6"
_SCALE = 3      # upscale factor before OCR — improves accuracy on pixelated fonts


def _upscale(img: "Image") -> "Image":
    """Return a copy of *img* scaled up by *_SCALE* using nearest-neighbour."""
    from PIL import Image as PILImage
    w, h = img.size
    return img.resize((w * _SCALE, h * _SCALE), PILImage.NEAREST)


def _preprocess(img: "Image") -> "Image":
    """Convert to greyscale and upscale for better Tesseract accuracy."""
    return _upscale(img.convert("L"))


def _run_tesseract_tsv(img: "Image", psm: str = _PSM_BLOCK) -> list[dict]:
    """Run Tesseract on *img* and return a list of word records.

    Each record is a dict with keys: ``left``, ``top``, ``width``, ``height``,
    ``conf``, ``text`` — all in **scaled** image pixel coordinates.

    :param img: PIL Image to OCR.
    :param psm: Tesseract page-segmentation mode string (default ``"6"``).
    :returns: List of word dicts from the TSV output.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    try:
        img.save(tmp_path)
        result = subprocess.run(
            ["tesseract", tmp_path, "stdout", "--psm", psm, "tsv"],
            capture_output=True,
            timeout=10,
        )
        lines = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if len(lines) < 2:
        return []

    headers = lines[0].split("\t")
    records = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < len(headers):
            continue
        row = dict(zip(headers, parts))
        text = row.get("text", "").strip()
        if not text:
            continue
        try:
            records.append({
                "left":   int(row["left"]),
                "top":    int(row["top"]),
                "width":  int(row["width"]),
                "height": int(row["height"]),
                "conf":   float(row.get("conf", 0)),
                "text":   text,
            })
        except (KeyError, ValueError):
            continue
    return records


def _normalize(s: str) -> str:
    """Strip non-alphanumeric chars and lowercase for fuzzy matching."""
    return "".join(c for c in s.lower() if c.isalnum() or c.isspace()).strip()


def find_text_bounds(
    img: "Image",
    text: str,
    *,
    psm: str = _PSM_BLOCK,
    min_conf: float = 10.0,
    fuzzy: bool = True,
) -> tuple[int, int, int, int] | None:
    """Return the bounding box of *text* in *img*, or ``None`` if not found.

    The search is **case-insensitive** and matches whole words joined by
    spaces.  Bounding boxes are returned in the **original image's** pixel
    space.

    :param img: PIL Image to search.
    :param text: Text to locate (e.g. ``"2D Board"``).
    :param psm: Tesseract PSM mode string.
    :param min_conf: Minimum Tesseract confidence (0–100) to accept a word.
    :param fuzzy: If ``True`` (default), normalise OCR noise before matching
        (strips non-alphanumeric chars so ``"#0D"`` matches ``"2D"``).
    :returns: ``(left, top, width, height)`` in original image pixels, or
        ``None`` if not found.
    """
    scaled = _preprocess(img)
    records = _run_tesseract_tsv(scaled, psm=psm)

    needle_words = text.lower().split()
    if not needle_words:
        return None

    accepted = [r for r in records if r["conf"] >= min_conf]

    def _match_word(needle_word: str, ocr_word: str) -> bool:
        if fuzzy:
            return _normalize(needle_word) in _normalize(ocr_word)
        return needle_word in ocr_word.lower()

    # Single-word search
    if len(needle_words) == 1:
        for r in accepted:
            if _match_word(needle_words[0], r["text"]):
                return _unscale_box(r, _SCALE)
        return None

    # Multi-word: slide a window over consecutive tokens
    for i in range(len(accepted) - len(needle_words) + 1):
        group = accepted[i : i + len(needle_words)]
        if all(_match_word(needle_words[j], group[j]["text"]) for j in range(len(needle_words))):
            left   = min(r["left"]  for r in group)
            top    = min(r["top"]   for r in group)
            right  = max(r["left"] + r["width"]  for r in group)
            bottom = max(r["top"]  + r["height"] for r in group)
            return _unscale_box(
                {"left": left, "top": top,
                 "width": right - left, "height": bottom - top},
                _SCALE,
            )
    return None


def find_nth_text_bounds(
    img: "Image",
    text: str,
    n: int = 1,
    *,
    psm: str = _PSM_BLOCK,
    min_conf: float = 10.0,
) -> tuple[int, int, int, int] | None:
    """Return the bounding box of the *n*-th occurrence of *text*.

    Occurrences are ordered top-to-bottom.  Useful when the same word (e.g.
    ``"Board"``) appears multiple times and you need a specific row.

    :param img: PIL Image to search.
    :param text: Word to locate.
    :param n: 1-based occurrence index (default 1 = first).
    :param psm: Tesseract PSM mode.
    :param min_conf: Minimum OCR confidence.
    :returns: ``(left, top, width, height)`` in original image pixels, or
        ``None`` if fewer than *n* occurrences exist.
    """
    scaled = _preprocess(img)
    records = _run_tesseract_tsv(scaled, psm=psm)
    needle = _normalize(text)
    hits = sorted(
        [r for r in records if r["conf"] >= min_conf and needle in _normalize(r["text"])],
        key=lambda r: r["top"],
    )
    if len(hits) < n:
        return None
    return _unscale_box(hits[n - 1], _SCALE)


def find_all_text(
    img: "Image",
    *,
    psm: str = _PSM_BLOCK,
    min_conf: float = 10.0,
) -> list[tuple[str, int, int, int, int]]:
    """Return all recognised text fragments with their bounding boxes.

    :param img: PIL Image to OCR.
    :param psm: Tesseract PSM mode.
    :param min_conf: Minimum confidence threshold.
    :returns: List of ``(text, left, top, width, height)`` tuples in
        original image pixels.
    """
    scaled = _preprocess(img)
    records = _run_tesseract_tsv(scaled, psm=psm)
    result = []
    for r in records:
        if r["conf"] < min_conf:
            continue
        l, t, w, h = _unscale_box(r, _SCALE)
        result.append((r["text"], l, t, w, h))
    return result


def _unscale_box(
    r: dict, scale: int
) -> tuple[int, int, int, int]:
    """Convert scaled pixel coordinates back to original image coordinates."""
    return (
        r["left"]   // scale,
        r["top"]    // scale,
        r["width"]  // scale,
        r["height"] // scale,
    )
