#!/usr/bin/env python3
"""Find all branches/calls into the 0x001A0-0x001CC range (D0=0xA1 progress callback)."""
import sys, struct, re
sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

print(f"ROM code size: {len(code)} bytes (0x{len(code):X})")
print(f"Bytes at 0x001DA: {code[0x001DA:0x001DA+6].hex()}")
print(f"Bytes at 0x001A6: {code[0x001A6:0x001A6+4].hex()}")
print(f"Bytes at 0x001C6: {code[0x001C6:0x001C6+6].hex()}")

# Find branches targeting 0x001A6-0x001CC
targets = set(range(0x001A0, 0x001CD))
hits = []
branch_mnems = {'bra', 'bsr', 'beq', 'bne', 'blt', 'bgt', 'ble', 'bge',
                'bhi', 'bls', 'bpl', 'bmi', 'bcs', 'bcc', 'bvc', 'bvs',
                'jsr', 'jmp', 'dbra', 'dbf'}

for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if ins.mnemonic not in branch_mnems: continue
    m = re.match(r'^\$([0-9a-fA-F]+)$', ins.op_str.strip())
    if m:
        t = int(m.group(1), 16)
        if t in targets:
            hits.append((addr, ins.mnemonic, ins.op_str, t))

print(f"\nBranches/calls targeting 0x001A0-0x001CC ({len(hits)} total):")
for addr, mnem, op, t in sorted(hits):
    print(f"  0x{addr:05X}: {mnem:4} {op}  → 0x{t:05X}")

# Also show what's right BEFORE 0x001A6 — maybe there's a direct BRA into it
print("\n=== Instructions at 0x001E0-0x001A6 area ===")
for ins in md.disasm(code[0x001DC:0x001A6+8], 0x001DC):
    print(f"  0x{ins.address:05X}: {code[ins.address:ins.address+ins.size].hex()} "
          f"{ins.mnemonic} {ins.op_str}")
    if ins.address >= 0x001C0: break

# Also trace what's at 0x001C6 - 20 bytes (to see what falls into it)
print("\n=== Code just BEFORE 0x001C6 (falling into it from bne.b loop) ===")
for ins in md.disasm(code[0x001B0:0x001CC], 0x001B0):
    print(f"  0x{ins.address:05X}: {code[ins.address:ins.address+ins.size].hex()} "
          f"{ins.mnemonic} {ins.op_str}")
