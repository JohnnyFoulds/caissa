#!/usr/bin/env python3
"""Quick hunk structure dump for debugging."""
import struct, sys

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "Resources/Retro/BattleChess.amiga"
    data = open(path, "rb").read()
    print(f"Total bytes: {len(data)}")

    def read32(pos):
        return struct.unpack_from(">I", data, pos)[0], pos + 4

    HUNK_NAMES = {
        0x3E9: "HUNK_CODE", 0x3EA: "HUNK_DATA", 0x3EB: "HUNK_BSS",
        0x3EC: "HUNK_RELOC32", 0x3ED: "HUNK_RELOC16", 0x3EE: "HUNK_RELOC8",
        0x3EF: "HUNK_EXT", 0x3F0: "HUNK_SYMBOL", 0x3F1: "HUNK_DEBUG",
        0x3F2: "HUNK_END", 0x3F3: "HUNK_HEADER", 0x3F4: "HUNK_OVERLAY",
        0x3F5: "HUNK_BREAK", 0x3F9: "HUNK_DREL32", 0x3FA: "HUNK_DREL16",
        0x3FB: "HUNK_DREL8",
    }

    pos = 0
    magic, pos = read32(pos)
    nlib, pos = read32(pos)
    table_size, pos = read32(pos)
    first, pos = read32(pos)
    last, pos = read32(pos)
    n_hunks = last - first + 1
    print(f"magic=0x{magic:08X} nlib={nlib} table_size={table_size} first={first} last={last} n_hunks={n_hunks}")

    for i in range(n_hunks):
        sz, pos = read32(pos)
        print(f"  size[{i}] = 0x{sz:08X} = {(sz & 0x3FFFFFFF)*4} bytes allocated")

    print(f"\nHunk data starts at offset {pos} (0x{pos:04X})")

    for hunk_idx in range(n_hunks):
        print(f"\n=== HUNK {hunk_idx} ===")
        while True:
            if pos + 4 > len(data):
                print(f"  EOF at {pos}")
                break
            raw, pos = read32(pos)
            t = raw & 0x3FFFFFFF
            name = HUNK_NAMES.get(t, f"UNKNOWN_0x{t:08X}")
            print(f"  offset=0x{pos-4:05X} raw=0x{raw:08X} type=0x{t:08X} {name}")
            if t == 0x3F2:
                break
            elif t in (0x3E9, 0x3EA):
                sz_raw, pos = read32(pos)
                sz = (sz_raw & 0x3FFFFFFF) * 4
                print(f"    size={sz} bytes, data at 0x{pos:05X}..0x{pos+sz-1:05X}")
                pos += sz
            elif t == 0x3EB:
                sz_raw, pos = read32(pos)
                sz = (sz_raw & 0x3FFFFFFF) * 4
                print(f"    bss_size={sz} bytes (no data)")
            elif t == 0x3EC:
                while True:
                    cnt, pos = read32(pos)
                    if cnt == 0:
                        break
                    hunk_ref, pos = read32(pos)
                    print(f"    reloc32: {cnt} relocs for hunk {hunk_ref}")
                    pos += cnt * 4
            elif t == 0x3F0:
                while True:
                    nlen, pos = read32(pos)
                    if nlen == 0:
                        break
                    pos += nlen * 4 + 4
            elif t == 0x3F1:
                sz_raw, pos = read32(pos)
                sz = (sz_raw & 0x3FFFFFFF) * 4
                print(f"    debug: {sz} bytes")
                pos += sz
            else:
                print(f"    STOPPING — context: {data[pos-4:pos+20].hex()}")
                break
        print(f"  After hunk {hunk_idx}: pos=0x{pos:05X}")

    print(f"\nFinal pos: 0x{pos:05X}, file size: 0x{len(data):05X}")

main()
