#!/usr/bin/env python3
"""
Trace what addresses the AI search reads from the board area.

Run from AI_OUTER_DRIVER_ADDR (0x81DC) with:
  1. Board at 0x030F4 zeroed (current state — no position loaded)
  2. Board at 0x030F4 filled with a candidate starting position

This tells us:
  - Whether the search reads from 0x030F4 at all
  - Which byte offsets within each 4-byte square entry it reads
  - What [0x012C2]/[0x012C4] contains after the run
"""
import sys, struct
sys.path.insert(0, "bin")
import unicorn
import unicorn.m68k_const as m68k
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk

rom_data = open(default_rom_path(), "rb").read()
regions = parse_amiga_hunk(rom_data)

A4 = 0x7FFE
CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000

BOARD_ADDR = 0x030F4   # A4 - 0x4F0A
BOARD_SIZE = 64 * 4
PIECE_TABLE_ADDR = 0x0892
PIECE_ENTRY_SIZE = 32
NUM_PIECE_ENTRIES = 32
AI_OUTER_DRIVER_ADDR = 0x81DC
EXEC_BASE = 0x800000; LIB_RANGE = 0x040000
ALLOC_POOL = 0x200000
ALLOC_POOL_SIZE = 0x100000

# Candidate starting position in 4-byte board format:
# We try two hypotheses for piece_type encoding:
# H1: piece_type in byte[0], 0=empty; pieces: pawn=1,knight=2,bishop=3,rook=4,queen=5,king=6
# H2: piece_type in byte[0] with different values
# Color encoding:
# C1: byte[2]=color (0=white,1=black)
# C2: byte[2]=0 for white, byte[2]=1 for black

def build_starting_board_h1():
    """Hypothesis: byte[0]=piece_type(1-6,0=empty), byte[1]=piece_idx(0-31), byte[2]=color(0=W,1=B), byte[3]=0."""
    board = bytearray(64 * 4)
    # piece_idx: white pieces 0-15, black pieces 16-31
    pieces = [
        # White back rank (rank 1 = squares 0-7)
        (0, 4, 0, 0), (1, 2, 0, 1), (2, 3, 0, 2), (3, 5, 0, 3),
        (4, 6, 0, 4), (5, 3, 0, 5), (6, 2, 0, 6), (7, 4, 0, 7),
        # White pawns (rank 2 = squares 8-15)
        (8, 1, 0, 8), (9, 1, 0, 9), (10, 1, 0, 10), (11, 1, 0, 11),
        (12, 1, 0, 12), (13, 1, 0, 13), (14, 1, 0, 14), (15, 1, 0, 15),
        # Black pawns (rank 7 = squares 48-55)
        (48, 1, 1, 16), (49, 1, 1, 17), (50, 1, 1, 18), (51, 1, 1, 19),
        (52, 1, 1, 20), (53, 1, 1, 21), (54, 1, 1, 22), (55, 1, 1, 23),
        # Black back rank (rank 8 = squares 56-63)
        (56, 4, 1, 24), (57, 2, 1, 25), (58, 3, 1, 26), (59, 5, 1, 27),
        (60, 6, 1, 28), (61, 3, 1, 29), (62, 2, 1, 30), (63, 4, 1, 31),
    ]
    for sq, piece_type, color, piece_idx in pieces:
        board[sq*4 + 0] = piece_type
        board[sq*4 + 1] = piece_idx
        board[sq*4 + 2] = color
        board[sq*4 + 3] = 0
    return bytes(board)


def setup_unicorn(board_data):
    """Set up a Unicorn instance with the given board data at 0x030F4."""
    uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(unicorn.m68k_const.UC_CPU_M68K_M68000)

    # Maps
    uc.mem_map(CHIP_RAM_BASE, CHIP_RAM_SIZE)
    for r in regions:
        if r.size > 0:
            uc.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
    uc.mem_map(ALLOC_POOL, ALLOC_POOL_SIZE)
    uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
    uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)
    uc.mem_map(0xFFFF0000, 0x10000)

    uc.reg_write(m68k.UC_M68K_REG_A4, A4)

    # Patches from trace_step.py (known-working setup)
    for addr in (0x025C, 0x025D, 0x024F, 0x024E):
        uc.mem_write(addr, b"\x00")
    uc.mem_write(0x1152, b"\x00\x00\x00\x00")
    uc.mem_write(0x6FFF, b"\x00" * (A4 - 0x6FFF))
    uc.mem_write(0x36B0, b"\x4e\x73")  # RTE at F-line handler

    # Write board data
    uc.mem_write(BOARD_ADDR, board_data)

    # Set computer colors (white=computer)
    PLAYER_TYPE_BASE = 0x07D4
    uc.mem_write(PLAYER_TYPE_BASE + 0, struct.pack(">H", 2))  # White=Computer
    uc.mem_write(PLAYER_TYPE_BASE + 2, struct.pack(">H", 1))  # Black=Human
    # Set [0x0331C] (PLAYER2_COLOR_ADDR): which side is player 2
    uc.mem_write(0x0331C, struct.pack(">H", 1))  # Player2=Black

    # AllocMem bump
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


