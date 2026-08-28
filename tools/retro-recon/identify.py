#!/usr/bin/env python3
"""
tools/retro-recon/identify.py — Battle Chess binary identification tool.

EXPERIMENTAL — Phase 1 spike. Deleted in Phase 10.

Usage:
    python3 tools/retro-recon/identify.py /path/to/BattleChess
    python3 tools/retro-recon/identify.py /path/to/BCHESS.EXE

Prints the sha256, file size, format (Amiga Hunk or DOS MZ), hunk table,
and packer detection. No unicorn needed.
"""

import hashlib
import struct
import sys
from pathlib import Path


# Amiga Hunk type constants (big-endian 32-bit values)
_HUNK_NAMES = {
    0x3E9: "HUNK_CODE",
    0x3EA: "HUNK_DATA",
    0x3EB: "HUNK_BSS",
    0x3EC: "HUNK_RELOC32",
    0x3ED: "HUNK_RELOC16",
    0x3EE: "HUNK_RELOC8",
    0x3EF: "HUNK_EXT",
    0x3F0: "HUNK_SYMBOL",
    0x3F1: "HUNK_DEBUG",
    0x3F2: "HUNK_END",
    0x3F3: "HUNK_HEADER",
    0x3F4: "HUNK_OVERLAY",
    0x3F5: "HUNK_BREAK",
    0x3F6: "HUNK_DREL32",
    0x3F7: "HUNK_DREL16",
    0x3F8: "HUNK_DREL8",
    0x3F9: "HUNK_LIB",
    0x3FA: "HUNK_INDEX",
}

