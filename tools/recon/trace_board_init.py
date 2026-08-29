#!/usr/bin/env python3
"""
Trace the game's board initialization to discover the exact 4-byte board format at 0x030F4.

Calls 0x0183E (new_game_setup) under Unicorn, hooks all writes to 0x030F4..0x031F3,
then dumps the resulting board state.  Also dumps a few piece entries from 0x0892.
"""
import sys, struct
sys.path.insert(0, "bin")
import unicorn
import unicorn.m68k_const as m68k
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk

rom_data = open(default_rom_path(), "rb").read()
regions = parse_amiga_hunk(rom_data)

A4 = 0x7FFE
CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000

BOARD_ADDR = A4 - 0x4F0A   # 0x030F4
BOARD_SIZE = 64 * 4         # 256 bytes
PIECE_TABLE_ADDR = 0x0892
PIECE_ENTRY_SIZE = 32
NUM_PIECE_ENTRIES = 32

# Function addresses
NEW_GAME_SETUP = 0x0183E

uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(unicorn.m68k_const.UC_CPU_M68K_M68000)

# Chip RAM
uc.mem_map(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0:
        uc.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])

# Exec library stub (all RTS) + AllocMem/FindName stubs
EXEC_BASE = 0x800000
LIB_RANGE = 0x040000
uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)

# Sentinel page
uc.mem_map(0xFFFF0000, 0x10000)
uc.mem_write(SENTINEL, b"\x4e\x75")  # RTS at sentinel

uc.reg_write(m68k.UC_M68K_REG_A4, A4)

bump = [0x200000]  # AllocMem bump pointer (in the mapped alloc pool region above chip RAM)
# Actually alloc pool is NOT mapped yet — map a simple pool
ALLOC_BASE = 0x1A0000
uc.mem_write(ALLOC_BASE, b"\x00" * (CHIP_RAM_SIZE - ALLOC_BASE))

def code_stub(emu, addr, size, _):
    if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
        offset = addr - EXEC_BASE
        if offset == -0xC6:  # AllocMem
            d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
            aligned = (d0 + 7) & ~7
            result = bump[0]
            bump[0] += max(aligned, 8)
            emu.reg_write(m68k.UC_M68K_REG_D0, result)
        elif offset == -0x198:  # FindName
            emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)

uc.hook_add(UC_HOOK_CODE, code_stub)

def mem_read_stub(emu, access, address, size, value, _):
    if address == 0x4:  # AbsExecBase
        emu.mem_write(0x4, EXEC_BASE.to_bytes(4, "big"))

uc.hook_add(UC_HOOK_MEM_READ, mem_read_stub)

def fault_h(emu, access, address, size, value, _):
    import unicorn.unicorn_const as uc_const
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    if address >= 0xFF000000:
        print(f"  [FAULT] PC=0x{pc:05X} addr=0x{address:08X} — hit sentinel, stopping")
        emu.emu_stop(); return False
    if 0x200000 <= address < 0x7C0000:
        print(f"  [FAULT] PC=0x{pc:05X} addr=0x{address:08X} size={size} — unmapped mid-RAM")
        emu.emu_stop(); return False
    return True

uc.hook_add(UC_HOOK_MEM_INVALID, fault_h)

# Track writes to board area
board_writes = []

def board_write_hook(emu, access, address, size, value, _):
    if BOARD_ADDR <= address < BOARD_ADDR + BOARD_SIZE:
        sq = (address - BOARD_ADDR) // 4
        off = (address - BOARD_ADDR) % 4
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        board_writes.append((address, sq, off, size, value, pc))

uc.hook_add(UC_HOOK_MEM_WRITE, board_write_hook)

# Also track writes to 0x0892 (piece entry table)
piece_writes = []

def piece_write_hook(emu, access, address, size, value, _):
    end = PIECE_TABLE_ADDR + NUM_PIECE_ENTRIES * PIECE_ENTRY_SIZE
    if PIECE_TABLE_ADDR <= address < end:
        entry = (address - PIECE_TABLE_ADDR) // PIECE_ENTRY_SIZE
        off = (address - PIECE_TABLE_ADDR) % PIECE_ENTRY_SIZE
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        piece_writes.append((address, entry, off, size, value, pc))

# (We'll use the same generic hook)

# Stop hook: stop when 0x0183E returns (we pushed SENTINEL as return addr)
def stop_hook(emu, address, size, _):
    if address == SENTINEL:
        emu.emu_stop()

uc.hook_add(UC_HOOK_CODE, stop_hook)

# Set up stack: push sentinel as return address, then call 0x0183E
sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)

# Zero the board area before the call so we can see what gets written
uc.mem_write(BOARD_ADDR, b"\x00" * BOARD_SIZE)
uc.mem_write(PIECE_TABLE_ADDR, b"\x00" * NUM_PIECE_ENTRIES * PIECE_ENTRY_SIZE)

