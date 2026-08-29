#!/usr/bin/env python3
"""Inline disassembler for ai_outer_driver (0x81DC) and related functions.

Discovers how the piece-list at 0x0892 is structured and what
the search actually reads from memory.
"""
import sys, importlib.util, types, struct, re
import capstone

# -- module loading without triggering Code/__init__ --
_code_pkg = types.ModuleType('Code')
_code_pkg.__path__ = ['bin/Code']
sys.modules['Code'] = _code_pkg
_retro_pkg = types.ModuleType('Code.Retro')
_retro_pkg.__path__ = ['bin/Code/Retro']
sys.modules['Code.Retro'] = _retro_pkg

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

print(f"Code region: 0x0000 - 0x{len(code)-1:05X}  ({len(code)} bytes)")


def a4rel(disp_str):
    """Convert A4-relative displacement string to absolute address annotation."""
    d = int(disp_str.replace('-', '').replace('$', ''), 16)
    if disp_str.startswith('-'):
        d = -d
    return f"  ;[0x{(A4 + d) & 0xFFFFFF:05X}]"


def annotate(ins):
    ea = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        ea += a4rel(m.group(1))
    # Annotate PC-relative jumps with absolute target
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        target = int(m.group(1), 16)
        ea += f"  ;->0x{target:05X}"
    return ea


def dis(start, n_insns=80, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE (size={len(code):#x}) ===")
        return
    print(f"\n=== 0x{start:05X}  {label} ===")
    data = code[start:start + n_insns * 10]
    for i, ins in enumerate(md.disasm(data, start)):
        raw = code[ins.address:ins.address + ins.size].hex()
        ann = annotate(ins)
        print(f"  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}")
        if ins.mnemonic in ('rts', 'rte') and i > 3:
            break
        if i >= n_insns - 1:
            break


# ── 1. ai_outer_driver ──────────────────────────────────────────────────────
dis(0x81DC, 100, "ai_outer_driver")

# ── 2. ai_phase0_init ───────────────────────────────────────────────────────
dis(0x8230, 80, "ai_phase0_init")

# ── 3. The function at 0x04B1A (make/undo prev move) ───────────────────────
dis(0x04B1A, 60, "make_undo_move (0x04B1A)")

# ── 4. alpha-beta search entry 0x31C6 ───────────────────────────────────────
dis(0x31C6, 120, "alpha_beta_search (0x31C6)")

# ── 5. What 0x31C6 receives: the function called at 0x0100A ─────────────────
# The call at 0x0100A: jsr $31c6(pc)  from PC=0x0100C → target 0x31C6+0x100C=0x41D2?
# Actually: jsr $31c6(pc) means offset=$31C6 from next PC
# Let's compute: 0x0100A bytes are [4e ba 30 ba] → 4eba = jsr (d16,PC)
# offset = 0x30BA; PC after instr = 0x0100C; target = 0x0100C + 0x30BA = 0x31C6. ✓
# So look at 0x01000-0x01010 to see what it pushes:
print(f"\n=== 0x00FFC-0x01012  (call to 0x31C6 with piece entry) ===")
for i, ins in enumerate(md.disasm(code[0x00FFC:0x01020], 0x00FFC)):
    raw = code[ins.address:ins.address + ins.size].hex()
    ann = annotate(ins)
    print(f"  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}")
    if i >= 25:
        break

# ── 6. Raw bytes at 0x0892 (piece list base) ────────────────────────────────
print(f"\n=== ROM bytes at 0x0892-0x0A92 (piece list, 0x200 bytes, 32 bytes/entry) ===")
for entry in range(10):  # first 10 entries = 320 bytes
    base = 0x0892 + entry * 32
    b = code[base:base + 32]
    print(f"  entry[{entry:2d}] 0x{base:04X}: {b.hex()}")

# ── 7. What's at [0x04ADE] (index into piece list) ─────────────────────────
print(f"\n=== ROM bytes at 0x04ADE (piece-list current index) ===")
b = code[0x04AD0:0x04AF0]
print(f"  0x04AD0-0x04AEF: {b.hex()}")

# ── 8. Scan for all instructions referencing address 0x0892 ─────────────────
print(f"\n=== Scan for references to [0x0892] (piece_list_base) ===")
# A4 - 0x776C = 0x0892 → look for -$776c(a4)
# encoded as 0x776C as signed 16-bit displacement
hits = []
for addr in range(0, len(code) - 4, 2):
    raw = code[addr:addr + 10]
    insns = list(md.disasm(raw, addr))
    if insns:
        ins = insns[0]
        if '-$776c(a4)' in ins.op_str or '-$776C(a4)' in ins.op_str:
            hits.append((addr, ins.mnemonic, ins.op_str))

for (a, mn, op) in hits:
    print(f"  0x{a:05X}: {mn} {op}")

# ── 9. Scan for references to [0x04ADE] ─────────────────────────────────────
# A4 - 0x3320 = 0x4ADE → -$3320(a4)
print(f"\n=== Scan for references to [0x04ADE] (piece_list_index) — -$3320(a4) ===")
for addr in range(0, len(code) - 4, 2):
    raw = code[addr:addr + 10]
    insns = list(md.disasm(raw, addr))
    if insns:
        ins = insns[0]
        if '-$3320(a4)' in ins.op_str:
            hits2 = (addr, ins.mnemonic, ins.op_str)
            print(f"  0x{hits2[0]:05X}: {hits2[1]} {hits2[2]}")
