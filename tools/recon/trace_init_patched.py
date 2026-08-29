#!/usr/bin/env python3
"""
Run 0x0183E with progressive patching to capture the board state at 0x030F4.

Strategy: hook crashes, patch problematic calls to NOP/RTS, and proceed until
0x0183E completes or the board area gets written.
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
code_region = rom_data[regions[0].offset:regions[0].offset + regions[0].size]

A4 = 0x7FFE
CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000

BOARD_ADDR = 0x030F4
BOARD_SIZE = 64 * 4
PIECE_TABLE_ADDR = 0x0892

EXEC_BASE = 0x800000; LIB_RANGE = 0x040000
ALLOC_POOL = 0x200000; ALLOC_POOL_SIZE = 0x100000

# --- Setup ---
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

# Standard patches from trace_step.py
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    uc.mem_write(addr, b"\x00")
uc.mem_write(0x6FFF, b"\x00" * (A4 - 0x6FFF))
uc.mem_write(0x36B0, b"\x4e\x73")  # RTE at F-line handler

# Patch 0x000C0 to RTS (skip the A6-dependent calculation)
uc.mem_write(0x000C0, b"\x4e\x75")
print("Patched 0x000C0 → RTS")

# Set [0x04AA4] (initial heap ptr) so 0x0183E can do its pointer arithmetic
HEAP_START = 0x1A0000
uc.mem_write(A4 - 0x355A, struct.pack(">I", HEAP_START))  # [0x04AA4]
uc.mem_write(A4 - 0x3556, struct.pack(">I", HEAP_START))  # [0x04AA8]

# [0x028D6] = large limit so we don't bail early in 0x0774E
uc.mem_write(A4 - 0x5728, struct.pack(">I", 0x0FFFFFFF))

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

board_writes = []

def board_write_hook(emu, access, address, size, value, _):
    if BOARD_ADDR <= address < BOARD_ADDR + BOARD_SIZE:
        sq = (address - BOARD_ADDR) // 4
        off = (address - BOARD_ADDR) % 4
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        board_writes.append((address, sq, off, size, value, pc))

def fault_h(emu, access, address, size, value, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    if address >= 0xFF000000:
        emu.emu_stop(); return False
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

def stop_hook(emu, address, size, _):
    if address == SENTINEL:
        emu.emu_stop()

uc.hook_add(UC_HOOK_CODE, code_stub)
uc.hook_add(UC_HOOK_CODE, stop_hook)
uc.hook_add(UC_HOOK_MEM_READ, mem_stub)
uc.hook_add(UC_HOOK_MEM_WRITE, board_write_hook)
uc.hook_add(UC_HOOK_MEM_INVALID, fault_h)

# Set up stack and call 0x0183E
sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)

# Set up an A6 value that makes `divu.w -(a6), d0` work if 0x000C0 gets called despite the patch
# (if there are other callers). A6 points to a word with some safe value.
A6_DATA = 0x190000  # within chip RAM
uc.mem_write(A6_DATA, struct.pack(">H", 1))  # word = 1 for safe division
uc.reg_write(m68k.UC_M68K_REG_A6, A6_DATA + 2)  # pre-decrement will read A6-2=A6_DATA

print(f"\nCalling 0x0183E (new_game_setup) with patches...")
print(f"  Heap at 0x{HEAP_START:06X}, alloc pool at 0x{ALLOC_POOL:06X}")

try:
    uc.emu_start(0x0183E, SENTINEL, count=5_000_000)
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"  Finished, PC=0x{final_pc:05X}")
except Exception as e:
    final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
    print(f"  Error: {e}, PC=0x{final_pc:05X}")

if exceptions:
    print(f"\n  Exception at PC=0x{exceptions[0][0]:05X}: addr=0x{exceptions[0][1]:08X} ({exceptions[0][2]})")

# Dump board writes
print(f"\n{'='*60}")
print(f"Board writes to 0x030F4: {len(board_writes)}")
if board_writes:
    for (addr, sq, off, size, val, pc) in board_writes[:40]:
        rank = sq // 8; file = sq % 8
        col = chr(ord('a') + file)
        print(f"  sq[{sq:2d}]({col}{rank+1}) +{off}: val=0x{val:X} from PC=0x{pc:05X}")

# Dump board state
board_data = bytes(uc.mem_read(BOARD_ADDR, BOARD_SIZE))
print(f"\nBoard at 0x030F4: {'all zeros' if all(b==0 for b in board_data) else 'HAS DATA'}")
if not all(b == 0 for b in board_data):
    for sq in range(64):
        e = board_data[sq*4:sq*4+4]
        if any(e):
            rank = sq // 8; file = sq % 8
            col = chr(ord('a') + file)
            print(f"  sq{sq:2d}({col}{rank+1}): {e.hex()} = [{e[0]} {e[1]} {e[2]} {e[3]}]")

# Dump piece entries
print(f"\nPiece entries at 0x0892:")
pe = bytes(uc.mem_read(PIECE_TABLE_ADDR, 32*32))
for i in range(32):
    e = pe[i*32:(i+1)*32]
    if any(e):
        w0 = struct.unpack(">H", e[0:2])[0]
        w1 = struct.unpack(">H", e[2:4])[0]
        w2 = struct.unpack(">H", e[4:6])[0]
        b6 = e[6]; b10 = e[10]; b11 = e[11]
        ptr14 = struct.unpack(">I", e[20:24])[0]
        ptr1c = struct.unpack(">I", e[28:32])[0]
        print(f"  entry[{i:2d}]: w0=0x{w0:04X}(sq={w0}) w1=0x{w1:04X} w2=0x{w2:04X} b6={b6} b10={b10} ptr14=0x{ptr14:06X} next=0x{ptr1c:06X}")

# Dump linked list head
ll = struct.unpack(">I", bytes(uc.mem_read(0x01152, 4)))[0]
print(f"\nLinked list head [0x01152] = 0x{ll:08X}")

# Dump 0x04DC2 square table
print(f"\nSquare→piece_idx table at 0x04DC2 (runtime values):")
sq_table = bytes(uc.mem_read(0x04DC2, 64))
for rank in range(8):
    row_vals = []
    for file in range(8):
        sq = rank * 8 + file
        row_vals.append(f"{sq_table[sq]:3d}")
    print(f"  rank{rank+1}: {''.join(row_vals)}")

# Dump 0x04AE0 table (movement descriptors)
print(f"\n0x04AE0 table (first 8 entries × 8 bytes = movement descriptors):")
ae0 = bytes(uc.mem_read(0x04AE0, 12*8))
for i in range(12):
    e = ae0[i*8:(i+1)*8]
    print(f"  [0x{0x04AE0+i*8:05X}]: {e.hex()}")

print(f"\nAlloc pool bump: 0x{bump[0]:06X} (used {bump[0]-ALLOC_POOL} bytes)")
