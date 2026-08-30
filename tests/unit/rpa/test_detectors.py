"""
tests/unit/rpa/test_detectors.py — unit tests for Vision/Detectors.py.

Each detector gets a true-positive test AND a no-false-positive test.
All test cases use hand-written literal Scenes — no cv2, no screenshots.

:spec: docs/features/rpa-design-vision/feature_spec.md §2.2 FR-7, FR-8
"""
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# invisible_fill — Phase 2b
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_invisible_fill_fires_on_flat_palette_window():
    """invisible_fill fires when a node's fill hex equals its local background_hex
    (palette().window() case from WRibbon unselected tabs)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_invisible_fill_fires_on_gradient_straddling_background():
    """invisible_fill fires on a gradient_v fill whose midpoint equals the local
    background_hex (pane caption case: #252526->#363636 over #2d2d2d)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_invisible_fill_mean_rule_would_pass_gradient():
    """Companion to test_invisible_fill_fires_on_gradient_straddling_background.
    A mean-based visibility rule on the same gradient fixture must return True.
    This assertion pins the max-vs-mean decision to its cause."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# spacing_uniformity — Phase 2b
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_spacing_uniformity_fails_ribbon_perceived():
    """spacing_uniformity on the six-tab ribbon literal reports non_uniform on the
    perceived basis (spread 12,13,24,24,25 — 2.08×)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_spacing_uniformity_passes_notation_tabs():
    """spacing_uniformity on the five-tab notation literal reports uniform (all gaps 2).
    This is the wrong-predicate regression guard from correction 5: spacing IS uniform,
    the defect is that it should be zero, which uniformity cannot express."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# peer_adjacency — Phase 2b
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_peer_adjacency_fires_on_ancestor_seam():
    """peer_adjacency fires when Seam.shows_owner='ancestor' (gap shows grandparent
    background — a hole through the widget hierarchy)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_peer_adjacency_silent_on_parent_seam():
    """peer_adjacency is silent when Seam.shows_owner='parent' (a deliberate margin
    in the parent's own colour). Same pixel value, opposite verdicts."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_peer_adjacency_spacing_uniformity_silent_same_scene():
    """On the five-tab notation Scene where peer_adjacency fires (ancestor seams),
    spacing_uniformity must report 'uniform'. This paired assertion pins the lesson
    of correction 5: uniformity and should-be-zero are different predicates."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# surface_broken — Phase 2b
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_surface_broken_fires_four_breaks():
    """surface_broken on a tab_page Surface(tab[0]+notation_content) with 8px tl/tr
    corners, closed seam, and ΔE=2 fill returns exactly four breaks."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_surface_broken_corner_listed_first():
    """The corner break must be listed first in surface_broken.breaks — it is the
    defect you identified as the main problem (correction 6)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_surface_broken_indeterminate_not_ok_when_corners_not_measured():
    """When corners=() and 'corners' not in SceneNode.measured, surface_broken must
    report indeterminate for the corner slot, not 'ok'. N-RPAV-2 regression guard."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_surface_broken_zero_breaks_clean_surface():
    """surface_broken on a Surface with radius_px=0, open seam, and matching fill
    returns zero breaks."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# orphan_style_rule — Phase 2b
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_orphan_style_rule_fires_on_qtabwidget_pane():
    """orphan_style_rule fires on 'QTabWidget::pane' when no QTabWidget exists in the
    widget-type set. This is the live example: 8 theme files declare this rule;
    no QTabWidget is in the application."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Detectors.py not yet written")
def test_orphan_style_rule_silent_on_qtabbar_tab():
    """orphan_style_rule is silent on 'QTabBar::tab' when QTabBar IS present.
    No-false-positive guard."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# fill_extent — Phase 7 (deferred — kept as xfail to hold the name)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_fill_extent_silent_on_full_width_captions():
    """fill_extent must NOT fire on a four-caption Scene where width is CONSTANT 566
    against parents 566px wide. This is the false-positive regression guard for
    correction 4: asserting 'fill is text-sized' on full-width captions would be wrong."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Deferred detectors — Phase 7 stubs
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_contrast_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_missing_child_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_text_duplication_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_peer_divergence_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_edge_alignment_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_containment_fires():
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — deferred until a real query demands it")
def test_theme_blindness_fires():
    raise NotImplementedError
