#!/usr/bin/env python3
"""Find callers of fn_09CC2 and fn_07922 + disassemble relevant functions."""
import sys, re, importlib.util, types
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


def annotate(ins):
    r = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        d = int(m.group(1).replace('-', '').replace('$', ''), 16)
        if m.group(1).startswith('-'):
            d = -d
        r += f"  ;[0x{(A4 + d) & 0xFFFF:05X}]"
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        r += f"  ;->0x{int(m.group(1), 16):05X}"
    return r


def dis(start, n=60, label=""):
    print(f"\n=== 0x{start:05X}  {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n * 10], start)):
        print(f"  0x{ins.address:05X}: [{ins.bytes.hex():<12}] {ins.mnemonic} {ins.op_str}{annotate(ins)}")
        if i + 1 >= n:
            break


# Find callers of fn_09CC2 (0x09CC2) and fn_07922 (0x07922)
targets = {0x09CC2: "fn_09CC2", 0x07922: "fn_07922"}
callers = {t: [] for t in targets}

for ins in md.disasm(code[:0x12000], 0):
    if ins.mnemonic not in ('jsr', 'bsr', 'bsr.b', 'bsr.w', 'jmp'):
        continue
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        tgt = int(m.group(1), 16)
        if tgt in targets:
            callers[tgt].append(ins.address)

for tgt, name in targets.items():
    print(f"\n=== Callers of {name} (0x{tgt:05X}) ===")
    for addr in callers[tgt]:
        print(f"  Call from 0x{addr:05X}:")
        start = max(0, addr - 40)
        for ins in md.disasm(code[start:addr + 8], start):
            print(f"    0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}{annotate(ins)}")

# fn_07D96 area
dis(0x07D96, 60, "fn_07D96")
# fn_07EBA
dis(0x07EBA, 60, "fn_07EBA")
