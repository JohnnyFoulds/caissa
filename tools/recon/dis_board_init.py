#!/usr/bin/env python3
"""Disassemble board-init functions called by ai_phase0_init.

Focus: 0x07CCE, 0x0857E, 0x08820, 0x08D32 — one of these populates 0x0892 piece list.
Also look at 0x03102 (first call inside 0x31C6) and 0x03218 (core search).
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


def a4abs(disp_str):
    d = int(disp_str.replace('-', '').replace('$', ''), 16)
    if disp_str.startswith('-'):
        d = -d
    return (A4 + d) & 0xFFFFFF


def annotate(ins, addr):
    ea = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        ea += f"  ;[0x{a4abs(m.group(1)):05X}]"
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        target = int(m.group(1), 16)
        ea += f"  ;->0x{target:05X}"
    for m in re.finditer(r'^bsr\b|^bra\b|^beq\b|^bne\b|^blt\b|^bgt\b|^bhi\b|^bls\b|^bge\b|^ble\b', ins.mnemonic):
        for sm in re.finditer(r'\$([0-9a-fA-F]+)$', ins.op_str):
            ea += f"  ;->0x{int(sm.group(1),16):05X}"
    return ea


def dis(start, n_insns=80, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE ===")
        return
    print(f"\n=== 0x{start:05X}  {label} ===")
    data = code[start:start + n_insns * 10]
    for i, ins in enumerate(md.disasm(data, start)):
        raw = code[ins.address:ins.address + ins.size].hex()
        ann = annotate(ins, ins.address)
        print(f"  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}")
        if ins.mnemonic in ('rts', 'rte') and i > 3:
            break
        if i >= n_insns - 1:
            break


# 0x07CCE — third call in ai_phase0_init; likely board → piece list
dis(0x07CCE, 100, "board_to_piecelist? (0x07CCE)")

# 0x0857E — fourth call in ai_phase0_init
dis(0x0857E, 80, "fourth_init (0x0857E)")

# 0x08820 — first call in ai_phase0_init
dis(0x08820, 60, "first_init (0x08820)")

# 0x08D32 — second call in ai_phase0_init
dis(0x08D32, 60, "second_init (0x08D32)")

# 0x03102 — first call inside 0x31C6 (piece entry helper)
dis(0x03102, 60, "piece_entry_helper (0x03102)")

# 0x03218 — core search called by 0x31C6
dis(0x03218, 80, "core_search (0x03218)")

# Now look at where [0x012BC] and [0x012BE] are WRITTEN
# [0x012BC] = A4 - 0x6D42 = target offset 0x92C2 → -$6d42(a4)
# [0x012BE] = A4 - 0x6D40 = target offset 0x92C0 → -$6d40(a4)
print(f"\n=== Scan for WRITES to [0x012BC] (-$6d42(a4)) and [0x012BE] (-$6d40(a4)) ===")
targets = {
    0x012BC: '6d42',
    0x012BE: '6d40',
    0x012BA: '6d44',
    0x012B7: '6d47',
    0x012B9: '6d45',
}
for tgt, hex_disp in sorted(targets.items()):
    hits = []
    for addr in range(0, len(code) - 4, 2):
        raw = code[addr:addr + 10]
        insns = list(md.disasm(raw, addr))
        if insns:
            ins = insns[0]
            if f'-${hex_disp}(a4)' in ins.op_str.lower():
                hits.append((addr, ins.mnemonic, ins.op_str))
    print(f"\n  [0x{tgt:05X}] referenced at {len(hits)} places:")
    for (a, mn, op) in hits[:15]:
        print(f"    0x{a:05X}: {mn} {op}")

# Also: what is 0x012BC at ROM time?
print(f"\n=== ROM bytes at 0x012B0-0x012D0 ===")
for addr in range(0x012B0, 0x012D0, 2):
    b = code[addr:addr+2]
    insns = list(md.disasm(code[addr:addr+8], addr))
    dis_str = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else '???'
    print(f"  0x{addr:05X}: {b.hex()}  {dis_str}")
