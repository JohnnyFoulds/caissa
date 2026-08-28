"""
tests/test_sidebar_icon_consistency.py

Three-layer verification that the Caissa sidebar renders icons at a
consistent visual weight across all screens.

  Layer 1 — toolbar_info    live button W×H from the running app
  Layer 2 — icon pack       content bbox and alpha coverage from Iconos_vscode.bin
  Layer 3 — screenshot crop pixel-level ground truth: icons that share
                            identical source art must look identical when
                            rendered in different screen contexts

Run:
    pytest tests/test_sidebar_icon_consistency.py -v
"""
import io
import json
import math
import os
import socket
import time

import pytest
from PIL import Image, ImageChops

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PACK_BIN = os.path.join(_REPO, "Resources", "IntFiles", "Iconos_vscode.bin")
_PACK_DIC = os.path.join(_REPO, "Resources", "IntFiles", "Iconos_vscode.dic")

# ---------------------------------------------------------------------------
# Icon name constants
# ---------------------------------------------------------------------------

# Map from toolbar button text → Iconos function name in the VSCode pack.
BUTTON_TO_ICON = {
    # Home screen
    "Quit":        "FinPartida",
    "Play":        "Libre",
    "Train":       "Entrenamiento",
    "Compete":     "NuevaPartida",
    "Tools":       "Tools",
    "Engines":     "Engines",
    "Options":     "Options",
    "Information": "Informacion",
    # Play screen
    "Cancel":      "Cancelar",
    "Resign":      "Abandonar",
    "Draw":        "Tablas",
    "Advice":      "Advice",
    "Takeback":    "Atras",
    "Reinit":      "Reiniciar",
    "Pause":       "Pelicula_Pausa",
    "Adjourn":     "Aplazar",
    "Config":      "Configurar",
    "Utilities":   "Utilidades",
}

# Icons known to share identical source artwork (same override PNG).
# Used as ground-truth pairs in Layer 3.
GROUND_TRUTH_PAIRS = [
    # (home_button_text, play_button_text, shared_source_png)
    ("Tools", "Utilities", "tools.png"),
]

# Thresholds
CONTENT_MAX_DIM_PX   = 22   # no icon content should exceed this in either axis
CONTENT_RANGE_PX     = 8    # max spread: largest - smallest content dim across all icons
ALPHA_COVERAGE_MIN   = 0.04  # at least 4 % of canvas should be non-transparent
ALPHA_COVERAGE_MAX   = 0.55  # at most 55 % (prevents fully-filled blobs)
ALPHA_RANGE_MAX      = 0.30  # max coverage spread across all sidebar icons
CROP_DIFF_THRESHOLD  = 5     # max mean absolute pixel difference for ground-truth crop test


# ---------------------------------------------------------------------------
# Remote-control helpers
# ---------------------------------------------------------------------------

_SOCK = "/tmp/caissa-control.sock"


def _send(command: str, timeout: float = 15.0) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(_SOCK)
    sock.sendall((command + "\n").encode())
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\n"):
            break
    sock.close()
    return json.loads(data.decode().strip())


def navigate_to_home() -> None:
    """Return to the home (main menu) screen."""
    _send("force_cancel", timeout=10)
    time.sleep(1.5)


def navigate_to_play(engine: str = "drawfish") -> None:
    """Start a game to reach the play screen."""
    _send(f"startgame engine={engine}", timeout=15)
    time.sleep(2.0)


def take_screenshot(path: str) -> str:
    """Take a screenshot of the current window and return the saved path."""
    resp = _send(f"screenshot {path}")
    assert resp.get("ok"), f"screenshot failed: {resp}"
    return path


def sidebar_buttons(toolbar_info: dict) -> list:
    """Return only real buttons from toolbar_info (skip zero-height separators)."""
    return [b for b in toolbar_info["buttons"] if b["height"] > 0 and b["text"]]


