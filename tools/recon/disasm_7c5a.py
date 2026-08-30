"""Disassemble 0x7C5A AI dispatch, 0x7F00 movegen, 0x7F96 phase1, 0xA062 movegen2."""
import sys, os, re
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')
from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
A4 = 0x7FFE

def ea(disp_signed):
    return (A4 + disp_signed) & 0xFFFF

def disasm_range(start, end, label=None):
    if label: print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        # Fix annotation: correctly handle signed displacement
        def annotate(m):
            sign_neg = m.group(1) == '-'
            hex_str = m.group(2)
            v = int(hex_str, 16)
            effective = (A4 - v) & 0xFFFF if sign_neg else (A4 + v) & 0xFFFF
            return f'{"-" if sign_neg else ""}${hex_str}(a4)[0x{effective:04X}]'
        op_ann = re.sub(r'(-?)\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

disasm_range(0x7C5A, 0x7C90, '0x7C5A AI dispatch')
disasm_range(0x7F00, 0x7F60, '0x7F00 move gen (phase 0)')
disasm_range(0x7F96, 0x7FC0, '0x7F96 phase 1')
disasm_range(0xA062, 0xA0A0, '0xA062 move gen per side')
disasm_range(0xABBE, 0xABF0, '0xABBE (called from 0x9494)')
disasm_range(0xAE1C, 0xAE60, '0xAE1C (called from 0x9494)')
disasm_range(0x00E4, 0x0118, '0x00E4 event check')
