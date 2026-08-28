"""
tools/design/review.py — Fritz design review sheet.

Renders each scene (or fetches a live screenshot), pairs it with its Fritz 18
reference crop, and writes a side-by-side HTML sheet.  Opens the sheet in your
browser via ``webbrowser.open``.

Usage
─────
    # Mockup column (static widget rendering)
    QT_QPA_PLATFORM=offscreen python3 tools/design/review.py --scene all

    # Live column (right-hand column = screenshot of the running app)
    python3 tools/design/review.py --scene all --live

    # Single scene, light variant
    QT_QPA_PLATFORM=offscreen python3 tools/design/review.py --scene clocks --variant light

Options
───────
    --scene SCENE [SCENE …]  Scenes to review; ``all`` reviews every scene
    --variant dark|light      QSS variant (default: dark)
    --live                    Replace the mockup column with a running-app screenshot
    --no-browser              Write review.html but do not open it
    --out DIR                 Override CAISSA_DESIGN_OUT

:spec: §0.4, Phase 0 (feature_spec.md)
"""
from __future__ import annotations

import argparse
import base64
import io
import socket
import tempfile
import webbrowser
from pathlib import Path

from PIL import Image


# ── helpers ────────────────────────────────────────────────────────────────────

def _img_to_b64(path: Path) -> str:
    """Return a base64-encoded data URI for an image file."""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:{mime};base64,{b64}"


