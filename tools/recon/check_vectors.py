#!/usr/bin/env python3
import sys, struct
sys.path.insert(0, "bin")
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone

rom_data = open(default_rom_path(), "rb").read()
regions  = parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)
A4 = 0x7FFE

print("=== F-line handler @ 0x36B0 (full) ===")
for i, ins in enumerate(md.disasm(code[0x36B0:0x36B0+120], 0x36B0)):
    print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
    if ins.mnemonic == 'rts' and i > 5: break
    if i >= 40: break

# What's between 0x33F0 and the F-line area, precise layout
print("\n=== 0x33F0 → 0x3430 (precise bytes) ===")
for ins in md.disasm(code[0x33F0:0x3450], 0x33F0):
    raw = code[ins.address:ins.address+ins.size].hex()
    ea_note = ""
    import re
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
    if m:
        ds = m.group(1)
        d = int(ds.replace('$','').replace('-',''), 16)
        if ds.startswith('-'): d = -d
        ea = (A4 + d) & 0xFFFFFF
        ea_note = f"  ; 0x{ea:05X}"
    print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea_note}")
    if ins.address >= 0x3445: break

# 0x8820 full
print("\n=== 0x8820 (full) ===")
for i, ins in enumerate(md.disasm(code[0x8820:0x8820+60], 0x8820)):
    raw = code[ins.address:ins.address+ins.size].hex()
    ea = ""
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
    if m:
        ds = m.group(1)
        d = int(ds.replace('$','').replace('-',''), 16)
        if ds.startswith('-'): d = -d
        effective = (A4 + d) & 0xFFFFFF
        ea = f"  ; 0x{effective:05X}"
    print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
    if ins.mnemonic == 'rts' and i > 5: break
    if i >= 25: break
