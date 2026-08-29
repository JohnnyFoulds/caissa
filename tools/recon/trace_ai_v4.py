#!/usr/bin/env python3
"""
trace_ai_v4.py — two-phase: run game startup (0x005A) first to initialize
direction/movement tables, then set up position and call AI (0x081DC).

Root cause of prior crashes: the move generator at 0x0B186 reads direction vectors
from table[0x0782] = A4-0x787C. These are runtime-computed by game startup; before
startup runs they contain ROM code bytes that cause sq arithmetic to jump to 0xC59C.

Fix: emulate 0x005A first (it's a proper function — called via jsr from fn_857E and
0x0C198, so it has an RTS). After startup the direction table has valid values.
We set [0x0015C]=0x00164 (the patched RTS) before startup so any indirect input-wait
calls return immediately instead of jumping through garbage pointers.
"""
import sys, struct, collections
sys.path.insert(0, "bin")
import unicorn, unicorn.m68k_const as m68k

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
        uc.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
uc.mem_map(ALLOC_POOL, 0x100000)
uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)
uc.mem_map(SENTINEL, 0x10000)
uc.mem_write(SENTINEL, b"\x4e\x75")
uc.reg_write(m68k.UC_M68K_REG_A4, A4)
uc.mem_write(4, struct.pack(">I", EXEC_BASE))
uc.mem_write(0x36B0, b"\x4e\x73")   # F-line → RTE

bump = [ALLOC_POOL]
startup_crash = []


def alloc_stub(emu, addr, size, _):
    if addr == SENTINEL:
        emu.emu_stop()
    if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
        off = addr - EXEC_BASE
        if off == -0xC6:
            d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
            emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
            bump[0] += max((d0 + 7) & ~7, 8)
        elif off == -0x198:
            emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)


def startup_fault(emu, access, addr, size, val, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    startup_crash.append((pc, addr))
    emu.emu_stop(); return False


h_code = uc.hook_add(unicorn.UC_HOOK_CODE, alloc_stub)
h_fault = uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, startup_fault)

# ===== PHASE 1: run game startup (0x005A) to initialize direction/movement tables =====
# Patch 0x00164 → RTS early: game startup may call the input handler indirectly.
uc.mem_write(0x00164, b"\x4e\x75")
# [0x0015C] is an indirect pointer to the input handler; before startup it's garbage.
# Set it to 0x00164 (our RTS stub) so fn_8820's jsr (a0) always returns cleanly.
uc.mem_write(0x0015C, b"\x4e\x75")   # jsr -$7ea2(a4) with A4=0x7FFE → 0x015C
uc.mem_write(0x0015A, b"\x4e\x75")   # jsr -$7ea2(a4) with A4=0x7FFC → 0x015A
# Standard OS-ABI patches
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    uc.mem_write(addr, b"\x00")
# FIX: zero [0x1152] (A4-0x6EAC = linked-list head) before startup.
# At startup time [0x1152] has ROM code bytes; fn_0x3102 walks the list and
# chases those bytes as pointers into unmapped memory → crash at 0x3114.
# Setting it to 0 makes fn_0x3102 treat the list as empty and return immediately.
uc.mem_write(0x01152, b"\x00\x00\x00\x00")
# FIX: patch 0x000C2 (first instruction of the infinite game loop) → RTS.
# The original is `jsr $7c5a(pc)` followed by `bra.b $c2`.  Replacing with RTS
# lets startup run all initialization code (jsr calls at 0x006A–0x000BE) and
# then return cleanly instead of looping forever.
uc.mem_write(0x000C2, b"\x4e\x75")

sp0 = STACK_TOP - 4
uc.mem_write(sp0, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp0)
# A6 = ExecBase in Amiga convention; game startup reads library offsets via A6
uc.reg_write(m68k.UC_M68K_REG_A6, EXEC_BASE)

# Add write hook during startup so we can see what tables get initialized
dir_writes = {}
def startup_write(emu, access, addr, size, val, _):
    if 0x0780 <= addr < 0x07C0:
        dir_writes[addr] = (size, val)
h_sw = uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, startup_write)

print("Phase 1: running game startup (0x005A) to init direction/movement tables ...")
try:
    uc.emu_start(0x005A, SENTINEL, count=5_000_000)
except Exception as e:
    print(f"  startup error: {e}")

init_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
uc.hook_del(h_sw)
print(f"  startup done: PC=0x{init_pc:05X}")
if startup_crash:
    print(f"  startup crash: PC=0x{startup_crash[0][0]:05X} addr=0x{startup_crash[0][1]:08X}")
