"""
tests/unit/fritz/test_qss_rules.py — Unit tests for ``Code.Fritz.QssRules``.

Tests:

- T-QSS-01  ``scan_qss`` detects a planted Q1 violation
- T-QSS-02  ``scan_qss`` detects a planted Q3 violation
- T-QSS-03  Fritz-authored ``.qss`` files contain no Q1/Q3 violations
- T-QSS-04  ``template_gaps`` is empty for every ``.colors`` file vs ``colors.template``
- T-QSS-05  ``qproperties`` parses ``qproperty-`` values including comma-containing values
- T-QSS-06  ``qproperties`` returns ``{}`` when no ``qproperty-`` lines are present
- T-QSS-07  ``qproperties`` raises ``QssContractError`` on unbalanced braces

Note: T-QSS-03 scopes to Fritz-authored stylesheets (files containing "Fritz" in the
name, plus ``Fritz.qss`` when it exists in Phase 6).  Upstream files such as ``Mid.qss``
and ``By default.qss`` predate this feature and use same-line ``{`` throughout; they are
not edited by this feature and are therefore excluded from the Q3 gate.

:spec: §5.2, N-FRITZ-4 (feature_spec.md)
"""

from __future__ import annotations

import glob
import os

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _styles_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "Resources", "Styles")
    )


def _parse_keys(path: str) -> list[str]:
    """Return the key names (left of ``=``) from a template or ``.colors`` file."""
    keys: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("[") and not stripped.startswith("#"):
                keys.append(stripped.split("=")[0].strip())
    return keys


def _fritz_qss_files() -> list[str]:
    """Return Fritz-authored .qss files (name contains 'Fritz' or is exactly 'Fritz.qss')."""
    styles = _styles_dir()
    result = []
    for path in sorted(glob.glob(os.path.join(styles, "*.qss"))):
        name = os.path.basename(path)
        if "Fritz" in name:
            result.append(path)
    return result


# ---------------------------------------------------------------------------
# T-QSS-01 — scan_qss detects Q1 violation
# ---------------------------------------------------------------------------

def test_qss_scan_finds_q1_violation():
    """T-QSS-01 FAIL: scan_qss must detect a hex colour on a multi-colon line."""
    from Code.Fritz.QssRules import scan_qss

    # Two colons + hex on same line → Q1
    text = "qproperty-foo: color: #ff0000;"
    violations = scan_qss(text)
    q1 = [v for v in violations if v[1] == "Q1"]
    assert q1, (
        "T-QSS-01 FAIL: scan_qss returned no Q1 violation for "
        f"'qproperty-foo: color: #ff0000;' (got {violations!r})"
    )


# ---------------------------------------------------------------------------
# T-QSS-02 — scan_qss detects Q3 violation
# ---------------------------------------------------------------------------

def test_qss_scan_finds_q3_violation():
    """T-QSS-02 FAIL: scan_qss must detect a selector with '{' on the same line."""
    from Code.Fritz.QssRules import scan_qss

    text = "QWidget {"
    violations = scan_qss(text)
    q3 = [v for v in violations if v[1] == "Q3"]
    assert q3, (
        "T-QSS-02 FAIL: scan_qss returned no Q3 violation for "
        f"'QWidget {{' (got {violations!r})"
    )


# ---------------------------------------------------------------------------
# T-QSS-03 — Fritz-authored .qss files are clean
# ---------------------------------------------------------------------------

def test_qss_scan_clean_on_all_shipped_stylesheets():
    """T-QSS-03 FAIL: Fritz-authored .qss files must contain no Q1 or Q3 violations.

    Scoped to files whose name contains 'Fritz' — upstream stylesheets such as
    ``Mid.qss`` predate this feature and are not edited by it.
    """
    from Code.Fritz.QssRules import scan_qss

    fritz_files = _fritz_qss_files()
    assert fritz_files, (
        f"T-QSS-03 FAIL: no Fritz-authored .qss files found in {_styles_dir()}"
    )

    all_violations: list[str] = []
    for path in fritz_files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for line_no, rule, line in scan_qss(text):
            rel = os.path.relpath(path)
            all_violations.append(f"{rel}:{line_no} [{rule}] {line!r}")

    assert not all_violations, (
        f"T-QSS-03 FAIL: {len(all_violations)} violation(s) in Fritz-authored .qss files:\n"
        + "\n".join(all_violations)
    )