def _pil_to_b64(img: Image.Image) -> str:
    """Return a base64-encoded PNG data URI for a PIL image."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _diff_score(our_path: Path, ref_path: Path) -> float | None:
    """Compute mean-diff score between our render and the reference."""
    if not our_path.exists() or not ref_path.exists():
        return None
    from tools.design.compare import images_mean_diff
    from tools.design.compare import score_label
    a = Image.open(our_path)
    b = Image.open(ref_path)
    return images_mean_diff(a, b)


def _live_screenshot(scene: str) -> bytes | None:
    """
    Grab a screenshot of the running Caissa app via the Unix socket.

    Returns raw PNG bytes, or None if the app is not running.
    """
    sock_path = "/tmp/caissa-control.sock"
    if not Path(sock_path).exists():
        return None
    import json
    import os

    tmp = Path(tempfile.gettempdir()) / f"caissa-review-live-{scene}.png"
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(sock_path)
        cmd = f"screenshot {tmp}\n"
        s.sendall(cmd.encode())
        data = b""
        while b"\n" not in data:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        s.close()
        resp = json.loads(data.decode().strip())
        if resp.get("ok") and tmp.exists():
            return tmp.read_bytes()
    except Exception:
        pass
    return None


# ── HTML template ──────────────────────────────────────────────────────────────

_CSS = """
body { font-family: system-ui, -apple-system, sans-serif; background: #1a1a1a;
       color: #d4d4d4; margin: 0; padding: 16px; }
h1 { font-size: 18px; font-weight: 600; color: #ffffff; margin-bottom: 4px; }
p.meta { font-size: 11px; color: #888; margin-top: 0; }
table { border-collapse: collapse; width: 100%; margin-bottom: 32px; }
th { background: #252526; color: #aaa; font-size: 11px; font-weight: normal;
     padding: 6px 10px; text-align: left; border: 1px solid #3a3a3a; }
td { border: 1px solid #3a3a3a; padding: 8px; vertical-align: top; }
td.scene-label { width: 120px; font-size: 12px; font-weight: 600;
                 color: #d4d4d4; background: #252526; white-space: nowrap; }
td.img-cell { background: #111; }
td.score-cell { width: 90px; text-align: center; background: #252526; }
img { max-width: 100%; display: block; }
.score { font-size: 20px; font-weight: 700; }
.score-identical { color: #6fc35a; }
.score-close     { color: #b5ce77; }
.score-similar   { color: #e5c07b; }
.score-different { color: #e06c75; }
.score-na        { color: #555; }
.verdict { font-size: 10px; color: #888; margin-top: 2px; }
.missing { color: #555; font-size: 11px; font-style: italic; padding: 40px 0; text-align: center; }
"""

_ROW_TEMPLATE = """
<tr>
  <td class="scene-label">{scene}</td>
  <td class="img-cell" title="Fritz 18 reference">{ref_img}</td>
  <td class="img-cell" title="Caissa mockup">{our_img}</td>
  <td class="score-cell">
    <div class="score {score_class}">{score_text}</div>
    <div class="verdict">{verdict}</div>
  </td>
</tr>
"""


def _score_class(score: float | None) -> tuple[str, str, str]:
    """Return (css_class, text, verdict) for a diff score."""
    if score is None:
        return "score-na", "—", "no reference"
    from tools.design.compare import score_label
    label = score_label(score)
    return f"score-{label}", f"{score:.1f}", label


def build_html(rows: list[dict]) -> str:
    """Build the full review HTML from a list of row dicts."""
    import datetime

    row_html = ""
    for row in rows:
        score_css, score_text, verdict = _score_class(row["score"])
        ref_html = (f'<img src="{row["ref_src"]}" alt="Fritz 18 reference">'
                    if row["ref_src"] else '<div class="missing">no reference</div>')
        our_html = (f'<img src="{row["our_src"]}" alt="Caissa mockup">'
                    if row["our_src"] else '<div class="missing">not rendered</div>')
        row_html += _ROW_TEMPLATE.format(
            scene=row["scene"],
            ref_img=ref_html,
            our_img=our_html,
            score_class=score_css,
            score_text=score_text,
            verdict=verdict,
        )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Caissa Fritz Design Review</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Caissa Fritz Design Review</h1>
<p class="meta">Generated {now} &nbsp;·&nbsp;
Left: Fritz 18 reference &nbsp;·&nbsp;
Right: Caissa mockup &nbsp;·&nbsp;
Score: mean-abs-diff (0=identical, 255=opposite)</p>
<table>
<thead>
<tr>
  <th>Scene</th>
  <th>Fritz 18 reference</th>
  <th>Caissa mockup</th>
  <th>Diff score</th>
</tr>
</thead>
<tbody>
{row_html}
</tbody>
</table>
</body>
</html>"""


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build Fritz design review sheet."
    )
    parser.add_argument("--scene", nargs="+", default=["all"])
    parser.add_argument("--variant", choices=["dark", "light"], default="dark")
    parser.add_argument("--live", action="store_true",
                        help="Use a running-app screenshot instead of a static mockup.")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    import sys
    import os
    _REPO = Path(__file__).resolve().parents[2]
    _BIN = _REPO / "bin"
    for p in [str(_REPO), str(_BIN)]:
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(_BIN)

    from tools.design import DESIGN_OUT, FRITZ_REF, SCENES, SCENE_REF

    out_dir = args.out or DESIGN_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine which scenes to review
    all_scenes = SCENES
    if "all" in args.scene:
        scenes_to_review = all_scenes
    else:
        scenes_to_review = [s for s in args.scene if s in all_scenes]

    # Render mockups (unless --live)
    if not args.live:
        print("Rendering mockups…")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fritz_mock", _REPO / "tools" / "design" / "fritz_mock.py"
        )
        mock_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mock_mod)
        mock_mod._init()
        for name in scenes_to_review:
            fn = mock_mod._SCENES.get(name)
            if fn:
                path = fn(out_dir, args.variant, 420)
                print(f"  {name:20s}  →  {path.name}")

    # Build rows
    rows = []
    for scene in scenes_to_review:
        ref_file = FRITZ_REF / SCENE_REF.get(scene, "")
        our_file = out_dir / f"{scene}_{args.variant}.png"

        # Reference image
        ref_src = _img_to_b64(ref_file) if ref_file.exists() else None

        # Our image: live screenshot or rendered mockup
        our_src = None
        if args.live:
            png_bytes = _live_screenshot(scene)
            if png_bytes:
                img = Image.open(io.BytesIO(png_bytes))
                our_src = _pil_to_b64(img)
                # Also save for diffing
                live_path = out_dir / f"{scene}_live.png"
                live_path.write_bytes(png_bytes)
                our_file = live_path
        else:
            our_src = _img_to_b64(our_file) if our_file.exists() else None

        # Diff score
        score = _diff_score(our_file, ref_file) if (our_file.exists() and ref_file.exists()) else None

        rows.append({
            "scene": scene,
            "ref_src": ref_src,
            "our_src": our_src,
            "score": score,
        })

    # Write HTML
    html = build_html(rows)
    review_path = out_dir / "review.html"
    review_path.write_text(html, encoding="utf-8")
    print(f"\nReview sheet: {review_path}")

    if not args.no_browser:
        webbrowser.open(review_path.as_uri())


if __name__ == "__main__":
    main()
