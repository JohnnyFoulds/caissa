#!/usr/bin/env python3
"""Disassemble 0x0FC6 (alpha-beta search) to find piece-table format."""
import sys; sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone, re

rom_data = open(default_rom_path(), 'rb').read()
regions = parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)


def dis(start, end=None, n=120):
    if end:
        n = (end - start) // 2 + 20
    print(f"\n=== 0x{start:05X} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n*8], start)):
        ea = ''
        for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a[0-9]\)', ins.op_str):
            disp_str = m.group(1)
            reg_match = re.search(r'\(a([0-9])\)', m.group(0))
            if reg_match:
                reg = int(reg_match.group(1))
                if reg == 4:  # a4-relative
                    d = int(disp_str.replace('-', '').replace('$', ''), 16)
                    if disp_str.startswith('-'):
                        d = -d
                    ea += f"  ;[0x{(A4 + d) & 0xFFFFFF:05X}]"
        raw = code[ins.address:ins.address+ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if end and ins.address >= end:
            break
        if ins.mnemonic in ('rts', 'rte') and i > 5:
            break
        if i >= n - 1:
            break


# Disassemble the alpha-beta search function 0x0FC6
# It was called via jsr $fc6(pc) at 0x012AA, which is PC-relative
# Target: 0x012AA + 2 + signed(0xFD1A) = 0x012AC - 0x02E6 = 0x0FC6
dis(0x0FC6, 0x011A0)  # Disassemble from 0x0FC6 until ~0x01032
print("\n\n")

# Also look at what happens around the result storage addresses
# specifically A4 - 0x6D3A = 0x012C4 and A4 - 0x6D3C = 0x012C2
# Find all stores to these in the ROM
print("=== Scanning for writes to [0x012C2] (A4-$6d3c) and [0x012C4] (A4-$6d3a) ===")
# Encode as big-endian: A4-relative. The encoding would be A4 + negative offset.
# -0x6D3C = 0xFFFF92C4 as unsigned 32-bit, but as 16-bit: 0x92C4
# Actually: -0x6D3C as signed word = 0x92C4 (since 0xFFFF - 0x6D3C + 1 = 0x92C4)
target_offsets = {
    0x12C4: (-(0x7FFE - 0x12C4)) & 0xFFFF,  # = -(0x6D3A) = 0x92C6 as unsigned word
    0x12C2: (-(0x7FFE - 0x12C2)) & 0xFFFF,  # = -(0x6D3C) = 0x92C4
    0x12B6: (-(0x7FFE - 0x12B6)) & 0xFFFF,
    0x12B8: (-(0x7FFE - 0x12B8)) & 0xFFFF,
    0x12BC: (-(0x7FFE - 0x12BC)) & 0xFFFF,
    0x12B7: (-(0x7FFE - 0x12B7)) & 0xFFFF,
    0x12B9: (-(0x7FFE - 0x12B9)) & 0xFFFF,
    0x12BD: (-(0x7FFE - 0x12BD)) & 0xFFFF,
}
for target, off in sorted(target_offsets.items()):
    off_be = struct.pack('>H', off).hex() if 'struct' in dir() else f"{off:04x}"
    print(f"  Target [0x{target:05X}]: A4-relative word = 0x{off:04X}")

import struct

# Search for instructions that reference any of these code bytes
hits_by_target = {t: [] for t in target_offsets}
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns:
        continue
    ins = insns[0]
    for m in re.finditer(r'-\$([0-9a-fA-F]+)\(a4\)', ins.op_str):
        d = int(m.group(1), 16)
        ea = (A4 - d) & 0xFFFFFF
        if ea in hits_by_target:
            hits_by_target[ea].append((addr, ins.mnemonic, ins.op_str))

for target in sorted(hits_by_target):
    hits = hits_by_target[target]
    if hits:
        print(f"\n  [0x{target:05X}] referenced from {len(hits)} places:")
        for (a, mn, op) in hits[:20]:
            print(f"    0x{a:05X}: {mn} {op}")
