#!/usr/bin/env python3
"""Quick disassembly of key addresses using Capstone."""
import sys, struct
sys.path.insert(0, "bin")

from pathlib import Path
from Code.Retro.Manifest import default_rom_path, verify
from Code.Retro.Rom import parse_amiga_hunk

try:
    from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
    USE_CAPSTONE = True
except ImportError:
    USE_CAPSTONE = False

rom_path = default_rom_path()
manifest = Path(__file__).parents[2] / "Resources/Retro/manifest.json"
verify(rom_path, manifest)
rom_data = open(rom_path, "rb").read()
regions = parse_amiga_hunk(rom_data)
base_offset = regions[0].offset

def dump(label, start, nbytes=64):
    off = base_offset + start
    data = rom_data[off:off+nbytes]
    print(f"\n=== {label} (0x{start:X}) ===")
    if USE_CAPSTONE:
        cs = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
        cs.detail = False
        for ins in cs.disasm(data, start):
            print(f"  0x{ins.address:05X}: {ins.bytes.hex():12s}  {ins.mnemonic} {ins.op_str}")
    else:
        # raw hex fallback
        for i in range(0, len(data), 2):
            w = struct.unpack(">H", data[i:i+2])[0]
            print(f"  0x{start+i:05X}: {w:04X}")

dump("0x00240 (low memory near chaos addr 0x278)", 0x00240, 100)
dump("0x0E76 (graphics call from 0x03456)", 0x0E76, 120)