# Show key indirect function pointers set during startup
for label, addr in [
    ("[0x000E4] A4-0x7F1A (phase1 first-call)", 0x000E4),
    ("[0x00036] A4-0x7FC8 (ai_search cb1)", 0x00036),
    ("[0x0003C] A4-0x7FC2 (ai_search cb2)", 0x0003C),
    ("[0x00138] A4-0x7EC6 (fn_07D96 callback)", 0x00138),
    ("[0x04AA8] A4-0x3556 (fn_07922 arg1 buffer)", 0x04AA8),
    ("[0x04AA4] A4-0x355A (alloc result)", 0x04AA4),
]:
    v = struct.unpack(">I", bytes(uc.mem_read(addr, 4)))[0]
    print(f"  {label} = 0x{v:08X}")
if dir_writes:
    print(f"  [0x0780..0x07C0] writes during startup ({len(dir_writes)} addresses):")
    for a in sorted(dir_writes):
        sz, v = dir_writes[a]
        print(f"    [0x{a:05X}] ← 0x{v:04X} (size={sz})")

# Show direction table AFTER startup
print("  Direction table [0x0782..0x07B0] after startup:")
for i in range(12):
    addr = 0x0782 + i * 2
    w = struct.unpack(">h", bytes(uc.mem_read(addr, 2)))[0]
    print(f"    dir[{i:2d}] = {w:+5d} (0x{w & 0xFFFF:04X})")

# Restore [0x1152] = PE_BASE for Phase 2 (we zeroed it for startup to avoid crash).
# DO NOT restore yet — Phase 2 setup below writes PE entries first, then sets this.
uc.hook_del(h_fault)   # remove crash-stopping fault hook for Phase 2

# ===== PHASE 2: set up position and run AI =====

def sq88(f, r):
    return r * 16 + f


def make_pt_entry(sq, color, piece_type):
    return struct.pack(">HHBBH", sq, color, piece_type, 0, 0)


# Piece table [0x03322]: 8 bytes/entry × 105 entries
PT_BASE = 0x03322
PT_SIZE = 8
PT_SLOTS = 105
pt_data = bytearray(PT_SLOTS * PT_SIZE)
pt_pieces = [
    # Game encoding: king=1, rook=2, knight=3, bishop=4, queen=5, pawn=6
    # Black back rank
    (sq88(0, 7), 1, 2), (sq88(1, 7), 1, 3), (sq88(2, 7), 1, 4),
    (sq88(3, 7), 1, 5), (sq88(4, 7), 1, 1), (sq88(5, 7), 1, 4),
    (sq88(6, 7), 1, 3), (sq88(7, 7), 1, 2),
    # Black pawns
    (sq88(0, 6), 1, 6), (sq88(1, 6), 1, 6), (sq88(2, 6), 1, 6),
    (sq88(3, 6), 1, 6), (sq88(4, 6), 1, 6), (sq88(5, 6), 1, 6),
    (sq88(6, 6), 1, 6), (sq88(7, 6), 1, 6),
    # White back rank
    (sq88(0, 0), 0, 2), (sq88(1, 0), 0, 3), (sq88(2, 0), 0, 4),
    (sq88(3, 0), 0, 5), (sq88(4, 0), 0, 1), (sq88(5, 0), 0, 4),
    (sq88(6, 0), 0, 3), (sq88(7, 0), 0, 2),
    # White pawns
    (sq88(0, 1), 0, 6), (sq88(1, 1), 0, 6), (sq88(2, 1), 0, 6),
    (sq88(3, 1), 0, 6), (sq88(4, 1), 0, 6), (sq88(5, 1), 0, 6),
    (sq88(6, 1), 0, 6), (sq88(7, 1), 0, 6),
]
for i, (sq, color, pt) in enumerate(pt_pieces):
    pt_data[i * PT_SIZE:(i + 1) * PT_SIZE] = make_pt_entry(sq, color, pt)
uc.mem_write(PT_BASE, bytes(pt_data))

# Active piece for fn_7CCE: black e7 pawn (game encoding: pawn=6)
uc.mem_write(0x0077A, make_pt_entry(sq88(4, 6), 1, 6))
uc.mem_write(0x03320, struct.pack(">H", 0xFFFF))   # -1 → fn_7CCE self-copies only

# 32-byte piece entries [0x0892]: linked list for the search
uc.mem_write(0x0892, b"\x00" * 32 * 32)
PE_BASE = 0x0892
PE_SIZE = 32
pe_pieces = [(sq, col, pt) for sq, col, pt in pt_pieces if col == 1]
for i, (sq, col, pt) in enumerate(pe_pieces):
    pe = bytearray(PE_SIZE)
    struct.pack_into(">H", pe, 0, sq)
    struct.pack_into(">H", pe, 2, i)
    pe[0x0A] = pt
    next_ptr = (PE_BASE + (i + 1) * PE_SIZE) if i < len(pe_pieces) - 1 else 0
    struct.pack_into(">I", pe, 0x1C, next_ptr)
    uc.mem_write(PE_BASE + i * PE_SIZE, bytes(pe))

