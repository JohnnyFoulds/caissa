"""
tests/unit/rpa/test_region.py — unit tests for Vision/Region.py.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""
import pytest

pytestmark = pytest.mark.unit


def test_resolve_all_returns_list_not_single():
    """Resolve.resolve_all returns a list of ElementRefs; never raises on multi-match."""
    from Code.Rpa.Fakes import FakeDriver, World
    from Code.Rpa.Resolve import TargetResolver
    from Code.Rpa.Targets import Target, Selector
    from Code.Rpa.Types import Rect

    world = World(
        current_state="HOME",
        widget_trees={"HOME": [
            {"cls": "QPushButton", "object_name": "btn1", "visible": True,
             "rect": Rect(0, 0, 50, 20)},
            {"cls": "QPushButton", "object_name": "btn2", "visible": True,
             "rect": Rect(0, 30, 50, 20)},
        ]},
    )
    snap = FakeDriver(world).snapshot()
    resolver = TargetResolver()
    target = Target(Selector(cls="QPushButton"))
    results = resolver.resolve_all(target, snap)
    assert isinstance(results, list), "resolve_all must return a list"
    assert len(results) == 2, f"expected 2 matches, got {len(results)}"


def test_flatten_produces_absolute_rects_for_deeply_nested_widget():
    """Region.flatten on a 4-deep synthetic tree returns capture-absolute rects.

    A shallow test passes even when offset accumulation is wrong — this test uses
    depth >= 4 to catch the nested case that the old flat iteration missed.
    """
    from Code.Rpa.Vision.Region import flatten
    from Code.Rpa.Types import Rect

    tree = [
        {"cls": "QMainWindow", "rect": Rect(100, 200, 800, 600), "children": [
            {"cls": "QWidget", "rect": Rect(10, 20, 780, 560), "children": [
                {"cls": "QFrame", "rect": Rect(5, 5, 200, 100), "children": [
                    {"cls": "QPushButton", "rect": Rect(2, 3, 80, 24)},
                ]},
            ]},
        ]},
    ]
    flat = flatten(tree)
    # 4 nodes total
    assert len(flat) == 4
    # Deepest node: absolute x = 100+10+5+2 = 117, y = 200+20+5+3 = 228
    button = next(n for n in flat if n.get("cls") == "QPushButton")
    assert button["rect"] == Rect(117, 228, 80, 24), (
        f"Capture-absolute rect wrong: {button['rect']!r}"
    )
    # Depth is tracked
    assert button["_depth"] == 3


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
