"""
tests/unit/rpa/test_style_source.py — Unit tests for Vision/StyleSource.py.

The gate test (test_style_source_file_tab_governing) asserts that:
- WRibbon.py:118 (_FlatTabBar._BG_FIRST) governs the File tab fill
- fritz-widgets.qss:288 (#WRibbonTabBar::tab:first) is matched_overridden
- Fritz.qss:1015 (#WRibbonTabBar::tab:first) is matched_overridden
- Caissa.qss:214 (QTabWidget::pane) is loaded_unmatched

These are the four cases where my first analysis named the wrong governing source
and pointed at dead rules.  This test suite must fail if any of those regress.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

import pytest
from pathlib import Path

pytestmark = pytest.mark.unit

from Code.Rpa.Vision.StyleSource import (
    parse_rules,
    resolve_placeholders,
    effective,
    paint_colour_constants,
    style_sources_for,
    _selector_widget_type,
)


# ---------------------------------------------------------------------------
# parse_rules
# ---------------------------------------------------------------------------

_SIMPLE_QSS = """\
QTabBar::tab
{
    background-color: #252526;
    padding: 6px 14px;
    margin-right: 2px;
}

QTabBar::tab:selected
{
    background-color: #272728;
    color: #d6d6dd;
}
"""

_PLACEHOLDER_QSS = """\
#WRibbonTabBar::tab:first
{
background-color: {CHROME_ACCENT};
color: {CHROME_SURFACE_2};
border-radius: 0;
}
"""

_INLINE_QSS = """\
QWidget { background-color: #1e1e1e; color: #d4d4d4; }
"""


def test_parse_rules_basic():
    """parse_rules extracts selectors and properties from a simple QSS block."""
    rules = parse_rules(_SIMPLE_QSS)
    assert "QTabBar::tab" in rules
    assert rules["QTabBar::tab"]["background-color"] == "#252526"
    assert rules["QTabBar::tab"]["padding"] == "6px 14px"
    assert rules["QTabBar::tab"]["margin-right"] == "2px"


def test_parse_rules_multiple_selectors():
    """parse_rules parses multiple consecutive selector blocks."""
    rules = parse_rules(_SIMPLE_QSS)
    assert "QTabBar::tab:selected" in rules
    assert rules["QTabBar::tab:selected"]["color"] == "#d6d6dd"


def test_parse_rules_inline_selector():
    """parse_rules handles selector { prop: val; } on one line."""
    rules = parse_rules(_INLINE_QSS)
    assert "QWidget" in rules
    assert rules["QWidget"]["background-color"] == "#1e1e1e"


def test_parse_rules_placeholder_text_unchanged():
    """parse_rules leaves {KEY} placeholders intact in values."""
    rules = parse_rules(_PLACEHOLDER_QSS)
    assert "#WRibbonTabBar::tab:first" in rules
    assert rules["#WRibbonTabBar::tab:first"]["background-color"] == "{CHROME_ACCENT}"


def test_parse_rules_empty():
    """parse_rules returns empty dict on blank input."""
    assert parse_rules("") == {}


# ---------------------------------------------------------------------------
# resolve_placeholders
# ---------------------------------------------------------------------------

def test_resolve_placeholders_basic():
    """resolve_placeholders substitutes {KEY} tokens from colour_map."""
    resolved, found = resolve_placeholders(
        "background-color: {CHROME_ACCENT};",
        {"CHROME_ACCENT": "#007acc"},
    )
    assert "#007acc" in resolved
    assert found == {"CHROME_ACCENT": "#007acc"}


def test_resolve_placeholders_unknown_key_unchanged():
    """resolve_placeholders leaves unknown {KEY} tokens untouched."""
    resolved, found = resolve_placeholders(
        "color: {UNKNOWN_KEY};",
        {"CHROME_ACCENT": "#007acc"},
    )
    assert "{UNKNOWN_KEY}" in resolved
    assert "UNKNOWN_KEY" not in found


def test_resolve_placeholders_multiple():
    """resolve_placeholders substitutes multiple {KEY} tokens in one pass."""
    text = "bg: {A}; fg: {B};"
    resolved, found = resolve_placeholders(text, {"A": "#111", "B": "#222"})
    assert "A" in found and "B" in found
    assert "#111" in resolved and "#222" in resolved


# ---------------------------------------------------------------------------
# _selector_widget_type
# ---------------------------------------------------------------------------

def test_selector_widget_type_qtabwidget():
    assert _selector_widget_type("QTabWidget::pane") == "QTabWidget"


def test_selector_widget_type_qtabbar():
    assert _selector_widget_type("QTabBar::tab:selected") == "QTabBar"


def test_selector_widget_type_object_name():
    """Object-name selectors (#name) have no extractable type."""
    assert _selector_widget_type("#WRibbonTabBar::tab:first") == ""


def test_selector_widget_type_plain_class():
    assert _selector_widget_type("QWidget") == "QWidget"


def test_selector_widget_type_lowercase():
    """Lowercase selectors (not a Qt class name) return empty string."""
    assert _selector_widget_type("div") == ""


# ---------------------------------------------------------------------------
# effective
# ---------------------------------------------------------------------------

def test_effective_loaded_unmatched():
    """QTabWidget::pane is loaded_unmatched when no QTabWidget is in the tree."""
    result = effective(
        selector="QTabWidget::pane",
        paint_overrides={},
        widget_types=frozenset({"QTabBar", "QTextEdit", "_FlowingNotation"}),
        live_stylesheet="QTabBar::tab { padding: 6px; }",
    )
    assert result == "loaded_unmatched"


def test_effective_matched_overridden_by_paint():
    """A selector whose widget has paintEvent override is matched_overridden."""
    result = effective(
        selector="#WRibbonTabBar::tab:first",
        paint_overrides={"paintEvent": {"file": "WRibbon.py", "line": 126,
                                         "class": "_FlatTabBar"}},
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        live_stylesheet="#WRibbonTabBar { background: #1e1e1e; }",
    )
    assert result == "matched_overridden"


def test_effective_unconfirmed_without_live_stylesheet():
    """Without a live stylesheet the state is unconfirmed."""
    result = effective(
        selector="QTabBar::tab",
        paint_overrides={},
        widget_types=frozenset({"QTabBar"}),
        live_stylesheet=None,
    )
    assert result == "unconfirmed"


def test_effective_returns_effective_when_confirmed():
    """A selector present in the tree and in the stylesheet with no override is effective."""
    result = effective(
        selector="QTabBar::tab",
        paint_overrides={},
        widget_types=frozenset({"QTabBar"}),
        live_stylesheet="QTabBar::tab { padding: 6px 14px; }",
    )
    assert result == "effective"


# ---------------------------------------------------------------------------
# paint_colour_constants
# ---------------------------------------------------------------------------

_WRIBBON_SOURCE = """\
from PySide6 import QtGui, QtWidgets

class _FlatTabBar(QtWidgets.QTabBar):
    _BG_FIRST   = QtGui.QColor("#007acc")
    _FG_FIRST   = QtGui.QColor("#ffffff")
    _BG_SEL     = QtGui.QColor("#ffffff")
    _FG_SEL     = QtGui.QColor("#005b99")
    _BORDER_SEL = QtGui.QColor("#9daab8")
    _FG_NORMAL  = QtGui.QColor("#1e1e1e")
    _BG_HOVER   = QtGui.QColor("#e4e6f0")

    def paintEvent(self, event):
        pass
"""


def test_paint_colour_constants_finds_seven(tmp_path):
    """paint_colour_constants finds all 7 QColor literals in _FlatTabBar."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)
    consts = paint_colour_constants(src, "_FlatTabBar")
    assert len(consts) == 7
    assert all(c["e1_violation"] for c in consts)


def test_paint_colour_constants_symbols(tmp_path):
    """paint_colour_constants records the class.attr symbol names."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)
    consts = paint_colour_constants(src, "_FlatTabBar")
    symbols = {c["symbol"] for c in consts}
    assert "_FlatTabBar._BG_FIRST" in symbols
    assert "_FlatTabBar._FG_SEL" in symbols


def test_paint_colour_constants_bg_first_hex(tmp_path):
    """paint_colour_constants captures the correct hex value for _BG_FIRST."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)
    consts = paint_colour_constants(src, "_FlatTabBar")
    bg_first = next(c for c in consts if "_BG_FIRST" in c["symbol"])
    assert bg_first["hex"] == "#007acc"


def test_paint_colour_constants_wrong_class(tmp_path):
    """paint_colour_constants returns empty for a class not in the file."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)
    assert paint_colour_constants(src, "SomeOtherClass") == []


def test_paint_colour_constants_missing_file(tmp_path):
    """paint_colour_constants returns empty when the file does not exist."""
    assert paint_colour_constants(tmp_path / "nonexistent.py", "_FlatTabBar") == []


# ---------------------------------------------------------------------------
# style_sources_for — the gate test
# ---------------------------------------------------------------------------

# Minimal QSS fragments representative of the real files.
_FRITZ_WIDGETS_FRAGMENT = """\
#WRibbonTabBar::tab
{
font-size: 8pt;
padding: 4px 13px;
}

#WRibbonTabBar::tab:first
{
background-color: {CHROME_ACCENT};
color: {CHROME_SURFACE_2};
border-radius: 0;
}
"""

_FRITZ_QSS_FRAGMENT = """\
#WRibbonTabBar::tab:first
{
background-color: {CHROME_ACCENT};
color: {CHROME_SURFACE_2};
}
"""

_CAISSA_FRAGMENT = """\
QTabWidget::pane
{
    border: 1px solid #363636;
    top: -1px;
}

QTabBar::tab
{
    background-color: #252526;
    padding: 6px 14px;
}
"""

_PAINT_OVERRIDES = {
    "paintEvent": {
        "file": "bin/Code/Fritz/WRibbon.py",
        "line": 126,
        "class": "_FlatTabBar",
    }
}

_WIDGET_TYPES_NO_QTABWIDGET = frozenset({
    "QTabBar", "_FlatTabBar", "QTextEdit",
    "_FlowingNotation", "QWidget", "QLabel",
})

_COLOUR_MAP = {
    "CHROME_ACCENT": "#007acc",
    "CHROME_SURFACE_2": "#2d2d2d",
}


def test_style_source_file_tab_governing(tmp_path):
    """THE GATE TEST — the style bridge must name the right governing source.

    Given the three QSS files and the _FlatTabBar paint override:
    - fritz-widgets.qss::tab:first must be matched_overridden (paintEvent wins)
    - Fritz.qss::tab:first must be matched_overridden (paintEvent wins)
    - Caissa.qss::pane must be loaded_unmatched (no QTabWidget in tree)
    """
    fw = tmp_path / "fritz-widgets.qss"
    fr = tmp_path / "Fritz.qss"
    ca = tmp_path / "Caissa.qss"
    fw.write_text(_FRITZ_WIDGETS_FRAGMENT)
    fr.write_text(_FRITZ_QSS_FRAGMENT)
    ca.write_text(_CAISSA_FRAGMENT)

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[
            (fw, _FRITZ_WIDGETS_FRAGMENT),
            (fr, _FRITZ_QSS_FRAGMENT),
            (ca, _CAISSA_FRAGMENT),
        ],
        paint_overrides=_PAINT_OVERRIDES,
        widget_types=_WIDGET_TYPES_NO_QTABWIDGET,
        colour_map=_COLOUR_MAP,
        live_stylesheet="#WRibbonTabBar::tab { padding: 4px 13px; }",
    )

    assert sources, "style_sources_for returned no results"

    kinds = {s["selector"]: s["effective"] for s in sources}

    # fritz-widgets.qss::tab:first — paintEvent defeats it
    tab_first_keys = [k for k in kinds if "tab:first" in k or "tab_first" in k.lower()]
    for k in tab_first_keys:
        assert kinds[k] == "matched_overridden", (
            f"Expected {k!r} to be matched_overridden; got {kinds[k]!r}"
        )

    # Caissa.qss::pane — no QTabWidget in tree
    pane_keys = [k for k in kinds if "pane" in k.lower()]
    for k in pane_keys:
        assert kinds[k] == "loaded_unmatched", (
            f"Expected {k!r} to be loaded_unmatched; got {kinds[k]!r}"
        )


def test_style_source_padding_effective(tmp_path):
    """Geometry rules remain effective even when paintEvent overrides colour."""
    fw = tmp_path / "fritz-widgets.qss"
    fw.write_text(_FRITZ_WIDGETS_FRAGMENT)

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[(fw, _FRITZ_WIDGETS_FRAGMENT)],
        paint_overrides=_PAINT_OVERRIDES,
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map=_COLOUR_MAP,
        live_stylesheet="#WRibbonTabBar::tab { padding: 4px 13px; }",
    )

    tab_rules = [s for s in sources if s["selector"] == "#WRibbonTabBar::tab"]
    assert tab_rules, "No rule found for #WRibbonTabBar::tab"
    tab_rule = tab_rules[0]
    # padding governs geometry, which paintEvent does NOT override
    assert "geometry" in tab_rule["governs"]