# Board [0x030F4]: 128 sq × 4 bytes (byte0=type, byte1=color)
BOARD = bytearray(128 * 4)


def set_sq(sq, piece_type, color):
    BOARD[sq * 4] = piece_type
    BOARD[sq * 4 + 1] = color


# Game encoding: king=1, rook=2, knight=3, bishop=4, queen=5, pawn=6
set_sq(sq88(0, 0), 2, 0); set_sq(sq88(1, 0), 3, 0); set_sq(sq88(2, 0), 4, 0)
set_sq(sq88(3, 0), 5, 0); set_sq(sq88(4, 0), 1, 0); set_sq(sq88(5, 0), 4, 0)
set_sq(sq88(6, 0), 3, 0); set_sq(sq88(7, 0), 2, 0)
for f in range(8):
    set_sq(sq88(f, 1), 6, 0)
for f in range(8):
    set_sq(sq88(f, 6), 6, 1)
set_sq(sq88(0, 7), 2, 1); set_sq(sq88(1, 7), 3, 1); set_sq(sq88(2, 7), 4, 1)
set_sq(sq88(3, 7), 5, 1); set_sq(sq88(4, 7), 1, 1); set_sq(sq88(5, 7), 4, 1)
set_sq(sq88(6, 7), 3, 1); set_sq(sq88(7, 7), 2, 1)
uc.mem_write(0x030F4, bytes(BOARD))

# King table [0x032D4]
KING_TABLE = bytearray(64)
KING_TABLE[0] = sq88(4, 0) + 1
KING_TABLE[32] = sq88(4, 7) + 1
uc.mem_write(0x032D4, bytes(KING_TABLE))
uc.mem_write(0x007A2, b"\x00\x00\x00\x00")

# Other AI state variables
uc.mem_write(0x048BA, struct.pack(">H", 0))
uc.mem_write(0x048BC, struct.pack(">H", 0))
for addr in (0x04A50, 0x04A54, 0x04A56, 0x04A58,
             0x048B0, 0x048B2, 0x048B4, 0x048B6, 0x048B8,
             0x04ADE, 0x04DB0):
    uc.mem_write(addr, b"\x00\x00")
uc.mem_write(0x007D2, b"\x00\x00")
uc.mem_write(0x04DBE, struct.pack(">I", 0))
uc.mem_write(0x012C2, b"\x00\xff")
uc.mem_write(0x012C4, b"\x00\xff")

# Additional patches for AI run
uc.mem_write(0x085A2, b"\x60\x00\x00\xae")   # bge.w → bra.w (skip 0x857E piece-swap loop)
uc.mem_write(0x0858C, b"\x4e\x71\x4e\x71")   # NOP NOP (fn_857E → skip game startup re-call)
# Allow search_setup (0x0C198) to run so it initialises the eval tables and [0x48BE].
# Patch ONLY the two indirect jsr calls whose targets are uninitialised pointers:
#   0x0C1AC: jsr -$7fa4(a4) → [A4-0x7FA4] = [0x005A] — ROM code bytes, not a fn ptr
#   0x0C2C8: jsr -$7f74(a4) → [A4-0x7F74] = [0x008A] — ROM code bytes, not a fn ptr
# Both are single-argument calls: push / jsr / addq SP.  NOPing just the jsr leaves the
# push-and-cleanup balanced, so SP is correct after each call site.
uc.mem_write(0x0C1AC, b"\x4e\x71\x4e\x71")   # NOP NOP — replaces jsr -$7fa4(a4)
uc.mem_write(0x0C2C8, b"\x4e\x71\x4e\x71")   # NOP NOP — replaces jsr -$7f74(a4)
# Phase1 at 0x082E2 calls `jsr -$7f1a(a4)` → [0x000E4] which is set by game startup
# to an address that falls mid-instruction (0x00232 = inside `move.l a0, -$2c(a5)`)
# → executing FF D4 there triggers an F-line trap (UC_ERR_EXCEPTION).
# NOP this call: phase1 doesn't need it for the alpha-beta search itself.
uc.mem_write(0x082E2, b"\x4e\x71\x4e\x71")   # NOP NOP — replaces jsr -$7f1a(a4)
# Zero the best-move source buffer [0x48BE] (A4-0x3740) so search_setup starts
# from a clean "no move" state rather than ROM garbage.
uc.mem_write(0x48BE, b"\x00" * 8)

