#!/usr/bin/env python3
"""Disassemble the key addresses to understand the full AI call chain."""
import sys, re
sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

def dis(start, n=30, label=""):
    print(f"\n=== 0x{start:05X} {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n * 6], start)):
        ea = ""
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            ea = f"  ; [0x{(A4 + d) & 0xFFFFFF:05X}]"
        raw = code[ins.address:ins.address + ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if ins.mnemonic == 'rts': break
        if i >= n - 1: break

dis(0x00000, 20, "ROM start / exception vectors")
dis(0x00016, 20, "stack caller 0x00016")
dis(0x00240, 20, "stack caller 0x00240")
dis(0x00274, 20, "0x0274 (loop-back?)")
dis(0x00FC6, 20, "0x0FC6 (AI search called from 0x012A4)")
