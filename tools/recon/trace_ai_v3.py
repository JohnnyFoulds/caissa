#!/usr/bin/env python3
"""
trace_ai_v3.py — same setup as v2 but with 0x00164 patched → RTS.

The 0x00164 function is the game's input/event handler. When called headlessly
during the search (via phase0 → 0x0C198 → 0x0C41C chain), it loops forever
waiting for keyboard/joystick input. Patching it to RTS lets the search return.

Changes vs v2:
- uc.mem_write(0x00164, b"\x4e\x75")  # patch input-wait → immediate return
- More call sites in call_watch
- count raised to 20M to give phase1 room to run
"""
import sys, struct
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
uc.mem_write(0x36B0, b"\x4e\x73")  # F-line handler → RTE


def sq88(f, r):
    return r * 16 + f


# ===== STANDARD PATCHES =====
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    uc.mem_write(addr, b"\x00")
# DO NOT bulk-zero 0x6FFF..0x7FFD — that range contains fn_7CCE (0x7CCE) and other
# legitimate code.  Zero only the specific data variables that need it.

# ===== ZERO KEY DATA AREAS IN ROM CODE RANGE =====
# Many AI state variables live at addresses within the ROM code range
# (0x000000..0x11D1B) and contain ROM code bytes before game initialises them.
# We must zero each area specifically — we cannot zero code pages wholesale.

# ===== PIECE TABLE at 0x03322 (8 bytes/entry × 104 entries = 832 bytes) =====
# fn_7CCE is a bubble-sort that inserts the "active piece" from [0x0077A] into
# entry[0] and entry[104].  With [0x03320]=0xFFFF (-1) the sort loop does
# 104 self-copy no-ops, so pre-populated entries 1..103 survive intact.
# fn_7CCE then writes [0x0077A] to entry[0] and entry[104].
# Entry format: sq(H), color(H), type(B), flags(B), reserved(H)  (8 bytes)

def make_pt_entry(sq, color, piece_type):
    return struct.pack(">HHBBH", sq, color, piece_type, 0, 0)

PT_BASE = 0x03322
PT_SIZE = 8
PT_SLOTS = 105   # entries 0..104

pt_data = bytearray(PT_SLOTS * PT_SIZE)

# Starting position pieces — black to move.
# We'll put black pieces at entries 0..15, white at 16..31, zeros for 32..104.
pt_pieces = [
    # Black back rank
    (sq88(0, 7), 1, 4), (sq88(1, 7), 1, 2), (sq88(2, 7), 1, 3),
    (sq88(3, 7), 1, 5), (sq88(4, 7), 1, 6), (sq88(5, 7), 1, 3),
    (sq88(6, 7), 1, 2), (sq88(7, 7), 1, 4),
    # Black pawns
    (sq88(0, 6), 1, 1), (sq88(1, 6), 1, 1), (sq88(2, 6), 1, 1),
    (sq88(3, 6), 1, 1), (sq88(4, 6), 1, 1), (sq88(5, 6), 1, 1),
    (sq88(6, 6), 1, 1), (sq88(7, 6), 1, 1),
    # White back rank
    (sq88(0, 0), 0, 4), (sq88(1, 0), 0, 2), (sq88(2, 0), 0, 3),
    (sq88(3, 0), 0, 5), (sq88(4, 0), 0, 6), (sq88(5, 0), 0, 3),
    (sq88(6, 0), 0, 2), (sq88(7, 0), 0, 4),
    # White pawns
    (sq88(0, 1), 0, 1), (sq88(1, 1), 0, 1), (sq88(2, 1), 0, 1),
    (sq88(3, 1), 0, 1), (sq88(4, 1), 0, 1), (sq88(5, 1), 0, 1),
    (sq88(6, 1), 0, 1), (sq88(7, 1), 0, 1),
]
for i, (sq, color, pt) in enumerate(pt_pieces):
    entry = make_pt_entry(sq, color, pt)
    pt_data[i * PT_SIZE:(i + 1) * PT_SIZE] = entry

uc.mem_write(PT_BASE, bytes(pt_data))

# [0x0077A]: "active piece" — fn_7CCE copies this to entry[0] and entry[104].
# Use the black pawn at e7 (first piece in our pt_pieces above ... actually
# entry[12] = e7 pawn).  Use e-pawn so it matches our board setup.
ACTIVE_PIECE_ADDR = 0x0077A
BLACK_E_PAWN_SQ = sq88(4, 6)  # e7 = 0x64
uc.mem_write(ACTIVE_PIECE_ADDR, make_pt_entry(BLACK_E_PAWN_SQ, 1, 1))

