"""Disassemble 0x5538 (first call from AI), 0x0066, 0x1CA0, 0x7C34, 0x7C5A."""
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

# 0x5538 - first call from AI entry
disasm_range(0x5538, 0x5580, '0x5538 (first call in AI)')

# 0x0066 - second call in AI entry
disasm_range(0x0066, 0x0096, '0x0066 (second call in AI)')

# Check what's right before 0x0096 (where the caller code is)
# 0x0088-0x0096 should be the caller setup
disasm_range(0x0085, 0x0096, '0x0085-0x0095 (caller of 0x0096)')

# What the game loop context looks like when inside - what function
# contains 0x01EA-0x0274? Let's find its entry (look for LINK before 0x013E)
# Try from 0x00FA and work upward
for start in range(0x00B0, 0x013F, 2):
    chunk = code_bytes[start:start+4]
    if chunk[:2] == b'\x4e\x55':  # LINK instruction
        print(f'\nFound LINK at 0x{start:04X}')

# Also search for LINK near our loop
for start in [0x00C8, 0x00E0, 0x0100, 0x0108, 0x00F5, 0x00F8]:
    chunk = code_bytes[start:start+2]
    print(f'At 0x{start:04X}: {chunk.hex()}')

# Let's also show what happens at the very start of 0x0060
disasm_range(0x0060, 0x00C0, '0x0060-0x00BF (before hot loop)')
