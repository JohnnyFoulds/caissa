"""
tests/unit/rpa/test_types.py — unit tests for Rpa/Types.py Rect methods (Phase 1).

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""
import pytest

pytestmark = pytest.mark.unit


def test_rect_intersects():
    """Rect.intersects returns True for overlapping rects and False for touching/disjoint."""
    from Code.Rpa.Types import Rect
    a = Rect(0, 0, 10, 10)
    b = Rect(5, 5, 10, 10)       # overlapping
    c = Rect(10, 0, 10, 10)      # touching (not overlapping — open interval)
    d = Rect(20, 20, 10, 10)     # disjoint
    assert a.intersects(b) is True
    assert b.intersects(a) is True
    assert a.intersects(c) is False
    assert a.intersects(d) is False


def test_rect_intersection():
    """Rect.intersection returns the clipped overlap rect, or None for disjoint rects."""
    from Code.Rpa.Types import Rect
    a = Rect(0, 0, 10, 10)
    b = Rect(5, 5, 10, 10)
    result = a.intersection(b)
    assert result == Rect(5, 5, 5, 5)
    assert a.intersection(Rect(20, 20, 5, 5)) is None


def test_rect_area():
    """Rect.area returns width * height and is zero for zero-width or zero-height rects."""
    from Code.Rpa.Types import Rect
    assert Rect(0, 0, 10, 20).area == 200
    assert Rect(5, 5, 0, 10).area == 0
    assert Rect(5, 5, 10, 0).area == 0


def test_rect_translate():
    """Rect.translate(dx, dy) returns a new Rect shifted by (dx, dy); original unchanged."""
    from Code.Rpa.Types import Rect
    original = Rect(10, 20, 30, 40)
    moved = original.translate(5, -3)
    assert moved == Rect(15, 17, 30, 40)
    assert original == Rect(10, 20, 30, 40)  # unchanged (frozen)


def test_rect_inset():
    """Rect.inset(n) returns a Rect shrunk by n pixels on all sides; clamps to zero."""
    from Code.Rpa.Types import Rect
    r = Rect(10, 10, 20, 20)
    assert r.inset(2) == Rect(12, 12, 16, 16)
    assert r.inset(20) == Rect(30, 30, 0, 0)   # clamped — no negative dimensions


def test_rect_contains_point():
    """Rect.contains_point(x, y) returns True iff the point is strictly inside the rect."""
    from Code.Rpa.Types import Rect
    r = Rect(10, 10, 20, 20)
    assert r.contains_point(15, 15) is True
    assert r.contains_point(10, 10) is True   # inclusive lower bound
    assert r.contains_point(29, 29) is True   # inclusive top of open interval
    assert r.contains_point(30, 10) is False  # exclusive right
    assert r.contains_point(10, 30) is False  # exclusive bottom
    assert r.contains_point(9, 10) is False
