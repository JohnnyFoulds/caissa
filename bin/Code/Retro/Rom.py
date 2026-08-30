"""
bin/Code/Retro/Rom.py — Amiga HUNK executable container parser.

Parses the Amiga HUNK format used by Battle Chess (Interplay, 1988) and returns
a list of :class:`~Code.Retro.Types.MemRegion` objects describing each loadable
segment.

**ZERO third-party imports** — stdlib only (struct).

Hunk type constants
-------------------
The Amiga HUNK format defines hunk blocks by 4-byte type words.  Bits 30-31
encode memory-type flags (CHIP/FAST) and are masked off before comparison.

:spec: feature_spec.md §5
"""

from __future__ import annotations

import logging
import struct

from Code.Retro.Errors import PackedBinaryError, RomError
from Code.Retro.Types import MemRegion

logger = logging.getLogger(__name__)

__all__ = ["detect_packer", "parse_amiga_hunk"]

# ---------------------------------------------------------------------------
# Hunk type constants
# ---------------------------------------------------------------------------

_HUNK_HEADER = 0x3F3
_HUNK_CODE   = 0x3E9
_HUNK_DATA   = 0x3EA
_HUNK_BSS    = 0x3EB
_HUNK_RELOC32 = 0x3EC
_HUNK_SYMBOL  = 0x3F0
_HUNK_DEBUG   = 0x3F1
_HUNK_END     = 0x3F2

_MEMF_MASK = 0x3FFFFFFF

# ---------------------------------------------------------------------------
# Packer detection
# ---------------------------------------------------------------------------

_PACKER_SIGNATURES: dict[bytes, str] = {
    b"PP20": "PowerPacker",
    b"IMP!": "Imploder",
    b"XPKF": "XPK",
    b"LZXF": "LZX",
}


def detect_packer(data: bytes) -> str | None:
    """Return the packer name if the binary's first four bytes match a known signature.

    :param data: Raw binary data of the ROM file.
    :return: Human-readable packer name (e.g. ``'PowerPacker'``), or ``None`` if
        no known packer signature is detected.
    """
    sig = data[:4]
    return _PACKER_SIGNATURES.get(sig)


# ---------------------------------------------------------------------------
# HUNK parser
# ---------------------------------------------------------------------------

def _read_u32(data: bytes, pos: int) -> tuple[int, int]:
    """Read a big-endian unsigned 32-bit word at *pos* and return (value, new_pos).

    :param data: Source bytes.
    :param pos: Byte offset to read from.
    :return: Tuple of (value, pos + 4).
    :raises RomError: If there are fewer than 4 bytes remaining at *pos*.
    """
    if pos + 4 > len(data):
        raise RomError(
            f"unexpected end of data at offset {pos} (need 4 bytes, have {len(data) - pos})"
        )
    (value,) = struct.unpack_from(">I", data, pos)
    return value, pos + 4


