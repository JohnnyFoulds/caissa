"""
tools/design/elements.py — Per-element review artefacts for the ribbon design gate.

For each visual element in the ribbon, produces:

  elem_<name>.png  — Fritz reference crop above / Caissa candidate crop below,
                     1 px grey gutter, 4× nearest-neighbour upscale, caption strip.
  elem_<name>.txt  — same numbers as text (quotable).

Usage::

    python3 tools/design/elements.py [--variant light|dark] [--element NAME]

The script is a development tool; not a test and not a CI artefact.
The gate passes only on user sign-off per element — this script provides the evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_BIN = _REPO / "bin"
os.chdir(_BIN)
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from tools.design import DESIGN_OUT, FRITZ_REF  # noqa: E402

# ── Element registry ──────────────────────────────────────────────────────────
# Each entry: (name, claim, ref_box, cand_box_fn, target_values)
# ref_box: (x0, y0, x1, y1) in ribbon_home.png coordinates (image is 820×242,
#          ribbon runs y=5..147).
# cand_box_fn(cand_w, cand_h): returns (x0, y0, x1, y1) in the candidate image.
# target_values: list of (label, target_value) for the caption.

_REF_W = 820


def _w(x0, y0, x1, y1):
    """Simple box as closure."""
    return (x0, y0, x1, y1)


ELEMENTS = [
    {
        "name": "chrome_bg",
        "claim": "Flat #efeff2 everywhere — no banding, no blue tint",
        "ref_box":   (200, 5, 500, 148),
        "cand_box":  lambda w, h: (200, 0, min(500, w), h),
        "targets": [
            ("background hex", "#efeff2"),
            ("same in all bands", "yes"),
        ],
    },
    {
        "name": "band_geometry",
        "claim": "QAT 29px / tabs 21px / rule 1px / content 91px = 143 total",
        "ref_box":   (0, 5, 40, 148),
        "cand_box":  lambda w, h: (0, 0, 40, h),
        "targets": [
            ("total height", "143 px"),
            ("QAT row", "29 px"),
            ("tab row", "21 px"),
            ("content", "91 px"),
        ],
    },
    {
        "name": "qat_row",
        "claim": "QAT is its own row ABOVE the tabs, 29 px tall, 16-20 px icons",
        "ref_box":   (0, 5, 820, 34),
        "cand_box":  lambda w, h: (0, 0, w, min(29, h)),
        "targets": [
            ("QAT is above tabs", "yes"),
            ("QAT row height", "29 px"),
        ],
    },
    {
        "name": "unselected_tabs",
        "claim": "Flat on #efeff2, #1e1e1e text, no fill, no border, ~13px padding",
        "ref_box":   (65, 34, 250, 56),
        "cand_box":  lambda w, h: (65, 29, min(250, w), 50),
        "targets": [
            ("tab bg", "#efeff2"),
            ("text colour", "#1e1e1e"),
            ("no border", "yes"),
        ],
    },
    {
        "name": "file_tab",
        "claim": "First tab, solid #007acc fill, #ffffff text",
        "ref_box":   (0, 34, 75, 56),
        "cand_box":  lambda w, h: (0, 29, 75, 50),
        "targets": [
            ("fill", "#007acc"),
            ("text", "#ffffff"),
            ("position", "first"),
        ],
    },
    {
        "name": "selected_tab",
        "claim": "#efeff2 fill, 3-sided #cccedb border, #005b99 text, breaks rule",
        "ref_box":   (170, 34, 260, 57),
        "cand_box":  lambda w, h: (170, 29, min(260, w), 52),
        "targets": [
            ("fill", "#efeff2 (same as bg)"),
            ("border top/left/right", "#cccedb"),
            ("no bottom border", "yes — breaks rule"),
            ("text", "#005b99"),
        ],
    },
    {
        "name": "rules_borders",
        "claim": "Tab-row rule and ribbon bottom border are 1px #cccedb",
        "ref_box":   (0, 53, 300, 60),
        "cand_box":  lambda w, h: (0, 48, min(300, w), 55),
        "targets": [
            ("rule colour", "#cccedb"),
            ("rule height", "1 px"),
            ("bottom border", "#cccedb"),
        ],
    },
    {
        "name": "group_separators",
        "claim": "#cccedb hairlines, ~86/91 content height, NO group box outlines",
        "ref_box":   (210, 56, 235, 148),
        "cand_box":  lambda w, h: (210, 51, min(235, w), h),
        "targets": [
            ("colour", "#cccedb"),
            ("height", "~86 of 91 px"),
            ("margin", "2px top, 3px bottom"),
            ("group boxes", "none"),
        ],
    },
    {
        "name": "large_button",
        "claim": "32px icon above 8pt text, ~66px tall, text wraps 2 lines",
        "ref_box":   (221, 56, 360, 148),
        "cand_box":  lambda w, h: (221, 51, min(360, w), h),
        "targets": [
            ("icon size", "32×32 px"),
            ("button height", "~66 px"),
            ("text", "8pt, 2 lines where needed"),
        ],
    },
    {
        "name": "active_large_button",
        "claim": "Solid #007acc fill, #ffffff text when button is active/toggled",
        "ref_box":   (10, 56, 70, 135),
        "cand_box":  lambda w, h: (10, 51, 70, min(135, h)),
        "targets": [
            ("active fill", "#007acc"),
            ("active text", "#ffffff"),
        ],
    },
    {
        "name": "dropdown_chevron",
        "claim": "5×3 px chevron centred below text, only on menu buttons",
        "ref_box":   (240, 110, 360, 135),
        "cand_box":  lambda w, h: (240, 105, min(360, w), min(135, h)),
        "targets": [
            ("chevron size", "5×3 px"),
            ("position", "centred, below text"),
            ("only on menu buttons", "yes"),
        ],
    },
    {
        "name": "checkbox",
        "claim": "11px indicator, 1px #a2a4a5 border, #ffffff fill, #1e1e1e check",
        "ref_box":   (80, 60, 230, 130),
        "cand_box":  lambda w, h: (80, 55, min(230, w), min(130, h)),
        "targets": [
            ("indicator size", "11×11 px"),
            ("border colour", "#a2a4a5"),
            ("fill", "#ffffff"),
        ],
    },
    {
        "name": "disabled_state",
        "claim": "#a2a4a5 text and border for disabled controls",
        "ref_box":   (638, 56, 820, 100),
        "cand_box":  lambda w, h: (max(0, w - 182), 51, w, 100),
        "targets": [
            ("disabled text", "#a2a4a5"),
            ("disabled border", "#a2a4a5"),
        ],
    },
    {
        "name": "group_caption",
        "claim": "#1e1e1e (not grey), 8pt, horizontally centred under group",
        "ref_box":   (80, 128, 480, 148),
        "cand_box":  lambda w, h: (80, max(0, h - 20), min(480, w), h),
        "targets": [
            ("colour", "#1e1e1e"),
            ("size", "8 pt"),
            ("alignment", "centred under group"),
        ],
    },
]


def _make_font(size: int):
    """Try to load a system font; fall back to default."""
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _caption_strip(targets: list, w: int) -> Image.Image:
    """Build a grey caption strip with target values."""
    font = _make_font(11)
    row_h = 14
    h = len(targets) * row_h + 4
    strip = Image.new("RGB", (w, h), (240, 240, 240))
    draw = ImageDraw.Draw(strip)
    for i, (label, val) in enumerate(targets):
        text = f"{label}: {val}"
        draw.text((4, 2 + i * row_h), text, fill=(20, 20, 20), font=font)
    return strip


def render_element(
    ref: Image.Image,
    candidate: Image.Image,
    elem: dict,
    out_dir: Path,
    scale: int = 4,
) -> Path:
    """Render a single element comparison image and its text file.

    :param ref: Full Fritz reference image (820×242).
    :param candidate: Full candidate ribbon image.
    :param elem: Element dict from ELEMENTS.
    :param out_dir: Output directory.
    :param scale: Upscale factor (default 4 — nearest-neighbour).
    :returns: Path to the saved PNG.
    """
    name = elem["name"]
    rx0, ry0, rx1, ry1 = elem["ref_box"]
    cand_w, cand_h = candidate.size
    cx0, cy0, cx1, cy1 = elem["cand_box"](cand_w, cand_h)

    ref_crop = ref.crop((rx0, ry0, rx1, ry1)).convert("RGB")
    cand_crop = candidate.crop((cx0, cy0, cx1, cy1)).convert("RGB")

    # Normalise widths for side-by-side
    target_w = max(ref_crop.width, cand_crop.width)
    if ref_crop.width < target_w:
        tmp = Image.new("RGB", (target_w, ref_crop.height), (0xef, 0xef, 0xf2))
        tmp.paste(ref_crop, (0, 0))
        ref_crop = tmp
    if cand_crop.width < target_w:
        tmp = Image.new("RGB", (target_w, cand_crop.height), (0xef, 0xef, 0xf2))
        tmp.paste(cand_crop, (0, 0))
        cand_crop = tmp

    # Upscale both
    ref_up = ref_crop.resize(
        (ref_crop.width * scale, ref_crop.height * scale), Image.NEAREST
    )
    cand_up = cand_crop.resize(
        (cand_crop.width * scale, cand_crop.height * scale), Image.NEAREST
    )

    gutter_h = 2
    full_w = max(ref_up.width, cand_up.width)
    label_h = 14
    caption = _caption_strip(elem["targets"], full_w)

    total_h = label_h + ref_up.height + gutter_h + cand_up.height + 2 + caption.height
    out_img = Image.new("RGB", (full_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(out_img)

    # Header label
    font = _make_font(12)
    draw.text((4, 0), f"Element: {name}  —  {elem['claim']}", fill=(40, 40, 40), font=font)

    y = label_h
    out_img.paste(ref_up, (0, y))
    y += ref_up.height
    # gutter
    draw.rectangle([(0, y), (full_w, y + gutter_h - 1)], fill=(160, 160, 160))
    y += gutter_h
    out_img.paste(cand_up, (0, y))
    y += cand_up.height + 2
    out_img.paste(caption, (0, y))

    out_path = out_dir / f"elem_{name}.png"
    out_img.save(str(out_path))

    # Text file
    txt_path = out_dir / f"elem_{name}.txt"
    lines = [
        f"Element: {name}",
        f"Claim: {elem['claim']}",
        f"Ref crop: ({rx0},{ry0})-({rx1},{ry1}) in ribbon_home.png",
        f"Cand crop: ({cx0},{cy0})-({cx1},{cy1}) in candidate",
        "",
        "Targets:",
    ]
    for label, val in elem["targets"]:
        lines.append(f"  {label}: {val}")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return out_path


def main() -> None:
    """Produce per-element comparison images for the design gate."""
    parser = argparse.ArgumentParser(description="Fritz ribbon per-element review images")
    parser.add_argument("--variant", default="light", choices=["light", "dark"])
    parser.add_argument("--element", default=None, help="Render one element by name")
    args = parser.parse_args()

    # Bootstrap Qt + load the mock module
    spec = importlib.util.spec_from_file_location(
        "fritz_mock", str(_REPO / "tools" / "design" / "fritz_mock.py")
    )
    mock_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock_mod)
    mock_mod._init()

    out_dir = DESIGN_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    # Render candidate (ribbon_calib preferred; ribbon_home fallback)
    scene_fn = mock_mod._SCENES.get("ribbon_calib") or mock_mod._SCENES.get("ribbon_home")
    if scene_fn is None:
        print("ERROR: no ribbon_calib or ribbon_home scene in fritz_mock.py")
        sys.exit(1)
    cand_path = scene_fn(out_dir, args.variant, 820)
    candidate = Image.open(cand_path).convert("RGB")
    print(f"Candidate: {cand_path}  {candidate.size}")

    # Load reference
    ref_file = FRITZ_REF / "ribbon_home.png"
    if not ref_file.exists():
        print(f"ERROR: reference not found: {ref_file}")
        sys.exit(1)
    ref = Image.open(ref_file).convert("RGB")
    print(f"Reference: {ref_file}  {ref.size}")

    # Resize candidate to 820 wide (reference width) for pixel-accurate crops
    if candidate.width != 820:
        scale = 820 / candidate.width
        candidate = candidate.resize(
            (820, int(candidate.height * scale)), Image.LANCZOS
        )

    # Pick elements
    elems = ELEMENTS
    if args.element:
        elems = [e for e in ELEMENTS if e["name"] == args.element]
        if not elems:
            names = [e["name"] for e in ELEMENTS]
            print(f"Unknown element {args.element!r}. Available: {names}")
            sys.exit(1)

    for elem in elems:
        out_path = render_element(ref, candidate, elem, out_dir)
        print(f"  {elem['name']:28s}  {out_path}")

    print(f"\nAll element images in: {out_dir}")


if __name__ == "__main__":
    main()
