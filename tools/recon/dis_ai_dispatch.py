#!/usr/bin/env python3
"""Disassemble the AI dispatch chain: 0x8230 (called from 0x81DC), 0x82DE, 0x84C4.
Also dumps 0x00AE, 0x000D2, 0x000DE, 0x000C0 to understand what they are.
"""
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


def dis(start, n_insns=100, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE ({start} > {len(code)}) ===")
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


# The actual AI search phases
dis(0x8230, 120, "AI phase0_init (0x8230) — called from 0x81DC when [0x04A5C]==0")
dis(0x82DE, 80, "AI phase1 (0x82DE) — called from 0x81DC when [0x04A5C]==1")
dis(0x84C4, 80, "AI phase2 (0x84C4) — called from 0x81DC when [0x04A5C]==2")

# The functions called from 0x0774E
dis(0x000AE, 60, "fn_0x00AE (called from 0x07022)")
dis(0x000D2, 60, "fn_0x000D2 (called from 0x0774E)")
dis(0x000DE, 40, "fn_0x000DE (called from 0x0774E)")
dis(0x000C0, 40, "fn_0x000C0 (the patched A6-dep call)")

# The 0x01722 function called from 0x01294
dis(0x01722, 80, "fn_0x01722 (called from 0x01294)")

# What is at 0x0022E? (called from 0x01320)
dis(0x0022E, 80, "fn_0x0022E (called from 0x01320)")

# ROM bytes at 0x365A (AI_BEST_MOVE_ADDR = A4 - 0x49A4)
print(f"\n=== ROM at 0x365A (AI_BEST_MOVE_ADDR = A4 - 0x49A4) ===")
b = code[0x365A:0x365A+8] if 0x365A+8 <= len(code) else b'?'*8
print(f"  {b.hex()}")

# Key area: 0x00502 onwards (post-search move extraction from context)
dis(0x00502, 60, "post_search_move_extract (0x00502) — reads [0x012C4]/[0x012C2]")

# Find all references to 0x365A (AI_BEST_MOVE_ADDR = A4 - 0x49A4)
print(f"\n=== Code referencing AI_BEST_MOVE_ADDR 0x365A (A4 - 0x49A4) ===")
for addr in range(0, len(code) - 4, 2):
    raw_bytes = code[addr:addr + 10]
    insns = list(md.disasm(raw_bytes, addr))
    if insns:
        ins = insns[0]
        if '-$49a4(a4)' in ins.op_str.lower() or '-$49a3(a4)' in ins.op_str.lower():
            print(f"  0x{addr:05X}: {ins.mnemonic} {ins.op_str}")
