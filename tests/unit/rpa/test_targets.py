"""
Phase 3 — Selector, Target, and TargetResolver unit tests.

All tests are pure Python — no Qt, no PySide6.

:spec: FR-4, §6 (feature_spec.md)
"""

import json
import logging

import pytest

pytestmark = pytest.mark.rpa

from Code.Rpa.Errors import AmbiguousMatchError, SelectorError, TargetNotFoundError
from Code.Rpa.Resolve import TargetResolver, _CONF_CLASS_ONLY, _CONF_EXACT_OBJECT_NAME
from Code.Rpa.Targets import Selector, Target
from Code.Rpa.Types import Rect, Snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(*widgets) -> Snapshot:
    """Build a Snapshot from a list of widget dicts."""
    return Snapshot(state_name="HOME", widget_tree=list(widgets), timestamp_ms=0.0)


def _w(cls="QPushButton", object_name=None, text=None, visible=True,
       x=0, y=0, w=50, h=20):
    """Build a minimal widget-info dict."""
    return {
        "cls": cls,
        "object_name": object_name,
        "text": text,
        "visible": visible,
        "rect": Rect(x=x, y=y, w=w, h=h),
    }


# ---------------------------------------------------------------------------
# Selector — construction validation
# ---------------------------------------------------------------------------

def test_selector_requires_discriminating_field():
    """Selector with no discriminating field must raise SelectorError."""
    with pytest.raises(SelectorError, match="discriminating"):
        Selector(tier="auto")


def test_selector_requires_discriminating_field_index_alone():
    """Selector with only index set (no discriminator) must raise SelectorError."""
    with pytest.raises(SelectorError):
        Selector(index=2)


def test_selector_unknown_tier_raises():
    """Selector with an unknown tier must raise SelectorError."""
    with pytest.raises(SelectorError, match="tier"):
        Selector(tier="magic", cls="QPushButton")


# ---------------------------------------------------------------------------
# Selector — JSON codec
# ---------------------------------------------------------------------------

def test_selector_json_roundtrip():
    """Selector serialises to JSON and deserialises back to an equal object."""
    original = Selector(tier="object", cls="QPushButton", text="Play")
    as_json = original.to_json()
    restored = Selector.from_json(as_json)
    assert restored == original


def test_selector_json_roundtrip_minimal():
    """Minimal selector (object_name only) survives JSON roundtrip."""
    s = Selector(object_name="play_btn")
    assert Selector.from_json(s.to_json()) == s


def test_selector_from_json_str():
    """from_json_str parses a JSON string directly."""
    s = Selector(cls="QLineEdit", text="Name")
    assert Selector.from_json_str(json.dumps(s.to_json())) == s


def test_selector_from_json_str_invalid_json():
    """from_json_str raises SelectorError on invalid JSON."""
    with pytest.raises(SelectorError):
        Selector.from_json_str("not json at all {{")


# ---------------------------------------------------------------------------
# Selector — compact-string codec
# ---------------------------------------------------------------------------

def test_selector_compact_string_roundtrip():
    """Compact-string roundtrip preserves tier and discriminating fields."""
    original = Selector(tier="object", cls="QPushButton", text="Play")
    compact = original.to_compact()
    assert compact.startswith("obj:")
    restored = Selector.from_compact(compact)
    assert restored.tier == "object"
    assert restored.cls == "QPushButton"
    assert restored.text == "Play"


def test_selector_compact_auto_tier():
    """auto tier renders as 'auto:' prefix."""
    s = Selector(tier="auto", object_name="toolbar_btn")
    compact = s.to_compact()
    assert compact.startswith("auto:")
    restored = Selector.from_compact(compact)
    assert restored.tier == "auto"
    assert restored.object_name == "toolbar_btn"


def test_selector_compact_unknown_tier_raises():
    """from_compact with an unknown prefix raises SelectorError."""
    with pytest.raises(SelectorError, match="abbreviation"):
        Selector.from_compact("bad:cls=QPushButton")


def test_selector_compact_missing_tier_raises():
    """from_compact without a colon prefix raises SelectorError."""
    with pytest.raises(SelectorError, match="missing tier"):
        Selector.from_compact("cls=QPushButton")


# ---------------------------------------------------------------------------
# Object-tier confidence
# ---------------------------------------------------------------------------

def test_object_confidence_exact_name_is_one():
    """Exact object_name match yields confidence 1.00."""
    resolver = TargetResolver()
    widget = _w(object_name="play_btn")
    snap = _snap(widget)
    sel = Selector(object_name="play_btn")
    candidates = resolver._object_candidates(sel, snap)
    assert len(candidates) == 1
    assert candidates[0].confidence == _CONF_EXACT_OBJECT_NAME