# Player/color setup: black to move, black=computer, white=human
uc.mem_write(0x0331E, struct.pack(">H", 1))
uc.mem_write(0x0331C, struct.pack(">H", 0))
# Phase1 at 0x0831C reads [0x007D4] and compares with [0x007D6].
# If equal → D0=1 → phase1 calls ai_search (0x094D8).
# If not equal → D0=0 → phase1 calls fn_07D96 (the move-list display path) instead.
# We want ai_search, so both must be equal.
uc.mem_write(0x07D4, struct.pack(">H", 1))
uc.mem_write(0x07D6, struct.pack(">H", 1))   # was 2; must equal [0x07D4] to trigger ai_search

# Uninitialized ROM library-function pointers: these are A4-relative slots that the game's
# startup sequence fills with OS library function addresses.  Since startup never completes
# in our headless setup, they contain ROM instruction bytes (garbage pointers).
# Setting them to our RTS stub (0x00164) makes every indirect call return immediately:
#   [0x00036] A4-0x7FC8: called from ai_search at 0x09546 — notify/print stub
#   [0x0003C] A4-0x7FC2: called from ai_search at 0x0955C — another print/notify stub
#   [0x00138] A4-0x7EC6: called from fn_07D96 (0x07DE0) and fn_098BE (0x098CC) —
#             supposed to be a FillMem/CopyMem; we already set up the board manually
# Write RTS (4E75) directly at each jsr target address.
# jsr d(An) is a DIRECT jump to address An+d — NOT a memory-indirect dereference.
# We must place actual RTS bytes at the target, not a pointer value.
# Patch both A4=0x7FFE and A4=0x7FFC variants in case A4 shifts.
uc.mem_write(0x00036, b"\x4e\x75")   # A4=0x7FFE: jsr -$7fc8(a4)
uc.mem_write(0x0003C, b"\x4e\x75")   # A4=0x7FFE: jsr -$7fc2(a4)
uc.mem_write(0x00138, b"\x4e\x75")   # A4=0x7FFE: jsr -$7ec6(a4)
uc.mem_write(0x00034, b"\x4e\x75")   # A4=0x7FFC: jsr -$7fc8(a4)
uc.mem_write(0x0003A, b"\x4e\x75")   # A4=0x7FFC: jsr -$7fc2(a4)
uc.mem_write(0x00136, b"\x4e\x75")   # A4=0x7FFC: jsr -$7ec6(a4)
uc.mem_write(0x0013C, b"\x4e\x75")   # A4=0x7FFC: jsr -$7ec0(a4)
uc.mem_write(0x0013E, b"\x4e\x75")   # A4=0x7FFE: jsr -$7ec0(a4)
# fn_07D96 at 0x07E20 calls `jsr -$7fe0(a4)` → 0x001E.
# 0x001E is mid-body of the startup dispatcher (fn_0006) — no RTS there.
# Execution falls through: pea $20002; jsr [0x0186]; sub.l #$36b0,d0;
# pea #2; move.l d0,-(a7) → then hits our RTS at 0x003C which pops D0 as
# a return address → jumps to garbage PC → A7 corrupts to 0x05538.
# fn_07D96 is only post-search display setup; stubbing this call is safe.
uc.mem_write(0x0001E, b"\x4e\x75")   # A4=0x7FFE: jsr -$7fe0(a4) in fn_07D96
uc.mem_write(0x0001C, b"\x4e\x75")   # A4=0x7FFC: jsr -$7fe0(a4) variant

# fn_07922 (move-list / encoding utility) reads its write-buffer pointer from
# [A4-0x3556] = [0x04AA8].  Startup was supposed to allocate a buffer (via the
# Amiga OS allocator) and store the pointer there, but startup crashed before it
# could do so.  The call chain is:
#   phase1 → fn_09CC2 → fn_0E084 → jsr -$7f80(a4) [jumps to startup code at 0x007C]
#   → ROM junk executes → move.l [0x04AA8], -(a7) pushes garbage → jsr fn_07922
#   → fn_07922 tries to write to garbage address → UC_ERR_WRITE_UNMAPPED
# Fix: point [0x04AA8] at a valid scratch area in ALLOC_POOL so fn_07922's writes
# land safely and the whole call chain returns cleanly.
SCRATCH_BUF = ALLOC_POOL + 0x50000   # 0x250000 — well inside our mapped region
uc.mem_write(0x04AA8, struct.pack(">I", SCRATCH_BUF))
uc.mem_write(0x04AA6, struct.pack(">I", SCRATCH_BUF))   # A4=0x7FFC: A4-0x3556=0x04AA6

# AI phase flag
uc.mem_write(0x04A5A, struct.pack(">H", 2))
uc.mem_write(0x012B6, struct.pack(">H", 0))
uc.mem_write(0x04A5C, struct.pack(">H", 0))
uc.mem_write(0x04A5E, struct.pack(">H", 0))

# Linked list head
uc.mem_write(0x01152, struct.pack(">I", PE_BASE))

