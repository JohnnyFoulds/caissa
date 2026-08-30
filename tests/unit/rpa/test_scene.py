"""
tests/unit/rpa/test_scene.py — unit tests for Vision/Scene.py primitives.

:spec: docs/features/rpa-design-vision/feature_spec.md §5
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Scene.py not yet written")
def test_scene_node_measured_field_distinguishes_not_measured_from_absent():
    """SceneNode with corners=() and measured not containing 'corners' must report
    indeterminate, not passing, for corner checks."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Scene.py not yet written")
def test_fill_gradient_visible_uses_max_not_mean():
    """Fill with gradient #252526->#363636 over background #2d2d2d must return
    visible=False with visible_delta<=9. Mean-based rule would return True."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Scene.py not yet written")
def test_fill_visible_false_for_palette_window_match():
    """Fill hex equal to background_hex must return visible=False."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 2 — Scene.py not yet written")
def test_to_ascii_includes_not_measured_line():
    """Scene.to_ascii(verbosity='full') must print 'not measured:' for any property
    absent from SceneNode.measured."""
    raise NotImplementedError