# ---------------------------------------------------------------------------
# T-QSS-04 — template_gaps empty for every .colors file
# ---------------------------------------------------------------------------

def test_template_gaps_empty_for_all_shipped_colors():
    """T-QSS-04 FAIL: every shipped .colors file must contain all colors.template keys."""
    from Code.Fritz.QssRules import template_gaps

    styles = _styles_dir()
    template_path = os.path.join(styles, "colors.template")
    assert os.path.isfile(template_path), (
        f"T-QSS-04 FAIL: colors.template not found at {template_path}"
    )

    template_keys = _parse_keys(template_path)
    assert template_keys, "T-QSS-04 FAIL: colors.template contains no keys"

    colors_files = glob.glob(os.path.join(styles, "*.colors"))
    assert colors_files, f"T-QSS-04 FAIL: no .colors files found in {styles}"

    all_gaps: list[str] = []
    for path in sorted(colors_files):
        colors_keys = _parse_keys(path)
        gaps = template_gaps(template_keys, colors_keys)
        if gaps:
            rel = os.path.relpath(path)
            all_gaps.append(f"{rel}: missing keys: {gaps}")

    assert not all_gaps, (
        f"T-QSS-04 FAIL: {len(all_gaps)} .colors file(s) have template gaps:\n"
        + "\n".join(all_gaps)
    )


# ---------------------------------------------------------------------------
# T-QSS-05 — qproperties parses multi-value lines correctly
# ---------------------------------------------------------------------------

def test_qproperties_parses_multivalue_correctly():
    """T-QSS-05 FAIL: qproperties must parse property values including those with commas."""
    from Code.Fritz.QssRules import qproperties

    text = (
        "WFritzLCD\n"
        "{\n"
        "qproperty-litColor: #30ff70;\n"
        "qproperty-boxHeight: 34;\n"
        "qproperty-titleBrush: qlineargradient(x1:0, y1:0, x2:0, y2:1);\n"
        "background-color: #000000;\n"
        "}\n"
    )
    result = qproperties(text)
    assert "WFritzLCD" in result, (
        f"T-QSS-05 FAIL: selector 'WFritzLCD' not found (got {list(result.keys())!r})"
    )
    props = result["WFritzLCD"]
    assert props.get("litColor") == "#30ff70", (
        f"T-QSS-05 FAIL: litColor expected '#30ff70', got {props.get('litColor')!r}"
    )
    assert props.get("boxHeight") == "34", (
        f"T-QSS-05 FAIL: boxHeight expected '34', got {props.get('boxHeight')!r}"
    )
    # Value with commas must be preserved
    assert "titleBrush" in props, (
        f"T-QSS-05 FAIL: 'titleBrush' (comma-containing value) not found in {props!r}"
    )
    # Non-qproperty line must not appear
    assert "background-color" not in props, (
        "T-QSS-05 FAIL: 'background-color' must not be included in qproperty- results"
    )


# ---------------------------------------------------------------------------
# T-QSS-06 — qproperties returns {} for no qproperty- lines
# ---------------------------------------------------------------------------

def test_qproperties_returns_empty_for_no_qproperty_lines():
    """T-QSS-06 FAIL: qproperties must return {} when no qproperty- lines are present."""
    from Code.Fritz.QssRules import qproperties

    text = (
        "QWidget\n"
        "{\n"
        "background-color: #252526;\n"
        "color: #d4d4d4;\n"
        "}\n"
    )
    result = qproperties(text)
    assert result == {}, (
        f"T-QSS-06 FAIL: expected empty dict, got {result!r}"
    )


# ---------------------------------------------------------------------------
# T-QSS-07 — qproperties raises QssContractError on unbalanced braces
# ---------------------------------------------------------------------------

def test_qproperties_raises_on_unbalanced_brace():
    """T-QSS-07 FAIL: qproperties must raise QssContractError for unbalanced braces."""
    from Code.Fritz.Errors import QssContractError
    from Code.Fritz.QssRules import qproperties

    text = (
        "WFritzLCD\n"
        "{\n"
        "qproperty-litColor: #30ff70;\n"
        # Missing closing brace — depth ends at 1
    )
    with pytest.raises(QssContractError, match="braces"):
        qproperties(text)
