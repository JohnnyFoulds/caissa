#!/usr/bin/env python3
"""Disassemble phase-1, phase-2, 0x7D3C, 0x94D8 from the Battle Chess ROM."""
import sys, importlib.util, types, re
import capstone

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
print(f'Code region: 0x0000 - 0x{len(code)-1:05X}  ({len(code)} bytes)\n')


def a4rel(disp_str):
    d = int(disp_str.replace('-', '').replace('$', ''), 16)
    if disp_str.startswith('-'):
        d = -d
    return f'  ;[0x{(A4 + d) & 0xFFFFFF:05X}]'


def annotate(ins):
    ea = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        ea += a4rel(m.group(1))
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        target = int(m.group(1), 16)
        ea += f'  ;->0x{target:05X}'
    return ea


def dis(start, n_insns=80, label=''):
    if start >= len(code):
        print(f'\n=== 0x{start:05X} OUTSIDE CODE (size={len(code):#x}) ===')
        return
    print(f'=== 0x{start:05X}  {label} ===')
    data = code[start:start + n_insns * 10]
    for i, ins in enumerate(md.disasm(data, start)):
        raw = code[ins.address:ins.address + ins.size].hex()
        ann = annotate(ins)
        print(f'  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}')
        if ins.mnemonic in ('rts', 'rte') and i > 3:
            break
        if i >= n_insns - 1:
            break
    print()


dis(0x82DE, 80, 'Phase-1 / ai_phase1')
dis(0x84C4, 80, 'Phase-2 / ai_phase2')
dis(0x7D3C, 80, '0x7D3C')
dis(0x94D8, 80, '0x94D8')
dis(0x008A, 30, 'TC / time_check')
