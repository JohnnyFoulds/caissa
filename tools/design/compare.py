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


def mean_abs_diff_full(a: Image.Image, b: Image.Image) -> float:
    """Full-resolution mean absolute RGB difference between two same-size images.

    No resize — caller must ensure sizes match.  Raises ``ValueError`` if they differ.

    :param a: First image.
    :param b: Second image.
    :returns: Mean absolute difference per channel, 0–255.
    :raises ValueError: If image sizes differ.
    """
    a = a.convert("RGB")
    b = b.convert("RGB")
    if a.size != b.size:
        raise ValueError(f"Size mismatch: {a.size} vs {b.size}")
    diff = ImageChops.difference(a, b)
    pixels = list(diff.getdata())
    total = sum(sum(ch for ch in px) / len(px) for px in pixels)
    return total / len(pixels)


def chrome_mask(ref: Image.Image, tol: int = 8) -> Image.Image:
    """Build a 1-bit mask of chrome pixels in *ref*.

    A pixel is "chrome" if its RGB distance to any of the three Fritz palette
    colours (``#efeff2``, ``#cccedb``, ``#007acc``) is within *tol*.  Icon
    artwork pixels are excluded, which lets ``masked_mean_diff`` score style
    fidelity independently of the icon content.

    :param ref: The Fritz reference image (RGB).
    :param tol: Maximum Euclidean distance from a palette colour (default 8).
    :returns: ``"1"`` mode PIL image — white = chrome, black = artwork.
    """
    import math

    PALETTE = [
        (0xef, 0xef, 0xf2),  # background
        (0xcc, 0xce, 0xdb),  # separator / border
        (0x00, 0x7a, 0xcc),  # accent
    ]
    ref = ref.convert("RGB")
    px = ref.load()
    w, h = ref.size
    mask = Image.new("1", (w, h), 0)
    mx = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            for cr, cg, cb in PALETTE:
                d = math.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
                if d <= tol:
                    mx[x, y] = 1
                    break
    return mask


def masked_mean_diff(a: Image.Image, b: Image.Image, mask: Image.Image) -> float:
    """Mean absolute RGB difference restricted to mask-white pixels.

    Use ``chrome_mask(ref)`` to get the mask.  This is the *style score*: it
    measures chrome fidelity where Fritz has chrome and excludes icon artwork.

    :param a: First image (same size as *b* and *mask*).
    :param b: Second image.
    :param mask: ``"1"`` mode image — white pixels are included in the diff.
    :returns: Mean absolute difference over the masked region, 0–255.
              Returns 255.0 if no mask pixels are set.
    """
    a = a.convert("RGB")
    b = b.convert("RGB")
    a_px = a.load()
    b_px = b.load()
    m_px = mask.load()
    w, h = a.size
    total = 0.0
    count = 0
    for y in range(h):
        for x in range(w):
            if m_px[x, y]:
                ra, ga, ba = a_px[x, y]
                rb, gb, bb = b_px[x, y]
                total += (abs(ra - rb) + abs(ga - gb) + abs(ba - bb)) / 3.0
                count += 1
    return (total / count) if count else 255.0


def row_ink_profile(img: Image.Image, bg: tuple = (0xef, 0xef, 0xf2)) -> list:
    """Per-row count of non-background pixels.

    Used to compare band boundaries: peaks correspond to tab text, rule lines,
    button icons, and captions; troughs correspond to empty padding rows.

    :param img: Source image (RGB).
    :param bg: Background colour as ``(R, G, B)`` tuple (default ``#efeff2``).
    :returns: List of length ``img.height`` with the non-bg pixel count per row.
    """
    img = img.convert("RGB")
    px = img.load()
    w, h = img.size
    return [sum(1 for x in range(w) if px[x, y] != bg) for y in range(h)]


def diff_heatmap(a: Image.Image, b: Image.Image) -> Image.Image:
    """Amplified absolute-difference image for visual review.

    Resizes *b* to match *a* if they differ in size.  Each channel difference is
    multiplied by 4 and clamped to 0–255, so a 10-unit difference shows as 40
    (clearly visible) rather than a barely-perceptible shadow.

    :param a: Reference image.
    :param b: Candidate image.
    :returns: RGB heatmap — black where identical, bright where different.
    """
    a = a.convert("RGB")
    b = b.convert("RGB").resize(a.size, Image.LANCZOS)
    diff = ImageChops.difference(a, b)
    # Amplify 4× and clamp via point()
    amplified = diff.point(lambda v: min(255, v * 4))
    return amplified