# [0x03320] = 0xFFFF (-1): tells fn_7CCE the piece table is already sorted.
# With -1, fn_7CCE's sort loop does 104 self-copy no-ops (dest==src every time).
uc.mem_write(0x03320, struct.pack(">H", 0xFFFF))

# 32-byte piece entries at 0x0892 for the AI search (linked list).
# Format: +0=sq(H) +2=priority(H) +0xA=type(B) +0x14=state_ptr(L) +0x1C=next_ptr(L)
# Fill all 32 pieces; link them via +0x1C, last entry's next=0.
uc.mem_write(0x0892, b"\x00" * 32 * 32)
PE_BASE = 0x0892
PE_SIZE = 32
pe_pieces = [(sq, col, pt) for (sq, col, pt) in pt_pieces if col == 1]  # black pieces
for i, (sq, col, pt) in enumerate(pe_pieces):
    pe = bytearray(PE_SIZE)
    struct.pack_into(">H", pe, 0, sq)
    struct.pack_into(">H", pe, 2, i)          # priority = insertion order
    pe[0x0A] = pt
    next_ptr = (PE_BASE + (i + 1) * PE_SIZE) if i < len(pe_pieces) - 1 else 0
    struct.pack_into(">I", pe, 0x1C, next_ptr)
    uc.mem_write(PE_BASE + i * PE_SIZE, bytes(pe))

# Piece-count bounds used by 0x857E — must have start >= end to skip loop
uc.mem_write(0x048BA, struct.pack(">H", 0))   # count-start
uc.mem_write(0x048BC, struct.pack(">H", 0))   # count-end

# Other AI state variables in ROM code range that contain garbage
for addr in (0x04A50, 0x04A54, 0x04A56, 0x04A58,
             0x048B0, 0x048B2, 0x048B4, 0x048B6, 0x048B8,
             0x04ADE, 0x04DB0):
    uc.mem_write(addr, b"\x00\x00")

# Specific data variables in 0x6FFF..0x7FFD that need zeroing.
# (Previously covered by the bulk zero-fill, now targeted individually.)
# [0x007D2]: tested by phase0 at 0x0824C — must be 0 for the normal path
uc.mem_write(0x007D2, b"\x00\x00")

# Board-search-table pointer [0x04DBE]: must point somewhere valid.
# The table is accessed via adda.l [0x04DBE], a2 in 0x03470.
# Zero the pointer so the offset is 0 (accesses board itself — safe).
uc.mem_write(0x04DBE, struct.pack(">I", 0))

# Move result slots
uc.mem_write(0x012C2, b"\x00\xff")   # FROM = 0x00FF (no-move sentinel)
uc.mem_write(0x012C4, b"\x00\xff")   # TO   = 0x00FF (no-move sentinel)

# ===== KEY PATCHES =====
# 0x00164 → RTS: game input/keyboard handler; loops forever headlessly
uc.mem_write(0x00164, b"\x4e\x75")
# 0x085A2: bge.w $8652 → bra.w $8652
# 0x857E's piece-swap loop uses [0x03320] (PIECE_COUNTER = ROM garbage) to
# compute piece-table offsets, producing out-of-range board addresses.
# Forcing the branch skips the loop entirely — it only handles promotions.
uc.mem_write(0x085A2, b"\x60\x00\x00\xae")
# 0x0858C: jsr -$7fa4(a4) [→ 0x005A game startup] → NOP NOP (in 0x857E)
uc.mem_write(0x0858C, b"\x4e\x71\x4e\x71")
# 0x0C1AC: jsr -$7fa4(a4) [→ 0x005A game startup] → NOP NOP (in 0x0C198)
uc.mem_write(0x0C1AC, b"\x4e\x71\x4e\x71")


# ===== BOARD at 0x030F4: 128 sq × 4 bytes, 0x88 format =====
BOARD = bytearray(128 * 4)


def set_sq(sq, piece_type, color):
    BOARD[sq * 4] = piece_type    # 1=P 2=N 3=B 4=R 5=Q 6=K
    BOARD[sq * 4 + 1] = color     # 0=white 1=black


# Starting position — black to move
set_sq(sq88(0, 0), 4, 0); set_sq(sq88(1, 0), 2, 0); set_sq(sq88(2, 0), 3, 0)
set_sq(sq88(3, 0), 5, 0); set_sq(sq88(4, 0), 6, 0); set_sq(sq88(5, 0), 3, 0)
set_sq(sq88(6, 0), 2, 0); set_sq(sq88(7, 0), 4, 0)
for f in range(8):
    set_sq(sq88(f, 1), 1, 0)   # white pawns
for f in range(8):
    set_sq(sq88(f, 6), 1, 1)   # black pawns
