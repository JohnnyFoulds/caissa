"""Disassemble the AI entry at 0x0096 and related functions."""
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

# The AI wrapper function at 0x0096
disasm_range(0x0096, 0x010E, 'AI wrapper fn 0x0096-0x010E')

# What's at 0x0060-0x0096 (game loop machinery?)
disasm_range(0x0060, 0x0096, '0x0060-0x0096')

# More context around 0x0000-0x0060 (already shown but interesting)
# Let's also look at the function that handles a new game setup
# If the game calls 0x0096 after the user makes their move,
# what sets up [0x12B6] and [0x331C] etc.?

# Check 0x0638 (jumped to from 0x02B0) - this is important
disasm_range(0x0638, 0x0720, '0x0638-0x0720 (game loop body)')

# Also 0x081C (called from 0x0282)
disasm_range(0x081C, 0x0880, '0x081C-0x087F')

# Show the 0x1294 function (called from 0x023C - "display thinking" ?)
disasm_range(0x1294, 0x12C0, '0x1294-0x12BF')