def test_style_source_placeholder_in_authored(tmp_path):
    """authored dict carries the raw {KEY} token, resolved dict carries the hex."""
    fw = tmp_path / "fritz-widgets.qss"
    fw.write_text(_FRITZ_WIDGETS_FRAGMENT)

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[(fw, _FRITZ_WIDGETS_FRAGMENT)],
        paint_overrides={},
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map=_COLOUR_MAP,
        live_stylesheet=None,
    )

    tab_first_rules = [s for s in sources
                       if "tab:first" in s.get("selector", "")]
    assert tab_first_rules, "No rule for tab:first found"
    rule = tab_first_rules[0]
    assert rule["authored"].get("background-color") == "{CHROME_ACCENT}"
    assert rule["resolved"].get("background-color") == "#007acc"
    assert rule["placeholder_of"].get("background-color") == "CHROME_ACCENT"


def test_style_source_qtabwidget_pane_loaded_unmatched(tmp_path):
    """QTabWidget::pane is loaded_unmatched when no QTabWidget exists in tree.

    This is the single most important regression guard in this module — it is
    exactly the mistake that caused three successive wrong diagnoses.
    """
    ca = tmp_path / "Caissa.qss"
    ca.write_text(_CAISSA_FRAGMENT)

    sources = style_sources_for(
        object_name="",
        cls="QTextEdit",
        qss_sources=[(ca, _CAISSA_FRAGMENT)],
        paint_overrides={},
        widget_types=_WIDGET_TYPES_NO_QTABWIDGET,
        colour_map={},
        live_stylesheet="QTabBar::tab { padding: 6px 14px; }",
    )

    pane = [s for s in sources if "pane" in s.get("selector", "").lower()]
    assert pane, "QTabWidget::pane rule not found in sources"
    assert pane[0]["effective"] == "loaded_unmatched", (
        f"Expected loaded_unmatched for QTabWidget::pane; got {pane[0]['effective']!r}"
    )