def run_test(label, board_data, limit=2_000_000):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")

    uc = setup_unicorn(board_data)

    # Track reads from board area
    board_reads = {}  # {(sq, offset): count}
    # Track writes to [0x012C2] and [0x012C4]
    result_writes = []

    def read_hook(emu, access, address, size, value, _):
        if BOARD_ADDR <= address < BOARD_ADDR + BOARD_SIZE:
            sq = (address - BOARD_ADDR) // 4
            off = (address - BOARD_ADDR) % 4
            key = (sq, off)
            board_reads[key] = board_reads.get(key, 0) + 1

    def write_hook(emu, access, address, size, value, _):
        if address in (0x012C2, 0x012C4):
            pc = emu.reg_read(m68k.UC_M68K_REG_PC)
            result_writes.append((address, size, value, pc))

    uc.hook_add(UC_HOOK_MEM_READ, read_hook)
    uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)

    try:
        uc.emu_start(AI_OUTER_DRIVER_ADDR, SENTINEL, count=limit)
        final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
        print(f"  Done, PC=0x{final_pc:05X}")
    except Exception as e:
        final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
        print(f"  Error: {e}, PC=0x{final_pc:05X}")

    # Read [0x012C2] and [0x012C4]
    from_sq = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
    to_sq = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
    print(f"\n  [0x012C2] FROM = 0x{from_sq:04X} ({from_sq})")
    print(f"  [0x012C4] TO   = 0x{to_sq:04X} ({to_sq})")

    if from_sq != 0x00FF and to_sq != 0x00FF:
        print(f"  *** VALID MOVE FOUND! ***")
        rank_f = from_sq // 8; file_f = from_sq % 8
        rank_t = to_sq // 8;   file_t = to_sq % 8
        uci = f"{chr(ord('a')+file_f)}{rank_f+1}{chr(ord('a')+file_t)}{rank_t+1}"
        print(f"  UCI: {uci}")
    elif from_sq == 0x00FF and to_sq == 0x00FF:
        print(f"  Search returned: no move (0x00FF sentinel)")
    else:
        print(f"  Mixed sentinel state")

    if result_writes:
        print(f"\n  Writes to result area: {len(result_writes)}")
        for (addr, sz, val, pc) in result_writes[:10]:
            print(f"    [0x{addr:05X}] ← 0x{val:04X} from PC=0x{pc:05X}")
    else:
        print(f"  No writes to [0x012C2]/[0x012C4]")

    # Summarize board reads
    if board_reads:
        print(f"\n  Board reads: {len(board_reads)} unique (sq,offset) pairs")
        # Show per-byte-offset stats
        per_offset = {}
        for (sq, off), count in board_reads.items():
            per_offset[off] = per_offset.get(off, 0) + count
        for off in sorted(per_offset):
            print(f"    offset +{off}: {per_offset[off]} reads total")
        # Show which squares were read
        squares_read = sorted(set(sq for (sq, off) in board_reads))
        print(f"    Squares accessed: {squares_read}")
    else:
        print(f"  NO BOARD READS at all")


# Test 1: Empty board (current Bridge behavior — writes to 0x3322 not 0x030F4)
empty_board = b"\x00" * (64 * 4)
run_test("Empty board (current Bug: 0x030F4 = all zeros)", empty_board, limit=500_000)

# Test 2: Starting position with H1 format
h1_board = build_starting_board_h1()
run_test("Starting position H1 (byte0=type 1-6, byte1=idx, byte2=color)", h1_board, limit=2_000_000)
