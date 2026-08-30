"""Disassemble move gen 0x9494 to find board access pattern, and 0x17D2."""
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

def disasm_range(start, end, label=None):
    if label:
        print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        def annotate(m):
            s = m.group(1)
            v = int(s, 16)
            if v > 0x7FFF: v = -(0x10000-v)
            effective = (A4 + v) & 0xFFFF
            return f'${s}(a4)[{effective:#06x}]'
        op_ann = re.sub(r'\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

# Move gen (generate legal moves)
disasm_range(0x9494, 0x9540, '0x9494 move gen entry')

# Also look at 0x94D8 (called from 0x7F14)
disasm_range(0x94D8, 0x9530, '0x94D8 (called from 0x7F14)')

# 0x17D2 (event handler in main game loop)
disasm_range(0x17D2, 0x1840, '0x17D2 event handler')

# 0x9DD0 (called before board setup from 0x7C90)
disasm_range(0x9DD0, 0x9E40, '0x9DD0 pre-board setup')

# 0x7D96 (called from 0x7C34 and 0x7FAC)
disasm_range(0x7D96, 0x7DE0, '0x7D96')