# Known packer magic bytes
_PACKERS = [
    (b"PP20", "PowerPacker"),
    (b"PX20", "PowerPacker (variant)"),
    (b"IMP!", "Imploder"),
    (b"LZX!", "LZX"),
    (b"\x0d\x0aLZEXE", "LZEXE"),
    (b"\x4d\x5a", None),  # MZ — handled separately
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def detect_packer(data: bytes) -> str | None:
    """Return packer name if a known compression header is detected, else None."""
    for magic, name in _PACKERS:
        if data.startswith(magic) and name is not None:
            return name
    return None


def is_amiga_hunk(data: bytes) -> bool:
    if len(data) < 8:
        return False
    hunk_type = struct.unpack_from(">I", data, 0)[0]
    return hunk_type == 0x3F3  # HUNK_HEADER


def is_dos_mz(data: bytes) -> bool:
    return data[:2] == b"MZ" or data[:2] == b"ZM"


def parse_amiga_hunk(data: bytes) -> list[dict]:
    """Parse Amiga Hunk format and return a list of hunk descriptors."""
    hunks = []
    pos = 0

    def read_long() -> int:
        nonlocal pos
        val = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return val

    def read_long_signed() -> int:
        nonlocal pos
        val = struct.unpack_from(">i", data, pos)[0]
        pos += 4
        return val

    # HUNK_HEADER
    hunk_type = read_long()
    if hunk_type != 0x3F3:
        return [{"type": "UNKNOWN", "note": f"Expected HUNK_HEADER, got 0x{hunk_type:X}"}]

    # Library names (usually 0)
    lib_count = read_long()
    for _ in range(lib_count):
        name_len = read_long()
        pos += name_len * 4

    total_hunks = read_long()
    first_hunk = read_long()
    last_hunk = read_long()

    # Hunk sizes (in longwords)
    hunk_sizes = []
    for i in range(last_hunk - first_hunk + 1):
        sz_lw = read_long()
        mem_flags = (sz_lw >> 30) & 0x3  # top 2 bits = memory attributes
        size_bytes = (sz_lw & 0x3FFFFFFF) * 4
        hunk_sizes.append((size_bytes, mem_flags))

    # Parse each hunk
    hunk_idx = 0
    while pos < len(data):
        if pos + 4 > len(data):
            break
        raw_type = read_long()
        hunk_type = raw_type & 0x3FFFFFFF
        type_name = _HUNK_NAMES.get(hunk_type, f"0x{hunk_type:X}")

        if hunk_type == 0x3F2:  # HUNK_END
            hunks.append({"type": "HUNK_END", "offset": pos - 4})
            hunk_idx += 1
            continue

        if hunk_type == 0x3E9:  # HUNK_CODE
            sz_lw = read_long()
            size_bytes = sz_lw * 4
            code_offset = pos
            pos += size_bytes
            hunks.append({
                "type": "HUNK_CODE",
                "index": hunk_idx,
                "data_offset": code_offset,
                "data_size": size_bytes,
                "first_bytes": data[code_offset:code_offset + 16].hex(),
            })
            continue

        if hunk_type == 0x3EA:  # HUNK_DATA
            sz_lw = read_long()
            size_bytes = sz_lw * 4
            data_offset = pos
            pos += size_bytes
            hunks.append({
                "type": "HUNK_DATA",
                "index": hunk_idx,
                "data_offset": data_offset,
                "data_size": size_bytes,
            })
            continue

        if hunk_type == 0x3EB:  # HUNK_BSS
            sz_lw = read_long()
            size_bytes = sz_lw * 4
            hunks.append({
                "type": "HUNK_BSS",
                "index": hunk_idx,
                "bss_size": size_bytes,
            })
            continue

        if hunk_type == 0x3EC:  # HUNK_RELOC32
            reloc_count_total = 0
            while True:
                num_offsets = read_long()
                if num_offsets == 0:
                    break
                _ = read_long()  # hunk number
                for _ in range(num_offsets):
                    read_long()
                reloc_count_total += num_offsets
            hunks.append({"type": "HUNK_RELOC32", "reloc_count": reloc_count_total})
            continue

        if hunk_type == 0x3F0:  # HUNK_SYMBOL
            symbols = []
            while True:
                name_len = read_long()
                if name_len == 0:
                    break
                name_bytes = data[pos:pos + name_len * 4]
                pos += name_len * 4
                sym_val = read_long()
                name = name_bytes.rstrip(b"\x00").decode("latin-1", errors="replace")
                symbols.append((name, sym_val))
            hunks.append({"type": "HUNK_SYMBOL", "count": len(symbols), "symbols": symbols[:20]})
            continue

        if hunk_type == 0x3F1:  # HUNK_DEBUG
            sz_lw = read_long()
            pos += sz_lw * 4
            hunks.append({"type": "HUNK_DEBUG", "size": sz_lw * 4})
            continue

        # Unknown — stop
        hunks.append({"type": type_name, "offset": pos - 4, "note": "unhandled — stopping"})
        break

    return hunks


def identify(path: Path) -> None:
    data = path.read_bytes()

    print(f"File:   {path}")
    print(f"Size:   {len(data):,} bytes ({len(data):#x})")
    print(f"SHA256: {sha256_file(path)}")
    print()

    packer = detect_packer(data)
    if packer:
        print(f"Packer: {packer}  *** PACKED — must unpack before analysis ***")
        print()

    if is_dos_mz(data):
        print("Format: DOS MZ executable")
        mz_relocs = struct.unpack_from("<H", data, 6)[0]
        header_para = struct.unpack_from("<H", data, 8)[0]
        print(f"  Relocation entries: {mz_relocs}")
        print(f"  Header size: {header_para * 16} bytes ({header_para} paragraphs)")
        code_start = header_para * 16
        print(f"  Code starts at: 0x{code_start:X}")
        if packer:
            print("  NOTE: DOS binary is packed — run unpacker before Ghidra/Unicorn analysis")
    elif is_amiga_hunk(data):
        print("Format: Amiga Hunk executable")
        hunks = parse_amiga_hunk(data)
        print()
        print("Hunk table:")
        for h in hunks:
            if h["type"] == "HUNK_CODE":
                print(f"  [{h['index']}] HUNK_CODE  offset=0x{h['data_offset']:06X}  size=0x{h['data_size']:X} ({h['data_size']:,} bytes)")
                print(f"      First 16 bytes: {h['first_bytes']}")
            elif h["type"] == "HUNK_DATA":
                print(f"  [{h['index']}] HUNK_DATA  offset=0x{h['data_offset']:06X}  size=0x{h['data_size']:X} ({h['data_size']:,} bytes)")
            elif h["type"] == "HUNK_BSS":
                print(f"  [{h['index']}] HUNK_BSS   bss_size=0x{h['bss_size']:X} ({h['bss_size']:,} bytes)")
            elif h["type"] == "HUNK_RELOC32":
                print(f"      HUNK_RELOC32 ({h['reloc_count']} relocations)")
            elif h["type"] == "HUNK_SYMBOL":
                print(f"      HUNK_SYMBOL ({h['count']} symbols):")
                for name, val in h.get("symbols", []):
                    print(f"        0x{val:06X}  {name}")
            elif h["type"] == "HUNK_DEBUG":
                print(f"      HUNK_DEBUG ({h['size']} bytes)")
            elif h["type"] == "HUNK_END":
                print(f"      HUNK_END")
    else:
        print(f"Format: UNKNOWN (first 4 bytes: {data[:4].hex()})")
        print("  Not an Amiga Hunk or DOS MZ file.")
        print("  Possible explanations:")
        print("  - The binary is packed with an unrecognised packer")
        print("  - This is not the correct binary")

    print()
    print("Next step: run memory_trace.py with --entry <address> to profile the think function.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-binary>")
        sys.exit(1)
    identify(Path(sys.argv[1]))
