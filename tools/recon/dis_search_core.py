#!/usr/bin/env python3
"""Disassemble 0x3218 (search core), 0x31C6 (search loop), and the 0x0274 area."""
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

def dis(start, n=60, label=""):
    print(f"\n=== 0x{start:05X} {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n * 8], start)):
        ea = ""
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            ea = f"  ; [0x{(A4 + d) & 0xFFFFFF:05X}]"
        raw = code[ins.address:ins.address + ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if ins.mnemonic == 'rts' and i > 5: break
        if i >= n - 1: break

# The key area: 0x0258-0x0290 (what's around 0x0274?)
dis(0x0250, 30, "around 0x0274 (jsr [013E] trampoline)")

# 0x31C6: search loop entry
dis(0x31C6, 60, "search loop entry 0x31C6")

# 0x31C6 inner call: 0x3218 (from trace_first200)
dis(0x3218, 80, "search core 0x3218")

# 0x3102 (seen in trace_first200 between 0x31C6 and 0x3218)
dis(0x3102, 40, "0x3102 (between 31C6 and 3218)")

# What writes to [0x012B6]? Search for patterns around that address
# A4 + d = 0x012B6 → d = 0x012B6 - 0x7FFE = -0x6D48
# In hex: -0x6d48 → $6d48 with minus
print("\n=== Searching for writes to [0x012B6] = A4 - $6D48 ===")
TARGET_OFFSET = -0x6D48
count = 0
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if '-$6d48(a4)' in ins.op_str or '$6d48(a4)' in ins.op_str:
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d_str = m.group(1)
            d = int(d_str.replace('-','').replace('$',''), 16)
            if d_str.startswith('-'): d = -d
            effective = (A4 + d) & 0xFFFFFF
            if effective == 0x012B6:
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
                count += 1
print(f"  Total: {count} references to [0x012B6]")

# Also search for what sets [025C]=0 (a write of 0 to [025C])
# [025C] = A4 - 0x7DA2 (from prior trace: d = -0x7DA2)
# CLEAR: clr.b -$7da2(a4) or move.b #0, -$7da2(a4) or similar
print("\n=== Searching for clears/writes to [0x025C] = A4 - $7DA2 ===")
count2 = 0
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if '-$7da2(a4)' in ins.op_str or '$7da2(a4)' in ins.op_str:
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d_str = m.group(1)
            d = int(d_str.replace('-','').replace('$',''), 16)
            if d_str.startswith('-'): d = -d
            effective = (A4 + d) & 0xFFFFFF
            if effective == 0x025C:
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
                count2 += 1
print(f"  Total: {count2} references to [0x025C]")
