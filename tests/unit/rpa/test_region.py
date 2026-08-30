"""
tests/unit/rpa/test_region.py — unit tests for Vision/Region.py.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Resolve.resolve_all not yet written")
def test_resolve_all_returns_list_not_single():
    """Resolve.resolve_all(phrases, ...) must return a list even when given a single phrase.
    Callers must not have to special-case the one-phrase case."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 1 — Region.flatten not yet written")
def test_flatten_produces_absolute_rects_for_deeply_nested_widget():
    """Region.flatten on a 4-deep synthetic tree must return capture-absolute rects
    for every node, with parent offsets accumulated correctly. A shallow test passes
    even when offset accumulation is wrong; this test must use depth >= 4."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Region.resolve_phrase not yet written")
def test_locate_phrase_resolves_side_panel():
    """resolve_phrase('the side panel', ...) must resolve to objectName='WFritzRightCol'
    with source='objectname', not a geometric fallback."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2b — Region.resolve_phrase not yet written")
def test_locate_phrase_returns_none_not_guess_on_unknown():
    """resolve_phrase with a phrase not in the lexicon and no matching objectName must
    return None, never guess a region. A wrong region answers a different question."""
    raise NotImplementedError
