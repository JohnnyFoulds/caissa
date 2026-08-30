"""
tests/unit/rpa/test_segment.py — cv2-tier tests for Vision/Segment.py.

All fixtures are synthetic PNGs drawn at test time with cv2 — nothing committed.
Auto-skipped when cv2 is absent or platform is offscreen (tests/conftest.py:16-33).

:spec: docs/features/rpa-design-vision/feature_spec.md §4 Tier-2
"""
import pytest

pytestmark = pytest.mark.rpa_cv


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_fill_regions_two_components_not_one_for_adjacent_fills():
    """fill_regions on a synthetic image with adjacent #ffffff fill and #ffffff glyphs
    must return two components (CC + min_px), not one. The global-bbox implementation
    provably fails this test — it was the error found on the real crop."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_glyph_boxes_auto_polarity_inverted_region():
    """glyph_boxes(polarity='auto') on a light-on-dark synthetic region finds the glyphs.
    Correction 2 regression guard: inverted polarity is the Home tab case."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_glyph_boxes_fixed_threshold_fails_inverted_region():
    """Companion: glyph_boxes with a fixed threshold of 150 finds NONE of the glyphs in
    the same inverted fixture. Pins the lesson to a test rather than to prose."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_ink_of_uses_local_fill_not_global():
    """ink_of(img, region, fill_hex='#252526') measures ink relative to the local fill,
    not a global dark-pixel predicate. Global approach reads the whole tab as ink."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_fill_of_classifies_gradient_v():
    """fill_of on a synthetic vertical ramp #252526->#363636 returns kind='gradient_v'
    with correct hex_start and hex_end."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_fill_of_gradient_visible_false_straddling_background():
    """fill_of with background_hex='#2d2d2d' on the #252526->#363636 ramp must return
    visible=False and visible_delta<=9. The mean-based rule would return True."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 3 — Segment.py not yet written")
def test_corner_of_measures_radius_from_arc_staircase():
    """corner_of on a synthetic anti-aliased rounded rect of known radius must return
    the correct radius_px and shows_owner for the notch outside the arc."""
    raise NotImplementedError