# Initialize [0x04AA4] which 0x0183E copies to [0x04AA8] then uses as a heap ptr
# 0x04AA4 = A4 - 0x355A
# Set it to ALLOC_BASE
uc.mem_write(0x04AA4, struct.pack(">I", ALLOC_BASE))

# Initialize [0x028D6] = -$5728(a4): used in 0x0774E as a limit value
# Set to large number so we don't bail out early
uc.mem_write(0x028D6, struct.pack(">I", 0x0FFFFFFF))

print(f"Calling 0x{NEW_GAME_SETUP:05X} (new_game_setup)...")

try:
    uc.emu_start(NEW_GAME_SETUP, SENTINEL, count=5_000_000)
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"Finished, PC=0x{final_pc:05X}")
except Exception as e:
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"Error: {e}, PC=0x{final_pc:05X}")

# Dump board writes
print(f"\n{'='*60}")
print(f"Writes to board area (0x{BOARD_ADDR:05X}): {len(board_writes)}")
if board_writes:
    for (addr, sq, off, size, val, pc) in board_writes[:80]:
        rank = sq // 8
        file = sq % 8
        col = chr(ord('a') + file)
        print(f"  PC=0x{pc:05X} sq[{sq:2d}] ({col}{rank+1}) +{off}: size={size} val=0x{val:X}")

# Dump final board state
print(f"\n{'='*60}")
print(f"Board state at 0x{BOARD_ADDR:05X} after new_game_setup:")
board_data = bytes(uc.mem_read(BOARD_ADDR, BOARD_SIZE))

if all(b == 0 for b in board_data):
    print("  All zeros — board was NOT initialized by this function path")
else:
    PIECE_NAMES = ['?', 'pawn', 'knight', 'bishop', 'rook', 'queen', 'king']
    for sq in range(64):
        entry = board_data[sq*4 : sq*4+4]
        if any(entry):
            rank = sq // 8
            file = sq % 8
            col = chr(ord('a') + file)
            b0, b1, b2, b3 = entry
            piece_name = PIECE_NAMES[b0] if 0 <= b0 < len(PIECE_NAMES) else f'type={b0}'
            color = 'White' if b2 == 0 and b3 == 0 else f'c={b2:02x}{b3:02x}'
            print(f"  sq{sq:2d} ({col}{rank+1}): {entry.hex()}  b0={b0} b1={b1} b2={b2} b3={b3}  [{piece_name}?]")

# Dump piece entries at 0x0892
print(f"\n{'='*60}")
print(f"Piece entries at 0x{PIECE_TABLE_ADDR:05X} after new_game_setup:")
pe_data = bytes(uc.mem_read(PIECE_TABLE_ADDR, NUM_PIECE_ENTRIES * PIECE_ENTRY_SIZE))
for i in range(NUM_PIECE_ENTRIES):
    e = pe_data[i*PIECE_ENTRY_SIZE : (i+1)*PIECE_ENTRY_SIZE]
    if any(e):
        w0 = int.from_bytes(e[0:2], 'big')
        w1 = int.from_bytes(e[2:4], 'big')
        b10 = e[10] if len(e) > 10 else 0
        l14 = int.from_bytes(e[20:24], 'big') if len(e) >= 24 else 0
        l1c = int.from_bytes(e[28:32], 'big') if len(e) >= 32 else 0
        print(f"  entry[{i:2d}]: {e[:8].hex()}  w0=0x{w0:04X} w1=0x{w1:04X} b10=0x{b10:02X} l14=0x{l14:08X} l1c=0x{l1c:08X}")

# Dump [0x01152] (linked list head)
ll_head = struct.unpack(">I", bytes(uc.mem_read(0x01152, 4)))[0]
print(f"\nLinked list head [0x01152] = 0x{ll_head:08X}")
print(f"  (A4 - offset = 0x{ll_head:08X}, expected ~A4-0x6EAC = 0x{A4 - 0x6EAC:05X})")

# Also dump globals that the AI checks
print(f"\nKey globals after new_game_setup:")
for addr, name in [
    (0x0331C, "PLAYER2_COLOR_ADDR -$4ce2"),
    (0x0331E, "PLAYER1_COLOR_ADDR -$4ce0"),
    (0x03320, "PIECE_COUNTER -$4cde"),
    (0x03322, "3322 (game_tree[0])"),
    (A4 - 0x3556, "04AA8 heap_ptr"),
]:
    val_bytes = bytes(uc.mem_read(addr, 4))
    val = struct.unpack(">I", val_bytes)[0]
    print(f"  [0x{addr:05X}] {name}: 0x{val:08X} ({val})")
