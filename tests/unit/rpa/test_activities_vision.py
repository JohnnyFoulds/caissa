"""
tests/unit/rpa/test_activities_vision.py — unit tests for RPA Activities in Vision/.

Tests the six activities: DescribeScene, LocatePhrase, MeasureGaps, DetectIssues,
AnnotateCapture, InspectStyle. Also the three rpa_* verb wrappers.

:spec: docs/features/rpa-design-vision/feature_spec.md §7 FR-10, FR-11
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 — DescribeScene Activity not yet written")
def test_describe_scene_degrades_gracefully_no_screenshot():
    """DescribeScene.execute() must return a Scene with zero nodes and
    scene.capture_path=None when no screenshot is available, not raise."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 — DescribeScene Activity not yet written")
def test_describe_scene_warnings_when_cv_unavailable():
    """DescribeScene.execute() with cv2 absent from sys.modules must populate
    scene.warnings with N-RPAV-1 and N-RPA-9 notices, not silently omit measurements."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 — rpa_describe verb not yet written")
def test_rpa_describe_returns_report_id_immediately():
    """rpa_describe() must return a report_id within 200 ms even when the full
    Scene build is async. The contract is: hand a token back, not a result."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 — rpa_report_status verb not yet written")
def test_rpa_report_status_transitions():
    """rpa_report_status(report_id) must transition pending→building→ready,
    never skipping a state. A ready report must not revert to pending."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4 — rpa_inspect verb not yet written")
def test_rpa_inspect_under_200ms():
    """rpa_inspect() end-to-end on a 5-node synthetic Scene must complete
    in under 200 ms on the CI host (no cv2 path). FR-14 timing contract."""
    raise NotImplementedError