# ===== DIRECTION TABLE at [0x0782] = A4 - 0x787C =====
# This is a runtime-computed table that game startup initializes with 0x88 board
# direction deltas.  Game startup cannot run safely in our headless emulator context
# (it requires AmigaOS register conventions for A2/A6 etc.).
# We initialize it manually with the 8 standard 0x88 direction deltas so the
# move generator / evaluator at 0x0B186 doesn't produce garbage sq values.
# The exact ORDER may differ from the original; move-quality may vary but no crash.
#
# 0x88 direction deltas: rank+1=+0x10, rank-1=-0x10, file+1=+0x01, file-1=-0x01,
#   NE=+0x11, SW=-0x11, NW=+0x0F, SE=-0x0F
# All produce sq&0x88 ≠ 0 (off-board) within one byte after leaving the board.
DIR_TABLE = struct.pack(">8h",
    +0x10,   # dir[0]: rank+1 (up)
    -0x10,   # dir[1]: rank-1 (down)
    +0x01,   # dir[2]: file+1 (right)
    -0x01,   # dir[3]: file-1 (left)
    +0x11,   # dir[4]: NE diagonal
    -0x11,   # dir[5]: SW diagonal
    +0x0F,   # dir[6]: NW diagonal
    -0x0F,   # dir[7]: SE diagonal
)
uc.mem_write(0x0782, DIR_TABLE)
print(f"Direction table initialised at [0x0782]: {DIR_TABLE.hex()}")

# Zero out adjacent lookup tables in the same ROM area that also need runtime
# initialization.  Without game startup, these contain ROM code bytes.
# Zeroing the "piece type flags" table at [0x07A6] makes the evaluator's
# beq-early-exit fire (flag & mask == 0) instead of proceeding into crashes.
# Zero [0x0792..0x07C0]: covers piece-flags and any other small tables there.
uc.mem_write(0x0792, b"\x00" * (0x07C0 - 0x0792))

# Zero [0x3314..0x3321]: loop-counter initial value (A4-0x4CEA).
# The outer loop reads a word from here to set its starting sq counter.
# ROM bytes here cause the loop to iterate many times with large sq values
# that index past the king table into uninitialised ROM bytes — crash.
# This range ends just before PT_BASE (0x3322), so piece table is safe.
uc.mem_write(0x3314, b"\x00" * (0x3322 - 0x3314))

# Zero [0x3722..0x3A00]: position eval table indexed by board square.
# Extends past 0x3900 (the previous boundary) to cover [A2+2] = [0x3900]
# which is accessed when the position-eval loop uses sq=0 (arg4=arg3=0).
# 0x3A00 provides ample margin beyond the highest reachable index.
uc.mem_write(0x3722, b"\x00" * (0x3A00 - 0x3722))

# Back rank piece types: fn_07ED4 reads low byte from [0x07C2 + file*2] for each file.
# Game encoding: king=1, rook=2, knight=3, bishop=4, queen=5 (pawn=6 written directly).
# Order = files a..h: rook,knight,bishop,queen,king,bishop,knight,rook
uc.mem_write(0x07C2, struct.pack(">8H", 2, 3, 4, 5, 1, 4, 3, 2))

# Pre-set king positions used by fn_07D96 (path to [0x04A5A]=2) and king_detect.
# With 0xFFFF, fn_07D96 takes the wrong path and sets [0x04A5A]=1 instead of 2.
uc.mem_write(0x03318, struct.pack(">H", sq88(4, 0)))   # white king e1 = sq 4
uc.mem_write(0x0331A, struct.pack(">H", sq88(4, 7)))   # black king e8 = sq 0x74

# Trace infrastructure
trace_calls = []
crashes = []
last_insns = collections.deque(maxlen=1000)
result_writes = []
a4_changes = []
last_a4_val = [A4]

call_watch = {
    0x8230:  "phase0",
    0x82DE:  "phase1",
    0x84C4:  "phase2",
    0x8820:  "fn_8820",
    0x8D32:  "fn_8D32",
    0x7CCE:  "fn_7CCE",
    0x857E:  "fn_857E",
    0x0C198: "search_setup",
    0x08818: "fn_08818",
    0x094D8: "ai_search",
    0x0A062: "search_core",
    0x09FC4: "king_detect",
    0x09CC2: "fn_09CC2",
    0x09AE2: "move_swap",
    0x031C6: "alpha_beta",
    0x00FC6: "search_init",
    0x0356C: "move_gen",
    0x00164: "input_wait(patched)",
    0x0005A: "game_startup",
    0x07922: "fn_07922",
    0x07D96: "fn_07D96",
    0x07E28: "fn_07E28",
    0x098BE: "fn_098BE",
}
# Stop on the SECOND entry to phase0 — one full phase0→phase1→move_swap cycle has
# completed and the best move should be stored.  Continuing indefinitely causes
# an infinite phase0/phase1 loop because input_wait returns immediately.
phase0_count = [0]
move_swap_count = [0]


