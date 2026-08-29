#!/usr/bin/env python3
"""Search ROM for writes to [0x012C2]/[0x012C4] and disassemble key functions."""
import sys, types, importlib.util
sys.path.insert(0, "bin")

_code_pkg = types.ModuleType('Code'); _code_pkg.__path__ = ['bin/Code']; sys.modules['Code'] = _code_pkg
_retro_pkg = types.ModuleType('Code.Retro'); _retro_pkg.__path__ = ['bin/Code/Retro']; sys.modules['Code.Retro'] = _retro_pkg
def _load(dotpath, filepath):
    spec = importlib.util.spec_from_file_location(dotpath, filepath)
    mod = importlib.util.module_from_spec(spec); sys.modules[dotpath] = mod
    spec.loader.exec_module(mod); return mod
_load('Code.Retro.Types', 'bin/Code/Retro/Types.py')
_load('Code.Retro.Errors', 'bin/Code/Retro/Errors.py')
Manifest = _load('Code.Retro.Manifest', 'bin/Code/Retro/Manifest.py')
Rom = _load('Code.Retro.Rom', 'bin/Code/Retro/Rom.py')

import capstone as cs

rom_data = open(Manifest.default_rom_path(), 'rb').read()
regions = Rom.parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_BIG_ENDIAN + cs.CS_MODE_M68K_000)

# [0x012C2] with various A4 values (A4 changes by -2 per phase):
# A4=0x7FFE: -$6D3C(A4) / A4=0x7FFC: -$6D3A(A4) / A4=0x7FFA: -$6D38(A4)
# A4=0x7FF8: -$6D36(A4) / A4=0x7FF6: -$6D34(A4)
A4_values = [0x7FFE, 0x7FFC, 0x7FFA, 0x7FF8, 0x7FF6, 0x7FF4]
write_addrs = {0x012C2, 0x012C4, 0x012C0, 0x012C6}

a4_targets = set()
for a4 in A4_values:
    for wa in write_addrs:
        off = a4 - wa
        a4_targets.add(f'-${off:04x}')

print("=== Writes to [0x012C0..0x012C6] via any A4-relative addressing ===")
hits = []
for ins in md.disasm(code[:0x15000], 0):
    op = ins.op_str.lower()
    for t in a4_targets:
        if t + '(a4)' in op:
            hits.append(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
if hits:
    for h in hits: print(h)
else:
    print("  (none)")

# Search for absolute long writes to 0x012C2
print("\n=== Absolute writes containing 0x12C2 or 0x12C4 ===")
for i in range(0, len(code)-4, 2):
    w = (code[i]<<8)|code[i+1]
    if w in (0x12C2, 0x12C4, 0x12C0, 0x12C6):
        print(f"  ROM[0x{i:05X}] = 0x{w:04X}  (context: {code[max(0,i-4):i+6].hex()})")

# Search for moves where register indirect write uses address-register set to 0x012C?
# Specifically: look for move.w ?, (An) where An could be 0x012C2
# This requires runtime analysis, not static — skip

# Instead: look for ALL move.w stores to any absolute address in range 0x012B0..0x012D0
print("\n=== Any absolute-addressed stores to 0x012B0..0x012D0 ===")
for ins in md.disasm(code[:0x15000], 0):
    op = ins.op_str.lower()
    # Look for $12b?, $12c?, $12d? in destination of move instruction
    import re
    if 'move' in ins.mnemonic:
        for m in re.finditer(r'\$12[bcd][0-9a-f]', op):
            print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")

print("\n=== Dispatcher 0x081DC..0x082DE ===")
for ins in md.disasm(code[0x081DC:0x081DC+250], 0x081DC):
    print(f"  0x{ins.address:05X}: [{ins.bytes.hex()}] {ins.mnemonic} {ins.op_str}")

print("\n=== Phase2 0x084C4..0x085A0 ===")
for ins in md.disasm(code[0x084C4:0x084C4+250], 0x084C4):
    print(f"  0x{ins.address:05X}: [{ins.bytes.hex()}] {ins.mnemonic} {ins.op_str}")
