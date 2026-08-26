#!/usr/bin/env python3
"""
gen_modern.py — generate Iconos_midnight and Iconos_daylight icon packs.

Midnight: light glyphs (inverted + indigo/white ramp) for the dark theme.
Daylight: dark glyphs (navy/indigo ramp) for the light theme.

Run from bin/_genicons/ :
    python3 gen_modern.py

Safe to re-run; overwrites the .bin/.dic files in Resources/IntFiles/.
Does NOT touch Iconos.py, Iconos.bin, Iconos_sepia.*, or Iconos_dark.*.
"""
import os
import sys
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

TEMA = "Formatos.tema"
OUT  = "../../Resources/IntFiles"

# ── Override map for VSCODE pack: replace old-style icons with VS Code codicons ─
# Key: (nom_dir.lower(), nom_fichero.lower())  →  path to pre-rendered 32x32 PNG
_OVERRIDES_VSCODE_DIR = os.path.join(os.path.dirname(__file__), "overrides", "vscode")
VSCODE_OVERRIDES = {
    ("nuvola",  "connect_established.png"):       "play.png",           # Libre / Play
    ("nuvola",  "edu_miscellaneous.png"):          "mortar-board.png",   # Entrenamiento / Train
    ("nuvola",  "run.png"):                        "game.png",           # NuevaPartida / Compete
    ("gnome",   "64px-gnome-application-exit.png"):"sign-out.png",       # FinPartida / Quit
    ("nuvola",  "messagebox_info.png"):            "info.png",           # Informacion
    ("nuvola",  "kcontrol.png"):                   "tools.png",          # Tools
    ("icons8",  "icons8-servicios-32.png"):        "server-process.png", # Engines
    ("gnome",   "32px-gnome-preferences-desktop.png"): "settings-gear.png",  # Options
}

# ── Exclusion set 1: hardware photos / piece graphics → copy unchanged ──────
COPY_UNCHANGED = {
    "Milleniumt.png", "dgt.png", "dgtB.png", "Certabo.png", "Novag.png",
    "Chessnut.png", "SquareOff.png", "Saitek.png", "peon64r.png", "m1.png", "m2.png",
}

# ── Exclusion set 2: colour carries information → copy unchanged ─────────────
NO_TINT_SEMANTIC = {
    # LED status lights
    "ledblue.png", "ledblue32.png", "ledgray.png", "ledgray32.png",
    "ledgreen.png", "ledgreen32.png", "ledorange.png", "ledorange32.png",
    "ledpurple.png", "ledpurple32.png", "ledred.png", "ledred32.png",
    "ledyellow.png", "ledyellow32.png",
    # Silk bullet colours (pass/fail, Leitner)
    "bullet_black.png", "bullet_blue.png", "bullet_green.png",
    "bullet_orange.png", "bullet_purple.png", "bullet_red.png",
    "bullet_star.png", "bullet_white.png", "bullet_yellow.png",
    # Colour-picker / circles
    "Button_Color_Circle.png", "circles.png",
}

# ── Exclusion set 3: decorative source dirs → copy unchanged ────────────────
DECORATIVE_DIRS = {"cartoon/animals", "cartoon", "vehicles", "chessicons", "lucas"}


def _is_unchanged(nom_dir: str, nom_fichero: str) -> bool:
    return (
        nom_fichero in COPY_UNCHANGED
        or nom_fichero in NO_TINT_SEMANTIC
        or nom_dir.lower() in DECORATIVE_DIRS
    )


def _tint_midnight(src: str, dst: str):
    """Light glyph for dark backgrounds: invert grayscale then apply indigo/white ramp."""
    img = Image.open(src).convert("RGBA")
    alpha = img.split()[3]
    gray = ImageOps.invert(img.convert("L"))   # invert so dark shapes become light
    tinted = ImageOps.colorize(gray, black="#1e3a5f", mid="#818cf8", white="#e2e8f0")
    tinted = ImageEnhance.Contrast(tinted).enhance(1.2)
    tinted = tinted.filter(ImageFilter.SHARPEN)
    tinted.putalpha(alpha)
    tinted.save(dst)


def _tint_vscode(src: str, dst: str):
    """Neutral light glyph for dark backgrounds: matches VS Code's white/grey icon aesthetic."""
    img = Image.open(src).convert("RGBA")
    alpha = img.split()[3]
    gray = ImageOps.invert(img.convert("L"))   # invert so dark shapes become light
    tinted = ImageOps.colorize(gray, black="#3c3c3c", mid="#9e9e9e", white="#d4d4d4")
    tinted = ImageEnhance.Contrast(tinted).enhance(1.2)
    tinted = tinted.filter(ImageFilter.SHARPEN)
    tinted.putalpha(alpha)
    tinted.save(dst)


