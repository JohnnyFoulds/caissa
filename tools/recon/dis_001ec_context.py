#!/usr/bin/env python3
"""Disassemble 0x001EC (the function called from the search that enters the event loop)."""
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

def dis(start, n=40, label=""):
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

# What exactly IS [0x001EC]?
# The jsr is: jsr -$7e12(a4) at 0x03484
# [0x001EC] = A4 - 0x7E12 = 0x7FFE - 0x7E12 = 0x01EC
# This is a FUNCTION POINTER stored at address 0x01EC (NOT code at 0x01EC)
# Let's check what the ROM bytes at 0x01EC are:
print("=== ROM bytes at 0x01EC (function pointer?) ===")
val = struct.unpack('>I', code[0x01EC:0x01EC+4])[0]
print(f"  ROM[0x01EC:+4] = 0x{val:08X}")
print(f"  As code address: 0x{val:08X}")

# Disassemble whatever is AT that address (if it's in ROM)
if val < len(code):
    dis(val, 40, f"code at 0x{val:05X} (target of jsr -$7e12(a4))")

# Also disassemble the code around 0x03484
dis(0x03470, 25, "code around jsr -$7e12(a4) at 0x03484")

# What's at 0x001EC-0x0020A in the ROM (these look like event-loop code, but are they data?)
print("\n=== Raw bytes at 0x001EC ===")
hex_bytes = code[0x001EC:0x001EC+16].hex()
print(f"  0x001EC: {hex_bytes}")
print(f"  First 4 bytes: {code[0x001EC:0x001EC+4].hex()}")
print(f"  = 0x{struct.unpack('>I', code[0x001EC:0x001EC+4])[0]:08X}")

# Let me also check: what byte is at [0x007D4]? (the player table, checked in the event loop)
print(f"\n=== ROM byte at [0x007D4] ===")
print(f"  ROM[0x007D4] = 0x{code[0x007D4]:02X}  (0=human, 2=computer?)")
print(f"  ROM[0x007D6] = 0x{code[0x007D6]:02X}")

# The critical comparison at 0x001FE: cmpi.w #2, (a0, d0.l) where a0=[0x007D4]
# If [007D4 + d0*2] == 2 → computer → branch to 0x0274 (D0 computed from [0x0331C])
# What is [0x0331C] in ROM?
print(f"\n=== ROM word at [0x0331C] ===")
print(f"  ROM[0x0331C:+2] = 0x{struct.unpack('>H', code[0x0331C:0x0331C+2])[0]:04X}")

# Also: look at what [0x0331C] value means. Let me look at function at 0x01F2-0x00204
print(f"\n=== ROM byte at [0x025C] ===")
print(f"  ROM[0x025C] = 0x{code[0x025C]:02X}  (raw ROM instruction byte at this address)")
print(f"  Note: in emulation, we write 0 to this before starting")

# What are [007D4] and [007D6]? Look for writes to these
print("\n=== References to [0x007D4] = A4 - $782A ===")
count = 0
for addr in range(0, len(code) - 8, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if '-$782a(a4)' in ins.op_str or '$782a(a4)' in ins.op_str:
        m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
        if m:
            d_str = m.group(1)
            d = int(d_str.replace('-','').replace('$',''), 16)
            if d_str.startswith('-'): d = -d
            eff = (A4 + d) & 0xFFFFFF
            if eff == 0x007D4 and ('move' in ins.mnemonic or 'clr' in ins.mnemonic or 'set' in ins.mnemonic):
                print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
                count += 1
print(f"  (writes only; total: {count})")