sp_corrupted = [False]  # set True once we see sp < 0x100000


def code_hook(emu, addr, size, _):
    sp_v = emu.reg_read(m68k.UC_M68K_REG_A7)
    last_insns.append((addr, size, sp_v))
    a4_now = emu.reg_read(m68k.UC_M68K_REG_A4)
    if a4_now != last_a4_val[0]:
        # last_insns[-2] = the instruction that just ran and changed A4
        prev = list(last_insns)[-2] if len(last_insns) >= 2 else None
        a4_changes.append((addr, last_a4_val[0], a4_now, sp_v, prev))
        last_a4_val[0] = a4_now
    # SP corruption monitor: A7 should stay in stack region
    if not sp_corrupted[0] and sp_v < 0x100000:
        sp_corrupted[0] = True
        prev2 = list(last_insns)[-2] if len(last_insns) >= 2 else None
        crashes.append(('sp_corrupt', addr, sp_v, prev2))
    if addr == SENTINEL:
        emu.emu_stop()
    if addr in call_watch:
        sp_val = emu.reg_read(m68k.UC_M68K_REG_A7)
        extra = ""
        if addr in (0x00164, 0x09AE2, 0x07922, 0x07D96, 0x07E28, 0x098BE):
            slots = [struct.unpack(">I", bytes(emu.mem_read(sp_val + i*4, 4)))[0] for i in range(6)]
            a1v = emu.reg_read(m68k.UC_M68K_REG_A1)
            extra = "  stk=" + " ".join(f"0x{v:05X}" for v in slots) + f"  A1=0x{a1v:08X}"
        trace_calls.append((addr, sp_val, extra))
        if addr == 0x09AE2:
            move_swap_count[0] += 1
        if addr == 0x8230:
            phase0_count[0] += 1
        if addr == 0x84C4:
            # Phase2 is the final output stage — it writes [0x012C2]/[0x012C4].
            # Stop AFTER phase2 has run (let it complete by not stopping here).
            pass
        if len(trace_calls) > 5000:
            emu.emu_stop()
    if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
        off = addr - EXEC_BASE
        if off == -0xC6:
            d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
            emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
            bump[0] += max((d0 + 7) & ~7, 8)
        elif off == -0x198:
            emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)


best_move_written = [False]


def write_hook(emu, access, addr, size, val, _):
    if (0x012B0 <= addr < 0x012D0) or (0x03640 <= addr < 0x03690) or (0x48B0 <= addr < 0x48D0):
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        result_writes.append((addr, size, val, pc))
    if addr in (0x012C2, 0x012C4):
        emu.emu_stop()
    # NOTE: 0x03666/PC=0x082F0 fires at phase1's INITIAL copy of the active piece
    # (before the search), not after it.  Do NOT stop there — let phase1 run through
    # the full alpha-beta search so [0x012C2]/[0x012C4] get the actual move.
    pass


def fault_hook(emu, access, addr, size, val, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    a0 = emu.reg_read(m68k.UC_M68K_REG_A0)
    d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
    sp_val = emu.reg_read(m68k.UC_M68K_REG_A7)
    crashes.append(('fault', pc, addr, access, a0, d0, sp_val))
    if addr >= 0xFF000000:
        emu.emu_stop(); return False
    if 0x200000 <= addr and not (EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE):
        emu.emu_stop(); return False
    try:
        uc.mem_write(addr & ~3, b"\x00" * 4)
    except Exception:
        emu.emu_stop(); return False
    return True


uc.hook_del(h_code)
uc.hook_add(unicorn.UC_HOOK_CODE, code_hook)
uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_hook)
uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, fault_hook)

sp1 = STACK_TOP - 4
uc.mem_write(sp1, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp1)

p1 = bytes(uc.mem_read(0x00164, 2)).hex()
p2 = bytes(uc.mem_read(0x085A2, 4)).hex()
p3 = bytes(uc.mem_read(0x0858C, 4)).hex()
p4 = bytes(uc.mem_read(0x0C1AC, 4)).hex()
print(f"\nPhase 2 patches: [0x00164]={p1} [0x085A2]={p2} [0x0858C]={p3} [0x0C1AC]={p4}")

# === ROUND 1: call 0x081DC to run phase0 + search_setup ===
# The dispatcher at 0x081DC always clears [0x4A5C]=0 and calls phase0.
# Phase0 runs fn_7CCE (set up active piece), fn_857E, and search_setup.
# search_setup initialises the eval tables and writes the active piece to [0x48BE].
# After phase0 + search_setup, [0x4A5C]=1 indicating "ready for alpha-beta".
print("Round 1: calling 0x081DC (phase0 + search_setup) ...")
try:
    uc.emu_start(0x081DC, SENTINEL, count=30_000_000)