def _tint_daylight(src: str, dst: str):
    """Dark glyph for light backgrounds: grayscale then apply navy/indigo ramp."""
    img = Image.open(src).convert("RGBA")
    alpha = img.split()[3]
    gray = img.convert("L")
    tinted = ImageOps.colorize(gray, black="#0f172a", mid="#4f46e5", white="#64748b")
    tinted = ImageEnhance.Contrast(tinted).enhance(1.15)
    tinted = tinted.filter(ImageFilter.SHARPEN)
    tinted.putalpha(alpha)
    tinted.save(dst)


def _read_tema(ctema: str):
    entries = []
    seen = set()
    with open(ctema) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 3:
                print(f"  skipping bad line: {line!r}", file=sys.stderr)
                continue
            name, nom_dir, nom_fichero = parts
            if name in seen:
                print(f"  WARNING: duplicate key {name}", file=sys.stderr)
                continue
            seen.add(name)
            path = os.path.join(nom_dir, nom_fichero)
            if not os.path.isfile(path):
                print(f"  WARNING: missing source {path}", file=sys.stderr)
                continue
            entries.append((name, nom_dir, nom_fichero))
    return entries


def _generate_pack(entries, pack_name: str, tint_fn, tmp_name: str, overrides: dict = None):
    bin_path = os.path.join(OUT, f"{pack_name}.bin")
    dic_path = os.path.join(OUT, f"{pack_name}.dic")
    dedup: dict = {}   # (dir.lower(), file.lower()) → (offset_from, offset_to)
    offset = 0

    os.makedirs(OUT, exist_ok=True)
    with open(bin_path, "wb") as qbin, open(dic_path, "wt") as qdic:
        for i, (name, nom_dir, nom_fichero) in enumerate(entries, 1):
            if i % 50 == 0:
                print(f"  {i}/{len(entries)} …", flush=True)
            src = os.path.join(nom_dir, nom_fichero)
            key = (nom_dir.lower(), nom_fichero.lower())
            if key not in dedup:
                override_file = (overrides or {}).get(key)
                if override_file:
                    override_path = os.path.join(_OVERRIDES_VSCODE_DIR, override_file)
                    with open(override_path, "rb") as f:
                        data = f.read()
                elif _is_unchanged(nom_dir, nom_fichero):
                    with open(src, "rb") as f:
                        data = f.read()
                else:
                    tint_fn(src, tmp_name)
                    with open(tmp_name, "rb") as f:
                        data = f.read()
                qbin.write(data)
                end = offset + len(data)
                dedup[key] = (offset, end)
                offset = end
            frm, to = dedup[key]
            qdic.write(f"{name}={frm},{to}\n")

    if os.path.exists(tmp_name):
        os.remove(tmp_name)
    return dic_path


def _verify_keyset(new_dic: str):
    ref = os.path.join(OUT, "Iconos.dic")
    def load_keys(p):
        keys = set()
        with open(p) as f:
            for line in f:
                k = line.split("=")[0].strip()
                if k:
                    keys.add(k)
        return keys
    ref_keys = load_keys(ref)
    new_keys = load_keys(new_dic)
    missing = ref_keys - new_keys
    extra   = new_keys - ref_keys
    if missing:
        print(f"  ERROR: keys missing from {new_dic}: {sorted(missing)}")
    if extra:
        print(f"  WARNING: extra keys in {new_dic}: {sorted(extra)}")
    if not missing and not extra:
        print(f"  key sets match ({len(new_keys)} keys)")
    return not missing


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("Reading Formatos.tema …")
    entries = _read_tema(TEMA)
    print(f"  {len(entries)} entries")

    print("\nGenerating Iconos_midnight …")
    dic_m = _generate_pack(entries, "Iconos_midnight", _tint_midnight, "_tmp_midnight.png")
    _verify_keyset(dic_m)

    print("\nGenerating Iconos_daylight …")
    dic_d = _generate_pack(entries, "Iconos_daylight", _tint_daylight, "_tmp_daylight.png")
    _verify_keyset(dic_d)

    print("\nGenerating Iconos_vscode …")
    dic_v = _generate_pack(entries, "Iconos_vscode", _tint_vscode, "_tmp_vscode.png", overrides=VSCODE_OVERRIDES)
    _verify_keyset(dic_v)

    print("\nDone.")
