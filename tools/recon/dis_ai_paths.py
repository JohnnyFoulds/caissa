#!/usr/bin/env python3
"""Disassemble alternative AI paths and check key flag values."""
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

# Check ROM byte at key flag addresses
print("=== ROM bytes at key flag addresses ===")
for addr, name in [(0x04AD5, '[04AD5] beq-path flag'), (0x04AD4, '[04AD4]'),
                   (0x04AD2, '[04AD2] from'), (0x04AD3, '[04AD3] to'),
                   (0x025C, '[025C] ai_busy'), (0x025F, '[025F] move_found')]:
    if addr < len(code):
        val = code[addr]
        print(f"  ROM[0x{addr:05X}] = 0x{val:02X}  ({name})")

# Disassemble 0x0010E (AI dispatch function)
dis(0x0010E, 50, "AI dispatch [0x010E]")
# Disassemble 0x00138 (alternate path when [04AD5]=0)
dis(0x00138, 30, "beq path 0x00138")
# What function is at [0x04AD6] (position struct pointer)
print("\n=== [0x04AD6] pointer value in ROM ===")
if 0x04AD6 + 4 <= len(code):
    import struct
    val = struct.unpack('>I', code[0x04AD6:0x04AD6+4])[0]
    print(f"  ROM[0x04AD6:+4] = 0x{val:08X} (position struct pointer)")

# The jsr $17d2 inside 0x010E: disassemble 0x010E more carefully
print("\n=== Full [0x010E] function ===")
dis(0x0010E, 80, "complete")