def test_object_confidence_exact_text_is_0_95():
    """Exact text match yields confidence 0.95."""
    resolver = TargetResolver()
    widget = _w(text="Play")
    snap = _snap(widget)
    sel = Selector(text="Play", text_exact=True)
    candidates = resolver._object_candidates(sel, snap)
    assert len(candidates) == 1
    assert candidates[0].confidence == pytest.approx(0.95)


def test_object_confidence_substring_is_0_80():
    """Substring text match yields confidence 0.80."""
    resolver = TargetResolver()
    widget = _w(text="Play Game")
    snap = _snap(widget)
    sel = Selector(text="Play")
    candidates = resolver._object_candidates(sel, snap)
    assert len(candidates) == 1
    assert candidates[0].confidence == pytest.approx(0.80)


def test_object_confidence_class_only_is_0_60():
    """Class-only selector (no object_name or text) yields confidence 0.60."""
    resolver = TargetResolver()
    widget = _w(cls="QPushButton")
    snap = _snap(widget)
    sel = Selector(cls="QPushButton")
    candidates = resolver._object_candidates(sel, snap)
    assert len(candidates) == 1
    assert candidates[0].confidence == pytest.approx(_CONF_CLASS_ONLY)


# ---------------------------------------------------------------------------
# resolve_one — object tier
# ---------------------------------------------------------------------------

def test_resolve_object_exact_name():
    """resolve_one returns the element matching by exact object_name."""
    resolver = TargetResolver()
    snap = _snap(
        _w(object_name="cancel_btn", text="Cancel", x=100, y=0),
        _w(object_name="play_btn", text="Play", x=0, y=0),
    )
    ref = resolver.resolve_one(Target(Selector(object_name="play_btn")), snap)
    assert ref.selector == "play_btn"
    assert ref.rect == Rect(0, 0, 50, 20)


def test_resolve_object_exact_text():
    """resolve_one returns the element matching by exact text."""
    resolver = TargetResolver()
    snap = _snap(
        _w(text="Cancel"),
        _w(text="OK", x=100, y=0),
    )
    ref = resolver.resolve_one(Target(Selector(text="OK", text_exact=True)), snap)
    assert ref.rect.x == 100


def test_resolve_ambiguous_raises():
    """Two equal-confidence matches raise AmbiguousMatchError."""
    resolver = TargetResolver()
    snap = _snap(
        _w(cls="QPushButton", x=0, y=0),
        _w(cls="QPushButton", x=100, y=0),
    )
    with pytest.raises(AmbiguousMatchError):
        resolver.resolve_one(Target(Selector(cls="QPushButton")), snap)


def test_resolve_not_found_raises():
    """No matching widget raises TargetNotFoundError."""
    resolver = TargetResolver()
    snap = _snap(_w(cls="QLabel", text="hello"))
    with pytest.raises(TargetNotFoundError):
        resolver.resolve_one(Target(Selector(object_name="nonexistent")), snap)


def test_resolve_invisible_excluded():
    """Invisible widgets are excluded from resolution."""
    resolver = TargetResolver()
    snap = _snap(_w(object_name="hidden_btn", visible=False))
    with pytest.raises(TargetNotFoundError):
        resolver.resolve_one(Target(Selector(object_name="hidden_btn")), snap)


def test_resolve_index_disambiguates():
    """index=1 selects the second match among tied candidates."""
    resolver = TargetResolver()
    snap = _snap(
        _w(cls="QPushButton", text="A", x=0),
        _w(cls="QPushButton", text="B", x=100),
    )
    ref = resolver.resolve_one(Target(Selector(cls="QPushButton", index=1)), snap)
    # Second button (x=100)
    assert ref.rect.x == 100


# ---------------------------------------------------------------------------
# Anchor resolution
# ---------------------------------------------------------------------------

def test_resolve_anchor_right_of():
    """Anchor 'right-of' filters to candidates to the right of the anchor."""
    resolver = TargetResolver()
    label = _w(cls="QLabel", text="Name", x=0, y=0, w=60, h=20)
    field_right = _w(cls="QLineEdit", object_name="name_field", x=80, y=0, w=120, h=20)
    field_left = _w(cls="QLineEdit", object_name="other_field", x=-200, y=0, w=120, h=20)
    snap = _snap(label, field_right, field_left)

    target = Target(
        selector=Selector(cls="QLineEdit"),
        anchor=Selector(text="Name"),
        direction="right-of",
    )
    ref = resolver.resolve_one(target, snap)
    assert ref.selector == "name_field"


