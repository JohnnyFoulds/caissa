"""
tools/design/compare.py — image comparison helpers.

Lifted from tests/test_sidebar_icon_consistency.py so there is one
implementation.  Both that test file and review.py import from here.

:spec: §0.4, Phase 0 (feature_spec.md)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops


def images_mean_diff(a: Image.Image, b: Image.Image, size: int = 32) -> float:
    """Mean absolute pixel difference between two images (0–255).

    Both images are resized to ``size × size`` with LANCZOS before comparison,
    so different-resolution captures of the same scene produce a meaningful score.

    :param a: First image.
    :param b: Second image.
    :param size: Comparison resolution (default 32).
    :returns: Mean absolute difference per channel, 0 (identical) – 255 (opposite).
    """
    a = a.convert("RGB").resize((size, size), Image.LANCZOS)
    b = b.convert("RGB").resize((size, size), Image.LANCZOS)
    diff = ImageChops.difference(a, b)
    pixels = list(diff.getdata())
    total = sum(sum(ch for ch in px) / len(px) for px in pixels)
    return total / len(pixels)


def crop_button(screenshot_path: str | Path, btn: dict, dpr: float) -> Image.Image:
    """Crop one button's region from a screenshot.

    :param screenshot_path: Path to the PNG screenshot.
    :param btn: Dict with ``x``, ``y``, ``width``, ``height`` in logical pixels
                (window-relative).
    :param dpr: Device pixel ratio (2 on Retina, 1 on standard).
    :returns: Cropped PIL image.
    """
    img = Image.open(screenshot_path)
    scale = round(dpr)
    left   = int(btn["x"]      * scale)
    top    = int(btn["y"]      * scale)
    right  = left + int(btn["width"]  * scale)
    bottom = top  + int(btn["height"] * scale)
    return img.crop((left, top, right, bottom))


def crop_region(img: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    """Crop a fixed region from an image (logical pixel coordinates).

    :param img: Source PIL image.
    :param x: Left edge.
    :param y: Top edge.
    :param w: Width.
    :param h: Height.
    :returns: Cropped PIL image.
    """
    return img.crop((x, y, x + w, y + h))


def score_label(diff: float) -> str:
    """Return a short human-readable label for a mean-diff score.

    :param diff: Mean absolute difference (0–255).
    :returns: One of ``"identical"``, ``"close"``, ``"similar"``, ``"different"``.
    """
    if diff < 5:
        return "identical"
    if diff < 20:
        return "close"
    if diff < 50:
        return "similar"
    return "different"
