#!/usr/bin/env python3
"""Disassemble 0x03182 (piece entry builder) and the table at 0x04DC2."""
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


# Piece entry builder: called from 0x002DC with:
#   arg1 = piece_entry_ptr (push from lea -$776c(a4)+d0)
#   arg2 = ptr into 0x04AE0 table (8-byte entries)
#   arg3 = [0x04DB0]
#   arg4 = [0x04A8E]+0xC8
#   arg5 = [0x04A8C]
dis(0x03182, 120, "build_piece_entry (0x03182)")

# Also 0x05138 (called from 0x07022 with piece entry ptr)
dis(0x05138, 80, "fn_05138 (called from 07022 with piece_entry_ptr)")

# The alpha-beta search entry (0x031C6) — we need to understand its first few instructions
dis(0x031C6, 80, "alpha_beta_entry (0x031C6)")

# Table at 0x04DC2 (64 bytes: square → piece entry index)
print(f"\n=== Table at 0x04DC2 (64 bytes: sq→piece_idx) ===")
for rank in range(8):
    row = []
    for file in range(8):
        sq = rank * 8 + file
        val = code[0x04DC2 + sq]
        col = chr(ord('a') + file)
        row.append(f"{val:3d}")
    print(f"  rank{rank+1}: {''.join(row)}")

# Table at 0x04AE0 (8 bytes per entry: piece movement data)
print(f"\n=== Table at 0x04AE0 (8 bytes/entry: piece movement?) ===")
for i in range(12):
    addr = 0x04AE0 + i * 8
    b = code[addr:addr+8]
    print(f"  entry[{i:2d}]: {b.hex()}  [{' '.join(f'{x:3d}' for x in b)}]")

# Table at 0x01598 (piece flags: 0=pawn, ..., 5=king)
print(f"\n=== Table at 0x01598 (piece flags) ===")
for i in range(16):
    addr = 0x01598 + i
    val = code[addr]
    print(f"  [0x{addr:04X}] flags[{i}] = 0x{val:02X} = {val:08b}")

# Table at 0x012CC (piece values)
print(f"\n=== Table at 0x012CC (piece values, 8 entries) ===")
for i in range(8):
    val = code[0x012CC + i]
    print(f"  [0x{0x012CC+i:04X}] value[{i}] = {val}")

# Also: find what reads from 0x0892 piece entries in the alpha-beta search
# Specifically: what does 0x031C6 / 0x03218 look at in the piece entry?
dis(0x03218, 120, "core_search_0x03218")
