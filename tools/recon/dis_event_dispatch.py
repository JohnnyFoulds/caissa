#!/usr/bin/env python3
"""Disassemble the event dispatch at 0x018E-0x01E0 and the 0x00704 clear path."""
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

# 0x018E-0x0200: the result-dispatch block (D0 value handling)
dis(0x0180, 100, "result dispatch / [025E]=1 context around 0x001C6")

# 0x006F0-0x0720: context around 0x00704 (clr [025E])
dis(0x006D0, 60, "context around 0x00704 (clr [025E])")

# 0x07F00 - the function that contains 0x07F3E (set [012B6]=1)
dis(0x07F00, 60, "full function at 0x07F00 containing set-done")

# 0x013B6 (clr [012B6]) - where is this?
dis(0x01390, 40, "context around 0x013B6 clr [012B6]")

# Also: what is [0x00096]?  [0x00096] = A4 - 0x7F68, and the jsr uses -$7f68(a4)
# 0x00096 is the move-execution function. Let's look at 0x01376: jsr $1032(pc) → what's at 0x1032+0x01376+?
# Actually 0x01376: [4ebafcba] jsr $1032(pc) → target = 0x01376 + 2 + 0xFCBA = 0x01376 + 0xFCBC = 0x01032+?
# Let me compute: 0x01376 + 2 = 0x01378; + (int16) 0xFCBA = 0x01378 + (-0x0346) = 0x01032
# Hmm: 0xFCBA = -0x0346 (as signed 16-bit). So target = 0x01378 - 0x0346 = 0x01032
print("\n=== 0x01376 jsr target computation ===")
target = 0x01378 + int.from_bytes(bytes.fromhex("fcba"), 'big') - 0x10000
print(f"  0x01376: jsr $fcba(pc) → target = 0x{0x01376 + 2 + target:05X}")

# Disassemble 0x01032
dis(0x01032, 60, "function at 0x01032 (called from 0x01376)")
