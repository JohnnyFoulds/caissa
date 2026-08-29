#!/usr/bin/env python3
"""Disassemble the functions that build 0x0892 piece entries, focusing on what [+0x14] gets."""
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


# Known 0x0892 writers
dis(0x07022, 120, "writer_to_0892_at_07022")
dis(0x07356, 80, "writer_to_0892_at_07356")

# Also: what 0x002DC does (early writer called before AI)
dis(0x002DC, 120, "early_writer_002DC")

# And 0x00470
dis(0x00470, 80, "early_writer_00470")

# Key: find all WRITES to 0x0892 area (offsets in 0x0892..0x0892+32*32)
# Each piece entry is 32 bytes, so 0x0892 to 0x0892 + 1023 = 0x0C92
# The field at [+0x14] in entry 0 is at 0x0892+0x14 = 0x08A6
# Let's find writes to 0x08A6 (first entry's [+0x14])
print(f"\n=== Finding writes to 0x0892 area (piece entry [+0x14] = function pointer) ===")

# Direct scan for 0x0892 area references
PIECE_TABLE_START = 0x0892
PIECE_TABLE_END = PIECE_TABLE_START + 32 * 32  # 0x0C92

# A4 - offset approach: 0x0892 = A4 - 0x776C
# 0x776C = 0x7FFE - 0x0892
a4_offset_for_piece_base = A4 - PIECE_TABLE_START  # 0x776C
print(f"  Piece table base: 0x{PIECE_TABLE_START:04X} = A4 - 0x{a4_offset_for_piece_base:04X}")

# Scan for any address reference in the piece table range
# Strategy: look for move.l #imm, X(an) patterns near 0x0892
# Also look for lea.l near 0x0892

# Find all 'move.l' writes where dest is indexed by 0x0892 range
hits = []
for addr in range(0, len(code) - 4, 2):
    raw_bytes = code[addr:addr + 10]
    insns = list(md.disasm(raw_bytes, addr))
    if insns:
        ins = insns[0]
        # Look for writes (store) instructions to near-PC address range
        op = ins.op_str
        if ('(a' in op or '(a' in ins.mnemonic) and ins.mnemonic.startswith('move'):
            # Check if any address involved is in 0x0892-0x0C92
            for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', op):
                computed = a4rel(m.group(1))
                if PIECE_TABLE_START <= computed < PIECE_TABLE_END:
                    hits.append((addr, ins.mnemonic, op, computed))

# Also: look for PC-relative loads/stores
for addr in range(0, len(code) - 4, 2):
    raw_bytes = code[addr:addr + 10]
    insns = list(md.disasm(raw_bytes, addr))
    if insns:
        ins = insns[0]
        for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
            target = int(m.group(1), 16)
            if PIECE_TABLE_START <= target < PIECE_TABLE_END:
                hits.append((addr, ins.mnemonic, ins.op_str, target))

print(f"  Direct 0x0892-area references: {len(hits)}")
for (a, mn, op, computed) in hits[:20]:
    print(f"    0x{a:05X}: {mn} {op}  → [0x{computed:05X}]")

# Show what's at 0x0892 in ROM (original ROM bytes)
print(f"\n=== ROM bytes at 0x0892-0x08D2 (first 2 piece entries before any init) ===")
for i in range(2):
    base = 0x0892 + i * 32
    e = code[base:base+32]
    print(f"  entry[{i}]: {e.hex()}")
    for off in range(0, 32, 4):
        val = struct.unpack(">I", e[off:off+4])[0]
        print(f"    +0x{off:02X}: 0x{val:08X} ({val})")

# Find what CALLS 0x07022 (to understand the context)
print(f"\n=== Callers of 0x07022 ===")
for addr in range(0, len(code) - 4, 2):
    raw_bytes = code[addr:addr + 6]
    insns = list(md.disasm(raw_bytes, addr))
    if insns:
        ins = insns[0]
        if ins.mnemonic in ('jsr', 'bsr') and '7022' in ins.op_str:
            print(f"  0x{addr:05X}: {ins.mnemonic} {ins.op_str}")

# Also look for what scans the board at 0x030F4 to build pieces
# 0x030F4 = A4 - 0x4F0A
print(f"\n=== References to board base 0x030F4 (-$4f0a(a4)) ===")
for addr in range(0, len(code) - 4, 2):
    raw_bytes = code[addr:addr + 10]
    insns = list(md.disasm(raw_bytes, addr))
    if insns:
        ins = insns[0]
        if '-$4f0a(a4)' in ins.op_str.lower():
            print(f"  0x{addr:05X}: {ins.mnemonic} {ins.op_str}")
