#!/usr/bin/env python3
"""
Find the 32-byte piece entry format at 0x0892 by:
1. Tracing reads from the 0x0892 area during the AI search
2. Testing a candidate format with [0x01152] pointing to the list head

The search uses a linked list: head at [0x01152], next ptr at piece_entry[+0x1C].
"""
import sys, struct
sys.path.insert(0, "bin")
import unicorn
import unicorn.m68k_const as m68k
from unicorn import UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk

rom_data = open(default_rom_path(), "rb").read()
regions = parse_amiga_hunk(rom_data)

A4 = 0x7FFE
CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000

BOARD_ADDR = 0x030F4
PIECE_TABLE_ADDR = 0x0892
PIECE_ENTRY_SIZE = 32
NUM_PIECE_ENTRIES = 32
AI_OUTER_DRIVER_ADDR = 0x81DC
EXEC_BASE = 0x800000; LIB_RANGE = 0x040000
ALLOC_POOL = 0x200000; ALLOC_POOL_SIZE = 0x100000

# Linked list head
LL_HEAD_ADDR = 0x01152

# From context: piece entry fields:
#   [+0x00] word: ?
#   [+0x02] word: ?
#   [+0x0A] byte: ?
#   [+0x14] long: function pointer (move generator?)
#   [+0x1C] long: next ptr in linked list

# Candidate format for piece entries: let's set up 32 entries
# and link them all.  We'll put minimal data and see what the search reads.
#
# To make it interesting: put ONE piece at e2 (sq=12, White pawn moving to e4)
# We'll set all 32 entries but only the first few are "real".

def build_candidate_piece_entries():
    """Build 32 piece entries with candidate format.

    Strategy: One White pawn at e2 (square 12, file e=4, rank 2=1).
    Square encoding: sq = rank*8 + file = 1*8 + 4 = 12.

    Based on the search reading:
    - [+0x00]: maybe the square in internal format
    - [+0x02]: maybe piece type or color
    - [+0x0A]: maybe a flag (active=0?)
    - [+0x14]: maybe a function pointer for move generation
    - [+0x1C]: next linked-list pointer
    """
    entries = bytearray(NUM_PIECE_ENTRIES * PIECE_ENTRY_SIZE)

    # Starting position pieces:
    # White: pawns a2-h2 (sq 8-15), rooks a1/h1, knights b1/g1, bishops c1/f1, queen d1, king e1
    # Black: pawns a7-h7 (sq 48-55), rooks a8/h8, knights b8/g8, bishops c8/f8, queen d8, king e8

    pieces = [
        # White pieces (color=0): squares 0-7 (rank 1) + 8-15 (rank 2)
        # Rooks a1=sq0, h1=sq7
        # [sq, piece_type, color]
        (0,  4, 0),   # a1 rook white   idx=0
        (1,  2, 0),   # b1 knight white  idx=1
        (2,  3, 0),   # c1 bishop white  idx=2
        (3,  5, 0),   # d1 queen white   idx=3
        (4,  6, 0),   # e1 king white    idx=4
        (5,  3, 0),   # f1 bishop white  idx=5
        (6,  2, 0),   # g1 knight white  idx=6
        (7,  4, 0),   # h1 rook white    idx=7
        (8,  1, 0),   # a2 pawn white    idx=8
        (9,  1, 0),   # b2              idx=9
        (10, 1, 0),   # c2              idx=10
        (11, 1, 0),   # d2              idx=11
        (12, 1, 0),   # e2              idx=12
        (13, 1, 0),   # f2              idx=13
        (14, 1, 0),   # g2              idx=14
        (15, 1, 0),   # h2              idx=15
        # Black pieces
        (48, 1, 1),   # a7 pawn black   idx=16
        (49, 1, 1),   # b7
        (50, 1, 1),   # c7
        (51, 1, 1),   # d7
        (52, 1, 1),   # e7
        (53, 1, 1),   # f7
        (54, 1, 1),   # g7
        (55, 1, 1),   # h7              idx=23
        (56, 4, 1),   # a8 rook black   idx=24
        (57, 2, 1),   # b8 knight black
        (58, 3, 1),   # c8 bishop black
        (59, 5, 1),   # d8 queen black
        (60, 6, 1),   # e8 king black
        (61, 3, 1),   # f8 bishop black
        (62, 2, 1),   # g8 knight black
        (63, 4, 1),   # h8 rook black   idx=31
    ]

    for idx, (sq, piece_type, color) in enumerate(pieces):
        base = idx * PIECE_ENTRY_SIZE
        # [+0x00] word = sq (internal square encoding: rank*8 + file = sq)
        struct.pack_into(">H", entries, base + 0x00, sq)
        # [+0x02] word = piece_type (1-6)
        struct.pack_into(">H", entries, base + 0x02, piece_type)
        # [+0x04] word = color (0=white, 1=black)
        struct.pack_into(">H", entries, base + 0x04, color)
        # [+0x0A] byte = 0 (active flag? not captured)
        entries[base + 0x0A] = 0
        # [+0x14] long = 0 (function pointer — unknown)
        struct.pack_into(">I", entries, base + 0x14, 0)
        # [+0x1C] long = next ptr (link to next entry, or 0 for last)
        if idx < len(pieces) - 1:
            next_addr = PIECE_TABLE_ADDR + (idx + 1) * PIECE_ENTRY_SIZE
            struct.pack_into(">I", entries, base + 0x1C, next_addr)
        else:
            struct.pack_into(">I", entries, base + 0x1C, 0)  # end of list

    return bytes(entries)