# ---------------------------------------------------------------------------
# Icon pack helpers (Layer 2)
# ---------------------------------------------------------------------------

def _load_pack() -> tuple[bytes, dict]:
    with open(_PACK_BIN, "rb") as f:
        data = f.read()
    dic = {}
    with open(_PACK_DIC, "rt") as f:
        for line in f:
            key, rng = line.split("=")
            xfrom, xto = rng.strip().split(",")
            dic[key.strip()] = (int(xfrom), int(xto))
    return data, dic


def load_icon(name: str, pack_data: bytes = None, pack_dic: dict = None) -> Image.Image:
    """Load a named icon from the VSCode pack as a PIL RGBA image."""
    if pack_data is None or pack_dic is None:
        pack_data, pack_dic = _load_pack()
    xfrom, xto = pack_dic[name]
    return Image.open(io.BytesIO(pack_data[xfrom:xto])).convert("RGBA")


def measure_icon(img: Image.Image) -> dict:
    """
    Return visual metrics for a 32×32 icon image:
      bbox_max_dim   max(width, height) of the non-transparent content region
      alpha_pct      fraction of canvas pixels that are non-transparent (alpha > 0)
    """
    bbox = img.getbbox()
    if bbox is None:
        return {"bbox_max_dim": 0, "alpha_pct": 0.0}
    content_w = bbox[2] - bbox[0]
    content_h = bbox[3] - bbox[1]
    total_px = img.width * img.height
    alpha_channel = img.split()[3]
    non_transparent = sum(1 for px in alpha_channel.getdata() if px > 0)
    return {
        "bbox_max_dim": max(content_w, content_h),
        "alpha_pct": non_transparent / total_px,
    }


# ---------------------------------------------------------------------------
# Screenshot crop helper (Layer 3)
# ---------------------------------------------------------------------------

def crop_button(screenshot_path: str, btn: dict, dpr: float) -> Image.Image:
    """
    Crop one button's region from a screenshot.
    btn must have x, y, width, height (logical pixels, window-relative).
    dpr is the device pixel ratio (2 on Retina, 1 on standard).
    """
    img = Image.open(screenshot_path)
    scale = round(dpr)
    left   = int(btn["x"] * scale)
    top    = int(btn["y"] * scale)
    right  = left + int(btn["width"] * scale)
    bottom = top  + int(btn["height"] * scale)
    return img.crop((left, top, right, bottom))


def images_mean_diff(a: Image.Image, b: Image.Image) -> float:
    """Mean absolute pixel difference between two same-size images (0–255)."""
    a = a.convert("RGB").resize((32, 32), Image.LANCZOS)
    b = b.convert("RGB").resize((32, 32), Image.LANCZOS)
    diff = ImageChops.difference(a, b)
    pixels = list(diff.getdata())
    total = sum(sum(ch for ch in px) / len(px) for px in pixels)
    return total / len(pixels)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pack():
    """Loaded icon pack, shared across all pack tests."""
    return _load_pack()


@pytest.fixture(scope="module")
def home_toolbar(tmp_path_factory):
    """toolbar_info captured on the home screen."""
    navigate_to_home()
    return _send("toolbar_info")


@pytest.fixture(scope="module")
def play_toolbar(tmp_path_factory):
    """toolbar_info captured on the play screen."""
    navigate_to_play()
    resp = _send("toolbar_info")
    navigate_to_home()
    return resp


@pytest.fixture(scope="module")
def home_screenshot(tmp_path_factory):
    navigate_to_home()
    path = str(tmp_path_factory.mktemp("shots") / "home.png")
    take_screenshot(path)
    return path, _send("toolbar_info")


@pytest.fixture(scope="module")
def play_screenshot(tmp_path_factory):
    navigate_to_play()
    path = str(tmp_path_factory.mktemp("shots") / "play.png")
    take_screenshot(path)
    info = _send("toolbar_info")
    navigate_to_home()
    return path, info


