#!/usr/bin/env python3
"""Disassemble 0x81DC (ai_outer_driver) to find the piece-list setup format."""
import sys, importlib.util, types, struct, re
# Bypass Code/__init__.py (needs psutil) — import Retro modules directly
def _load(dotpath):
    parts = dotpath.split('.')
    path = 'bin/' + '/'.join(parts) + '.py'
    spec = importlib.util.spec_from_file_location(dotpath, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotpath] = mod
    spec.loader.exec_module(mod)
    return mod

_load('Code')
_load('Code.Retro')
Manifest = _load('Code.Retro.Manifest')
_load('Code.Retro.Types')
_load('Code.Retro.Errors')
Rom = _load('Code.Retro.Rom')
default_rom_path = Manifest.default_rom_path
parse_amiga_hunk = Rom.parse_amiga_hunk
import capstone

rom_data = open(default_rom_path(), 'rb').read()
regions = parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

print(f"Code region: offset={regions[0].offset:#x}  size={regions[0].size:#x}  "
      f"load={regions[0].load_address:#x}")
print(f"Code covers: 0x0000 - 0x{regions[0].size-1:05X}")


def dis(start, n=80, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE (size={len(code):#x}) ===")
        return
    print(f"\n=== 0x{start:05X} {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n*8], start)):
        ea = ''
        for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
            d = int(m.group(1).replace('-', '').replace('$', ''), 16)
            if m.group(1).startswith('-'):
                d = -d
            ea += f"  ;[0x{(A4 + d) & 0xFFFFFF:05X}]"
        raw = code[ins.address:ins.address+ins.size].hex()
        print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if ins.mnemonic == 'rts' and i > 3:
            break
        if i >= n - 1:
            break


# 1. Disassemble ai_outer_driver at 0x81DC
dis(0x81DC, 80, "ai_outer_driver")

# 2. Show what's at 0x8230 (ai_phase0_init)
dis(0x8230, 60, "ai_phase0_init")

# 3. Show what's at 0x31C6 (actual alpha-beta search)
dis(0x31C6, 100, "alpha_beta_search (0x31C6)")

# 4. Show the 0x04B1A function (make/undo move, called by 0x0FC6)
dis(0x04B1A, 40, "make_undo_move (0x04B1A)")

# 5. Show what's at [0x00892] area — the piece list (start of the game data)
print(f"\n=== ROM bytes at 0x0888-0x0900 (piece list area) ===")
for addr in range(0x0888, 0x0910, 16):
    b = code[addr:addr+16]
    hex_str = ' '.join(f'{x:02x}' for x in b)
    print(f"  0x{addr:04X}: {hex_str}")

# 6. Show what [0x012C6] area looks like (the post-0x012C4 code)
print(f"\n=== ROM bytes at 0x012C0-0x012D4 ===")
for addr in range(0x012C0, 0x012D4, 2):
    b = code[addr:addr+2]
    insns = list(md.disasm(code[addr:addr+8], addr))
    ins_str = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else '???'
    print(f"  0x{addr:05X}: {b.hex()}  {ins_str}")
