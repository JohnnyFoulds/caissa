"""
bin/Code/Rpa/Vision/StyleSource.py — QSS source resolution for Vision findings.

Maps widget (object_name, cls) + paint_overrides + flattened widget-type set
onto the style rules that actually govern it.  Emits three-valued ``effective``
states, named placeholders, and ``e1_violation`` flags for bare ``QColor``
class constants.

**No Qt imports.  No cv2.  No I/O.  Callers own the file reads.**

Usage::

    sources = style_sources_for(
        object_name="WRibbonTabBar",
        cls="_FlatTabBar",
        qss_sources=[
            (Path("fritz-widgets.qss"), fritz_widgets_text),
            (Path("Caissa.qss"), caissa_text),
        ],
        paint_overrides={"paintEvent": {"file": "WRibbon.py", "line": 127,
                                        "class": "_FlatTabBar"}},
        widget_types=frozenset({"QTabBar", "_FlatTabBar", "QTextEdit", ...}),
        colour_map={"CHROME_ACCENT": "#007acc", ...},
        live_stylesheet=app.styleSheet(),   # None for offline use
    )

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# QSS rule parser  (generalised from Fritz/QssRules.qproperties)
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([A-Z0-9_]+)\}")
_HEX_LITERAL_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def parse_rules(text: str) -> dict[str, dict[str, str]]:
    """Parse every CSS-property line from *text* into a selector→property map.

    Returns ``{selector: {property_name: value}}``.  Handles both the
    ``selector\\n{\\n  prop: val;\\n}`` (Q3-correct) and ``selector {`` (Q3
    violation but present in some files) forms.  Comment lines (``/* ... */``)
    and blank lines are skipped.

    Unlike ``QssRules.qproperties`` this is not restricted to ``qproperty-``
    lines — every CSS property in every block is captured.

    :param text: Full ``.qss`` file contents.
    :return: Nested dict; empty when the text has no parseable blocks.
    """
    result: dict[str, dict[str, str]] = {}
    current_selector: str | None = None
    depth = 0

    # CSS property: name followed by a single ':', not '::'
    # Negative-lookahead ensures we don't match "QTabBar::tab" as "QTabBar" + ":tab"
    _PROP_RE = re.compile(r"^([\w\-]+)\s*:(?!:)\s*(.+?)\s*;?\s*$")

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("/*") or stripped.startswith("//"):
            continue

        opens = stripped.count("{")
        closes = stripped.count("}")

        if stripped == "{":
            depth += 1
            continue

        if "}" in stripped and "{" not in stripped:
            depth = max(0, depth - closes)
            if depth == 0:
                current_selector = None
            continue

        # Only treat '{' as a CSS structural brace when outside a block (depth==0).
        # Inside a block (depth>0) a '{' is part of a placeholder value like {KEY}.
        if depth == 0 and "{" in stripped:
            # selector { ... } on one line, or selector {
            before = stripped.split("{")[0].strip()
            if before:
                current_selector = before
            net = opens - closes
            depth += net
            if depth < 0:
                depth = 0
            # If this is a single-line block "selector { prop: val; }", parse inline
            if net == 0 and current_selector and "}" in stripped:
                inner = stripped.split("{", 1)[1].rsplit("}", 1)[0].strip()
                for decl in inner.split(";"):
                    decl = decl.strip()
                    if decl:
                        m = _PROP_RE.match(decl)
                        if m:
                            prop, value = m.group(1), m.group(2).strip()
                            result.setdefault(current_selector, {})[prop] = value
                current_selector = None
            continue

        # Selector line: depth==0, no braces, and either no colon at all OR
        # only pseudo-class / sub-control colons (the line doesn't look like a
        # CSS property: a property line has exactly one ":" with a value after).
        if depth == 0 and not _PROP_RE.match(stripped):
            current_selector = stripped
            continue

        if depth > 0 and current_selector and ":" in stripped:
            m = _PROP_RE.match(stripped)
            if m:
                prop, value = m.group(1), m.group(2).rstrip(";").strip()
                result.setdefault(current_selector, {})[prop] = value

    return result


def resolve_placeholders(
    text: str,
    colour_map: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Replace ``{KEY}`` placeholders in *text* using *colour_map*.

    :param text: Raw ``.qss`` text with ``{KEY}`` tokens.
    :param colour_map: ``{KEY: resolved_value}`` mapping from the active theme.
    :return: ``(resolved_text, {found_key: resolved_value})``.
    """
    found: dict[str, str] = {}

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        val = colour_map.get(key, m.group(0))
        if val != m.group(0):
            found[key] = val
        return val

    resolved = _PLACEHOLDER_RE.sub(_replace, text)
    return resolved, found


# ---------------------------------------------------------------------------
# Effective state computation
# ---------------------------------------------------------------------------

def effective(
    selector: str,
    paint_overrides: dict,
    widget_types: frozenset[str],
    live_stylesheet: str | None,
) -> str:
    """Compute the three-valued ``effective`` state for a QSS selector.

    :param selector: The QSS selector string, e.g. ``"QTabWidget::pane"``.
    :param paint_overrides: Dict of ``{method_name: {file, line, class}}``
        describing ``paintEvent`` / ``sizeHint`` / ``tabSizeHint`` overrides on
        the owning widget class.
    :param widget_types: Set of class names present anywhere in the flattened
        widget tree (from ``Region.flatten``).
    :param live_stylesheet: ``QApplication.styleSheet()`` text, or ``None``
        when offline.
    :return: ``"loaded_unmatched"`` | ``"matched_overridden"`` | ``"effective"``
        | ``"unconfirmed"``.
    """
    # Extract the widget type from the selector (first token, possibly with
    # pseudo-class / sub-control suffixes).
    widget_type = _selector_widget_type(selector)

    # Check whether the type is present in the tree at all.
    if widget_type and widget_type not in widget_types:
        return "loaded_unmatched"

    # Check whether paintEvent defeats this selector's properties.
    if "paintEvent" in paint_overrides:
        return "matched_overridden"

    # Without a live stylesheet we cannot confirm.
    if live_stylesheet is None:
        return "unconfirmed"

    # A rule that didn't survive stylesheet composition (wrong theme order etc.)
    # won't appear in the live text.
    base_selector = selector.split("::")[0].split(":")[0].strip()
    if base_selector and base_selector not in live_stylesheet:
        return "loaded_unmatched"

    return "effective"


def _selector_widget_type(selector: str) -> str:
    """Extract the widget class name from a QSS selector.

    Examples::

        "QTabWidget::pane"     → "QTabWidget"
        "#WRibbonTabBar::tab"  → ""   (object-name selectors have no type)
        "QTabBar::tab:selected" → "QTabBar"

    :param selector: Raw QSS selector string.
    :return: Widget class name, or ``""`` when not extractable.
    """
    part = selector.split("::")[0].split(":")[0].strip()
    if part.startswith("#") or part.startswith("."):
        return ""
    # Strip any descendant combinators
    part = part.split()[-1] if " " in part else part
    if part and part[0].isupper():
        return part
    return ""


# ---------------------------------------------------------------------------
# Paint colour constants (AST scan for E1 violations)
# ---------------------------------------------------------------------------

def paint_colour_constants(
    source_path: Path,
    cls: str,
) -> list[dict]:
    """Find bare ``QColor("#RRGGBB")`` class-level attributes in *source_path*.

    These are E1 violations: a ``#RRGGBB`` literal in a widget module that is
    not a ``QtCore.Property`` default.

    :param source_path: Path to a Python source file.
    :param cls: Class name to scan within the file.
    :return: List of ``{symbol, hex, line, e1_violation: True}`` dicts.
    """
    try:
        src = Path(source_path).read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return []

    results: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != cls:
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            # Check for QColor("#RRGGBB") or QtGui.QColor("#RRGGBB") on the RHS
            val = item.value
            _is_qcolor = (
                isinstance(val, ast.Call)
                and val.args
                and isinstance(val.args[0], ast.Constant)
                and isinstance(val.args[0].value, str)
                and _HEX_LITERAL_RE.match(val.args[0].value)
                and (
                    (isinstance(val.func, ast.Name) and val.func.id == "QColor")
                    or (isinstance(val.func, ast.Attribute) and val.func.attr == "QColor")
                )
            )
            if not _is_qcolor:
                continue
            for target in item.targets:
                if isinstance(target, ast.Name):
                    results.append({
                        "symbol": f"{cls}.{target.id}",
                        "hex": val.args[0].value,
                        "line": item.lineno,
                        "e1_violation": True,
                    })
    return results


# ---------------------------------------------------------------------------
# Main bridge function
# ---------------------------------------------------------------------------

def style_sources_for(
    object_name: str,
    cls: str,
    qss_sources: Sequence[tuple[Path, str]],
    paint_overrides: dict,
    widget_types: frozenset[str],
    colour_map: dict[str, str] | None = None,
    live_stylesheet: str | None = None,
) -> list[dict]:
    """Resolve the style rules that govern widget (object_name, cls).

    Returns a list of source dicts, most-governing first.  Each entry carries:

    - ``kind``: ``"qss"`` | ``"paint"``
    - ``file``: repo-relative path string
    - ``line``: 1-based line number (int) or 0 when unavailable
    - ``selector``: QSS selector string (``"qss"`` entries only)
    - ``authored``: raw property→value dict before placeholder substitution
    - ``resolved``: property→value dict after substitution
    - ``placeholder_of``: ``{property: placeholder_key}`` for substituted props
    - ``effective``: ``"loaded_unmatched"`` | ``"matched_overridden"`` |
      ``"effective"`` | ``"unconfirmed"``
    - ``governs``: list of property categories this entry actually affects
    - ``e1_violation``: ``True`` when the source is an E1-violating paint const
      (``"paint"`` entries only)

    :param object_name: Widget ``objectName``, e.g. ``"WRibbonTabBar"``.
    :param cls: Python class name, e.g. ``"_FlatTabBar"``.
    :param qss_sources: List of ``(path, text)`` pairs, last-appended-wins order.
    :param paint_overrides: Dict of ``{method: {file, line, class}}`` from the
        driver snapshot's ``paint_overrides`` field.
    :param widget_types: Flat set of all widget class names in the tree.
    :param colour_map: Active theme's placeholder substitution map.
    :param live_stylesheet: ``QApplication.styleSheet()`` or ``None`` (offline).
    :return: List of source dicts; empty when no matching rules are found.
    """
    colour_map = colour_map or {}
    results: list[dict] = []

    for qss_path, raw_text in qss_sources:
        resolved_text, placeholder_map = resolve_placeholders(raw_text, colour_map)
        rules = parse_rules(resolved_text)
        raw_rules = parse_rules(raw_text)

        for sel, props in rules.items():
            authored_props = raw_rules.get(sel, {})
            resolved_props = props

            # Compute placeholder_of
            placeholder_of: dict[str, str] = {}
            for prop, val in authored_props.items():
                m = _PLACEHOLDER_RE.search(val)
                if m:
                    placeholder_of[prop] = m.group(1)

            # Find the line number of this selector in the raw text
            line_no = _find_selector_line(raw_text, sel)

            eff = effective(sel, paint_overrides, widget_types, live_stylesheet)

            # Determine what this entry governs
            governs = _classify_governs(resolved_props, paint_overrides)

            results.append({
                "kind": "qss",
                "file": str(qss_path),
                "line": line_no,
                "selector": sel,
                "authored": authored_props,
                "resolved": resolved_props,
                "placeholder_of": placeholder_of,
                "effective": eff,
                "governs": governs,
            })

    # Paint colour constants (E1 violations)
    if paint_overrides:
        for method, override in paint_overrides.items():
            src_file = override.get("file", "")
            src_line = override.get("line", 0)
            src_cls = override.get("class", cls)
            if src_file:
                consts = paint_colour_constants(Path(src_file), src_cls)
                for c in consts:
                    results.append({
                        "kind": "paint",
                        "file": src_file,
                        "line": c["line"],
                        "selector": f"{src_cls}.{c['symbol'].split('.')[-1]}",
                        "authored": {"value": c["hex"]},
                        "resolved": {"value": c["hex"]},
                        "placeholder_of": {},
                        "effective": "effective",
                        "governs": ["fill"],
                        "e1_violation": True,
                    })
            # Also record the paintEvent entry itself
            results.append({
                "kind": "paint",
                "file": src_file,
                "line": src_line,
                "selector": f"{src_cls}.{method}",
                "authored": {"method": method},
                "resolved": {"method": method},
                "placeholder_of": {},
                "effective": "effective",
                "governs": ["fill", "colour"],
                "e1_violation": False,
            })

    # Sort: most-governing first (paint → effective qss → matched_overridden → rest)
    _eff_order = {"effective": 0, "unconfirmed": 1,
                  "matched_overridden": 2, "loaded_unmatched": 3}
    _kind_order = {"paint": 0, "qss": 1}
    results.sort(
        key=lambda r: (
            _kind_order.get(r["kind"], 9),
            _eff_order.get(r["effective"], 9),
        )
    )

    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_selector_line(text: str, selector: str) -> int:
    """Return the 1-based line number of *selector* in *text*, or 0."""
    target = selector.strip()
    for i, raw in enumerate(text.splitlines(), start=1):
        if raw.strip() == target:
            return i
    return 0


def _classify_governs(
    props: dict[str, str],
    paint_overrides: dict,
) -> list[str]:
    """Return the property categories this rule governs.

    A rule that paintEvent overrides governs only geometry; otherwise it
    governs fill/colour too (paint has not stolen them).

    :param props: Resolved property dict for this rule.
    :param paint_overrides: Paint override map from the snapshot.
    :return: List of category strings.
    """
    categories: list[str] = []
    _GEO_PROPS = {"padding", "margin", "margin-right", "margin-left",
                  "margin-top", "margin-bottom", "font-size", "font",
                  "min-width", "min-height", "max-width", "max-height",
                  "width", "height", "border-radius", "border-top-left-radius",
                  "border-top-right-radius", "border-bottom-left-radius",
                  "border-bottom-right-radius", "top", "left", "right", "bottom",
                  "spacing", "padding-left", "padding-right", "padding-top",
                  "padding-bottom"}
    _COLOUR_PROPS = {"background-color", "color", "border", "border-color",
                     "border-top", "border-bottom", "border-left", "border-right",
                     "selection-background-color", "selection-color",
                     "outline", "outline-color"}

    has_geo = any(p in _GEO_PROPS for p in props)
    has_colour = any(p in _COLOUR_PROPS for p in props)

    if has_geo:
        categories.append("geometry")
    if has_colour:
        if paint_overrides:
            # paintEvent has stolen colour governance
            pass
        else:
            categories.append("colour")
    if not categories:
        categories.append("other")
    return categories