# ---------------------------------------------------------------------------
# Layer 1 — button sizes
# ---------------------------------------------------------------------------

class TestButtonSizes:
    """All sidebar buttons must be the same W×H regardless of which screen they're on."""

    def test_home_buttons_all_same_width(self, home_toolbar):
        btns = sidebar_buttons(home_toolbar)
        widths = {b["width"] for b in btns}
        assert len(widths) == 1, f"home buttons have mixed widths: {widths}"

    def test_home_buttons_all_same_height(self, home_toolbar):
        btns = sidebar_buttons(home_toolbar)
        heights = {b["height"] for b in btns}
        assert len(heights) == 1, f"home buttons have mixed heights: {heights}"

    def test_play_buttons_all_same_width(self, play_toolbar):
        btns = sidebar_buttons(play_toolbar)
        widths = {b["width"] for b in btns}
        assert len(widths) == 1, f"play buttons have mixed widths: {widths}"

    def test_play_buttons_all_same_height(self, play_toolbar):
        btns = sidebar_buttons(play_toolbar)
        heights = {b["height"] for b in btns}
        assert len(heights) == 1, f"play buttons have mixed heights: {heights}"

    def test_button_width_consistent_across_screens(self, home_toolbar, play_toolbar):
        home_w = {b["width"] for b in sidebar_buttons(home_toolbar)}
        play_w = {b["width"] for b in sidebar_buttons(play_toolbar)}
        assert home_w == play_w, f"button width differs: home={home_w} play={play_w}"

    def test_button_height_consistent_across_screens(self, home_toolbar, play_toolbar):
        home_h = {b["height"] for b in sidebar_buttons(home_toolbar)}
        play_h = {b["height"] for b in sidebar_buttons(play_toolbar)}
        assert home_h == play_h, f"button height differs: home={home_h} play={play_h}"


# ---------------------------------------------------------------------------
# Layer 2 — icon pack metrics
# ---------------------------------------------------------------------------

class TestIconPackMetrics:
    """Icon content bbox and alpha coverage must be consistent across all sidebar icons."""

    def _all_sidebar_icon_names(self, home_toolbar, play_toolbar) -> list:
        names = []
        for screen in (home_toolbar, play_toolbar):
            for btn in sidebar_buttons(screen):
                icon_name = BUTTON_TO_ICON.get(btn["text"])
                if icon_name:
                    names.append((btn["text"], icon_name))
        return names

    def test_no_icon_exceeds_content_max_dim(self, pack, home_toolbar, play_toolbar):
        data, dic = pack
        failures = []
        for btn_text, icon_name in self._all_sidebar_icon_names(home_toolbar, play_toolbar):
            if icon_name not in dic:
                continue
            m = measure_icon(load_icon(icon_name, data, dic))
            if m["bbox_max_dim"] > CONTENT_MAX_DIM_PX:
                failures.append(f"{btn_text}/{icon_name}: {m['bbox_max_dim']}px > {CONTENT_MAX_DIM_PX}px")
        assert not failures, "Icons exceed content size limit:\n" + "\n".join(failures)

    def test_content_size_range_is_narrow(self, pack, home_toolbar, play_toolbar):
        data, dic = pack
        dims = []
        for btn_text, icon_name in self._all_sidebar_icon_names(home_toolbar, play_toolbar):
            if icon_name not in dic:
                continue
            m = measure_icon(load_icon(icon_name, data, dic))
            dims.append(m["bbox_max_dim"])
        spread = max(dims) - min(dims)
        assert spread <= CONTENT_RANGE_PX, (
            f"Icon content size spread {spread}px > {CONTENT_RANGE_PX}px allowed. "
            f"Values: min={min(dims)}, max={max(dims)}"
        )

    def test_all_icons_have_meaningful_alpha_coverage(self, pack, home_toolbar, play_toolbar):
        data, dic = pack
        failures = []
        for btn_text, icon_name in self._all_sidebar_icon_names(home_toolbar, play_toolbar):
            if icon_name not in dic:
                continue
            m = measure_icon(load_icon(icon_name, data, dic))
            if not (ALPHA_COVERAGE_MIN <= m["alpha_pct"] <= ALPHA_COVERAGE_MAX):
                failures.append(f"{btn_text}/{icon_name}: {m['alpha_pct']:.2%} not in [{ALPHA_COVERAGE_MIN:.0%}, {ALPHA_COVERAGE_MAX:.0%}]")
        assert not failures, "Icons outside alpha coverage range:\n" + "\n".join(failures)

    def test_visual_weight_range_is_narrow(self, pack, home_toolbar, play_toolbar):
        data, dic = pack
        coverages = []
        for btn_text, icon_name in self._all_sidebar_icon_names(home_toolbar, play_toolbar):
            if icon_name not in dic:
                continue
            m = measure_icon(load_icon(icon_name, data, dic))
            coverages.append(m["alpha_pct"])
        spread = max(coverages) - min(coverages)
        assert spread <= ALPHA_RANGE_MAX, (
            f"Alpha coverage spread {spread:.2%} > {ALPHA_RANGE_MAX:.0%} allowed. "
            f"min={min(coverages):.2%}, max={max(coverages):.2%}"
        )


