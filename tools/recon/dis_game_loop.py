#!/usr/bin/env python3
"""Disassemble game-loop area (0x01EA) + find writers to AI_BEST_MOVE_ADDR (0x365A)."""
import sys, importlib.util, types, re
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


def dis(start, n_insns=60, label=""):
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


# 1. What's at the game-loop exit 0x01EA?
dis(0x01C0, 80, "game-loop area around 0x01EA")

# 2. Find all WRITES to AI_BEST_MOVE_ADDR = 0x365A
# A4 - 0x49A4 = 0x365A → -$49a4(a4)
print(f"\n=== Scan for WRITES to [0x365A] (-$49a4(a4)) — AI_BEST_MOVE_ADDR ===")
hits = []
for addr in range(0, len(code) - 4, 2):
    raw = code[addr:addr + 10]
    insns = list(md.disasm(raw, addr))
    if insns:
        ins = insns[0]
        if '-$49a4(a4)' in ins.op_str.lower():
            hits.append((addr, ins.mnemonic, ins.op_str))
for (a, mn, op) in hits:
    print(f"  0x{a:05X}: {mn} {op}")

# 3. Find all WRITES to [0x365A] range (8 bytes) -- look at +0 to +7 offsets
print(f"\n=== Scan for references to 0x365A-0x3661 range ===")
for offset_hex, abs_addr in [
    ('49a4', 0x365A), ('49a6', 0x365C), ('49a8', 0x365E),
    ('49aa', 0x3660), ('49a2', 0x3658), ('499c', 0x3662),
]:
    hits = []
    for addr in range(0, len(code) - 4, 2):
        raw = code[addr:addr + 10]
        insns = list(md.disasm(raw, addr))
        if insns and f'-${offset_hex}(a4)' in insns[0].op_str.lower():
            hits.append((addr, insns[0].mnemonic, insns[0].op_str))
    if hits:
        print(f"\n  [0x{abs_addr:05X}] ({len(hits)} refs):")
        for (a, mn, op) in hits[:10]:
            print(f"    0x{a:05X}: {mn} {op}")

# 4. Show what writes to the PIECE_TABLE entry at 0x365A area
# (from the Bridge docs: AI_BEST_MOVE_ADDR=0x365A, 8 bytes)
# Look for move to/from 0x365A area in memory-write context
# Alternative: look for what 0x01A20 (second call in game startup) does
dis(0x01A20, 80, "game_startup second init (0x01A20)")

# 5. What does 0x0183E (new game setup) do?
dis(0x0183E, 80, "new_game_setup (0x0183E)")

# 6. Look at 0x00502 area which reads [0x012C4] and [0x012C2]
# This is the code that reads FROM/TO after the search completes
# Let's see what it writes to AI_BEST_MOVE_ADDR
dis(0x00502, 100, "post_search: reads FROM/TO, writes best move")
