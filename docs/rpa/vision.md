# Vision Layer

**Status:** Finalised against Phase 7 (`feat/rpa-vision`).  
**See also:** `docs/rpa/selectors.md` (tier model), `docs/rpa/activities.md` (CV activities)

The Vision layer adds image and OCR location tiers on top of the object tier in
`TargetResolver`.  It is entirely optional — the full object-tier RPA layer works
without OpenCV or Tesseract installed.

---

## Architecture

```
bin/Code/Rpa/Vision/
├── __init__.py          0 bytes — zero import cost
├── Availability.py      Capability probe (cached, never raises)
├── Capture.py           QWidget → Screenshot  (Qt-touching — N-RPA-2)
├── Template.py          matchTemplate + NMS, hosts Match
├── Ocr.py               pytesseract phrase location
└── Manifest.py          Template manifest loader + sha256 verifier
```

**Only `Capture.py` may import PySide6.** All other Vision modules import only
`numpy`, `cv2`, and `pytesseract`.  Enforced by
`test_no_toplevel_numpy_or_cv2_import_outside_vision`.

The `Screenshot` dataclass and `Match` dataclass live in `Capture.py` and
`Template.py` respectively — **not** in `Types.py` — because `Types.py` must be
free of numpy/cv2 imports (N-RPA-1).

---

## Installing the Vision dependencies

```bash
pip install -r requirements-rpa.txt   # opencv-python-headless, pytesseract
brew install tesseract                 # macOS
# apt install tesseract-ocr            # Debian/Ubuntu
```

Run `tools/caissa-rpa doctor` to verify:

```
cv_available   : True
ocr_available  : True
```

The object-tier RPA layer works fully without these packages.

---

## Availability probe

```python
from Code.Rpa.Vision.Availability import probe, AvailabilityFlags

flags = probe()          # cached; never raises
print(flags.cv_available)   # True / False
print(flags.ocr_available)  # True / False
print(flags.reason)         # install hint when False
```

The probe is run at most once per process.  `_reset_cache()` is provided for tests
only.

---

## Capturing a screenshot

```python
from Code.Rpa.Vision.Capture import grab, Screenshot

shot = grab(some_qwidget)
# shot.rgb   — H×W×3 uint8 ndarray, RGB order, physical (DPR) resolution
# shot.dpr   — device pixel ratio
```

`Screenshot.logical()` returns the array resized to logical (DPR-1) coordinates
using `INTER_AREA`.  All matching and OCR run on `logical()` so returned `Rect`
values are in logical pixels.

**`bytesPerLine()` padding** — Qt pads each scanline to a 4-byte boundary.
`grab()` handles this correctly; naïve reshape on `w*3` shears the image for odd
widths.

**Channel order** — `Format_RGB888` is already RGB.  Nothing inside `Vision/`
calls `cvtColor` to swap channels.

---

## Template matching

```python
from Code.Rpa.Vision.Template import find_all, Match

matches = find_all(screenshot, template_rgb, threshold=0.80)
# returns list[Match] sorted by confidence descending
# Match.rect         — Rect in logical coordinates
# Match.confidence   — float in [0, 1]
# Match.scale        — scale at which the template was matched (1.0 = exact)
```

**Algorithm:**

1. Run `cv2.matchTemplate` with `TM_CCOEFF_NORMED` at scale 1.0.
2. If no match exceeds `threshold`, retry at `[0.95, 1.05, 0.90, 1.10]`.
3. When a non-1.0 scale wins, `logger.warning` is emitted — the template is stale.
4. Apply greedy NMS at IoU 0.3 to suppress overlapping detections.

**Authoring templates** — capture at DPR-1 (run `tools/caissa-rpa doctor` to
verify DPR).  The manifest records DPR, theme, ui_mode, and translator so stale
templates are traceable.

---

## OCR phrase location

```python
from Code.Rpa.Vision.Ocr import find_phrase, Match

matches = find_phrase(screenshot, "Player name")
# returns list[Match] sorted by confidence descending
```

**Algorithm:**

1. Upscale 2× with `INTER_CUBIC` + convert to grayscale (Tesseract is unreliable
   on 11–13 px UI text without upscaling).
2. Run `pytesseract.image_to_data`.
3. Group words by `(block_num, par_num, line_num)`.
4. Sliding-window match over each line for the target phrase.
5. Return bounding boxes covering the full phrase, in logical coordinates.

