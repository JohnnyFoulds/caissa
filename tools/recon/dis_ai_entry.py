#!/usr/bin/env python3
"""Disassemble AI_OUTER_DRIVER (0x81DC), 0x0774E (board init), and 0x07022 (piece builder)."""
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


# -----------------------------------------------------------------------
# 1. AI outer driver — what does 0x81DC do?
# -----------------------------------------------------------------------
dis(0x81DC, 120, "AI_OUTER_DRIVER (0x81DC) — called by Think.py to start a think")

# -----------------------------------------------------------------------
# 2. Board init functions called from 0x0183E
# -----------------------------------------------------------------------
dis(0x0774E, 100, "board_init_0x0774E — called from 0x0183E at line 0x01936")
dis(0x07922, 100, "board_init_0x07922 — called from 0x0183E at line 0x01942")

# -----------------------------------------------------------------------
# 3. The piece entry writer called from 0x07356
# -----------------------------------------------------------------------
dis(0x07022, 120, "piece_entry_writer_0x07022")

# -----------------------------------------------------------------------
# 4. The function at 0x01294 — "search call from game loop"
# -----------------------------------------------------------------------
dis(0x01294, 120, "search_call_0x01294 — jsr target from 0x0023C")

# -----------------------------------------------------------------------
# 5. ROM bytes at key addresses
# -----------------------------------------------------------------------
print(f"\n=== ROM bytes at 0x012BC (A4 - 0x6D42, depth/[+0x14] index) ===")
for off in range(-2, 6):
    addr = 0x012BC + off
    if 0 <= addr < len(code):
        b = code[addr]
        print(f"  [0x{addr:05X}] = 0x{b:02X} = {b}")

print(f"\n=== ROM bytes at 0x01152 (linked-list head) ===")
head_bytes = code[0x01152:0x01156]
print(f"  [0x01152..0x01155] = {head_bytes.hex()} = {struct.unpack('>I', head_bytes)[0]:#010X}")

print(f"\n=== ROM bytes at 0x0892 (first 4 entries of piece table area, before init) ===")
for i in range(4):
    base = 0x0892 + i * 32
    e = code[base:base+32]
    print(f"  entry[{i}] @ 0x{base:05X}: {e[:8].hex()} ... {e[16:24].hex()}")

print(f"\n=== ROM bytes at 0x04B60 (0x04AE0 + 16*8 = default [+0x14] for depth 0) ===")
addr = 0x04B60
if addr < len(code):
    b8 = code[addr:addr+8]
    print(f"  [0x{addr:05X}..+7]: {b8.hex()} = bytes {list(b8)}")

print(f"\n=== ROM bytes around 0x012B6-0x012C6 (scratch/result area) ===")
for addr in range(0x012B6, 0x012C8):
    b = code[addr] if addr < len(code) else 0xFF
    print(f"  [0x{addr:05X}] = 0x{b:02X}", end='')
    if addr == 0x012BC: print("  ← [0x012BC] depth-index", end='')
    if addr == 0x012C2: print("  ← [0x012C2] FROM-square result", end='')
    if addr == 0x012C4: print("  ← [0x012C4] TO-square result", end='')
    print()
