#!/usr/bin/env python3
"""Disassemble 0x08916 (populates 0x0892 entries) and find 0x077A writers."""
import sys, importlib.util, types, struct, re
import capstone

_code_pkg = types.ModuleType('Code'); _code_pkg.__path__ = ['bin/Code']; sys.modules['Code'] = _code_pkg
_retro_pkg = types.ModuleType('Code.Retro'); _retro_pkg.__path__ = ['bin/Code/Retro']; sys.modules['Code.Retro'] = _retro_pkg

def _load(dotpath, filepath):
    spec = importlib.util.spec_from_file_location(dotpath, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotpath] = mod
    spec.loader.exec_module(mod)
    return mod

_load('Code.Retro.Types', 'bin/Code/Retro/Types.py')
_load('Code.Retro.Errors', 'bin/Code/Retro/Errors.py')
Manifest = _load('Code.Retro.Manifest', 'bin/Code/Retro/Manifest.py')
Rom = _load('Code.Retro.Rom', 'bin/Code/Retro/Rom.py')

rom_data = open(Manifest.default_rom_path(), 'rb').read()
regions = Rom.parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)


def a4rel(disp_str):
    d = int(disp_str.replace('-', '').replace('$', ''), 16)
    if disp_str.startswith('-'):
        d = -d
    return (A4 + d) & 0xFFFFFF


def annotate(ins):
    ea = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        ea += f"  ;[0x{a4rel(m.group(1)):05X}]"
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        target = int(m.group(1), 16)
        ea += f"  ;->0x{target:05X}"
    return ea


def dis(start, n_insns=80, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE ===")
        return
    print(f"\n=== 0x{start:05X}  {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n_insns * 10], start)):
        raw = code[ins.address:ins.address + ins.size].hex()
        ann = annotate(ins)
        print(f"  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}")
        if ins.mnemonic in ('rts', 'rte') and i > 3:
            break
        if i >= n_insns - 1:
            break


# Main function that populates 0x0892 from 8-byte position entries
dis(0x08916, 120, "populate_piecelist (0x08916) — called when byte6 != 0")
dis(0x088DE, 80, "populate_piecelist_special (0x088DE) — called when byte7 == 1")

# Show the 8-byte structure at 0x077A area in ROM
print(f"\n=== ROM bytes at 0x0770-0x0800 (0x077A and vicinity) ===")
for addr in range(0x0770, 0x0800, 8):
    b = code[addr:addr+8]
    print(f"  0x{addr:04X}: {b.hex()}")

# Find all STORES to 0x077A (A4 - 0x7884)
# encoded as -$7884(a4) in A4-relative
print(f"\n=== Scan for WRITES to [0x077A] — -$7884(a4) ===")
hits = []
for addr in range(0, len(code) - 4, 2):
    raw = code[addr:addr + 10]
    insns = list(md.disasm(raw, addr))
    if insns:
        ins = insns[0]
        if '-$7884(a4)' in ins.op_str.lower():
            hits.append((addr, ins.mnemonic, ins.op_str))
for (a, mn, op) in hits:
    print(f"  0x{a:05X}: {mn} {op}")

# Also find what writes to 0x03322 (not just reads)
# -$4cdc(a4) for writes that STORE rather than just load
print(f"\n=== Scan for WRITES to [0x03322] — -$4cdc(a4) (stores only) ===")
hits2 = []
for addr in range(0, len(code) - 4, 2):
    raw = code[addr:addr + 10]
    insns = list(md.disasm(raw, addr))
    if insns:
        ins = insns[0]
        if '-$4cdc(a4)' in ins.op_str.lower():
            hits2.append((addr, ins.mnemonic, ins.op_str))
for (a, mn, op) in hits2[:20]:
    print(f"  0x{a:05X}: {mn} {op}")

# Show what's at 0x07022 (a writer to 0x0892)
dis(0x07022, 100, "writer to 0x0892 at 0x07022")

# Show what's at 0x07356 (another 0x0892 writer)
dis(0x07356, 80, "writer to 0x0892 at 0x07356")
