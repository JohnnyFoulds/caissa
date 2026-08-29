#!/usr/bin/env python3
"""Disassemble the game loop + 0x81DC to understand [0025C] usage."""
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

def dis(start, n=50, label=""):
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
        if i >= n - 1: break

dis(0x013E, 80, "main event loop")
dis(0x81DC, 60, "ai_outer_driver (0x81DC)")
dis(0x8230, 50, "ai_outer_inner (0x8230)")

# Grep ROM for all writes to [0025C] = A4 + (-0x7DA2) = A4 - 0x7DA2
# address 0x025C = A4 - 0x7DA2 = 0x7FFE - 0x7DA2 = 0x025C
# In immediate: move.b #X,$-7da2(a4)
# Search for pattern: move.*$-7da2(a4)
print("\n=== Writes to [0x025C] (A4-0x7DA2) in ROM ===")
for i, ins in enumerate(md.disasm(code, 0)):
    if '7da2' in ins.op_str.lower() or '7da0' in ins.op_str.lower():
        ea = ""
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            ea = f"  → [0x{(A4 + d) & 0xFFFFFF:05X}]"
        print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}{ea}")
