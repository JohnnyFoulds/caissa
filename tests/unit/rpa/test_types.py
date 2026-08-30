"""
tests/unit/rpa/test_types.py — unit tests for Rpa/Types.py Rect methods (Phase 1).

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_intersects():
    """Rect.intersects returns True for overlapping rects and False for touching/disjoint."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_intersection():
    """Rect.intersection returns the clipped overlap rect, or None for disjoint rects."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_area():
    """Rect.area returns width * height and is zero for zero-width or zero-height rects."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_translate():
    """Rect.translate(dx, dy) returns a new Rect shifted by (dx, dy); original unchanged."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_inset():
    """Rect.inset(n) returns a Rect shrunk by n pixels on all sides; negative n expands."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Rect methods not yet written")
def test_rect_contains_point():
    """Rect.contains_point(x, y) returns True iff the point is strictly inside the rect."""
    raise NotImplementedError