Multi-word phrases that span two lines are **not** matched — this is intentional.
Use a per-word selector and anchoring if you need cross-line targeting.

---

## Template manifest

The manifest at `Resources/Rpa/Templates/manifest.json` records metadata for every
template PNG:

```json
{
    "templates": [
        {
            "name": "toolbar_options_button",
            "path": "Resources/Rpa/Templates/toolbar_options_button.png",
            "dpr": 1.0,
            "theme": "Default",
            "ui_mode": "classical",
            "translator": "en",
            "captured_at": "2026-08-28T14:22:33Z",
            "sha256": "abcdef0123456789...",
            "width": 28,
            "height": 28
        }
    ]
}
```

`Manifest.load_and_verify()` checks every entry:

1. The PNG file exists at `path`.
2. Its SHA-256 matches `sha256`.

A mismatch raises `ManifestError` with the exact fix: re-capture the template.

An empty manifest (`{"templates": []}`) is valid — required even when no templates
have been captured.

---

## Integration with TargetResolver

When `tier="auto"`, the resolver tries:

1. **Object tier** (always) — Qt widget tree.
2. **Image tier** — if `selector.image` is set and `cv_available` is True.
3. **OCR tier** — if `selector.text` is set and `ocr_available` is True.

A `logger.warning` is emitted whenever a non-object tier wins:

```
WARNING Code.Rpa.Resolve: Non-object tier (image) used for selector ... — fix the object selector
```

This warning is the signal that the object selector needs updating.  CV wins are
journalled with their tier and confidence so they are diagnosable later.

**Explicit tier requests:**

```python
# image-only — raises VisionUnavailableError if cv2 not installed
Selector(tier="image", image="toolbar_options_button")

# ocr-only — raises VisionUnavailableError if tesseract not installed
Selector(tier="ocr", text="Player name")
```

`tier="auto"` silently skips unavailable tiers and falls back to the next one, so
removing OpenCV does not break the object-tier suite.

---

## The `rpa_cv` test marker

Tests that require cv2 or a real display are marked `rpa_cv`:

```bash
make test          # skips rpa_cv (default suite)
make test-cv       # CAISSA_RPA_CV=1 pytest -m rpa_cv -v
```

The conftest skip hook skips `rpa_cv` tests when:
- `QT_QPA_PLATFORM=offscreen` (headless CI), **or**
- `cv2` is not importable.

This guarantees that the default suite never depends on OpenCV.

---

## When to use CV vs object tier

| Situation | Recommendation |
|---|---|
| Widget has an `objectName` | Always use object tier |
| No `objectName` but predictable `text` | Object tier with `text=` |
| Custom-painted widget (board, piece rendering) | Image tier — object tier is blind here |
| Verifying icon presence | Image tier |
| Verifying text rendered by a QPainter | OCR tier |
| Both available | Object tier — CV is the fallback, not the default |

The governance rule: **every CV assertion must be paired with an object-tier
assertion where one is possible.**  CV-only tests carry `rpa_cv` and are excluded
from the default run.

---

## Whole-screen reference captures

`Resources/Rpa/Reference/` stores full-window reference captures:

```
Resources/Rpa/Reference/
├── home_screen.png          reference capture
├── home_screen.json         assertion list
├── config_dialog.png
└── config_dialog.json
```

Each `.json` sidecar lists:

```json
{
    "templates_present": ["toolbar_options_button"],
    "templates_absent": [],
    "ocr_phrases_present": ["Lucas Chess"],
    "regions": []
}
```

The reference PNG is never pixel-diffed — it is the human-readable record of what
the screen looked like when the expectations were authored.  Assertions are
template-presence and OCR-text-location *within* the capture (N-RPA-7).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `VisionUnavailableError: cv2 not installed` | cv2 absent | `pip install -r requirements-rpa.txt` |
| `VisionUnavailableError: tesseract binary not found` | binary absent | `brew install tesseract` |
| `ManifestError: SHA-256 mismatch for template X` | template file changed | Re-capture and update manifest |
| `find_all()` returns empty with `logger.warning: stale` | template size changed | Re-capture at DPR-1 |
| OCR misses a phrase | UI text too small | Check `confidence_threshold`; ensure DPR-1 capture |
| `rpa_cv` tests skip in CI | Offscreen platform or no cv2 | Expected; object-tier suite covers CI |
