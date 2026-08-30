"""Disassemble 0x9FC4, code around 0xAE0A, and 0xA09E onwards."""
import sys, os, re, struct
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')
from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
A4 = 0x7FFE

def ea_neg(hex_str):
    return (A4 - int(hex_str, 16)) & 0xFFFF

def disasm_range(start, end, label=None):
    if label: print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        def annotate(m):
            sign_neg = m.group(1) == '-'
            hex_str = m.group(2)
            v = int(hex_str, 16)
            effective = (A4 - v) & 0xFFFF if sign_neg else (A4 + v) & 0xFFFF
            return f'{"-" if sign_neg else ""}${hex_str}(a4)[0x{effective:04X}]'
        op_ann = re.sub(r'(-?)\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

disasm_range(0x9FC4, 0xA062, '0x9FC4 piece iterator')
disasm_range(0xADC0, 0xAE1C, '0xADC0-0xAE1C (code around 0xAE0A)')
disasm_range(0xA09E, 0xA130, '0xA09E onwards in 0xA062')
disasm_range(0xAC00, 0xAC60, '0xAC00 (0xABBE inner loop)')

# Also show what's at key ROM data addresses that might be board data
print('\n=== ROM data at possible board locations ===')
for label, start in [
    ('0x32D4 area (piece cnt table in BSS)', None),
    ('ROM 0x077A (used in 0xAE1C)', 0x077A),
    ('ROM 0x32D4 area bytes', 0x32D4),
]:
    if start is not None:
        data = code_bytes[start:start+32]
        print(f'{label}: {data.hex()}')
        print(f'  as bytes: {list(data)}')
