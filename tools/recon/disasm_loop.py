"""Disassemble the hot loop at 0x013E-0x0280 and the crack init area."""
import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')

from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]  # code hunk starts at offset 40

md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
md.detail = True

def disasm_range(start, end, label=None):
    if label:
        print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        print(f'  {insn.address:04X}  {insn.bytes.hex():16s}  {insn.mnemonic:12s} {insn.op_str}')

# The hot loop area
disasm_range(0x0000, 0x0060, 'Entry + crack header (0x0000-0x0060)')
disasm_range(0x013E, 0x020C, 'Hot loop body (0x013E-0x020C)')
disasm_range(0x0260, 0x0290, 'Hot loop end / after 0x0274 (0x0260-0x0290)')

# Also show what's at 0x110CA - the crack init entry
disasm_range(0x110CA, 0x110F0, 'Crack entry (0x110CA-0x110F0)')
disasm_range(0x11144, 0x111C0, 'Crack main init (0x11144-0x111C0)')
