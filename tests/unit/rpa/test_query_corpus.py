"""
tests/unit/rpa/test_query_corpus.py — integration tests for the query corpus (Phase 6).

Each test corresponds to a named query in docs/features/rpa-design-vision/feature_spec.md
§10 FR-15. CV-dependent tests carry the rpa_cv marker too.

:spec: docs/features/rpa-design-vision/feature_spec.md §10 FR-15
"""
import pytest

pytestmark = pytest.mark.rpa_cv


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 — query corpus not yet written")
def test_query_corpus_ribbon_tab_spacing():
    """Q1: 'Are the ribbon tab spacings uniform?' on a live capture must report
    non_uniform with perceived basis, the spread values, and no false positive
    against the notation tabs (which are uniform)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 — query corpus not yet written")
def test_query_corpus_side_panel_captions():
    """Q2: 'Why are the side panel captions hard to read?' must surface the
    invisible_fill finding for the gradient-over-background case — not rank
    contrast ahead of fill_visibility."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 — query corpus not yet written")
def test_query_corpus_notation_tab_group():
    """Q3: 'What is wrong with the notation tab group?' must surface peer_adjacency
    (ancestor seams) and NOT fire spacing_uniformity. Paired assertion pins the
    correction-5 lesson to a corpus test rather than just to unit stubs."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 6 — design verify workflow not yet written")
def test_design_verify_workflow_passes_dry_run():
    """design_verify --dry-run must exit 0 and emit a structured JSON report with
    'findings' and 'known_deviations' keys. A non-zero exit in dry-run means the
    verify pipeline is broken, not that design is bad."""
    raise NotImplementedError
