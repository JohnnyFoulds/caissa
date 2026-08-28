"""
tests/test_fritz_light_theme.py — Fritz light theme compliance tests.

T-LIT-01  test_template_gaps_empty_for_all_eleven_colors_files
T-LIT-02  test_no_q1_or_q3_violation_in_fritz_qss
T-LIT-03  test_geometry_parity_between_themes
T-LIT-04  test_same_qproperty_names_different_values
T-LIT-05  test_board_static_dark_in_both_themes
T-LIT-06  test_is_dark_differs_between_themes
T-LIT-07  test_both_modes_resolve_to_modern_fritz_ui_hook
T-LIT-08  test_every_wfritz_selector_present_in_both_themes

:spec: Phase 6 (feature_spec.md), FR-40..FR-47
"""

from __future__ import annotations

import glob
import os
import re

import pytest

pytestmark = pytest.mark.ui

_STYLES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "Resources", "Styles")
)
_FRITZ_QSS = os.path.join(_STYLES_DIR, "Fritz.qss")
_MF_QSS = os.path.join(_STYLES_DIR, "Modern Fritz.qss")
_FRITZ_COLORS = os.path.join(_STYLES_DIR, "Fritz.colors")
_MF_COLORS = os.path.join(_STYLES_DIR, "Modern Fritz.colors")
_TEMPLATE = os.path.join(_STYLES_DIR, "colors.template")


def _read_colors(path: str) -> dict[str, str]:
    """Parse a .colors file into {KEY: value}."""
    result: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    return result


def _strip_color_lines(qss_text: str) -> list[str]:
    """Return lines that contain no #RRGGBB hex colour values."""
    return [ln for ln in qss_text.splitlines() if not re.search(r"#[0-9A-Fa-f]{6}", ln)]


def _qproperty_names(qss_text: str) -> dict[str, set[str]]:
    """Parse {selector: {property_name, ...}} for all qproperty- lines."""
    result: dict[str, set[str]] = {}
    current: str | None = None
    for line in qss_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("qproperty-"):
            name = stripped.split(":")[0].replace("qproperty-", "")
            if current is not None:
                result.setdefault(current, set()).add(name)
        elif stripped == "{":
            pass
        elif stripped.endswith("{") and not stripped.startswith("/"):
            current = stripped.rstrip(" {").strip()
        elif stripped == "}":
            current = None
    return result


def _wfritz_selectors(qss_text: str) -> set[str]:
    """Return all WFritz* and WRibbon* selectors (and their # variants) in the QSS."""
    return set(re.findall(r"(?:^|\n)\s*(#?W(?:Fritz|Ribbon)\w+)", qss_text))


def test_template_gaps_empty_for_all_eleven_colors_files():
    """T-LIT-01: template_gaps is empty for all 11 .colors files against colors.template."""
    from Code.Fritz.QssRules import template_gaps

    with open(_TEMPLATE, encoding="utf-8") as fh:
        template_text = fh.read()
    template_keys: set[str] = set()
    for line in template_text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#") and not line.startswith("["):
            template_keys.add(line.split("=")[0].strip())

    colors_files = glob.glob(os.path.join(_STYLES_DIR, "*.colors"))
    assert len(colors_files) >= 11, (
        f"T-LIT-01 FAIL: expected ≥11 .colors files, found {len(colors_files)}"
    )

    violations: list[str] = []
    for cf in colors_files:
        with open(cf, encoding="utf-8") as fh:
            colors_text = fh.read()
        gaps = template_gaps(template_keys, set(_read_colors(cf).keys()))
        if gaps:
            violations.append(f"{os.path.basename(cf)}: missing {sorted(gaps)}")

    assert not violations, (
        "T-LIT-01 FAIL: some .colors files are missing template keys:\n"
        + "\n".join(violations)
    )