def test_resolve_anchor_below():
    """Anchor 'below' filters to candidates below the anchor."""
    resolver = TargetResolver()
    header = _w(cls="QLabel", text="Header", x=0, y=0)
    btn_below = _w(cls="QPushButton", object_name="below_btn", x=0, y=100, w=50, h=20)
    btn_above = _w(cls="QPushButton", object_name="above_btn", x=0, y=-50, w=50, h=20)
    snap = _snap(header, btn_below, btn_above)

    target = Target(
        selector=Selector(cls="QPushButton"),
        anchor=Selector(text="Header"),
        direction="below",
    )
    ref = resolver.resolve_one(target, snap)
    assert ref.selector == "below_btn"


def test_resolve_anchor_max_distance():
    """max_distance excludes candidates beyond the distance limit."""
    resolver = TargetResolver()
    anchor = _w(cls="QLabel", text="Label", x=0, y=0, w=50, h=20)
    # centre of anchor: (25, 10)
    near = _w(cls="QPushButton", object_name="near", x=60, y=0, w=50, h=20)  # centre (85,10) dist≈60
    far = _w(cls="QPushButton", object_name="far", x=500, y=0, w=50, h=20)  # centre (525,10) dist≈500
    snap = _snap(anchor, near, far)

    target = Target(
        selector=Selector(cls="QPushButton"),
        anchor=Selector(text="Label"),
        direction="right-of",
        max_distance=200,
    )
    ref = resolver.resolve_one(target, snap)
    assert ref.selector == "near"


# ---------------------------------------------------------------------------
# Non-object tier stubs
# ---------------------------------------------------------------------------

def test_image_tier_raises_vision_unavailable():
    """Image tier raises VisionUnavailableError (Phase 7 stub)."""
    from Code.Rpa.Errors import VisionUnavailableError
    resolver = TargetResolver()
    snap = _snap(_w(cls="QPushButton"))
    with pytest.raises(VisionUnavailableError):
        resolver.resolve_one(Target(Selector(tier="image", image="play_btn.png")), snap)


def test_ocr_tier_raises_vision_unavailable():
    """OCR tier raises VisionUnavailableError (Phase 7 stub)."""
    from Code.Rpa.Errors import VisionUnavailableError
    resolver = TargetResolver()
    snap = _snap(_w(cls="QPushButton"))
    with pytest.raises(VisionUnavailableError):
        resolver.resolve_one(Target(Selector(tier="ocr", text="Play")), snap)


# ---------------------------------------------------------------------------
# fallback tier warning
# ---------------------------------------------------------------------------

def test_fallback_tier_win_emits_warning(caplog):
    """When the object tier fails on auto, a warning is emitted about missing CV tiers."""
    resolver = TargetResolver()
    snap = _snap(_w(cls="QLabel", text="unrelated"))
    target = Target(Selector(tier="auto", object_name="missing_widget"))
    with caplog.at_level(logging.WARNING, logger="Code.Rpa.Resolve"):
        with pytest.raises(TargetNotFoundError):
            resolver.resolve_one(target, snap)
    assert any("object tier" in r.message.lower() or "image/ocr" in r.message.lower()
               for r in caplog.records)


# ---------------------------------------------------------------------------
# Target construction
# ---------------------------------------------------------------------------

def test_target_anchor_without_direction_raises():
    """Target with anchor but no direction raises SelectorError."""
    with pytest.raises(SelectorError, match="direction"):
        Target(
            selector=Selector(cls="QLineEdit"),
            anchor=Selector(text="Name"),
        )


def test_target_invalid_direction_raises():
    """Target with an unknown direction raises SelectorError."""
    with pytest.raises(SelectorError, match="direction"):
        Target(
            selector=Selector(cls="QLineEdit"),
            anchor=Selector(text="Name"),
            direction="diagonal",
        )


def test_target_json_roundtrip():
    """Target serialises to JSON and back."""
    t = Target(
        selector=Selector(cls="QPushButton", text="OK"),
        anchor=Selector(text="Name"),
        direction="right-of",
        max_distance=300,
        timeout_ms=2000,
    )
    restored = Target.from_json(t.to_json())
    assert restored.selector == t.selector
    assert restored.anchor == t.anchor
    assert restored.direction == t.direction
    assert restored.max_distance == t.max_distance
    assert restored.timeout_ms == t.timeout_ms


def test_target_from_json_missing_selector_raises():
    """Target.from_json without 'selector' key raises SelectorError."""
    with pytest.raises(SelectorError, match="selector"):
        Target.from_json({"direction": "right-of"})
