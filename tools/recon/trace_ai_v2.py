#!/usr/bin/env python3
"""
Trace AI with properly set up board, king table, and piece entries.
Key fixes vs trace_full_ai.py:
1. Write board at 0x030F4 (4 bytes/sq, 128 sq 0x88 format, byte[0]=type, byte[1]=color)
2. Set [0x032D4+color*32] = king square + 1 (adjusted for 0x09FC4's lookup)
3. Zero [0x007A2] (position adjustment table)
4. Set [0x04ADE] = 0 (use first piece entry)
5. Write valid piece entry at 0x0892
6. Set [0x01152] = 0x0892 (linked list head)
"""
import sys, struct
sys.path.insert(0, "bin")
import unicorn, unicorn.m68k_const as m68k
from unicorn import UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UC_HOOK_MEM_WRITE

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk

rom_data = open(default_rom_path(), "rb").read()
regions = parse_amiga_hunk(rom_data)
A4 = 0x7FFE
CHIP, CHIPSIZE = 0, 0x200000
STACK_TOP, SENTINEL = 0x1F0000, 0xFFFF0000
EXEC_BASE, LIB_RANGE = 0x800000, 0x040000
ALLOC_POOL = 0x200000

uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(unicorn.m68k_const.UC_CPU_M68K_M68000)
uc.mem_map(CHIP, CHIPSIZE)
for r in regions:
    if r.size > 0:
        uc.mem_write(r.load_address, rom_data[r.offset:r.offset+r.size])
uc.mem_map(ALLOC_POOL, 0x100000)
uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE*2)
uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)
uc.mem_map(SENTINEL, 0x10000)
uc.mem_write(SENTINEL, b"\x4e\x75")
uc.reg_write(m68k.UC_M68K_REG_A4, A4)
uc.mem_write(4, struct.pack(">I", EXEC_BASE))
uc.mem_write(0x36B0, b"\x4e\x73")

# Standard patches
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    uc.mem_write(addr, b"\x00")
uc.mem_write(0x6FFF, b"\x00" * (A4 - 0x6FFF))


def sq88(f, r):
    return r * 16 + f


# ===== BOARD at 0x030F4: 128 entries x 4 bytes, 0x88 format =====
BOARD = bytearray(128 * 4)


def set_sq(sq, piece_type, color):
    BOARD[sq * 4 + 0] = piece_type   # 1=P,2=N,3=B,4=R,5=Q,6=K
    BOARD[sq * 4 + 1] = color        # 0=white,1=black


# Starting position (black to move: AI plays black)
set_sq(sq88(0, 0), 4, 0); set_sq(sq88(1, 0), 2, 0); set_sq(sq88(2, 0), 3, 0)
set_sq(sq88(3, 0), 5, 0); set_sq(sq88(4, 0), 6, 0); set_sq(sq88(5, 0), 3, 0)
set_sq(sq88(6, 0), 2, 0); set_sq(sq88(7, 0), 4, 0)
for f in range(8):
    set_sq(sq88(f, 1), 1, 0)  # white pawns
set_sq(sq88(0, 7), 4, 1); set_sq(sq88(1, 7), 2, 1); set_sq(sq88(2, 7), 3, 1)
set_sq(sq88(3, 7), 5, 1); set_sq(sq88(4, 7), 6, 1); set_sq(sq88(5, 7), 3, 1)
set_sq(sq88(6, 7), 2, 1); set_sq(sq88(7, 7), 4, 1)
for f in range(8):
    set_sq(sq88(f, 6), 1, 1)  # black pawns
uc.mem_write(0x030F4, bytes(BOARD))

# ===== [0x032D4] king position table =====
# computed_value = input - [0x007A2+color*2] - 1
# We zero [0x007A2], so input = king_sq + 1
WHITE_KING_SQ = sq88(4, 0)   # 0x04
BLACK_KING_SQ = sq88(4, 7)   # 0x74
KING_TABLE = bytearray(64)
KING_TABLE[0] = WHITE_KING_SQ + 1   # white king position value
KING_TABLE[32] = BLACK_KING_SQ + 1  # black king position value
uc.mem_write(0x032D4, bytes(KING_TABLE))
uc.mem_write(0x007A2, b"\x00\x00\x00\x00")  # zero adjustment table

# ===== Piece entry at 0x0892 (32 bytes) =====
# Fields found from 0x031C6 / 0x3218 disassembly:
#   [+0] word: square (0x88 format)
#   [+2] word: priority for linked list sorting
#   [+0xA] byte: piece type
#   [+0x14] long: state ptr (0 = not yet started)
#   [+0x1C] long: next in linked list (0 = end)
BLACK_PAWN_SQ = sq88(4, 6)  # e7 = 0x64
pe = bytearray(32)
struct.pack_into(">H", pe, 0, BLACK_PAWN_SQ)    # square
struct.pack_into(">H", pe, 2, 0x0001)           # priority
pe[0xA] = 1                                     # piece type = pawn
struct.pack_into(">I", pe, 0x14, 0)             # no state ptr initially
struct.pack_into(">I", pe, 0x1C, 0)             # end of list
uc.mem_write(0x0892, bytes(pe))