# ---------------------------------------------------------------------------
# Layer 3 — ground truth: identical source art must render identically
# ---------------------------------------------------------------------------

class TestGroundTruth:
    """
    Icons that share the same source PNG must be pixel-identical in the pack
    and must produce visually identical crops in screenshots.
    """

    def test_shared_source_icons_are_pixel_identical_in_pack(self, pack):
        """
        Tools (home) and Utilities (play) both override to tools.png.
        Their rendered images must be pixel-identical.
        """
        data, dic = pack
        for home_btn, play_btn, _ in GROUND_TRUTH_PAIRS:
            home_name = BUTTON_TO_ICON[home_btn]
            play_name = BUTTON_TO_ICON[play_btn]
            if home_name not in dic or play_name not in dic:
                pytest.skip(f"{home_name} or {play_name} not in pack")
            home_img = load_icon(home_name, data, dic)
            play_img = load_icon(play_name, data, dic)
            diff = images_mean_diff(home_img, play_img)
            assert diff == 0.0, (
                f"{home_name} and {play_name} share source art but differ: mean_diff={diff:.2f}"
            )

    def test_shared_source_icons_render_identically_in_screenshots(
        self, pack, home_screenshot, play_screenshot
    ):
        """
        Crop the Tools button from the home screenshot and the Utilities button
        from the play screenshot. Both use the same source art so they must
        look identical when rendered by the same toolbar.
        """
        home_path, home_info = home_screenshot
        play_path, play_info = play_screenshot
        dpr = home_info.get("device_pixel_ratio", 2.0)

        for home_btn_text, play_btn_text, _ in GROUND_TRUTH_PAIRS:
            home_btns = {b["text"]: b for b in sidebar_buttons(home_info)}
            play_btns = {b["text"]: b for b in sidebar_buttons(play_info)}

            if home_btn_text not in home_btns or play_btn_text not in play_btns:
                pytest.skip(f"Button '{home_btn_text}' or '{play_btn_text}' not in toolbar_info")
            if "x" not in home_btns[home_btn_text]:
                pytest.skip("toolbar_info missing x/y — update RemoteControl.py")

            home_crop = crop_button(home_path, home_btns[home_btn_text], dpr)
            play_crop = crop_button(play_path, play_btns[play_btn_text], dpr)
            diff = images_mean_diff(home_crop, play_crop)
            assert diff <= CROP_DIFF_THRESHOLD, (
                f"'{home_btn_text}' (home) vs '{play_btn_text}' (play) mean pixel diff "
                f"{diff:.2f} > threshold {CROP_DIFF_THRESHOLD}. "
                f"These share the same source art and should look identical."
            )
