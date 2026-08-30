"""Disassemble 0x7F00 (move gen) and 0x81DC (AI search) to find board array address."""
import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')

from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
import re

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]

md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
md.detail = True

A4 = 0x7FFE

def ea(offset_str, base=A4):
    """Compute effective address from signed offset string and base."""
    v = int(offset_str, 16)
    if v > 0x7FFF: v = -(0x10000-v)
    return (base + v) & 0xFFFF

def disasm_range(start, end, label=None):
    if label:
        print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        # Annotate A4-relative addresses
        def annotate(m):
            s = m.group(1)
            v = int(s, 16)
            if v > 0x7FFF: v = -(0x10000-v)
            effective = (A4 + v) & 0xFFFF
            return f'${s}(a4)[={effective:#06x}]'
        op_ann = re.sub(r'\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

# Move generator at 0x7F00
disasm_range(0x7F00, 0x7F80, 'Move generator 0x7F00')

# AI search at 0x81DC (first 100 bytes)
disasm_range(0x81DC, 0x8280, 'AI search 0x81DC')

# What gets called from 0x7F00 in the first few instructions?
# Also check 0x7F96 (phase 1)
disasm_range(0x7F96, 0x7FD0, 'Phase 1 function 0x7F96')

# And 0x84CC (board setup from 0x7C94)
disasm_range(0x84CC, 0x8560, 'Board setup 0x84CC')