set_sq(sq88(0, 7), 4, 1); set_sq(sq88(1, 7), 2, 1); set_sq(sq88(2, 7), 3, 1)
set_sq(sq88(3, 7), 5, 1); set_sq(sq88(4, 7), 6, 1); set_sq(sq88(5, 7), 3, 1)
set_sq(sq88(6, 7), 2, 1); set_sq(sq88(7, 7), 4, 1)
uc.mem_write(0x030F4, bytes(BOARD))

# ===== [0x032D4] king position table =====
WHITE_KING_SQ = sq88(4, 0)   # e1 = 0x04
BLACK_KING_SQ = sq88(4, 7)   # e8 = 0x74
KING_TABLE = bytearray(64)
KING_TABLE[0] = WHITE_KING_SQ + 1
KING_TABLE[32] = BLACK_KING_SQ + 1
uc.mem_write(0x032D4, bytes(KING_TABLE))
uc.mem_write(0x007A2, b"\x00\x00\x00\x00")   # zero offset-adjustment table

# ===== Linked list head =====
uc.mem_write(0x01152, struct.pack(">I", PE_BASE))
uc.mem_write(0x04ADE, struct.pack(">H", 0))

# ===== Player/color setup: White=Human, Black=Computer =====
uc.mem_write(0x0331E, struct.pack(">H", 1))   # player1 = Black (side to move)
uc.mem_write(0x0331C, struct.pack(">H", 0))   # player2 = White
uc.mem_write(0x07D4, struct.pack(">H", 1))    # player[0]=Human (white)
uc.mem_write(0x07D6, struct.pack(">H", 2))    # player[1]=Computer (black)

# ===== AI phase flag & related =====
uc.mem_write(0x04A5A, struct.pack(">H", 2))   # enable state machine loop
uc.mem_write(0x012B6, struct.pack(">H", 0))
uc.mem_write(0x04A5C, struct.pack(">H", 0))
uc.mem_write(0x04A5E, struct.pack(">H", 0))

bump = [ALLOC_POOL]
trace_calls = []
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
    0x094D8: "ai_search_094D8",
    0x0A062: "search_core_0A062",
    0x09FC4: "king_detect",
    0x09CC2: "fn_09CC2",
    0x09AE2: "move_swap_09AE2",
    0x031C6: "alpha_beta",
    0x00FC6: "search_init",
    0x0356C: "move_gen",
    0x00164: "input_wait(patched)",
    0x000E4: "process_events",
    0x07C5A: "game_frame",
    0x0005A: "game_startup",
}
crashes = []
# Ring buffer: last 200 instructions, (addr, size, sp)
import collections
last_insns = collections.deque(maxlen=200)


def code_hook(emu, addr, size, _):
    last_insns.append((addr, size, emu.reg_read(m68k.UC_M68K_REG_A7)))
    if addr == SENTINEL:
        emu.emu_stop()
    if addr in call_watch:
        sp = emu.reg_read(m68k.UC_M68K_REG_A7)
        extra = ""
        if addr in (0x00164, 0x09AE2):
            # Read top 8 stack slots to understand the call path
            slots = []
            for i in range(8):
                raw = bytes(emu.mem_read(sp + i * 4, 4))
                slots.append(struct.unpack(">I", raw)[0])
            extra = "  stack=" + " ".join(f"0x{v:05X}" for v in slots)
            # For 0x09AE2: also capture the A5-relative argument at $8(a5)
            if addr == 0x09AE2:
                a5 = emu.reg_read(m68k.UC_M68K_REG_A5)
                arg_raw = bytes(emu.mem_read(a5 + 8, 2))
                sq_arg = struct.unpack(">H", arg_raw)[0]
                extra += f"  A5=0x{a5:05X} sq_arg=0x{sq_arg:04X}"
        trace_calls.append((addr, sp, extra))
        if len(trace_calls) > 500:
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
    sp = emu.reg_read(m68k.UC_M68K_REG_A7)
    a0 = emu.reg_read(m68k.UC_M68K_REG_A0)
    a1 = emu.reg_read(m68k.UC_M68K_REG_A1)
    d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
    d1 = emu.reg_read(m68k.UC_M68K_REG_D1)
    crashes.append((pc, addr, access, a0, a1, d0, d1, sp))
    if addr >= 0xFF000000:
        emu.emu_stop(); return False
    if 0x200000 <= addr < ALLOC_POOL and not (EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE):
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