def parse_amiga_hunk(data: bytes) -> list[MemRegion]:
    """Parse an Amiga HUNK format binary and return loadable memory regions.

    Supports single- and multi-hunk executables.  Handles HUNK_CODE, HUNK_DATA,
    HUNK_BSS, HUNK_RELOC32, HUNK_SYMBOL, and HUNK_DEBUG blocks.  Detects packed
    binaries (PowerPacker, Imploder, XPK, LZX) and refuses them with a clear error.

    :param data: Raw binary content of the Amiga executable.
    :return: Non-empty list of :class:`~Code.Retro.Types.MemRegion` objects, one
        per CODE/DATA/BSS hunk, with ``offset`` pointing into *data* and
        ``load_address`` set to the cumulative virtual address.
    :raises PackedBinaryError: If the binary is packed or compressed.
    :raises RomError: If the data is too short, has an invalid magic number, or
        contains an unrecognised hunk type.
    """
    packer = detect_packer(data)
    if packer:
        raise PackedBinaryError(
            f"binary is packed with {packer} and cannot be parsed directly; "
            f"unpack it first (e.g. with ppami or a UAE-based extractor)"
        )

    if len(data) < 8:
        raise RomError(
            f"data is only {len(data)} bytes — too short to be a valid HUNK file"
        )

    # ── HUNK_HEADER ────────────────────────────────────────────────────────
    pos = 0
    magic, pos = _read_u32(data, pos)
    if magic != _HUNK_HEADER:
        raise RomError(
            f"not an Amiga HUNK file: magic word is 0x{magic:08X} (expected 0x{_HUNK_HEADER:08X})"
        )

    n_lib_strings, pos = _read_u32(data, pos)
    for _ in range(n_lib_strings):
        # Each library name is a length (in longs) followed by that many longs of string data.
        length_longs, pos = _read_u32(data, pos)
        pos += length_longs * 4

    table_size, pos = _read_u32(data, pos)
    first_hunk, pos = _read_u32(data, pos)
    last_hunk, pos = _read_u32(data, pos)

    if last_hunk < first_hunk:
        raise RomError(
            f"HUNK_HEADER: last_hunk ({last_hunk}) < first_hunk ({first_hunk})"
        )

    n_hunks = last_hunk - first_hunk + 1

    # Read the hunk-size table (sizes in longs, top 2 bits are MEMF flags).
    hunk_sizes: list[int] = []
    for _ in range(n_hunks):
        sz_raw, pos = _read_u32(data, pos)
        hunk_sizes.append((sz_raw & _MEMF_MASK) * 4)  # convert longs → bytes

    # ── Hunk data blocks ────────────────────────────────────────────────────
    regions: list[MemRegion] = []
    load_address = 0
    _stop = False  # set to True when non-standard data is detected

    for hunk_idx in range(n_hunks):
        if _stop:
            break
        hunk_done = False
        while not hunk_done:
            if pos + 4 > len(data):
                # Tolerate a missing HUNK_END at end-of-file.
                hunk_done = True
                break

            raw_type, pos = _read_u32(data, pos)
            hunk_type = raw_type & _MEMF_MASK

            if hunk_type == _HUNK_END:
                hunk_done = True

            elif hunk_type in (_HUNK_CODE, _HUNK_DATA):
                size_longs, pos = _read_u32(data, pos)
                size_bytes = (size_longs & _MEMF_MASK) * 4
                label = "HUNK_CODE" if hunk_type == _HUNK_CODE else "HUNK_DATA"
                regions.append(
                    MemRegion(
                        offset=pos,
                        size=size_bytes,
                        label=label,
                        load_address=load_address,
                    )
                )
                pos += size_bytes
                load_address += size_bytes

            elif hunk_type == _HUNK_BSS:
                size_longs, pos = _read_u32(data, pos)
                size_bytes = (size_longs & _MEMF_MASK) * 4
                # BSS has no file bytes; size is the zero-fill extent at runtime.
                regions.append(
                    MemRegion(
                        offset=pos,
                        size=size_bytes,
                        label="HUNK_BSS",
                        load_address=load_address,
                    )
                )
                load_address += size_bytes

            elif hunk_type == _HUNK_RELOC32:
                # Read (count, hunk_ref, offsets[count]) groups until count == 0.
                while True:
                    count, pos = _read_u32(data, pos)
                    if count == 0:
                        break
                    _hunk_ref, pos = _read_u32(data, pos)
                    pos += count * 4  # skip the offset list

            elif hunk_type in (_HUNK_SYMBOL, _HUNK_DEBUG):
                # Variable-length: size in longs followed by that many longs of data.
                size_longs, pos = _read_u32(data, pos)
                pos += (size_longs & _MEMF_MASK) * 4

            else:
                # The Dragon Inc crack of BattleChess.amiga appends non-standard code
                # after the final HUNK_END (0x6600014C = bne.w, not a hunk type).
                # hunktool confirms only hunk 0 (HUNK_CODE, 72988 bytes) is valid.
                # Stop parsing here — the AI code is fully contained in hunk 0.
                trailing = len(data) - (pos - 4)
                logger.warning(
                    "non-standard hunk type 0x%X (raw 0x%X) at file offset %d "
                    "(hunk index %d) — stopping; %d trailing bytes are "
                    "Dragon-crack data, not standard HUNK blocks",
                    hunk_type, raw_type, pos - 4, hunk_idx, trailing,
                )
                # Stop here; remaining declared hunks in HUNK_HEADER are fictitious
                # (the Dragon crack populated the header but not the data).
                hunk_done = True
                _stop = True

    if not regions:
        raise RomError("no loadable CODE, DATA, or BSS hunks found in the binary")

    return regions