def test_no_q1_or_q3_violation_in_fritz_qss():
    """T-LIT-02: scan_qss reports no Q1 or Q3 violations in Fritz.qss."""
    from Code.Fritz.QssRules import scan_qss

    assert os.path.isfile(_FRITZ_QSS), "T-LIT-02 FAIL: Fritz.qss not found"
    with open(_FRITZ_QSS, encoding="utf-8") as fh:
        text = fh.read()

    violations = scan_qss(text)
    assert not violations, (
        f"T-LIT-02 FAIL: Fritz.qss has Q1/Q3 violations:\n"
        + "\n".join(f"  L{ln}: {rule} — {line!r}" for ln, rule, line in violations)
    )


def test_geometry_parity_between_themes():
    """T-LIT-03: Fritz.qss and Modern Fritz.qss are identical once colour-bearing lines are stripped."""
    for path in (_FRITZ_QSS, _MF_QSS):
        assert os.path.isfile(path), f"T-LIT-03 FAIL: {path} not found"

    with open(_FRITZ_QSS, encoding="utf-8") as fh:
        fritz_stripped = _strip_color_lines(fh.read())
    with open(_MF_QSS, encoding="utf-8") as fh:
        mf_stripped = _strip_color_lines(fh.read())

    assert fritz_stripped == mf_stripped, (
        "T-LIT-03 FAIL: Fritz.qss and Modern Fritz.qss differ in non-color lines.\n"
        "First diff:\n"
        + "\n".join(
            f"  Fritz   L{i+1}: {a!r}\n  MFritz  L{i+1}: {b!r}"
            for i, (a, b) in enumerate(zip(fritz_stripped, mf_stripped))
            if a != b
        )[:2000]
    )


def test_same_qproperty_names_different_values():
    """T-LIT-04: Both theme files declare the same set of qproperty- names per selector with different values."""
    for path in (_FRITZ_QSS, _MF_QSS):
        assert os.path.isfile(path), f"T-LIT-04 FAIL: {path} not found"

    with open(_FRITZ_QSS, encoding="utf-8") as fh:
        fritz_props = _qproperty_names(fh.read())
    with open(_MF_QSS, encoding="utf-8") as fh:
        mf_props = _qproperty_names(fh.read())

    # Every selector that appears in one must appear in the other with the same property names.
    all_selectors = set(fritz_props) | set(mf_props)
    violations: list[str] = []
    for sel in sorted(all_selectors):
        fp = fritz_props.get(sel, set())
        mp = mf_props.get(sel, set())
        if fp != mp:
            violations.append(
                f"Selector {sel!r}: Fritz={sorted(fp)} vs MFritz={sorted(mp)}"
            )

    assert not violations, (
        "T-LIT-04 FAIL: qproperty- name sets differ between themes:\n"
        + "\n".join(violations)
    )

    # At least the chrome colours should differ — a light/dark sanity check.
    chrome_selectors = [s for s in all_selectors if "WFritzPane" in s or "WFritzEvalGraph" in s]
    if chrome_selectors:
        with open(_FRITZ_QSS, encoding="utf-8") as fh:
            fritz_text = fh.read()
        with open(_MF_QSS, encoding="utf-8") as fh:
            mf_text = fh.read()
        assert fritz_text != mf_text, (
            "T-LIT-04 FAIL: Fritz.qss and Modern Fritz.qss are identical — light theme was not applied"
        )


def test_board_static_dark_in_both_themes():
    """T-LIT-05: BOARD_STATIC key is dark in both Fritz.colors and Modern Fritz.colors."""
    for path in (_FRITZ_COLORS, _MF_COLORS):
        assert os.path.isfile(path), f"T-LIT-05 FAIL: {path} not found"

    fritz_colors = _read_colors(_FRITZ_COLORS)
    mf_colors = _read_colors(_MF_COLORS)

    for name, colors in (("Fritz", fritz_colors), ("Modern Fritz", mf_colors)):
        bs = colors.get("BOARD_STATIC", "")
        assert bs, f"T-LIT-05 FAIL: BOARD_STATIC missing from {name}.colors"
        # Dark means all three RGB components ≤ 0x40 (dark background).
        # BOARD_STATIC=#161616 is black; any value lighter than #404040 fails.
        bs_clean = bs.lstrip("#")
        assert len(bs_clean) == 6, f"T-LIT-05 FAIL: malformed BOARD_STATIC in {name}: {bs!r}"
        r, g, b = int(bs_clean[0:2], 16), int(bs_clean[2:4], 16), int(bs_clean[4:6], 16)
        assert max(r, g, b) <= 0x40, (
            f"T-LIT-05 FAIL: BOARD_STATIC={bs!r} in {name}.colors is too light "
            f"(max channel {max(r,g,b):#04x} > 0x40)"
        )