except Exception as e:
    print(f"  Error: {e}")

r1_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
r1_phase = struct.unpack(">H", bytes(uc.mem_read(0x04A5C, 2)))[0]
r1_48be = bytes(uc.mem_read(0x48BE, 8))
print(f"  Round 1 done: PC=0x{r1_pc:05X} [0x4A5C]={r1_phase} [0x48BE]={r1_48be.hex()}")

# Verify that our patches survived Round 1
for label, addr in [
    ("[0x00036] A4-0x7FC8 → should be 0x00164", 0x00036),
    ("[0x0003C] A4-0x7FC2 → should be 0x00164", 0x0003C),
    ("[0x00138] A4-0x7EC6 → should be 0x00164", 0x00138),
    ("[0x007D4] player-match-a → should be 1", 0x07D4),
    ("[0x007D6] player-match-b → should be 1 (=equal to D4)", 0x07D6),
]:
    v = struct.unpack(">I", bytes(uc.mem_read(addr, 4)))[0]
    print(f"  POST-Round1 {label}: 0x{v:08X}")

# Reset A4 between rounds: Phase 1 startup crash may corrupt A4 via exception
# processing; explicitly restore it to the canonical value 0x7FFE before Round 2.
uc.reg_write(m68k.UC_M68K_REG_A4, A4)
last_a4_val[0] = A4

# === ROUND 2: call phase1 (0x082DE) directly ===
# Phase1 at 0x082DE is the alpha-beta search entry point.  It:
#   1. Calls jsr -$7f1a(a4) (some initialization, already set up after Round 1)
#   2. Copies [0x48BE] (active piece from search_setup) → entry[104]
#   3. Runs ai_search (0x094D8) — the real alpha-beta
#   4. After search, [0x48BE] has the best move found
# We call 0x082DE directly (not via the dispatcher at 0x081DC) because the
# dispatcher's loop-back condition ([0x4A5A]=2) is cleared by search_setup's
# sub-functions. Calling phase1 directly avoids that gating.
print("Round 2: calling phase1 (0x082DE) directly for alpha-beta search ...")
sp2 = STACK_TOP - 4
uc.mem_write(sp2, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp2)
best_move_written[0] = False   # reset stop flag for Round 2
try:
    uc.emu_start(0x082DE, SENTINEL, count=30_000_000)
except Exception as e:
    print(f"  Error: {e}")

r2_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
print(f"Round 2 stopped at PC=0x{r2_pc:05X}")

# === ROUND 3: call phase2 (0x084C4) directly to write [0x012C2]/[0x012C4] ===
# Phase2 is the final state in the dispatcher: it reads the best move stored by
# the alpha-beta search (in [0x0365A]/[0x03662]) and writes FROM → [0x012C2],
# TO → [0x012C4].  The dispatcher normally advances to it after phase1 sets
# [0x04A5A]=2, but here we call it directly after forcing that flag.
print("Round 3: calling phase2 (0x084C4) to extract best move ...")
uc.mem_write(0x04A5A, struct.pack(">H", 2))   # force "move ready" flag
sp3 = STACK_TOP - 4
uc.mem_write(sp3, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp3)
try:
    uc.emu_start(0x084C4, SENTINEL, count=5_000_000)
except Exception as e:
    print(f"  Error: {e}")
r3_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
print(f"Round 3 done: PC=0x{r3_pc:05X}")

final_pc = r3_pc

if crashes:
    for entry in crashes[:5]:
        if entry[0] == 'sp_corrupt':
            _, pc, sp_v, prev2 = entry
            prev_str = f" prev={prev2}" if prev2 else ""
            print(f"SP_CORRUPT: PC=0x{pc:05X} A7=0x{sp_v:08X}{prev_str}")
        else:
            _, pc, addr, acc, a0, d0, sp_v = entry
            print(f"CRASH: PC=0x{pc:05X} → addr=0x{addr:08X} access={acc}")
            print(f"       A0=0x{a0:08X} D0=0x{d0:08X} SP=0x{sp_v:05X}")

print(f"\n[0x0077A] active_piece: {bytes(uc.mem_read(0x0077A, 8)).hex()}")
print(f"[0x03320] piece_counter: 0x{struct.unpack('>H', bytes(uc.mem_read(0x03320, 2)))[0]:04X}")
print(f"[0x03322] entry[0]: {bytes(uc.mem_read(0x03322, 8)).hex()}")
print(f"[0x0332A] entry[1]: {bytes(uc.mem_read(0x0332A, 8)).hex()}")

