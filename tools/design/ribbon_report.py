"""
tools/design/ribbon_report.py — Fritz ribbon fidelity scorecard.

Renders the Caissa ribbon offscreen via ``fritz_mock.ribbon_home`` (which must
have been updated to use the real ``WRibbon`` widget), compares it pixel-by-pixel
against the Fritz 18 reference crop, and prints a target/actual/Δ/verdict table
for every measurable attribute.

Usage::

    python3 tools/design/ribbon_report.py [--variant light|dark]

The script is a development tool; it is not a test and not a CI artefact.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

# Bootstrap paths so Code.* imports resolve
_REPO = Path(__file__).resolve().parents[2]
_BIN = _REPO / "bin"
os.chdir(_BIN)
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

from tools.design import DESIGN_OUT, FRITZ_REF  # noqa: E402
from tools.design.compare import (  # noqa: E402
    chrome_mask,
    diff_heatmap,
    masked_mean_diff,
    mean_abs_diff_full,
    row_ink_profile,
    score_label,
)

# ── measured Fritz targets ────────────────────────────────────────────────────

# All values from pixel analysis of ~/Pictures/fritz-reference/ribbon_home.png.
_FRITZ_REF_FILE = "ribbon_home.png"

TARGET = {
    "total_height": 143,
    "qat_height": 29,
    "tabrow_height": 21,
    "rule_height": 1,
    "content_height": 91,
    "chrome_hex": "#efeff2",
    "separator_hex": "#cccedb",
    "accent_hex": "#007acc",
    "body_text_hex": "#1e1e1e",
    "caption_hex": "#1e1e1e",
    "selected_tab_text_hex": "#005b99",
    "disabled_hex": "#a2a4a5",
    "large_btn_height": 66,
    "large_icon_size": 32,
    "checkbox_indicator_px": 11,
    "group_sep_margin_top": 2,
    "group_sep_margin_bottom": 3,
}


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _nearest_hex(img: Image.Image, x0: int, y0: int, x1: int, y1: int) -> str:
    """Most common non-white pixel hex in a region."""
    from collections import Counter
    px = img.load()
    bg = (0xff, 0xff, 0xff)
    c: Counter = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            p = px[x, y]
            if p != bg:
                c[p] += 1
    if not c:
        return "#000000"
    r, g, b = c.most_common(1)[0][0]
    return f"#{r:02x}{g:02x}{b:02x}"


def _dominant_hex(img: Image.Image, x0: int, y0: int, x1: int, y1: int) -> str:
    """Dominant colour hex in a region."""
    from collections import Counter
    px = img.load()
    c: Counter = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            c[px[x, y]] += 1
    if not c:
        return "#000000"
    r, g, b = c.most_common(1)[0][0]
    return f"#{r:02x}{g:02x}{b:02x}"


def _count_band(img: Image.Image, y0: int, y1: int, bg_hex: str = "#efeff2") -> int:
    """Number of rows in [y0, y1) where non-bg count > 5 (i.e. ink rows)."""
    bg = _hex_to_rgb(bg_hex)
    px = img.load()
    w = img.width
    return sum(
        1 for y in range(y0, y1)
        if sum(1 for x in range(w) if px[x, y] != bg) > 5
    )


def _row_ink_profile_band(img: Image.Image, y0: int, y1: int, bg_hex: str = "#efeff2") -> list:
    bg = _hex_to_rgb(bg_hex)
    px = img.load()
    w = img.width
    return [sum(1 for x in range(w) if px[x, y] != bg) for y in range(y0, y1)]


def _band_height(profile: list) -> int:
    """Span from first to last row with ink (non-bg) > 5."""
    ink = [i for i, v in enumerate(profile) if v > 5]
    if not ink:
        return 0
    return ink[-1] - ink[0] + 1


def _selected_tab_breaks_rule(img: Image.Image, sep_hex: str = "#cccedb") -> bool:
    """True if there is a horizontal gap in the y=rule row under the selected tab."""
    sep = _hex_to_rgb(sep_hex)
    bg = _hex_to_rgb("#efeff2")
    px = img.load()
    w = img.width
    # Find the first row that is mostly separator colour
    for rule_y in range(20, min(60, img.height)):
        n_sep = sum(1 for x in range(w) if px[x, rule_y] == sep)
        if n_sep > w * 0.6:
            # Check if there is a gap (bg run >= 20 px wide)
            gap_run = 0
            max_gap = 0
            for x in range(w):
                if px[x, rule_y] == bg:
                    gap_run += 1
                    max_gap = max(max_gap, gap_run)
                else:
                    gap_run = 0
            return max_gap >= 20
    return False


def _file_tab_is_blue(img: Image.Image, accent_hex: str = "#007acc") -> bool:
    """True if the leftmost tab area has significant accent fill."""
    accent = _hex_to_rgb(accent_hex)
    px = img.load()
    count = sum(
        1 for y in range(10, min(60, img.height))
        for x in range(0, min(80, img.width))
        if px[x, y] == accent
    )
    return count > 50


def _measure_candidate(img: Image.Image) -> dict:
    """Extract pixel measurements from the candidate ribbon image."""
    bg = "#efeff2"
    profile = row_ink_profile(img, _hex_to_rgb(bg))
    w, h = img.size

    measured: dict = {}
    measured["total_height"] = h

    # Band heights: find major regions by row-ink changes
    # QAT row: rows near the top that have ink (icons)
    # Tab row: rows with moderate ink (text) after a background gap
    # Rule: single dense row
    # Content: bulk of ink
    # Bottom border: last ink row

    # Find rule row (mostly single-colour across width)
    rule_y = -1
    sep = _hex_to_rgb("#cccedb")
    sep_px = img.load()
    for y in range(10, min(h - 5, 80)):
        n = sum(1 for x in range(w) if sep_px[x, y] == sep)
        if n > w * 0.6:
            rule_y = y
            break

    measured["rule_height"] = 1 if rule_y >= 0 else 0

    # QAT band = rows above the tab bar with ink
    if rule_y > 0:
        # Tab row is above rule_y; QAT is above tab row
        # Heuristic: find any significant gap in ink rows from top to rule_y
        top_ink = [i for i, v in enumerate(profile[:rule_y]) if v > 5]
        if top_ink:
            # Split at largest gap
            gaps = []
            for i in range(len(top_ink) - 1):
                g = top_ink[i + 1] - top_ink[i]
                if g > 3:
                    gaps.append((g, top_ink[i]))
            if gaps:
                gap_after = max(gaps, key=lambda t: t[0])[1]
                measured["qat_height"] = gap_after + 1
                measured["tabrow_height"] = rule_y - gap_after - 2
            else:
                measured["qat_height"] = rule_y // 2
                measured["tabrow_height"] = rule_y - rule_y // 2
        else:
            measured["qat_height"] = 0
            measured["tabrow_height"] = rule_y
    else:
        measured["qat_height"] = 0
        measured["tabrow_height"] = 0

    # Content: rows below rule_y, above the last all-separator/blank row
    # Bottom border: last separator row
    if rule_y >= 0:
        content_rows = [i for i, v in enumerate(profile[rule_y + 1:], rule_y + 1)
                        if v > 5]
        measured["content_height"] = (content_rows[-1] - content_rows[0] + 1) if content_rows else 0
    else:
        measured["content_height"] = 0

    # Dominant chrome colour in a chrome-only band
    measured["chrome_hex"] = _dominant_hex(img, 0, 1, w, min(5, h))
    # Separator colour = dominant in the rule row
    measured["separator_hex"] = _dominant_hex(img, 0, rule_y, w, rule_y + 1) if rule_y >= 0 else "n/a"
    # Accent = dominant in the leftmost tab slot (File tab area)
    measured["accent_hex"] = _dominant_hex(img, 2, max(rule_y - 18, 0), 70, rule_y) if rule_y >= 0 else "n/a"

    measured["file_tab_is_blue"] = _file_tab_is_blue(img)
    measured["selected_tab_breaks_rule"] = _selected_tab_breaks_rule(img)

    return measured


def _row(label: str, target, actual, unit: str = "") -> str:
    ok = "✓" if str(target) == str(actual) else "✗"
    delta = ""
    try:
        d = int(actual) - int(target)
        delta = f"{d:+d}"
    except (TypeError, ValueError):
        pass
    return f"  {ok} {label:<34s} target={str(target)+unit:<12s} actual={str(actual)+unit:<12s} {delta}"


def main() -> None:
    """Run the ribbon scorecard."""
    parser = argparse.ArgumentParser(description="Fritz ribbon fidelity scorecard")
    parser.add_argument("--variant", default="light", choices=["light", "dark"])
    args = parser.parse_args()

    # Bootstrap Qt
    spec = importlib.util.spec_from_file_location(
        "fritz_mock", str(_REPO / "tools" / "design" / "fritz_mock.py")
    )
    mock_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock_mod)
    mock_mod._init()

    # Render the candidate
    out_dir = DESIGN_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    render_fn = mock_mod._SCENES.get("ribbon_calib") or mock_mod._SCENES.get("ribbon_home")
    if render_fn is None:
        print("ERROR: no ribbon_calib or ribbon_home scene found in fritz_mock.py")
        sys.exit(1)

    scene_name = "ribbon_calib" if "ribbon_calib" in mock_mod._SCENES else "ribbon_home"
    out_path = render_fn(out_dir, args.variant, 820)
    print(f"\nRendered: {out_path}")

    candidate = Image.open(out_path).convert("RGB")

    # Load reference
    ref_file = FRITZ_REF / _FRITZ_REF_FILE
    if not ref_file.exists():
        print(f"WARNING: reference not found at {ref_file} — skipping diff scores")
        ref = None
    else:
        ref = Image.open(ref_file).convert("RGB")
        ref_crop = ref.crop((0, 5, 820, 148))  # y=5..147 = ribbon proper

    # Measure candidate
    m = _measure_candidate(candidate)

    # Print scorecard
    print("\n══════════════════════════════════════════════════════════════")
    print(f"  Fritz ribbon fidelity — {scene_name} ({args.variant})")
    print("══════════════════════════════════════════════════════════════")
    print("\n  Band geometry")
    print(_row("total_height", TARGET["total_height"], m.get("total_height", "?"), " px"))
    print(_row("qat_height", TARGET["qat_height"], m.get("qat_height", "?"), " px"))
    print(_row("tabrow_height", TARGET["tabrow_height"], m.get("tabrow_height", "?"), " px"))
    print(_row("rule_height", TARGET["rule_height"], m.get("rule_height", "?"), " px"))
    print(_row("content_height", TARGET["content_height"], m.get("content_height", "?"), " px"))

    print("\n  Palette")
    print(_row("chrome_hex", TARGET["chrome_hex"], m.get("chrome_hex", "?")))
    print(_row("separator_hex", TARGET["separator_hex"], m.get("separator_hex", "?")))
    print(_row("accent_hex", TARGET["accent_hex"], m.get("accent_hex", "?")))

    print("\n  Structural booleans")
    print(_row("file_tab_is_blue", True, m.get("file_tab_is_blue", "?")))
    print(_row("selected_tab_breaks_rule", True, m.get("selected_tab_breaks_rule", "?")))

    if ref is not None:
        print("\n  Diff scores (candidate vs Fritz reference y=5..147, 820×143)")
        # Resize candidate to match reference crop
        ref_w, ref_h = ref_crop.size
        cand_scaled = candidate.resize((ref_w, ref_h), Image.LANCZOS)
        mask = chrome_mask(ref_crop)
        full_d = mean_abs_diff_full(ref_crop, cand_scaled)
        masked_d = masked_mean_diff(ref_crop, cand_scaled, mask)
        mask_px = sum(1 for p in mask.getdata() if p)
        total_px = ref_w * ref_h
        print(f"    chrome-masked diff (style score): {masked_d:.1f}  ({score_label(masked_d)})")
        print(f"    full-resolution diff:              {full_d:.1f}  ({score_label(full_d)})")
        print(f"    chrome pixel coverage:             {mask_px}/{total_px} = {100*mask_px/total_px:.0f}%")

        heatmap_path = out_dir / f"ribbon_heatmap_{args.variant}.png"
        diff_heatmap(ref_crop, cand_scaled).save(str(heatmap_path))
        print(f"\n  Heatmap: {heatmap_path}")

    print("\n══════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
