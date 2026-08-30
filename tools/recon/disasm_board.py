"""Disassemble AI loop (0x7C5A), board check (0x00E4), and piece table setup."""
import sys, os, struct
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
        a4 = 0x7FFE
        op = insn.op_str
        # Annotate A4-relative addresses
        if '(a4)' in op or '(A4)' in op:
            import re
            def annotate(m):
                s = m.group(1)
                v = int(s, 16)
                if v > 0x7FFF: v = -(0x10000-v)  # sign extend
                ea = (a4 + v) & 0xFFFF
                return f'${s}(a4) [{ea:#06x}]'
            op_ann = re.sub(r'\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        else:
            op_ann = op
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

# The AI main search step
disasm_range(0x7C5A, 0x7CC0, 'AI search step 0x7C5A')

# The board/event check 0x00E4
disasm_range(0x00E4, 0x0130, 'Board/event check 0x00E4')

# The board piece functions around 0x0820
disasm_range(0x0820, 0x0900, 'Piece table check 0x0820')

# Static data at 0x1598 (A4-0x6A66) — is this the board?
print('\n=== ROM bytes at 0x1598 (A4-0x6A66) ===')
data = code_bytes[0x1598:0x1598+128]
print('Hex:', data.hex())
print('As bytes:', list(data[:64]))

# What's at 0x1560 (A4-0x6A9E)?
print('\n=== ROM bytes at 0x1560 (A4-0x6A9E) ===')
data2 = code_bytes[0x1560:0x1560+64]
print('Hex:', data2.hex())
print('As bytes:', list(data2[:64]))

# Check 0x7C34
disasm_range(0x7C34, 0x7C5A, '0x7C34 (called before AI loop)')
