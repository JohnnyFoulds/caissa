"""
tests/unit/retro/test_rom.py — Phase 3 tests for Code.Retro.Rom.

All tests build synthetic Amiga HUNK containers in-memory; no copyrighted ROM
is needed.  The two tests named ``test_manifest_loads_known_rom`` and
``test_rom_parses_amiga_hunk`` supersede the xfail stubs that were present in
``test_foundations.py`` for Phase 3.

:spec: feature_spec.md §5
:phase: 3
"""

from __future__ import annotations

import struct

import pytest

pytestmark = pytest.mark.retro


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hunk(code: bytes) -> bytes:
    """Build a minimal single-CODE-hunk Amiga executable in memory.

    :param code: Raw code bytes (padded to 4-byte boundary automatically).
    :return: Complete HUNK binary with HUNK_HEADER, HUNK_CODE, and HUNK_END.
    """
    while len(code) % 4:
        code += b"\x00"
    n_longs = len(code) // 4
    hdr = struct.pack(">IIIII", 0x3F3, 0, 1, 0, 0) + struct.pack(">I", n_longs)
    body = struct.pack(">II", 0x3E9, n_longs) + code
    end = struct.pack(">I", 0x3F2)
    return hdr + body + end


_NOPS_8 = b"\x4e\x71" * 4  # 8 bytes of m68k NOP instructions


# ---------------------------------------------------------------------------
# detect_packer()
# ---------------------------------------------------------------------------

def test_detect_packer_powerpacker():
    """detect_packer returns 'PowerPacker' for PP20 signature.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import detect_packer

    assert detect_packer(b"PP20" + b"\x00" * 100) == "PowerPacker"


def test_detect_packer_imploder():
    """detect_packer returns 'Imploder' for IMP! signature.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import detect_packer

    assert detect_packer(b"IMP!" + b"\x00" * 100) == "Imploder"


def test_detect_packer_xpk():
    """detect_packer returns 'XPK' for XPKF signature.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import detect_packer

    assert detect_packer(b"XPKF" + b"\x00" * 100) == "XPK"


def test_detect_packer_none_for_valid_hunk():
    """detect_packer returns None for an uncompressed HUNK binary.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import detect_packer

    hunk = _make_hunk(_NOPS_8)
    assert detect_packer(hunk) is None


# ---------------------------------------------------------------------------
# parse_amiga_hunk() — happy paths
# ---------------------------------------------------------------------------

def test_parse_amiga_hunk_returns_code_region():
    """parse_amiga_hunk returns a single MemRegion labelled 'HUNK_CODE'.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk
    from Code.Retro.Types import MemRegion

    hunk = _make_hunk(_NOPS_8)
    regions = parse_amiga_hunk(hunk)

    assert len(regions) == 1
    r = regions[0]
    assert isinstance(r, MemRegion)
    assert r.label == "HUNK_CODE"
    assert r.size == 8
    assert r.load_address == 0


def test_parse_amiga_hunk_code_region_offset():
    """The MemRegion offset must point to the original code bytes within data.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk

    code = b"\x4e\x71" * 6  # 12 bytes of NOPs
    hunk = _make_hunk(code)
    regions = parse_amiga_hunk(hunk)

    r = regions[0]
    assert hunk[r.offset: r.offset + r.size] == code


def test_parse_amiga_hunk_with_reloc():
    """parse_amiga_hunk succeeds when a HUNK_RELOC32 block precedes HUNK_END.

    Builds a hunk with:
      HUNK_HEADER → HUNK_CODE → HUNK_RELOC32 (1 reloc, 0 offsets) → HUNK_END

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk

    code = b"\x4e\x75"  # RTS, padded to 4 bytes
    while len(code) % 4:
        code += b"\x00"
    n_longs = len(code) // 4

    # Build manually to insert HUNK_RELOC32 before HUNK_END
    hdr = struct.pack(">IIIII", 0x3F3, 0, 1, 0, 0) + struct.pack(">I", n_longs)
    body = struct.pack(">II", 0x3E9, n_longs) + code
    # HUNK_RELOC32: count=0 immediately (no actual relocations)
    reloc = struct.pack(">II", 0x3EC, 0)
    end = struct.pack(">I", 0x3F2)
    hunk = hdr + body + reloc + end

    regions = parse_amiga_hunk(hunk)
    assert len(regions) == 1
    assert regions[0].label == "HUNK_CODE"


def test_parse_amiga_hunk_bss_region_has_correct_size():
    """A HUNK_BSS region must carry the declared zero-fill size, not zero.

    BSS has no file bytes, but the consumer needs the size to know how many
    bytes to zero-fill at load time.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk

    bss_longs = 10  # 40 bytes of BSS
    code = b"\x4e\x75" + b"\x00\x00"  # RTS padded to 4 bytes

    n_longs = len(code) // 4
    hdr = (
        struct.pack(">IIIII", 0x3F3, 0, 2, 0, 1)  # 2 hunks: hunk 0 and hunk 1
        + struct.pack(">I", n_longs)               # hunk 0 size
        + struct.pack(">I", bss_longs)             # hunk 1 size
    )
    body_code = struct.pack(">II", 0x3E9, n_longs) + code
    end_code  = struct.pack(">I", 0x3F2)
    body_bss  = struct.pack(">II", 0x3EB, bss_longs)
    end_bss   = struct.pack(">I", 0x3F2)
    hunk = hdr + body_code + end_code + body_bss + end_bss

    regions = parse_amiga_hunk(hunk)

    bss = next(r for r in regions if r.label == "HUNK_BSS")
    assert bss.size == bss_longs * 4, (
        f"HUNK_BSS.size should be {bss_longs * 4} but got {bss.size}"
    )


