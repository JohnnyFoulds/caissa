"""
Disassemble the post-search code in AI_INIT (0x8230) to find where best move is stored.
Also disassemble the iterative deepening loop at 0xC198 to find best-move write address.
"""
import struct, sys
from pathlib import Path

rom_path = Path(__file__).parent.parent.parent / 'Resources/Retro/BattleChess.amiga'
rom_data = rom_path.read_bytes()

# Parse hunk header
pos = 0
def r32():
    global pos
    v = struct.unpack('>I', rom_data[pos:pos+4])[0]
    pos += 4
    return v

magic = r32()
assert magic == 0x3F3, f'Not HUNK_HEADER: {magic:08X}'
r32()  # table size
num_hunks = r32(); r32(); r32()  # first_hunk, last_hunk
sizes = [r32() & 0x3FFFFFFF for _ in range(num_hunks)]
hunk_type = r32()
assert hunk_type == 0x3E9, f'Expected HUNK_CODE: 0x{hunk_type:08X}'
hunk0_longs = r32()
hunk0_bytes = hunk0_longs * 4
hunk0_offset = pos
hunk0_data = rom_data[pos:pos+hunk0_bytes]
print(f'Hunk0: {hunk0_bytes} bytes at file offset 0x{hunk0_offset:X}')

try:
    from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
    md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)

    def disasm(start, end, label=''):
        code = hunk0_data[start:end]
        if label:
            print(f'\n=== {label} ===')
        print(f'Range: 0x{start:04X}..0x{end:04X}')
        for insn in md.disasm(code, start):
            print(f'  {insn.address:04X}  {insn.mnemonic:<12} {insn.op_str}')

    # 0xD970: instruction context — write #88301 (D3=0xE5E7 → [0x3662], A0=PT, D0=0x340)
    disasm(0xD960, 0xDA00, '0xD970 context: write D3=0xE5E7 to PT[0x68*8+0]')

    # 0xD3F0: write #88302 (word 0x0001 → [0x3666]) + 0xD41A (byte → [0x3668]) + 0xD44C (word 0x0000 → [0x3666])
    disasm(0xD3D0, 0xD490, '0xD3FE/0xD41A/0xD44C context: write PT[0x68*8+4..6]')

    # 0xDB00: earlier write of 0x0067 to [0x3665] (from write #7, PC=0xDB0C)
    disasm(0xDAF0, 0xDB50, '0xDB0C context: write 0x0067 to PT[0x68*8+3]')

    # Also the piece-table init/writer region to understand the format
    disasm(0xD700, 0xD900, '0xD700 piece-table writer region (find format)')

    # 0x9AE2 — called from 9CC2 with (move_entry[0..1], 0) — the core piece-mover
    disasm(0x9AE2, 0x9B20, '0x9AE2 move-piece (arg0=move_entry[0..1], arg1=0)')

    # ROM bytes at 0x3662..0x3669 (move entry before search)
    entry = hunk0_data[0x3662:0x366A]
    print(f'\nROM bytes at [0x3662..0x3669]: {entry.hex()}')
    print(f'Expected after search: E5 E7 00 67 00 00 05 00')

except ImportError:
    print('capstone not installed; hex dump only')
    for start, end, label in [
        (0x825E, 0x82E8, 'post-search'),
        (0xC198, 0xC310, 'search-loop'),
        (0xC41C, 0xC540, 'alpha-beta'),
    ]:
        print(f'\n=== {label} (0x{start:04X}..0x{end:04X}) ===')
        for i in range(start, end, 16):
            chunk = hunk0_data[i:i+16]
            print(f'  {i:04X}: {" ".join(f"{b:02x}" for b in chunk)}')
