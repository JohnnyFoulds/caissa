"""Disassemble full crack init from 0x110EE to 0x11200, and find the game entry."""
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

# Full crack init
disasm_range(0x110EE, 0x11200, 'Crack init (0x110EE-0x11200)')

# Also disassemble 0x11144 - 0x112A0 to see full init sequence
disasm_range(0x11144, 0x11300, 'Post-init setup (0x11144-0x11300)')

# And 0x0060 entry — first instruction context
disasm_range(0x0000, 0x0010, 'Game start 0x0000 (entry JMP)')