def setup_unicorn_with_pieces():
    uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(unicorn.m68k_const.UC_CPU_M68K_M68000)

    uc.mem_map(CHIP_RAM_BASE, CHIP_RAM_SIZE)
    for r in regions:
        if r.size > 0:
            uc.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
    uc.mem_map(ALLOC_POOL, ALLOC_POOL_SIZE)
    uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
    uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)
    uc.mem_map(0xFFFF0000, 0x10000)

    uc.reg_write(m68k.UC_M68K_REG_A4, A4)

    # Known patches from trace_step.py (but NOT zeroing 0x1152 this time)
    for addr in (0x025C, 0x025D, 0x024F, 0x024E):
        uc.mem_write(addr, b"\x00")
    uc.mem_write(0x6FFF, b"\x00" * (A4 - 0x6FFF))
    uc.mem_write(0x36B0, b"\x4e\x73")  # RTE at F-line handler

    # Write piece entries
    piece_entries = build_candidate_piece_entries()
    uc.mem_write(PIECE_TABLE_ADDR, piece_entries)

    # Set linked list head to first entry
    uc.mem_write(LL_HEAD_ADDR, struct.pack(">I", PIECE_TABLE_ADDR))

    # Set computer colors
    PLAYER_TYPE_BASE = 0x07D4
    uc.mem_write(PLAYER_TYPE_BASE + 0, struct.pack(">H", 2))  # White=Computer
    uc.mem_write(PLAYER_TYPE_BASE + 2, struct.pack(">H", 1))  # Black=Human
    uc.mem_write(0x0331C, struct.pack(">H", 1))  # Player2=Black (color to move)

    # Set board too (H1 format matching piece entries above)
    board = bytearray(64 * 4)
    pieces = [
        (0, 4, 0, 0), (1, 2, 0, 1), (2, 3, 0, 2), (3, 5, 0, 3),
        (4, 6, 0, 4), (5, 3, 0, 5), (6, 2, 0, 6), (7, 4, 0, 7),
        (8, 1, 0, 8), (9, 1, 0, 9), (10, 1, 0, 10), (11, 1, 0, 11),
        (12, 1, 0, 12), (13, 1, 0, 13), (14, 1, 0, 14), (15, 1, 0, 15),
        (48, 1, 1, 16), (49, 1, 1, 17), (50, 1, 1, 18), (51, 1, 1, 19),
        (52, 1, 1, 20), (53, 1, 1, 21), (54, 1, 1, 22), (55, 1, 1, 23),
        (56, 4, 1, 24), (57, 2, 1, 25), (58, 3, 1, 26), (59, 5, 1, 27),
        (60, 6, 1, 28), (61, 3, 1, 29), (62, 2, 1, 30), (63, 4, 1, 31),
    ]
    for sq, piece_type, color, idx in pieces:
        board[sq*4 + 0] = piece_type
        board[sq*4 + 1] = idx
        board[sq*4 + 2] = color
        board[sq*4 + 3] = 0
    uc.mem_write(BOARD_ADDR, bytes(board))

    bump = [ALLOC_POOL]
    def code_stub(emu, addr, size, _):
        if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
            offset = addr - EXEC_BASE
            if offset == -0xC6:
                d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
                aligned = (d0 + 7) & ~7
                emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
                bump[0] += max(aligned, 8)
            elif offset == -0x198:
                emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)

    def mem_stub(emu, access, address, size, value, _):
        if address == 0x4:
            emu.mem_write(0x4, EXEC_BASE.to_bytes(4, "big"))

    def fault_h(emu, access, address, size, value, _):
        if address >= 0x200000:
            emu.emu_stop(); return False
        aligned = address & ~3
        try:
            emu.mem_write(aligned, b"\x00" * 4)
        except:
            emu.emu_stop()
            return False
        return True

    uc.hook_add(UC_HOOK_CODE, code_stub)
    uc.hook_add(UC_HOOK_MEM_READ, mem_stub)
    uc.hook_add(UC_HOOK_MEM_INVALID, fault_h)

    sp = STACK_TOP - 4
    uc.mem_write(sp, struct.pack(">I", SENTINEL))
    uc.reg_write(m68k.UC_M68K_REG_A7, sp)

    return uc


