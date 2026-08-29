#!/usr/bin/env python3
"""Find all writes to done-flag [0x012B6] and move-flag [0x025F] in ROM."""
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

# Map: A4 + offset => address
TARGET_ADDRS = {
    0x012B6: 'done_flag',   # A4 - 0x6D48
    0x025F: 'move_found',   # A4 - 0x7D9F
    0x025C: 'ai_busy',      # A4 - 0x7DA2
    0x012B4: 'done_hi',     # nearby done
    0x04A5C: 'state',       # A4 - 0x35A2
}

def effective_a4_offset(op_str):
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', op_str)
    if not m: return None
    s = m.group(1)
    val = int(s.replace('-','').replace('$',''), 16)
    if s.startswith('-'): val = -val
    return (A4 + val) & 0xFFFFFF

print("=== All A4-relative writes to key flags ===")
for ins in md.disasm(code, 0):
    # Check if this instruction WRITES to a target address
    # Writes: move, clr, st, sf, tas, bset, bclr, addq, subq, neg, not, etc.
    is_write = ins.mnemonic.startswith(('move', 'clr', 'st', 'sf', 'tas',
                                         'bset', 'bclr', 'addq', 'subq',
                                         'neg', 'not', 'add', 'sub', 'and',
                                         'or', 'eor'))
    if not is_write: continue
    ea = effective_a4_offset(ins.op_str)
    if ea in TARGET_ADDRS:
        raw = code[ins.address:ins.address + ins.size].hex()
        name = TARGET_ADDRS[ea]
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}  → {name}=[0x{ea:05X}]")
    if ins.address > 0x11D1C: break

print("\n=== 0x8820 (first init func) ===")
for i, ins in enumerate(md.disasm(code[0x8820:0x8820+200], 0x8820)):
    ea = ""
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
    if m:
        d = int(m.group(1).replace('-','').replace('$',''), 16)
        if m.group(1).startswith('-'): d = -d
        ea = f"  ; [0x{(A4 + d) & 0xFFFFFF:05X}]"
    raw = code[ins.address:ins.address + ins.size].hex()
    print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
    if ins.mnemonic == 'rts': break
    if i >= 40: break

print("\n=== 0x8858 (AI driver?) ===")
for i, ins in enumerate(md.disasm(code[0x8858:0x8858+200], 0x8858)):
    ea = ""
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
    if m:
        d = int(m.group(1).replace('-','').replace('$',''), 16)
        if m.group(1).startswith('-'): d = -d
        ea = f"  ; [0x{(A4 + d) & 0xFFFFFF:05X}]"
    raw = code[ins.address:ins.address + ins.size].hex()
    print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
    if ins.mnemonic == 'rts': break
    if i >= 40: break
