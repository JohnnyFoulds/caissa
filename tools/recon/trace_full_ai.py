#!/usr/bin/env python3
"""
Trace the FULL AI run (0x81DC) with [0x04A5A]=2 set so phase0+phase1 both execute.

Key fixes vs prior attempts:
1. Set [0x04A5A] = 2 (AI state machine enable flag)
2. Write pieces to 0x3322 (Bridge.py's PIECE_TABLE_ADDR) in 8-byte 0x88 format
3. Set [0x3320] = -1 (PIECE_COUNTER = ready)
4. Set player types: computer plays Black, White is Human
5. Set [0x0331C] = 0 (player2 = White = Human, so AI loop continues)
6. ZERO the board area (0x030F4) to prevent ROM-code garbage from being used as pointers
7. Track what gets written to [0x012C2], [0x012C4], and 0x365A
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
BOARD_SIZE = 64 * 4
PIECE_TABLE_ADDR = 0x3322       # Bridge.py's PIECE_TABLE_ADDR (A4 - 0x4CDC)
PIECE_COUNTER_ADDR = 0x3320     # A4 - 0x4CDE
PIECE_ENTRY_SIZE = 8
MAX_PIECES = 32

AI_OUTER_DRIVER_ADDR = 0x81DC
AI_BEST_MOVE_ADDR = 0x365A      # A4 - 0x49A4
PLAYER_TYPE_BASE = 0x07D4       # A4 - 0x782A
PLAYER1_COLOR_ADDR = 0x331E     # A4 - 0x4CE0
PLAYER2_COLOR_ADDR = 0x331C     # A4 - 0x4CE2

# State machine enable flag
AI_PHASE_FLAG = 0x04A5A         # A4 - 0x35A4

EXEC_BASE = 0x800000; LIB_RANGE = 0x040000
ALLOC_POOL = 0x200000; ALLOC_POOL_SIZE = 0x100000


def sq88(file, rank):
    return rank * 16 + file


def make_entry(sq88_idx, color, piece_type):
    """8-byte piece entry: square(H=2), color(H=2), piece_type(B=1), flags(B=1), reserved(H=2)"""
    return struct.pack(">HHBBH", sq88_idx, color, piece_type, 0, 0)


def build_starting_position():
    """Build starting position piece entries in Bridge.py 0x88 sq format."""
    pieces = []
    # White back rank
    pieces += [(sq88(0, 0), 0, 4), (sq88(1, 0), 0, 2), (sq88(2, 0), 0, 3),
               (sq88(3, 0), 0, 5), (sq88(4, 0), 0, 6), (sq88(5, 0), 0, 3),
               (sq88(6, 0), 0, 2), (sq88(7, 0), 0, 4)]
    # White pawns
    pieces += [(sq88(f, 1), 0, 1) for f in range(8)]
    # Black pawns
    pieces += [(sq88(f, 6), 1, 1) for f in range(8)]
    # Black back rank
    pieces += [(sq88(0, 7), 1, 4), (sq88(1, 7), 1, 2), (sq88(2, 7), 1, 3),
               (sq88(3, 7), 1, 5), (sq88(4, 7), 1, 6), (sq88(5, 7), 1, 3),
               (sq88(6, 7), 1, 2), (sq88(7, 7), 1, 4)]
    return pieces


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
uc.mem_write(SENTINEL, b"\x4e\x75")

uc.reg_write(m68k.UC_M68K_REG_A4, A4)

# Standard patches
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    uc.mem_write(addr, b"\x00")
uc.mem_write(0x6FFF, b"\x00" * (A4 - 0x6FFF))
uc.mem_write(0x36B0, b"\x4e\x73")  # RTE at F-line handler

# === KEY SETUP ===

# 1. Zero the board area (avoid ROM code bytes being used as pointers)
uc.mem_write(BOARD_ADDR, b"\x00" * BOARD_SIZE)

# 2. Zero piece entries area (0x0892)
uc.mem_write(0x0892, b"\x00" * 32 * 32)

# 3. Write pieces to PIECE_TABLE_ADDR (0x3322) in 8-byte Bridge.py format
pieces = build_starting_position()
piece_data = b"\x00" * PIECE_ENTRY_SIZE * MAX_PIECES
piece_data = bytearray(piece_data)
for i, (sq, color, piece_type) in enumerate(pieces):
    entry = make_entry(sq, color, piece_type)
    piece_data[i*PIECE_ENTRY_SIZE:(i+1)*PIECE_ENTRY_SIZE] = entry
uc.mem_write(PIECE_TABLE_ADDR, bytes(piece_data))

# 4. Set PIECE_COUNTER = -1 (ready state)
uc.mem_write(PIECE_COUNTER_ADDR, struct.pack(">h", -1))

# 5. Set player types: Black=Computer(2), White=Human(1)
uc.mem_write(PLAYER_TYPE_BASE + 0, struct.pack(">H", 1))  # White = Human
uc.mem_write(PLAYER_TYPE_BASE + 2, struct.pack(">H", 2))  # Black = Computer

# 6. Computer plays Black (color=1), so side_to_move = 1 (Black's turn)
uc.mem_write(PLAYER1_COLOR_ADDR, struct.pack(">H", 1))  # side to move = Black
uc.mem_write(PLAYER2_COLOR_ADDR, struct.pack(">H", 0))  # other side = White

# 7. Set [0x04A5A] = 2 (enable the AI state machine loop in 0x81DC)
uc.mem_write(AI_PHASE_FLAG, struct.pack(">H", 2))

# 8. Clear AI_BEST_MOVE at 0x365A
uc.mem_write(AI_BEST_MOVE_ADDR, b"\x00" * 8)

# 9. Set [0x012B6] = 0 (clean state for 0x81DC's clear check)
uc.mem_write(0x012B6, struct.pack(">H", 0))

print("Setup:")
print(f"  PIECE_TABLE_ADDR  0x{PIECE_TABLE_ADDR:05X} = {len(pieces)} pieces")
print(f"  PIECE_COUNTER     0x{PIECE_COUNTER_ADDR:05X} = -1")
print(f"  PLAYER_TYPE[0]    0x{PLAYER_TYPE_BASE:05X} = White = Human")
print(f"  PLAYER_TYPE[1]    0x{PLAYER_TYPE_BASE+2:05X} = Black = Computer")
print(f"  PLAYER1_COLOR     0x{PLAYER1_COLOR_ADDR:05X} = {1} (Black to move)")
print(f"  PLAYER2_COLOR     0x{PLAYER2_COLOR_ADDR:05X} = {0} (White)")
print(f"  AI_PHASE_FLAG     0x{AI_PHASE_FLAG:05X} = 2 (loop enable)")
print(f"  AI_BEST_MOVE      0x{AI_BEST_MOVE_ADDR:05X} = cleared")

bump = [ALLOC_POOL]
exceptions = []

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
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    if address >= 0x200000 and not (EXEC_BASE - LIB_RANGE <= address < EXEC_BASE + LIB_RANGE):
        exceptions.append((pc, address, 'UNMAPPED'))
        emu.emu_stop(); return False
    aligned = address & ~3
    try:
        emu.mem_write(aligned, b"\x00" * 4)
    except:
        exceptions.append((pc, address, 'WRITE_FAIL'))
        emu.emu_stop()
        return False
    return True

result_writes = []
def write_hook(emu, access, address, size, value, _):
    if address in (0x012C2, 0x012C4, AI_BEST_MOVE_ADDR, 0x012BA, 0x012BC) or \
       (AI_BEST_MOVE_ADDR <= address < AI_BEST_MOVE_ADDR + 8):
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        result_writes.append((address, size, value, pc))

phase_calls = []
def stop_hook(emu, address, size, _):
    if address == SENTINEL:
        emu.emu_stop()
    elif address == 0x8230:
        phase_calls.append((0, 'phase0_init'))
    elif address == 0x82DE:
        phase_calls.append((1, 'phase1_search'))
    elif address == 0x84C4:
        phase_calls.append((2, 'phase2_noop'))
    elif address == 0x7CCE:
        phase_calls.append((-1, '0x7CCE_board_setup'))

uc.hook_add(UC_HOOK_CODE, code_stub)
uc.hook_add(UC_HOOK_CODE, stop_hook)
uc.hook_add(UC_HOOK_MEM_READ, mem_stub)
uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)
uc.hook_add(UC_HOOK_MEM_INVALID, fault_h)

sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)

print(f"\nStarting emulation from 0x{AI_OUTER_DRIVER_ADDR:05X} (AI_OUTER_DRIVER)...")
try:
    uc.emu_start(AI_OUTER_DRIVER_ADDR, SENTINEL, count=10_000_000)
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"  Finished clean, PC=0x{final_pc:05X}")
except Exception as e:
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"  Error: {e}, PC=0x{final_pc:05X}")

if exceptions:
    for (epc, eaddr, kind) in exceptions[:3]:
        print(f"  {kind} at PC=0x{epc:05X}: addr=0x{eaddr:08X}")

print(f"\nPhase calls: {phase_calls[:10]}")

# Read result
from_sq = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
to_sq   = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
print(f"\n[0x012C2] FROM-square = 0x{from_sq:04X} ({from_sq})")
print(f"[0x012C4] TO-square   = 0x{to_sq:04X} ({to_sq})")

if from_sq != 0x00FF and to_sq != 0x00FF and from_sq < 0x80 and to_sq < 0x80:
    # 0x88 sq: rank = sq >> 4, file = sq & 0xF
    rank_f = from_sq >> 4; file_f = from_sq & 0xF
    rank_t = to_sq >> 4;   file_t = to_sq & 0xF
    uci88 = f"{chr(ord('a')+file_f)}{rank_f+1}{chr(ord('a')+file_t)}{rank_t+1}"
    # rank*8+file format
    rank_f2 = from_sq >> 3; file_f2 = from_sq & 7
    rank_t2 = to_sq >> 3;   file_t2 = to_sq & 7
    uci_linear = f"{chr(ord('a')+file_f2)}{rank_f2+1}{chr(ord('a')+file_t2)}{rank_t2+1}"
    print(f"  As 0x88:     {uci88}")
    print(f"  As rank*8+f: {uci_linear}")
elif from_sq == 0x00FF:
    print("  No move (0x00FF sentinel)")
else:
    print(f"  Unknown format: from={from_sq:#x}, to={to_sq:#x}")

# Read AI_BEST_MOVE
best = bytes(uc.mem_read(AI_BEST_MOVE_ADDR, 8))
print(f"\nAI_BEST_MOVE @ 0x{AI_BEST_MOVE_ADDR:05X}: {best.hex()}")

if result_writes:
    print(f"\nResult-area writes ({len(result_writes)} total):")
    for (addr, sz, val, pc) in result_writes[:20]:
        print(f"  [0x{addr:05X}] ← 0x{val:X} (size={sz}) from PC=0x{pc:05X}")

# Dump piece table at 0x3322 to check if 0x7CCE modified it
print(f"\nPiece table at 0x3322 (first 4 entries after run):")
for i in range(4):
    e = bytes(uc.mem_read(PIECE_TABLE_ADDR + i*8, 8))
    print(f"  entry[{i}]: {e.hex()}")

# Dump piece entries at 0x0892 (first 4)
print(f"\nPiece entries at 0x0892 (first 4 entries after run):")
for i in range(4):
    e = bytes(uc.mem_read(0x0892 + i*32, 32))
    if any(e):
        w0 = struct.unpack(">H", e[0:2])[0]
        w1 = struct.unpack(">H", e[2:4])[0]
        ptr14 = struct.unpack(">I", e[20:24])[0]
        ptr1c = struct.unpack(">I", e[28:32])[0]
        print(f"  entry[{i}]: w0=0x{w0:04X}(sq) w1=0x{w1:04X} ptr14=0x{ptr14:06X} next=0x{ptr1c:06X}")
    else:
        print(f"  entry[{i}]: all zeros")

# Check linked list head
ll = struct.unpack(">I", bytes(uc.mem_read(0x01152, 4)))[0]
print(f"\nLinked list head [0x01152] = 0x{ll:08X}")
print(f"[0x04A5A] = 0x{struct.unpack('>H', bytes(uc.mem_read(0x04A5A, 2)))[0]:04X}")
print(f"[0x04A5C] = 0x{struct.unpack('>H', bytes(uc.mem_read(0x04A5C, 2)))[0]:04X}")
print(f"Alloc bump: 0x{bump[0]:06X} (used {bump[0]-ALLOC_POOL} bytes)")