def test_is_dark_differs_between_themes():
    """T-LIT-06: IS_DARK is 0 in Fritz.colors and 1 in Modern Fritz.colors."""
    for path in (_FRITZ_COLORS, _MF_COLORS):
        assert os.path.isfile(path), f"T-LIT-06 FAIL: {path} not found"

    fritz = _read_colors(_FRITZ_COLORS)
    mf = _read_colors(_MF_COLORS)

    assert fritz.get("IS_DARK") == "0", (
        f"T-LIT-06 FAIL: Fritz.colors IS_DARK={fritz.get('IS_DARK')!r}, expected '0'"
    )
    assert mf.get("IS_DARK") == "1", (
        f"T-LIT-06 FAIL: Modern Fritz.colors IS_DARK={mf.get('IS_DARK')!r}, expected '1'"
    )


def test_both_modes_resolve_to_modern_fritz_ui_hook():
    """T-LIT-07: load_mode_hook resolves both mode files to modern_fritz_ui.py."""
    import importlib.util

    from Code.UIModes.UIModes import load_mode_hook

    hook_light = load_mode_hook("Modern Fritz")
    assert hook_light is not None, (
        "T-LIT-07 FAIL: load_mode_hook('Modern Fritz') returned None"
    )
    assert hasattr(hook_light, "on_mode_enter"), (
        "T-LIT-07 FAIL: Modern Fritz hook has no on_mode_enter"
    )

    # The dark variant uses hook="modern_fritz" to share the same module.
    hook_dark = load_mode_hook("Modern Fritz Dark", hook="modern_fritz")
    assert hook_dark is not None, (
        "T-LIT-07 FAIL: load_mode_hook('Modern Fritz Dark', hook='modern_fritz') returned None"
    )
    assert hasattr(hook_dark, "on_mode_enter"), (
        "T-LIT-07 FAIL: Modern Fritz Dark hook has no on_mode_enter"
    )

    # Both must resolve to the same file.
    assert hook_light.__file__ == hook_dark.__file__, (
        f"T-LIT-07 FAIL: hooks resolved to different files:\n"
        f"  light: {hook_light.__file__}\n"
        f"  dark:  {hook_dark.__file__}"
    )


def test_every_wfritz_selector_present_in_both_themes():
    """T-LIT-08: Every #WFritz*/#WRibbon* selector present in one theme file is present in the other."""
    for path in (_FRITZ_QSS, _MF_QSS):
        assert os.path.isfile(path), f"T-LIT-08 FAIL: {path} not found"

    with open(_FRITZ_QSS, encoding="utf-8") as fh:
        fritz_selectors = _wfritz_selectors(fh.read())
    with open(_MF_QSS, encoding="utf-8") as fh:
        mf_selectors = _wfritz_selectors(fh.read())

    only_in_fritz = fritz_selectors - mf_selectors
    only_in_mf = mf_selectors - fritz_selectors

    assert not only_in_fritz and not only_in_mf, (
        "T-LIT-08 FAIL: WFritz/WRibbon selectors not present in both themes.\n"
        + (f"  Only in Fritz.qss: {sorted(only_in_fritz)}\n" if only_in_fritz else "")
        + (f"  Only in Modern Fritz.qss: {sorted(only_in_mf)}\n" if only_in_mf else "")
    )