c2 = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
c4 = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
print(f"\n[0x012C2] FROM = 0x{c2:04X}")
print(f"[0x012C4] TO   = 0x{c4:04X}")
print(f"[0x04A5C] phase = {struct.unpack('>H', bytes(uc.mem_read(0x04A5C, 2)))[0]}")
best = bytes(uc.mem_read(0x0365A, 8))
print(f"AI_BEST_MOVE @ 0x365A: {best.hex()}")
best48be = bytes(uc.mem_read(0x48BE, 8))
print(f"AI_BEST_MOVE @ 0x48BE (A4-0x3740): {best48be.hex()}")
entry104 = bytes(uc.mem_read(0x03662, 8))
print(f"entry[104]  @ 0x03662: {entry104.hex()}")
print(f"[0x03640..0x36A0] memory dump:")
for off in range(0, 0x60, 8):
    chunk = bytes(uc.mem_read(0x03640 + off, 8))
    if any(b != 0 for b in chunk):
        print(f"  [0x{0x03640+off:05X}]: {chunk.hex()}")
print(f"[0x012B0..0x012D0] memory dump:")
for off in range(0, 0x20, 4):
    w = struct.unpack(">I", bytes(uc.mem_read(0x012B0 + off, 4)))[0]
    print(f"  [0x{0x012B0+off:05X}]: 0x{w:08X}")

print(f"\nResult-area writes ({len(result_writes)}):")
for addr, sz, val, pc in result_writes:
    print(f"  [0x{addr:05X}] ← 0x{val:08X} (size={sz}) PC=0x{pc:05X}")

print(f"\nLast 600 instructions before stop:")
try:
    import capstone as _cs
    _md = _cs.Cs(_cs.CS_ARCH_M68K, _cs.CS_MODE_BIG_ENDIAN + _cs.CS_MODE_M68K_000)
    _code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
    for iaddr, isz, isp in list(last_insns)[-600:]:
        if iaddr < len(_code):
            decoded = list(_md.disasm(_code[iaddr:iaddr + max(isz, 8)], iaddr))
            if decoded:
                ins = decoded[0]
                print(f"  0x{iaddr:05X} sp=0x{isp:05X}  {ins.mnemonic:<8} {ins.op_str}")
            else:
                print(f"  0x{iaddr:05X} sp=0x{isp:05X}  (decode fail)")
        else:
            print(f"  0x{iaddr:05X} sp=0x{isp:05X}  (outside code)")
except ImportError:
    for iaddr, isz, isp in list(last_insns)[-80:]:
        print(f"  0x{iaddr:05X} sp=0x{isp:05X}")

# Disassemble crash PC context
if crashes:
    first = crashes[0]
    crash_pc = first[1]  # index 1 = PC for both 'sp_corrupt' and 'fault' entries
    print(f"\nDisassembly around crash PC=0x{crash_pc:05X}:")
    try:
        import capstone as _cs2
        _md2 = _cs2.Cs(_cs2.CS_ARCH_M68K, _cs2.CS_MODE_BIG_ENDIAN + _cs2.CS_MODE_M68K_000)
        _code2 = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
        start = max(0, crash_pc - 0x20)
        for ins2 in _md2.disasm(_code2[start:crash_pc + 0x20], start):
            marker = " <<<" if ins2.address == crash_pc else ""
            print(f"  0x{ins2.address:05X}: {ins2.bytes.hex():<12}  {ins2.mnemonic} {ins2.op_str}{marker}")
    except Exception as e2:
        print(f"  disasm error: {e2}")

print(f"\nA4 register changes ({len(a4_changes)} total):")
try:
    import capstone as _cs3
    _md3 = _cs3.Cs(_cs3.CS_ARCH_M68K, _cs3.CS_MODE_BIG_ENDIAN + _cs3.CS_MODE_M68K_000)
    _code3 = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
except Exception:
    _md3 = None; _code3 = None
for entry4 in a4_changes[:20]:
    change_pc, old_a4, new_a4, sp_v, prev = entry4
    prev_str = ""
    if prev and _md3 and _code3 and prev[0] < len(_code3):
        dec = list(_md3.disasm(_code3[prev[0]:prev[0]+8], prev[0]))
        if dec:
            prev_str = f"  [changed by: 0x{prev[0]:05X} {dec[0].mnemonic} {dec[0].op_str}]"
        else:
            prev_str = f"  [changed by: 0x{prev[0]:05X} ??]"
    print(f"  PC=0x{change_pc:05X} sp=0x{sp_v:05X}  A4: 0x{old_a4:08X} → 0x{new_a4:08X}{prev_str}")

print(f"\nFunction trace ({len(trace_calls)} total, first 100):")
for entry in trace_calls[:100]:
    addr, sp_val, extra = entry
    depth = (STACK_TOP - sp_val) // 4
    indent = "  " * min(depth // 4, 10)
    name = call_watch.get(addr, f"0x{addr:05X}")
    print(f"  {indent}{name} (sp=0x{sp_val:05X}){extra}")