# ===== Linked list head =====
uc.mem_write(0x01152, struct.pack(">I", 0x0892))

# ===== Piece index for search =====
uc.mem_write(0x04ADE, struct.pack(">H", 0))

# ===== Player/color setup =====
uc.mem_write(0x0331E, struct.pack(">H", 1))   # player1 = Black (side to move)
uc.mem_write(0x0331C, struct.pack(">H", 0))   # player2 = White
uc.mem_write(0x07D4, struct.pack(">H", 1))    # player[0] = Human (white)
uc.mem_write(0x07D6, struct.pack(">H", 2))    # player[1] = Computer (black)

# ===== AI phase flag =====
uc.mem_write(0x04A5A, struct.pack(">H", 2))
uc.mem_write(0x012B6, struct.pack(">H", 0))
uc.mem_write(0x04A5C, struct.pack(">H", 0))
uc.mem_write(0x04A5E, struct.pack(">H", 0))

bump = [ALLOC_POOL]
trace_calls = []
call_watch = {
    0x8230: 'phase0',
    0x82DE: 'phase1',
    0x094D8: 'ai_search',
    0x0A062: 'search_core',
    0x09FC4: 'king_detect',
    0x0A028: 'no_king_result',
    0x0A08A: 'after_king_ok',
    0x031C6: 'alpha_beta',
    0x00FC6: 'search_init',
    0x03146: 'list_add',
    0x03102: 'list_remove',
}
crashes = []


def code_hook(emu, addr, size, _):
    if addr == SENTINEL:
        emu.emu_stop()
    if addr in call_watch:
        trace_calls.append((addr, emu.reg_read(m68k.UC_M68K_REG_A7)))
        if len(trace_calls) > 100:
            emu.emu_stop()
    if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
        off = addr - EXEC_BASE
        if off == -0xC6:
            d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
            emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
            bump[0] += max((d0 + 7) & ~7, 8)
        elif off == -0x198:
            emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)


result_writes = []


def write_hook(emu, access, addr, size, val, _):
    if addr in (0x012C2, 0x012C4) or (0x0365A <= addr < 0x0365A + 8):
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        result_writes.append((addr, size, val, pc))


def fault_hook(emu, access, addr, size, val, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    if addr >= 0xFF000000:
        emu.emu_stop(); return False
    if 0x200000 <= addr < ALLOC_POOL and not (EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE):
        crashes.append((pc, addr))
        emu.emu_stop(); return False
    try:
        uc.mem_write(addr & ~3, b"\x00" * 4)
    except Exception:
        emu.emu_stop(); return False
    return True


uc.hook_add(unicorn.UC_HOOK_CODE, code_hook)
uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_hook)
uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, fault_hook)

sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)

print("Running AI from 0x81DC...")
try:
    uc.emu_start(0x081DC, SENTINEL, count=5_000_000)
except Exception as e:
    print(f"Error: {e}")

final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
print(f"Stopped at PC=0x{final_pc:05X}")

if crashes:
    print(f"CRASH: PC=0x{crashes[0][0]:05X} → addr=0x{crashes[0][1]:08X}")

print(f"\nFunction trace ({len(trace_calls)} calls):")
for addr, sp_val in trace_calls[:60]:
    depth = (STACK_TOP - sp_val) // 4
    indent = "  " * min(depth // 4, 8)
    print(f"  {indent}{call_watch[addr]} @ 0x{addr:05X}  (sp=0x{sp_val:05X})")

print(f"\nResult-area writes ({len(result_writes)}):")
for addr, sz, val, pc in result_writes[:20]:
    print(f"  [0x{addr:05X}] ← 0x{val:X} (size={sz}) PC=0x{pc:05X}")

c2 = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
c4 = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
best = bytes(uc.mem_read(0x0365A, 8))
print(f"\n[0x012C2] FROM = 0x{c2:04X}")
print(f"[0x012C4] TO   = 0x{c4:04X}")
print(f"AI_BEST_MOVE @ 0x365A: {best.hex()}")

# Dump relevant runtime state
print(f"\n[0x032D4] (king table): {bytes(uc.mem_read(0x032D4,4)).hex()}")
print(f"[0x007A2] (adj table): {bytes(uc.mem_read(0x007A2,4)).hex()}")
print(f"[0x01152] (list head): {struct.unpack('>I',bytes(uc.mem_read(0x01152,4)))[0]:#010x}")
print(f"[0x04ADE] (piece idx): {struct.unpack('>H',bytes(uc.mem_read(0x04ADE,2)))[0]}")