def test_parse_amiga_hunk_multi_hunk_returns_two_regions():
    """parse_amiga_hunk with CODE + BSS hunks returns two MemRegion objects.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk

    code = b"\x4e\x71" * 2  # 4 bytes of NOPs
    n_longs = 1
    bss_longs = 8

    hdr = (
        struct.pack(">IIIII", 0x3F3, 0, 2, 0, 1)
        + struct.pack(">I", n_longs)
        + struct.pack(">I", bss_longs)
    )
    body_code = struct.pack(">II", 0x3E9, n_longs) + code
    end_code  = struct.pack(">I", 0x3F2)
    body_bss  = struct.pack(">II", 0x3EB, bss_longs)
    end_bss   = struct.pack(">I", 0x3F2)
    hunk = hdr + body_code + end_code + body_bss + end_bss

    regions = parse_amiga_hunk(hunk)

    assert len(regions) == 2
    assert regions[0].label == "HUNK_CODE"
    assert regions[1].label == "HUNK_BSS"
    # BSS load address follows CODE
    assert regions[1].load_address == regions[0].size


# ---------------------------------------------------------------------------
# parse_amiga_hunk() — error paths
# ---------------------------------------------------------------------------

def test_parse_amiga_hunk_invalid_magic_raises():
    """parse_amiga_hunk raises RomError for data with wrong magic word.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Errors import RomError
    from Code.Retro.Rom import parse_amiga_hunk

    with pytest.raises(RomError, match="not an Amiga HUNK"):
        parse_amiga_hunk(b"\x00\x01\x02\x03" * 20)


def test_parse_amiga_hunk_too_short_raises():
    """parse_amiga_hunk raises RomError for data that is just the magic and nothing more.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Errors import RomError
    from Code.Retro.Rom import parse_amiga_hunk

    with pytest.raises(RomError):
        parse_amiga_hunk(b"\x00\x00\x03\xf3")  # magic only, no header fields


def test_packed_binary_raises_on_parse():
    """parse_amiga_hunk raises PackedBinaryError for a PP20-prefixed binary.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Errors import PackedBinaryError
    from Code.Retro.Rom import parse_amiga_hunk

    with pytest.raises(PackedBinaryError):
        parse_amiga_hunk(b"PP20" + b"\x00" * 100)


# ---------------------------------------------------------------------------
# Replacements for xfail stubs from test_foundations.py (Phase 3)
# ---------------------------------------------------------------------------

def test_manifest_loads_known_rom():
    """Manifest.load() must return a non-empty list from the real manifest.json.

    Replaces the Phase-3 xfail stub in test_foundations.py.

    :spec: N-RETRO-6
    """
    from pathlib import Path

    from Code.Retro.Manifest import load

    manifest_path = Path(__file__).parents[3] / "Resources" / "Retro" / "manifest.json"
    entries = load(manifest_path)
    assert len(entries) >= 1
    assert all("sha256" in e for e in entries)


def test_rom_parses_amiga_hunk():
    """parse_amiga_hunk returns a non-empty list for a valid synthetic HUNK.

    Replaces the Phase-3 xfail stub in test_foundations.py.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Rom import parse_amiga_hunk

    hunk = _make_hunk(b"\x4e\x71" * 4)
    regions = parse_amiga_hunk(hunk)
    assert len(regions) >= 1
