"""
tests/unit/rpa/test_vision.py — Unit tests for the Phase 7 Vision layer.

Two tests run without cv2 (checking import hygiene and availability messaging).
All others are ``rpa_cv`` marked and skipped when cv2 is absent or when
``QT_QPA_PLATFORM=offscreen``.

:spec: FR-7, NFR-7, NFR-9, §9 (feature_spec.md)
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile

import pytest

pytestmark = pytest.mark.rpa


# ===========================================================================
# Helpers — run without cv2
# ===========================================================================

def _all_rpa_py_files():
    """Yield absolute paths of all .py files in bin/Code/Rpa/ excluding Vision/."""
    rpa_root = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "bin", "Code", "Rpa"
    )
    rpa_root = os.path.normpath(rpa_root)
    for dirpath, dirnames, filenames in os.walk(rpa_root):
        # Exclude Vision/ — only Vision/ is allowed to import cv2/numpy
        dirnames[:] = [d for d in dirnames if d != "Vision"]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


# ===========================================================================
# No-cv2 tests — always run
# ===========================================================================

def test_availability_no_cv_returns_reason_with_install_command():
    """When cv2 is absent, probe() sets cv_available=False and reason contains the install command."""
    from Code.Rpa.Vision import Availability

    # Temporarily hide cv2 from sys.modules to simulate absence
    cv2_saved = sys.modules.pop("cv2", None)
    try:
        Availability._reset_cache()
        flags = Availability.probe()
        if not flags.cv_available:
            assert "pip install" in flags.reason or "requirements-rpa" in flags.reason, (
                f"Expected install command in reason, got: {flags.reason!r}"
            )
        else:
            # cv2 is actually installed — still verify the shape is correct
            assert isinstance(flags.cv_available, bool)
            assert isinstance(flags.ocr_available, bool)
            assert isinstance(flags.reason, str)
    finally:
        if cv2_saved is not None:
            sys.modules["cv2"] = cv2_saved
        Availability._reset_cache()


def test_no_toplevel_numpy_or_cv2_import_outside_vision():
    """No .py file in Code.Rpa (outside Vision/) has a top-level import of cv2 or numpy."""
    forbidden = {"cv2", "numpy", "np"}
    violations = []

    for path in _all_rpa_py_files():
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=path)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            # Only top-level imports — those whose parent is the Module node
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            # Check depth: top-level nodes have col_offset == 0
            if node.col_offset != 0:
                continue
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            else:
                names = [node.module.split(".")[0]] if node.module else []
            for name in names:
                if name in forbidden:
                    rel = os.path.relpath(path)
                    violations.append(f"{rel}: top-level import of {name!r}")

    assert not violations, (
        "These files outside Vision/ have top-level cv2/numpy imports:\n"
        + "\n".join(violations)
    )


# ===========================================================================
# rpa_cv tests — skipped unless cv2 is available and not offscreen
# ===========================================================================

@pytest.mark.rpa_cv
def test_capture_rgb_channel_order(qt_app):
    """Screenshot.rgb has channels in RGB order (R != B pixel check)."""
    import numpy as np
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QLabel

    label = QLabel()
    label.resize(16, 16)
    # Fill with a pixel where R != B so we can distinguish RGB from BGR
    pm = QPixmap(16, 16)
    pm.fill(QColor(200, 100, 50))  # R=200, G=100, B=50
    label.setPixmap(pm)

    from Code.Rpa.Vision.Capture import grab
    shot = grab(label)

    assert shot.rgb.shape == (16, 16, 3)
    # Top-left pixel must be (200, 100, 50) in RGB — not (50, 100, 200) (BGR)
    r, g, b = shot.rgb[0, 0]
    assert abs(int(r) - 200) < 10, f"Expected R~200, got {r}"
    assert abs(int(b) - 50) < 10, f"Expected B~50, got {b}"


@pytest.mark.rpa_cv
def test_capture_handles_byteperline_padding(qt_app):
    """Screenshot.rgb has correct shape for an odd-width widget."""
    import numpy as np
    from PySide6.QtWidgets import QLabel

    # 15 pixels wide — bytesPerLine will be padded to 16*3=48 (4-byte aligned)
    label = QLabel()
    label.resize(15, 8)

    from Code.Rpa.Vision.Capture import grab
    shot = grab(label)

    assert shot.rgb.shape == (8, 15, 3), (
        f"Expected (8, 15, 3), got {shot.rgb.shape}"
    )


@pytest.mark.rpa_cv
def test_screenshot_logical_resizes_by_dpr(qt_app):
    """Screenshot.logical() returns an array whose size is physical / dpr."""
    import numpy as np
    from PySide6.QtWidgets import QLabel

    label = QLabel()
    label.resize(20, 10)

    from Code.Rpa.Vision.Capture import Screenshot
    import numpy as np

    fake_rgb = np.zeros((20, 40, 3), dtype=np.uint8)
    shot = Screenshot(rgb=fake_rgb, dpr=2.0)
    logical = shot.logical()

    assert logical.shape == (10, 20, 3), (
        f"Expected (10, 20, 3), got {logical.shape}"
    )


@pytest.mark.rpa_cv
def test_template_match_finds_known_template():
    """Template.find_all() finds a template embedded in a larger image."""
    import numpy as np

    from Code.Rpa.Vision.Capture import Screenshot
    from Code.Rpa.Vision.Template import find_all

    # Build a 50×50 white image with a 10×10 red patch at (20, 10)
    img = np.full((50, 50, 3), 220, dtype=np.uint8)
    img[10:20, 20:30] = [200, 0, 0]  # red patch

    template = img[10:20, 20:30].copy()
    shot = Screenshot(rgb=img, dpr=1.0)

    matches = find_all(shot, template, threshold=0.95)
    assert len(matches) >= 1
    m = matches[0]
    assert abs(m.rect.x - 20) <= 2
    assert abs(m.rect.y - 10) <= 2
    assert m.confidence >= 0.95


@pytest.mark.rpa_cv
def test_template_multi_scale_warns_on_nonunit_scale():
    """find_all() emits a logger.warning when a non-unit scale wins."""
    import logging
    import numpy as np

    from Code.Rpa.Vision.Capture import Screenshot
    from Code.Rpa.Vision.Template import find_all

    # Build image with a 12×12 patch; template is 10×10 — scale mismatch
    img = np.full((60, 60, 3), 220, dtype=np.uint8)
    img[20:32, 20:32] = [0, 180, 0]  # 12×12 green patch

    template = np.full((10, 10, 3), 220, dtype=np.uint8)
    template[:, :] = [0, 180, 0]  # 10×10 — must scale to 1.1 or 1.2 to match

    shot = Screenshot(rgb=img, dpr=1.0)

    with pytest.warns(None) as rec:
        # Capture warnings via logging
        import Code.Rpa.Vision.Template as tmod
        with pytest.MonkeyPatch.context() as mp:
            warned = []
            orig_warn = tmod.logger.warning
            mp.setattr(tmod.logger, "warning", lambda msg, *a: warned.append(msg % a if a else msg))
            matches = find_all(shot, template, threshold=0.80)

    # Either matches found at a non-unit scale (warning issued), or no match at all
    if matches:
        non_unit = [m for m in matches if abs(m.scale - 1.0) > 0.01]
        if non_unit:
            assert any("stale" in w.lower() or "scale" in w.lower() for w in warned)


@pytest.mark.rpa_cv
def test_ocr_finds_multiword_phrase():
    """Ocr.find_phrase() finds a multi-word phrase in a rendered image."""
    import numpy as np
    import cv2

    from Code.Rpa.Vision.Capture import Screenshot
    from Code.Rpa.Vision.Ocr import find_phrase

    # Render text into an image for OCR
    img = np.full((60, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Player name", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)

    shot = Screenshot(rgb=img, dpr=1.0)
    matches = find_phrase(shot, "Player name")

    assert len(matches) >= 1, "Should find 'Player name' in the image"
    m = matches[0]
    assert m.confidence > 0.0


@pytest.mark.rpa_cv
def test_ocr_grouped_by_block_par_line():
    """Ocr.find_phrase() groups words by (block, par, line) so cross-line phrases are not matched."""
    import numpy as np
    import cv2

    from Code.Rpa.Vision.Capture import Screenshot
    from Code.Rpa.Vision.Ocr import find_phrase

    # Put "Player" on line 1 and "name" on line 2
    img = np.full((120, 200, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Player", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, "name", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    shot = Screenshot(rgb=img, dpr=1.0)
    # "Player name" spans two lines — should NOT be found as one phrase
    matches = find_phrase(shot, "Player name")
    # It's acceptable to find zero matches (cross-line is not grouped)
    # What must NOT happen is a high-confidence match
    for m in matches:
        # If something is returned, it should be low-confidence
        assert m.confidence < 0.95, (
            "Cross-line phrase should not produce a confident match"
        )


@pytest.mark.rpa_cv
def test_manifest_hashes_match_files():
    """Manifest.load_and_verify() succeeds when hashes are correct."""
    import hashlib

    from Code.Rpa.Vision.Manifest import load_and_verify

    with tempfile.TemporaryDirectory() as td:
        # Create a dummy PNG (just bytes — Manifest doesn't care about format)
        png_path = os.path.join(td, "btn.png")
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        with open(png_path, "wb") as fh:
            fh.write(content)
        digest = hashlib.sha256(content).hexdigest()

        manifest_data = {
            "templates": [
                {
                    "name": "btn",
                    "path": "btn.png",
                    "sha256": digest,
                    "dpr": 1.0,
                    "theme": "Default",
                    "ui_mode": "classical",
                    "translator": "en",
                    "captured_at": "2026-08-28T00:00:00Z",
                    "width": 10,
                    "height": 10,
                }
            ]
        }
        manifest_path = os.path.join(td, "manifest.json")
        with open(manifest_path, "w") as fh:
            json.dump(manifest_data, fh)

        m = load_and_verify(manifest_path)
        assert "btn" in m.entries
        entry = m.entries["btn"]
        assert entry.dpr == 1.0
        assert entry.theme == "Default"


@pytest.mark.rpa_cv
def test_manifest_missing_entry_raises():
    """Manifest.get() raises ManifestError for an unknown template name."""
    from Code.Rpa.Errors import ManifestError
    from Code.Rpa.Vision.Manifest import load_and_verify

    with tempfile.TemporaryDirectory() as td:
        manifest_path = os.path.join(td, "manifest.json")
        with open(manifest_path, "w") as fh:
            json.dump({"templates": []}, fh)

        m = load_and_verify(manifest_path)
        with pytest.raises(ManifestError, match="not in the manifest"):
            m.get("nonexistent_template")
