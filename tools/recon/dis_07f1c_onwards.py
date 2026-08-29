#!/usr/bin/env python3
"""Disassemble from 0x07F1C onwards to find the function containing 0x07F3E (set [012B6]=1)."""
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
        if ins.mnemonic == 'rts' and i > 3: break
        if i >= n - 1: break

# Function at 0x07F1C (right after 0x07F1A rts of previous function)
dis(0x07F1C, 60, "function at 0x07F1C (contains [012B6]=1 at 0x07F3E)")

# What calls this function? Search for jsr to addresses around 0x07F1C-0x07F5C
print("\n=== Searching for callers of 0x07F1C area ===")
# Any jsr/bsr that targets 0x07F1C-0x07F60
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if ins.mnemonic in ('jsr', 'bsr'):
        # Try to extract target
        op = ins.op_str
        # Look for absolute address or pc-relative
        m = re.match(r'^\$([0-9a-fA-F]+)', op)
        if m:
            target = int(m.group(1), 16)
            if 0x07F1C <= target <= 0x07F60:
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {op}  → 0x{target:05X}")
        # Also check (d16, PC) pattern: 4eba = jsr d16(pc)
        if code[addr:addr+2] == b'\x4e\xba' and addr + 4 <= len(code):
            d16 = struct.unpack('>h', code[addr+2:addr+4])[0]
            target = addr + 2 + d16
            if 0x07F1C <= target <= 0x07F60:
                print(f"  0x{addr:05X}: jsr $pc+{d16}  → 0x{target:05X}")

# Also: what is [0x004DBE]? (used in the search: -$3240(a4) at 0x03470)
# A4 - 0x3240 = 0x7FFE - 0x3240 = 0x4DBE
print(f"\n=== ROM long at [0x04DBE] ===")
print(f"  ROM[0x04DBE:+4] = 0x{struct.unpack('>I', code[0x04DBE:0x04DBE+4])[0]:08X}")

# The key flag [025E] gets set to 1 at 0x001C6 AND cleared at 0x00704.
# 0x00704: let's find its context
dis(0x006F0, 30, "context around 0x00704 (clr [025E])")

# What function contains 0x00704?
print("\n=== Searching for callers of [025E]-clear function (around 0x006F0) ===")
for addr in range(0, len(code) - 8, 2):
    if code[addr:addr+2] == b'\x4e\xba':
        d16 = struct.unpack('>h', code[addr+2:addr+4])[0]
        target = addr + 2 + d16
        if 0x006E0 <= target <= 0x00710:
            print(f"  0x{addr:05X}: jsr $pc+{d16}  → 0x{target:05X}")
    elif code[addr:addr+2] in (b'\x4e\xac', b'\x4e\xb9', b'\x4e\xb8'):
        insns = list(md.disasm(code[addr:addr+8], addr))
        if insns and insns[0].mnemonic == 'jsr':
            # For indirect jsr through a4-relative
            m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str)
            if m:
                d = int(m.group(1).replace('-','').replace('$',''), 16)
                if m.group(1).startswith('-'): d = -d
                eff = (A4 + d) & 0xFFFFFF
                if 0x006E0 <= eff <= 0x00710:
                    print(f"  0x{addr:05X}: {insns[0].mnemonic} {insns[0].op_str}  → [0x{eff:05X}]")
