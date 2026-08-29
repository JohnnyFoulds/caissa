#!/usr/bin/env python3
"""Disassemble 0x7CCE and functions it calls, to understand how it sets up the piece list."""
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

def dis(start, n_insns=120, label=""):
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

# What 0x7CCE does
dis(0x7CCE, 150, "0x7CCE — called from phase0_init (0x8230)")

# Check 0x8820, 0x8D32 (called before 0x7CCE in phase0)
dis(0x8820, 60, "0x8820 — called from 0x8230 first")
dis(0x8D32, 60, "0x8D32 — called from 0x8230 second")

# The key 0x094D8 function called from phase1 (0x82DE)
dis(0x094D8, 100, "0x094D8 — called from phase1 (0x82DE), likely actual AI search")

# What is at 0x00FC6? (called at start of 0x01294)
dis(0x00FC6, 60, "0x00FC6 — called from 0x01294")

# The 0x7852 function called from 0x0774E
dis(0x7852, 80, "0x7852 — called from 0x0774E")

# Verify raw bytes at 0x81F4 (jsr to phase1)
print(f"\n=== Raw bytes at 0x81F4-0x81FC (jsr dispatch to phase1) ===")
for addr in range(0x81F4, 0x8200, 2):
    b = code[addr:addr+2]
    insns = list(md.disasm(code[addr:addr+8], addr))
    if insns:
        ins = insns[0]
        print(f"  0x{addr:05X}: {code[addr:addr+ins.size].hex():10s} = {ins.mnemonic} {ins.op_str}")
        addr += ins.size - 2
