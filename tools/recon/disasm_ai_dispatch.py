"""Disassemble from 0x020A onward to find what happens when all AI conditions are met."""
import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')

from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]

md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
md.detail = True

def disasm_range(start, end, label=None):
    if label:
        print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        print(f'  {insn.address:04X}  {insn.bytes.hex():16s}  {insn.mnemonic:12s} {insn.op_str}')

# Continue from 0x020A (after AI condition check) — what happens when conditions are met?
disasm_range(0x020A, 0x0140, '0x020A-0x013F (AI dispatch, wraps around)')
# Actually continue the disassembly after 0x020A
disasm_range(0x020A, 0x0340, '0x020A-0x033F')

# What's before 0x013E — the function entry point
disasm_range(0x00F0, 0x0140, '0x00F0-0x013E (before hot loop)')

# The inner function at 0x010E (keyboard check)
disasm_range(0x010E, 0x013E, '0x010E-0x013D (keyboard/input check)')

# What's at 0x011A (called from 0x0180)
disasm_range(0x011A, 0x0140, '0x011A-0x013F (get key data)')

# What's at 0x021C (called after input dispatch)
disasm_range(0x021C, 0x0260, '0x021C-0x025F')