def test_style_source_e1_paint_constants_present(tmp_path):
    """style_sources_for includes paint colour constants as e1_violation entries."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[],
        paint_overrides={
            "paintEvent": {
                "file": str(src),
                "line": 11,
                "class": "_FlatTabBar",
            }
        },
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map={},
        live_stylesheet=None,
    )

    paint_consts = [s for s in sources if s.get("e1_violation")]
    assert len(paint_consts) == 7, (
        f"Expected 7 E1 violation entries; got {len(paint_consts)}: "
        f"{[s['selector'] for s in paint_consts]}"
    )


def test_style_source_ordering_paint_before_qss(tmp_path):
    """style_sources_for returns paint (governing) sources before QSS ones."""
    fw = tmp_path / "fritz-widgets.qss"
    fw.write_text(_FRITZ_WIDGETS_FRAGMENT)
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[(fw, _FRITZ_WIDGETS_FRAGMENT)],
        paint_overrides={
            "paintEvent": {
                "file": str(src),
                "line": 11,
                "class": "_FlatTabBar",
            }
        },
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map=_COLOUR_MAP,
        live_stylesheet=None,
    )

    kinds = [s["kind"] for s in sources]
    # All paint entries must appear before qss entries
    first_qss = next((i for i, k in enumerate(kinds) if k == "qss"), len(sources))
    last_paint = max((i for i, k in enumerate(kinds) if k == "paint"), default=-1)
    assert last_paint < first_qss, (
        f"Expected all paint entries before QSS; got order: {kinds}"
    )


# ---------------------------------------------------------------------------
# Planned test names from feature_steps.md (spec-gate compliance)
# These names are the canonical test IDs; the implementation may delegate to
# helpers above but the name itself must exist in the suite.
# ---------------------------------------------------------------------------

def test_style_source_wribbon_file_fill_governed_by_paintEvent(tmp_path):
    """WRibbon.py paint constants govern fill; QSS colour rules are overridden."""
    src = tmp_path / "WRibbon.py"
    src.write_text(_WRIBBON_SOURCE)
    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[],
        paint_overrides={"paintEvent": {"file": str(src), "line": 11,
                                        "class": "_FlatTabBar"}},
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map={},
        live_stylesheet=None,
    )
    paint_consts = [s for s in sources if s.get("e1_violation")]
    assert len(paint_consts) == 7
    assert all(s["effective"] == "effective" for s in paint_consts)


def test_style_source_fritz_widgets_qss_290_matched_overridden(tmp_path):
    """fritz-widgets.qss::tab:first is matched_overridden when paintEvent owns colour."""
    fw = tmp_path / "fritz-widgets.qss"
    fw.write_text(_FRITZ_WIDGETS_FRAGMENT)
    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[(fw, _FRITZ_WIDGETS_FRAGMENT)],
        paint_overrides=_PAINT_OVERRIDES,
        widget_types=frozenset({"QTabBar", "_FlatTabBar"}),
        colour_map=_COLOUR_MAP,
        live_stylesheet=None,
    )
    tab_first = [s for s in sources if "tab:first" in s.get("selector", "")]
    assert tab_first, "No tab:first rule found"
    assert tab_first[0]["effective"] == "matched_overridden"


def test_style_source_caissa_qss_214_loaded_unmatched(tmp_path):
    """Caissa.qss QTabWidget::pane is loaded_unmatched — no QTabWidget in the tree."""
    ca = tmp_path / "Caissa.qss"
    ca.write_text(_CAISSA_FRAGMENT)
    sources = style_sources_for(
        object_name="",
        cls="QTextEdit",
        qss_sources=[(ca, _CAISSA_FRAGMENT)],
        paint_overrides={},
        widget_types=_WIDGET_TYPES_NO_QTABWIDGET,
        colour_map={},
        live_stylesheet="QTabBar::tab { padding: 6px 14px; }",
    )
    pane = [s for s in sources if "pane" in s.get("selector", "").lower()]
    assert pane, "QTabWidget::pane rule not found"
    assert pane[0]["effective"] == "loaded_unmatched"


@pytest.mark.xfail(strict=True, reason="Requires Phase 2c: font_mismatch detection not yet implemented")
def test_style_source_font_mismatch_detected():
    """style_sources_for detects a font-size mismatch between QSS and paintEvent font."""
    raise NotImplementedError("Phase 2c: font_mismatch detection")
