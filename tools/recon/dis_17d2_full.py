#!/usr/bin/env python3
"""Fully disassemble 0x17D2 (think function) to find the level=1 exit path."""
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

def dis(start, n=120, label="", stop_at_rts=True):
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
        if stop_at_rts and ins.mnemonic == 'rts' and i > 5: break
        if i >= n - 1: break

# Full disassembly of 0x17D2
dis(0x017D2, 120, "think function 0x17D2")

# Also check what's at 0x0182E (the "equal" branch in 0x17D2)
print("\n--- 0x0182E (skipped-path in 0x17D2 when [024E]==level) ---")
dis(0x0182E, 40, "0x182E", stop_at_rts=True)

# Also disassemble 0x00234 to see what it calls and whether it always BRAs
dis(0x00234, 40, "0x00234 (the non-returning 'orchestrate' function)")