# Run trace
uc = setup_unicorn_with_pieces()

# Hook reads from piece table area
PIECE_TABLE_END = PIECE_TABLE_ADDR + NUM_PIECE_ENTRIES * PIECE_ENTRY_SIZE
piece_reads = {}  # {offset_in_entry: count}
crash_pc = [None]
result_writes = []

def read_hook(emu, access, address, size, value, _):
    if PIECE_TABLE_ADDR <= address < PIECE_TABLE_END:
        entry_idx = (address - PIECE_TABLE_ADDR) // PIECE_ENTRY_SIZE
        off = (address - PIECE_TABLE_ADDR) % PIECE_ENTRY_SIZE
        key = (entry_idx, off)
        piece_reads[key] = piece_reads.get(key, 0) + 1

def write_hook(emu, access, address, size, value, _):
    if address in (0x012C2, 0x012C4):
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        result_writes.append((address, size, value, pc))

uc.hook_add(UC_HOOK_MEM_READ, read_hook)
uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)

print(f"Running AI_OUTER_DRIVER (0x{AI_OUTER_DRIVER_ADDR:05X}) with candidate piece list...")
print(f"  Piece list head at [0x{LL_HEAD_ADDR:05X}] = 0x{PIECE_TABLE_ADDR:05X}")

try:
    uc.emu_start(AI_OUTER_DRIVER_ADDR, SENTINEL, count=2_000_000)
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"Done, PC=0x{final_pc:05X}")
except Exception as e:
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"Error: {e}, PC=0x{final_pc:05X}")

from_sq = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
to_sq   = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
print(f"\n[0x012C2] FROM = 0x{from_sq:04X}")
print(f"[0x012C4] TO   = 0x{to_sq:04X}")

if from_sq != 0x00FF and to_sq != 0x00FF:
    rank_f = from_sq // 8; file_f = from_sq % 8
    rank_t = to_sq // 8;   file_t = to_sq % 8
    uci = f"{chr(ord('a')+file_f)}{rank_f+1}{chr(ord('a')+file_t)}{rank_t+1}"
    print(f"*** VALID MOVE: {uci} ***")
else:
    print("No valid move (sentinel)")

# Report piece entry reads
if piece_reads:
    print(f"\nPiece entry reads: {len(piece_reads)} unique (entry, offset) pairs")
    per_offset = {}
    for (entry, off), count in piece_reads.items():
        per_offset[off] = per_offset.get(off, 0) + count
    print("Per-offset totals:")
    for off in sorted(per_offset):
        print(f"  offset +{off:#04x} ({off:3d}): {per_offset[off]} reads")
    entries_read = sorted(set(e for (e, o) in piece_reads))
    print(f"Entries accessed: {entries_read}")
else:
    print("\nNO PIECE TABLE READS — list was not traversed")

if result_writes:
    print(f"\nResult writes: {len(result_writes)}")
    for (addr, sz, val, pc) in result_writes[:10]:
        print(f"  [0x{addr:05X}] ← 0x{val:04X} (PC=0x{pc:05X})")

# Show linked list head after the run
ll_head_val = struct.unpack(">I", bytes(uc.mem_read(LL_HEAD_ADDR, 4)))[0]
print(f"\n[0x{LL_HEAD_ADDR:05X}] linked list head = 0x{ll_head_val:08X}")
