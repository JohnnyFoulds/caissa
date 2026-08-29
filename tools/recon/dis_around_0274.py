#!/usr/bin/env python3
"""Disassemble 0x0274-0x02B0 and 0x015C (game loop entry with link)."""
import sys, struct
sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone, re

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

def dis(start, n=80, label=""):
    print(f"\n=== 0x{start:05X} {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n * 8], start)):
        ea = ""
        for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            eff = (A4 + d) & 0xFFFFFF
            ea += f"  ;[0x{eff:05X}]"
        raw = code[ins.address:ins.address + ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if ins.mnemonic == 'rts' and i > 2: break
        if i >= n - 1: break

# 0x0274-0x02B0: what comes after jsr [013E]
dis(0x0274, 20, "after jsr [013E] — does it loop to [025E] check?")

# 0x015C: game loop entry with link
dis(0x015C, 60, "game loop entry at 0x015C")

# 0x00096: the 'make move' function
dis(0x00096, 60, "make-move function at 0x00096 (jsr -$7f68(a4))")

# Also: 0x01C6 context — what is the D0 dispatch that leads to [025E]=1?
dis(0x0174, 50, "game loop: 0x0174 dispatch area around [010E] call")

# Trace a different angle: the 0x00108 function called 2x from 0x0024A/0x00258
# -$7ef6(a4) = 0x7FFE - 0x7EF6 = 0x00108
dis(0x00108, 40, "function at 0x00108 (called 2x from 0x0024A, 0x00258)")
