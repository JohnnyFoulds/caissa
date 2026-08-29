#!/usr/bin/env python3
"""Disassemble 0x012A4 context and trace full call chain to it."""
import sys, struct, re
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
        if ins.mnemonic == 'rts': break

# context before and after 0x012A4
dis(0x01280, 40, "context around 0x012A4")

# who calls this? Search for jsr to 0x012xx range or the function containing 0x012A4
# look for the function start (find a LINK or RTS before it)
print("\n=== Scanning backward for function start ===")
for off in range(0x012A4, 0x011E0, -1):
    raw2 = code[off:off+2]
    if raw2 == b'\x4e\x75':  # RTS
        print(f"  RTS at 0x{off:05X} (possible function boundary)")
        break
    if raw2[:1] == b'\x4e' and raw2[1:2] == b'\x55':  # LINK.W
        print(f"  LINK.W at 0x{off:05X} (function start)")
        break

# Search all JSR targets pointing into 0x012A4 area (±0x100)
print("\n=== JSRs targeting 0x012xx range ===")
TARGET_LOW, TARGET_HIGH = 0x01200, 0x01300
for ins in md.disasm(code, 0):
    if ins.mnemonic in ('jsr', 'bsr', 'bsr.b', 'bsr.w') and ins.op_str.startswith('$'):
        try:
            t = int(ins.op_str.replace('$',''), 16)
            if TARGET_LOW <= t <= TARGET_HIGH:
                raw = code[ins.address:ins.address + ins.size].hex()
                print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}")
        except: pass
    if ins.address > 0x11D1C: break
