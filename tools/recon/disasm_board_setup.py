"""
Disassemble 0x7C34 (AI init), 0x0138 (move table init), 0x7D96 sub-chain,
0x7E28, 0x6712, and search for board-placement code (writes to BSS 0x30F4).
"""
import sys, os, re, struct
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, 'bin')
from pathlib import Path
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
A4 = 0x7FFE

def ea_a4(sign_neg, hex_str):
    v = int(hex_str, 16)
    return (A4 - v) & 0xFFFF if sign_neg else (A4 + v) & 0xFFFF

def disasm_range(start, end, label=None):
    if label: print(f'\n=== {label} ===')
    chunk = code_bytes[start:end]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        def annotate(m):
            s = m.group(1)=='-'; h = m.group(2)
            return f'{"-" if s else ""}${h}(a4)[0x{ea_a4(s,h):04X}]'
        op_ann = re.sub(r'(-?)\$([0-9a-fA-F]+)\(a4\)', annotate, op)
        print(f'  {insn.address:04X}  {insn.bytes.hex():14s}  {insn.mnemonic:12s} {op_ann}')

disasm_range(0x7C34, 0x7C5A, '0x7C34 AI init (before dispatch loop)')
disasm_range(0x0138, 0x01A0, '0x0138 move table init')
disasm_range(0x7E28, 0x7EB0, '0x7E28 (called from 0x7D96)')
disasm_range(0x6712, 0x6780, '0x6712 (board setup?)')
disasm_range(0x7EBA, 0x7F00, '0x7EBA (called from 0x7D96)')

# Disasm function that has code around 0x0F438 (small values found in ROM)
print('\n=== ROM at 0x0F420-0x0F480 (near small-value pattern) ===')
disasm_range(0x0F420, 0x0F480, 'context around 0x0F438')

# Search for writes to piece list addresses in the entire ROM
print('\n=== Instructions that write to [0x30F4+offset] range ===')
# Look for move.b d0, addr or move.b #val, addr where addr is in BSS piece range
# In 68k: move.b dx, (An) or similar
# Let's disassemble the entire code looking for patterns
TARGET_BASE = 0x30F4
TARGET_END  = 0x30F4 + 0x200  # piece list: 128 squares × 4 bytes = 0x200

for start in range(0, min(len(code_bytes), 0x12000), 2):
    chunk = code_bytes[start:start+8]
    for insn in md.disasm(chunk, start):
        # Look for store instructions with A4-relative address in board range
        op = insn.op_str
        m = re.search(r'(-?)\$([0-9a-fA-F]+)\(a4\)', op)
        if m and insn.mnemonic.startswith('move'):
            s = m.group(1)=='-'; h = m.group(2)
            ea = ea_a4(s, h)
            if TARGET_BASE <= ea < TARGET_END:
                def annotate2(m2):
                    s2=m2.group(1)=='-'; h2=m2.group(2)
                    return f'{"-" if s2 else ""}${h2}(a4)[0x{ea_a4(s2,h2):04X}]'
                print(f'  0x{insn.address:05X}: {insn.mnemonic} {re.sub(r"(-?)\\$([0-9a-fA-F]+)\\(a4\\)", annotate2, op)}')
        break  # one instruction per 2-byte block

# Also look for writes to [0x3318] (piece count) using A4-relative
print('\n=== Instructions writing piece counts [0x3318] or [0x331A] ===')
for start in range(0, min(len(code_bytes), 0x12000), 2):
    chunk = code_bytes[start:start+8]
    for insn in md.disasm(chunk, start):
        op = insn.op_str
        m = re.search(r'(-?)\$([0-9a-fA-F]+)\(a4\)', op)
        if m and insn.mnemonic.startswith('move'):
            s = m.group(1)=='-'; h = m.group(2)
            ea = ea_a4(s, h)
            if ea in (0x3318, 0x331A, 0x3314, 0x3316):
                print(f'  0x{insn.address:05X}: {insn.mnemonic} {op} → [0x{ea:04X}]')
        break
