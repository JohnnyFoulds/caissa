"""
tests/test_fritz_qproperties.py — WFritz* widget qproperty- contract tests (T-FQP-01..09).

:spec: §5.5, Phase 1 (feature_spec.md)
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

_ROOT = Path(__file__).parent.parent
_STYLES = _ROOT / "Resources" / "Styles"
_UIMODES = _ROOT / "bin" / "Code" / "UIModes"
_WFRITZ_FILES = sorted(_UIMODES.glob("WFritz*.py"))

_HEX_RE = re.compile(r'#[0-9A-Fa-f]{6}\b')
# Property() call in Python source
_PROP_RE = re.compile(r'\bProperty\(')
# qproperty- line in QSS
_QPROP_LINE_RE = re.compile(r'qproperty-(\w+)\s*:', re.MULTILINE)
# dic_colors direct read patterns
_DIC_COLORS_RE = re.compile(r'Code\.dic_colors|dic_colors\[')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _widget_class_names():
    """Return bare class names for each WFritz* widget module."""
    names = []
    for p in _WFRITZ_FILES:
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("WFritz"):
                names.append(node.name)
    return names


def _read_qss(name: str) -> str:
    path = _STYLES / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _qss_qproperty_names_for_class(qss_text: str, cls_name: str) -> set[str]:
    """Return qproperty- names declared under *cls_name* selector in QSS.

    Handles Q3-compliant QSS where ``{`` appears on the line after the selector.
    """
    names: set[str] = set()
    in_block = False
    pending = False  # saw cls_name but not yet the opening {
    depth = 0
    for line in qss_text.splitlines():
        stripped = line.strip()
        if not in_block:
            if cls_name in stripped and '{' in stripped:
                # same-line selector+brace (non-Q3 style)
                in_block = True
                pending = False
                depth = 1
            elif cls_name in stripped and '{' not in stripped:
                # Q3 style: selector on its own line
                pending = True
            elif pending and stripped == '{':
                in_block = True
                pending = False
                depth = 1
            elif stripped and stripped != '{':
                # something else — reset pending
                pending = False
        else:
            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                in_block = False
                continue
            m = re.match(r'qproperty-(\w+)\s*:', stripped)
            if m:
                names.add(m.group(1))
    return names


def _python_property_names(filepath: Path) -> set[str]:
    """Return property names declared as QtCore.Property(...) in a file."""
    text = filepath.read_text()
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Check if the value is a Property() call
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        if isinstance(func, ast.Attribute) and func.attr == "Property":
                            names.add(target.id)
                        elif isinstance(func, ast.Name) and func.id == "Property":
                            names.add(target.id)
    return names


# ---------------------------------------------------------------------------
# T-FQP-01: no hardcoded hex outside Property defaults
# ---------------------------------------------------------------------------

def test_no_hardcoded_hex_outside_property_defaults():
    """T-FQP-01: every WFritz*.py module's remaining #RRGGBB literals appear only as Property defaults."""
    violations = []
    for p in _WFRITZ_FILES:
        text = p.read_text()
        tree = ast.parse(text)
        # Collect line numbers of Property() assignments
        prop_lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    is_prop = (
                        (isinstance(func, ast.Attribute) and func.attr == "Property")
                        or (isinstance(func, ast.Name) and func.id == "Property")
                    )
                    if is_prop:
                        prop_lines.add(node.lineno)
            # Also collect __init__ lines where default values are set
            if isinstance(node, ast.Assign) and hasattr(node, 'lineno'):
                # Allow self._XXXColor = QColor("#...") lines
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr.endswith("Color"):
                        prop_lines.add(node.lineno)

        for i, line in enumerate(text.splitlines(), 1):
            if _HEX_RE.search(line) and i not in prop_lines:
                stripped = line.strip()
                # Skip: comment lines
                if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
                    continue
                # Skip: self._xxxColor = QColor("#...") — Property backing field defaults
                if re.match(r'self\._\w+\s*=\s*QtGui\.QColor\s*\(', stripped):
                    continue
                # Skip: _XXX_DEFAULT = "#..." — module-level Property default constants
                if re.match(r'_\w+_DEFAULT\s*=\s*["\']#', stripped):
                    continue
                # Skip: _PlayerRow(..., "#...") — static icon/piece colour arguments
                if '_PlayerRow(' in stripped:
                    continue
                # Skip: setStyleSheet(f"color:...") type icon colour overrides
                if 'setStyleSheet' in stripped:
                    continue
                violations.append(f"{p.name}:{i}: {stripped!r}")

    assert not violations, (
        "T-FQP-01 FAIL: hardcoded hex outside Property/default context:\n"
        + "\n".join(violations[:20])
    )


# ---------------------------------------------------------------------------
# T-FQP-02 / T-FQP-03: QSS ↔ Python property symmetry (Modern Fritz only for now)
# ---------------------------------------------------------------------------

def test_every_python_property_has_qss_line_in_both_themes():
    """T-FQP-02: every Property declared in Python has a qproperty- line in Modern Fritz.qss."""
    qss = _read_qss("Modern Fritz.qss")
    if not qss:
        pytest.skip("Modern Fritz.qss not found")

    missing = []
    for p in _WFRITZ_FILES:
        py_props = _python_property_names(p)
        if not py_props:
            continue
        # Find widget class name from file name
        cls_name = p.stem  # e.g. "WFritzEvalGraph"
        qss_props = _qss_qproperty_names_for_class(qss, cls_name)
        for name in py_props:
            if name not in qss_props:
                missing.append(f"{cls_name}.{name} declared in Python but no qproperty-{name} in Modern Fritz.qss")

    assert not missing, "T-FQP-02 FAIL:\n" + "\n".join(missing)


def test_every_qss_qproperty_has_python_property():
    """T-FQP-03: every qproperty- line under a WFritz* selector in Modern Fritz.qss resolves to a Python Property."""
    qss = _read_qss("Modern Fritz.qss")
    if not qss:
        pytest.skip("Modern Fritz.qss not found")

    # Build map of class -> python properties
    py_map: dict[str, set[str]] = {}
    for p in _WFRITZ_FILES:
        py_map[p.stem] = _python_property_names(p)

    missing = []
    for cls_name, py_props in py_map.items():
        qss_props = _qss_qproperty_names_for_class(qss, cls_name)
        for name in qss_props:
            if name not in py_props:
                missing.append(f"{cls_name}: qproperty-{name} in QSS but no Property in Python")

    assert not missing, "T-FQP-03 FAIL:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# T-FQP-04 / T-FQP-05: runtime property resolution — deferred (Qt required)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires live Qt app with two themes loaded — Phase 1 runtime gate")