# Verify patches actually hit the emulated memory
p1 = bytes(uc.mem_read(0x00164, 2)).hex()
p2 = bytes(uc.mem_read(0x085A2, 4)).hex()
p3 = bytes(uc.mem_read(0x0858C, 4)).hex()
p4 = bytes(uc.mem_read(0x0C1AC, 4)).hex()
print(f"Patches: [0x00164]={p1}  [0x085A2]={p2}  [0x0858C]={p3}  [0x0C1AC]={p4}")
print(f"  (want:  4e75         600000ae          4e714e71           4e714e71)")
print(f"[0x048BA]={struct.unpack('>H',bytes(uc.mem_read(0x048BA,2)))[0]}  [0x048BC]={struct.unpack('>H',bytes(uc.mem_read(0x048BC,2)))[0]}")
print("Running AI from 0x81DC (0x00164 patched → RTS)...")
try:
    uc.emu_start(0x081DC, SENTINEL, count=20_000_000)
except Exception as e:
    print(f"Error: {e}")

final_pc = uc.reg_read(m68k.UC_M68K_REG_PC)
print(f"Stopped at PC=0x{final_pc:05X}")

if crashes:
    for pc, addr, acc, a0, a1, d0, d1, sp in crashes[:5]:
        print(f"CRASH: PC=0x{pc:05X} → addr=0x{addr:08X} access={acc}")
        print(f"       A0=0x{a0:08X} A1=0x{a1:08X} D0=0x{d0:08X} D1=0x{d1:08X} SP=0x{sp:05X}")

# Post-run data dump
print(f"\n[0x0077A] active_piece: {bytes(uc.mem_read(0x0077A, 8)).hex()}")
print(f"[0x03320] piece_counter: {struct.unpack('>H', bytes(uc.mem_read(0x03320, 2)))[0]:#06x}")
print(f"[0x03322] entry[0]:  {bytes(uc.mem_read(0x03322, 8)).hex()}")
print(f"[0x0332A] entry[1]:  {bytes(uc.mem_read(0x0332A, 8)).hex()}")
print(f"[0x03662] entry[104]:{bytes(uc.mem_read(0x03662, 8)).hex()}")

print(f"\nLast {min(len(last_insns), 60)} instructions before crash:")
rom_bytes = open(default_rom_path(), "rb").read()
_regions = parse_amiga_hunk(rom_bytes)
_code = rom_bytes[_regions[0].offset:_regions[0].offset + _regions[0].size]
try:
    import capstone as _cs
    _md = _cs.Cs(_cs.CS_ARCH_M68K, _cs.CS_MODE_BIG_ENDIAN + _cs.CS_MODE_M68K_000)
    insn_list = list(last_insns)[-60:]
    for iaddr, isz, isp in insn_list:
        if iaddr < len(_code):
            raw = _code[iaddr:iaddr + max(isz, 8)]
            decoded = list(_md.disasm(raw, iaddr))
            if decoded:
                ins = decoded[0]
                print(f"  0x{iaddr:05X}  sp=0x{isp:05X}  {ins.mnemonic:<8} {ins.op_str}")
            else:
                print(f"  0x{iaddr:05X}  sp=0x{isp:05X}  (decode fail)")
        else:
            print(f"  0x{iaddr:05X}  sp=0x{isp:05X}  (outside code)")
except ImportError:
    for iaddr, isz, isp in list(last_insns)[-60:]:
        print(f"  0x{iaddr:05X}  sp=0x{isp:05X}  sz={isz}")

print(f"\nFunction trace ({len(trace_calls)} total, showing first 80):")
for entry in trace_calls[:80]:
    addr, sp_val = entry[0], entry[1]
    extra = entry[2] if len(entry) > 2 else ""
    depth = (STACK_TOP - sp_val) // 4
    indent = "  " * min(depth // 4, 10)
    print(f"  {indent}{call_watch.get(addr, hex(addr))} @ 0x{addr:05X}  (sp=0x{sp_val:05X}){extra}")

print(f"\nResult-area writes ({len(result_writes)}):")
for addr, sz, val, pc in result_writes[:20]:
    print(f"  [0x{addr:05X}] ← 0x{val:X} (size={sz}) PC=0x{pc:05X}")

c2 = struct.unpack(">H", bytes(uc.mem_read(0x012C2, 2)))[0]
c4 = struct.unpack(">H", bytes(uc.mem_read(0x012C4, 2)))[0]
print(f"\n[0x012C2] FROM = 0x{c2:04X}")
print(f"[0x012C4] TO   = 0x{c4:04X}")
print(f"[0x04A5C] (phase flag) = {struct.unpack('>H',bytes(uc.mem_read(0x04A5C,2)))[0]}")
print(f"[0x04A5A] (loop enable)= {struct.unpack('>H',bytes(uc.mem_read(0x04A5A,2)))[0]}")
best = bytes(uc.mem_read(0x0365A, 8))
print(f"AI_BEST_MOVE @ 0x365A: {best.hex()}")
