#!/usr/bin/env python3
"""Disassemble the done-signal paths: 0x0137A (clear ai_busy), 0x07F3E (set done), 0x00260 context."""
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
        for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            eff = (A4 + d) & 0xFFFFFF
            ea += f"  ;[0x{eff:05X}]"
        raw = code[ins.address:ins.address + ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if ins.mnemonic == 'rts' and i > 2: break
        if i >= n - 1: break

# Walk back from 0x0137A to find function start
def find_func_start(target, scan_back=0x100):
    start = max(0, target - scan_back)
    last_link = None
    for addr in range(start, target, 2):
        insns = list(md.disasm(code[addr:addr+6], addr))
        if insns and insns[0].mnemonic == 'link':
            last_link = addr
    return last_link or (target - 64)

# 0x0137A: clr.b [025C]
print("\n=== Context for 0x0137A (clr.b [025C]) ===")
start137 = find_func_start(0x0137A)
print(f"  (scanning from 0x{start137:05X})")
dis(start137, 80, "function containing clr.b [025C] at 0x0137A")

# 0x07F3E: move.w #$1, [012B6]
print("\n=== Context for 0x07F3E (move.w #1, [012B6]) ===")
start7f3e = find_func_start(0x07F3E)
print(f"  (scanning from 0x{start7f3e:05X})")
dis(start7f3e, 80, "function containing set done=1 at 0x07F3E")

# 0x01054: move.w d0, [012B6]
start1054 = find_func_start(0x01054)
print(f"  (scanning from 0x{start1054:05X})")
dis(start1054, 80, "function containing set done=D0 at 0x01054")

# 0x00260: the exit path from the search
dis(0x0220, 80, "function at 0x0220 containing 0x00260 exit path")

# What is [025E]? Search for writes to it:
# [025E] = A4 - 0x7DA0
print("\n=== All references to [0x025E] = A4 - $7DA0 ===")
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if '-$7da0(a4)' in ins.op_str or '$7da0(a4)' in ins.op_str:
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d_str = m.group(1)
            d = int(d_str.replace('-','').replace('$',''), 16)
            if d_str.startswith('-'): d = -d
            eff = (A4 + d) & 0xFFFFFF
            if eff == 0x025E:
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")

# [025D]: also near [025C]
print("\n=== All references to [0x025D] = A4 - $7DA1 ===")
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if '-$7da1(a4)' in ins.op_str or '$7da1(a4)' in ins.op_str:
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d_str = m.group(1)
            d = int(d_str.replace('-','').replace('$',''), 16)
            if d_str.startswith('-'): d = -d
            eff = (A4 + d) & 0xFFFFFF
            if eff == 0x025D:
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