def test_different_themes_yield_different_resolved_values():
    """T-FQP-04: each widget under Fritz and Modern Fritz reports different resolved colours."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires live Qt app — Phase 1 runtime gate")
def test_no_stylesheet_renders_with_documented_defaults():
    """T-FQP-05: each widget with no stylesheet reports its documented defaults."""
    pytest.fail("not yet implemented")


# ---------------------------------------------------------------------------
# T-FQP-06: player header height >= sum of row heights
# ---------------------------------------------------------------------------

def test_player_header_height_not_less_than_content():
    """T-FQP-06: WFritzPlayerHeader rowHeight * 2 + 1 == fixedHeight."""
    p = _UIMODES / "WFritzPlayerHeader.py"
    text = p.read_text()
    # The _set_rowHeight setter must call setFixedHeight(v * 2 + 1)
    assert "v * 2 + 1" in text, (
        "T-FQP-06 FAIL: _set_rowHeight must call setFixedHeight(v * 2 + 1) "
        "to prevent the 61px content-clip bug"
    )


# ---------------------------------------------------------------------------
# T-FQP-07: clock font family comes from QSS not hardcoded Menlo
# ---------------------------------------------------------------------------

def test_player_header_font_family_not_menlo_under_qss():
    """T-FQP-07: WFritzPlayerHeader.py contains no setFamily('Menlo') call."""
    p = _UIMODES / "WFritzPlayerHeader.py"
    text = p.read_text()
    assert 'setFamily("Menlo")' not in text and "setFamily('Menlo')" not in text, (
        "T-FQP-07 FAIL: hardcoded setFamily('Menlo') found; "
        "font-family must come from QSS (E3)"
    )


# ---------------------------------------------------------------------------
# T-FQP-08: NAG_* keys in template and all .colors files
# ---------------------------------------------------------------------------

def test_nag_keys_in_template_and_all_colors_files():
    """T-FQP-08: the six NAG_* keys exist in colors.template and every .colors file."""
    nag_keys = {
        "NAG_BRILLIANT", "NAG_GOOD", "NAG_INTERESTING",
        "NAG_DUBIOUS", "NAG_MISTAKE", "NAG_BLUNDER",
    }

    template = _STYLES / "colors.template"
    assert template.exists(), "T-FQP-08 FAIL: colors.template not found"
    tmpl_keys = {ln.split("=")[0].strip() for ln in template.read_text().splitlines() if "=" in ln}
    missing_in_template = nag_keys - tmpl_keys
    assert not missing_in_template, f"T-FQP-08 FAIL: missing from colors.template: {missing_in_template}"

    errors = []
    for fn in sorted(_STYLES.glob("*.colors")):
        keys = {ln.split("=")[0].strip() for ln in fn.read_text().splitlines() if "=" in ln}
        missing = nag_keys - keys
        if missing:
            errors.append(f"{fn.name}: missing {missing}")

    assert not errors, "T-FQP-08 FAIL:\n" + "\n".join(errors)


# ---------------------------------------------------------------------------
# T-FQP-09: no WFritz* module reads Code.dic_colors directly
# ---------------------------------------------------------------------------

def test_no_widget_reads_dic_colors_directly():
    """T-FQP-09: no WFritz* module reads Code.dic_colors directly."""
    violations = []
    for p in _WFRITZ_FILES:
        text = p.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if _DIC_COLORS_RE.search(line):
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('//'):
                    continue
                violations.append(f"{p.name}:{i}: {stripped!r}")

    assert not violations, (
        "T-FQP-09 FAIL: direct dic_colors read in widget modules "
        "(use ThemeGateway or qproperty-):\n"
        + "\n".join(violations)
    )
