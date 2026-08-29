#!/usr/bin/env python3
"""Disassemble key addresses needed to understand the AI call path."""
import sys, struct, re
sys.path.insert(0, "bin")

try:
    import capstone
except ImportError:
    print("capstone not available"); sys.exit(1)

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk

rom_path  = default_rom_path()
rom_data  = open(rom_path, "rb").read()
regions   = parse_amiga_hunk(rom_data)
code_off  = regions[0].offset
code_size = regions[0].size
code      = rom_data[code_off:code_off + code_size]

A4 = 0x7FFE

def disasm_at(addr, n=30, label=""):
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)
    buf = code[addr:addr + n * 8]
    print(f"\n=== {label or hex(addr)} ===")
    for i, ins in enumerate(md.disasm(buf, addr)):
        note = ""
        m = re.search(r'(-?\$[0-9a-f]+)\(a4\)', ins.op_str)
        if m:
            ds = m.group(1)
            d  = int(ds.replace('$','').replace('-',''), 16)
            if ds.startswith('-'): d = -d
            ea = (A4 + d) & 0xFFFFFF
            bv = struct.unpack(">I", code[ea:ea+4])[0] if ea+4 <= len(code) else 0
            sign = "-" if d < 0 else "+"
            note = f"  ; A4{sign}0x{abs(d):X}=0x{ea:04X}  ROM={bv:#010x}"
        print(f"  0x{ins.address:05X}: {ins.mnemonic:<12} {ins.op_str}{note}")
        if i+1 >= n: break

# The startup allocator called from 0x1115A
disasm_at(0x11A32, 50, "0x11A32 (alloc func called from startup)")

# 0x0234 — called from 0x17D2 (event queue)
disasm_at(0x0234, 30, "0x0234 (called from 0x17D2)")

# Phase0_init full path
disasm_at(0x8230, 60, "phase0_init full (0x8230)")

# Done flag area + what sets move at 0x4AD2/0x4AD3
disasm_at(0x07E80, 50, "AI completion / best move selection area (0x07E80)")

# 0xA062 — select best move (called from 0x07F34)
# Note: if 0xA062 < 0xAE04, it's in the BSS-zeroed range → it's DATA not code there
# The actual select-best-move function must be > 0xAE04
# Let's look at where 0x07F34 actually branches
disasm_at(0xAE04, 60, "First code above BSS (0xAE04) — expected AI functions")

print("\n--- BSS boundary check ---")
print(f"BSS start: 0x28D4 = {0x28D4}")
print(f"BSS end:   0xAE04 = {0xAE04}")
for addr, lbl in [
    (0x8230, "phase0_init"), (0x82DE, "phase1"), (0x84C4, "phase2"),
    (0x81DC, "outer_driver"), (0x8820, "0x8820"), (0x94D8, "minimax"),
    (0xA062, "select_move"), (0x07F34, "done_path"),
]:
    where = "BSS-ZERO" if 0x28D4 <= addr < 0xAE04 else "code"
    print(f"  0x{addr:05X} ({lbl}): {where}")
