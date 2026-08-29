#!/usr/bin/env python3
"""Disassemble 0x09CC2 (the real piece-list populator) + initial setup code."""
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


# The REAL piece-list builder
dis(0x09CC2, 150, "real_piecelist_builder (0x09CC2)")

# Initial setup at 0x002DC (very early in the code, writes to 0x0892)
dis(0x002DC, 80, "early_writer_to_0892 (0x002DC)")

# 0x00470 — another early writer
dis(0x00470, 60, "early_writer_0x00470")

# Table at 0x04DC2 = square→pieceindex mapping
print(f"\n=== ROM bytes at 0x04DC2-0x04E02 (square→pieceindex map) ===")
for addr in range(0x04DC2, 0x04E02, 16):
    b = code[addr:addr+16]
    print(f"  0x{addr:04X}: {' '.join(f'{x:02x}' for x in b)}")

# Table at 0x01598 = pieces info table (used for piece flags)
print(f"\n=== ROM bytes at 0x01598-0x015D8 (piece flags table) ===")
for addr in range(0x01598, 0x015D8, 16):
    b = code[addr:addr+16]
    print(f"  0x{addr:04X}: {' '.join(f'{x:02x}' for x in b)}")

# Table at 0x012CC = used for move-value lookup
print(f"\n=== ROM bytes at 0x012CC-0x012EE ===")
for addr in range(0x012CC, 0x012EE, 16):
    b = code[addr:addr+16]
    insns = list(md.disasm(code[addr:addr+16], addr))
    dis_str = ' | '.join(f"{i.mnemonic} {i.op_str}" for i in insns[:4])
    print(f"  0x{addr:04X}: {' '.join(f'{x:02x}' for x in b)}  {dis_str}")
