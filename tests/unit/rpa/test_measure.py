"""
tests/unit/rpa/test_measure.py — unit tests for Vision/Measure.py.

:spec: docs/features/rpa-design-vision/feature_spec.md §5
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_gaps_all_bases_ribbon_six_tab():
    """Six-tab literal: widget gaps all 0, fill gaps mostly undefined, ink uniform,
    perceived [12,13,24,24,25]."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_perceived_gaps_ribbon_six_tab_nonuniform():
    """perceived_gaps on the six-tab ribbon literal returns [12,13,24,24,25] non_uniform
    with a 2.08× spread."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_widget_gaps_ribbon_six_tab_uniform():
    """gaps(basis='widget') on the same six-tab literal returns [0,0,0,0,0] uniform.
    Companion to test_perceived_gaps_ribbon_six_tab_nonuniform — both must be asserted
    in a test so the per-basis distinction cannot be silently collapsed."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_seam_shows_owner_ancestor_vs_parent():
    """seam_owner('hex', node, ancestors) returns 'ancestor' when hex matches a
    grandparent fill, 'parent' when it matches the direct parent. Same pixel value,
    opposite verdicts."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_surface_breaks_four_breaks_corner_first():
    """surface_breaks on a tab_page Surface with 8px corner, closed seam, and ΔE=2 fill
    returns exactly four breaks with the corner break listed first."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_surface_breaks_zero_when_clean():
    """surface_breaks on a Surface with radius=0, open seam, and matching fill returns
    an empty breaks tuple."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Measure.py not yet written")
def test_surface_breaks_indeterminate_when_corners_not_measured():
    """surface_breaks when corners=() and 'corners' not in SceneNode.measured must
    return a break of 'corner_indeterminate', not zero breaks. N-RPAV-2."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Report.py not yet written")
def test_report_diff_joins_on_node_id():
    """Report.diff(before, after) must join on node_id, not position. Renaming a node
    id must show as removed+added, not as a modification."""
    raise NotImplementedError
