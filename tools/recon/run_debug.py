#!/usr/bin/env python3
"""Drive the Battle Chess AI headlessly.

KEY ARCHITECTURE (from disasm):
  - outer_driver (0x81DC): state machine calling phase0/phase1/phase2 in order.
    Reads phase_state (A4-0x35A2 = 0x4A5C) to pick which phase runs; loops until
    move_state (A4-0x35A4 = 0x4A5A) == 2 AND player_type[turn] != 1 (human).
  - phase0_init (0x8230): initialises search, sets phase_state=1 at 0x082CA.
    Calls jsr 0x8D32 which contains the F-line-heavy graphics loop — NOP'd.
  - ai_phase1_search (0x82DE): minimax dispatcher.
    When M[A4-0x499E]=M[0x3660] != 0 (AI vs human path), calls per_piece_eval.
  - per_piece_eval (0x94D8): recursive minimax.  Called many times per search.
  - ai_find_move (0x901C): accumulates best move in M[A4-0x7884] = M[0x017A].
  - ai_best_move output: M[A4-0x49A4] = M[0x365A], 8-byte MoveSpec.

PERFORMANCE: Use targeted hooks (begin=addr, end=addr+2), NOT all-instruction
hooks — per-instruction Python callbacks are 1000x slower.

F-LINE: Unicorn m68k false-positive F-line on d(An) with 0xF-prefix displacement.
Python intr_hook receives PC at displacement word; advance PC+2 to skip.
"""
import sys, struct
sys.path.insert(0, "bin")

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_HOOK_INTR
import unicorn.m68k_const as m68k

from pathlib import Path
from Code.Retro.Manifest import default_rom_path, verify
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import (
    A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge,
    PLAYER2_COLOR_ADDR, PLAYER_TYPE_BASE,
)
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_READ

def P(*args, **kw):
    print(*args, **kw, flush=True)

CHIP_RAM_BASE = 0x000000
CHIP_RAM_SIZE = 0x1000000
STACK_TOP     = 0xF00000
SENTINEL      = 0xFFFF0000
A4            = A4_VALUE   # 0x7FFE

# Key addresses
AI_OUTER_DRIVER   = 0x81DC
AI_PHASE1_SEARCH  = 0x82DE
PER_PIECE_EVAL    = 0x94D8
AI_FIND_MOVE      = 0x901C
BEST_MOVE_ADDR    = A4 - 0x7884   # 0x017A: accumulated best move during search
AI_BEST_MOVE_ADDR = A4 - 0x49A4   # 0x365A: final ai_best_move output (MoveSpec)

# AI path condition flags (inside ai_phase1_search at 0x82DE)
ADDR_3660 = A4 - 0x499E   # 0x3660: non-zero → call per_piece_eval (AI vs human)
ADDR_3668 = A4 - 0x4996   # 0x3668: zero → use main eval path

# ── Load ROM ──────────────────────────────────────────────────────────────────
rom_path = default_rom_path()
manifest = Path(__file__).parents[2] / "Resources/Retro/manifest.json"
verify(rom_path, manifest)
rom_data = open(rom_path, "rb").read()
regions  = parse_amiga_hunk(rom_data)

cpu = Unicorn68k()
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])

# RTS stubs over exec/dos vector range
lib_base = EXEC_BASE - LIB_RANGE
lib_size  = LIB_RANGE * 2
cpu.mem_write(lib_base, b"\x4e\x75" * (lib_size // 2))

traps = AmigaTraps(cpu)
# Use a TARGETED hook (not all-instruction) — the library range is 0x7C0000-0x840000.
# All-instruction hooks have O(N) Python overhead per instruction and kill performance.
cpu._uc.hook_add(UC_HOOK_CODE, traps._dispatch, begin=0x7C0000, end=0x840000)
traps.install_mem_hook()

NOP2 = b"\x4e\x71\x4e\x71"
NOP3 = b"\x4e\x71\x4e\x71\x4e\x71"

# ── Pre-init patches (safe to apply before init runs) ─────────────────────────
# F-line handler: addq.l #2, 2(a7) ; rte
cpu.mem_write(0x36B0, bytes([0x55, 0xAF, 0x00, 0x02, 0x4E, 0x73]))
# Zero AI-gate flags
cpu.mem_write(0x025C, b"\x00"); cpu.mem_write(0x025D, b"\x00"); cpu.mem_write(0x024F, b"\x00")
# NOP addq.w #2, a7 at 0x0140 (stack drift)
cpu.mem_write(0x0140, b"\x4e\x71")
# NOP move.b #1, -$7DA2(a4) at 0x012A4 (prevents 0x025C=1)
cpu.mem_write(0x012A4, NOP3)
# NOP jsr 0x8820 at 0x8234 (phase0_init event-handler bypass)
cpu.mem_write(0x8234, NOP2)
# NOP jsr 0x8D32 at 0x08238 — eliminates the F-line-heavy graphics loop.
#   0x8D32 is called by phase0_init; it runs 20M iterations containing
#   move.w -$42a(a4), d0  (displacement 0xFBD6 → false F-line from Unicorn bug).
#   Skipping it removes ~20M Python intr_hook callbacks, dramatically speeding init.
cpu.mem_write(0x08238, NOP2)
# NOP jsr $e76(pc) at 0x03456 — board-redraw callback inside the F-line false-fire
# recovery path.  After the false F-line at 0x03424, PC advances to 0x03426 and
# execution falls through to 0x03456 where it calls 0x0E76, which in turn calls
# 0x0688, which calls jsr -$7e8a(a4) → 0x0174 and jsr -$7e60(a4) → 0x019E.
# Those addresses are above the blanket-stub ceiling and contain real Amiga OS code
# that collapses the task stack to 0x272 and corrupts all state.
# Stack balance is preserved: pea.l at 0x03452 pushes 4 bytes;
# addq.w #4, a7 at 0x0345A pops them even after the NOP'd jsr.
cpu.mem_write(0x03456, NOP2)

P("Pre-init patches applied:")
P("  0x36B0: F-line advance-2 handler")
P("  0x025C/025D/024F: zeroed (AI gate flags)")
P("  0x0140: NOP addq.w #2,a7 (stack drift)")
P("  0x012A4: NOP move.b #1,025C")
P("  0x8234: NOP jsr 0x8820 (phase0 event-handler)")
P("  0x08238: NOP jsr 0x8D32 (eliminate F-line loop)")
P("  0x03456: NOP jsr 0x0E76 (suppress OS-call chaos via graphics callback)")

# ── Stack + A4 ────────────────────────────────────────────────────────────────
sp = STACK_TOP - 4
cpu.mem_write(sp, struct.pack(">I", SENTINEL))
cpu.reg_write("A7", sp)
cpu.reg_write("A4", A4)
bridge = Bridge(cpu)

bridge.write_position("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
bridge.set_computer_color(0)

p2c = struct.unpack(">H", cpu.mem_read(PLAYER2_COLOR_ADDR, 2))[0]
pt0 = struct.unpack(">H", cpu.mem_read(PLAYER_TYPE_BASE, 2))[0]
pt1 = struct.unpack(">H", cpu.mem_read(PLAYER_TYPE_BASE + 2, 2))[0]
P(f"\nPLAYER2_COLOR={p2c}  player_type[0]={pt0}  player_type[1]={pt1}")

files = "abcdefgh"
def sq88_to_alg(sq):
    f = sq & 0x0F; r = (sq >> 4) & 0x0F
    return f"{files[f]}{r+1}" if f < 8 and r < 8 else f"?0x{sq:02X}"

# ── Counters ──────────────────────────────────────────────────────────────────
F_LINE_COUNT   = [0]
intr_by_pc     = {}
_mapped_pages  = set()
PHASE0_COUNT   = [0]
PHASE1_COUNT   = [0]
MINIMAX_COUNT  = [0]
AI_FIND_COUNT  = [0]
DRIVER_EXITS   = [0]
DRIVER_ENTRIES = [0]
MOVE_FOUND     = [None]

# ── Interrupt hook (F-line advance) ──────────────────────────────────────────
def intr_hook(emu, intno, _ud=None):
    if intno == 11:
        F_LINE_COUNT[0] += 1
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        intr_by_pc[pc] = intr_by_pc.get(pc, 0) + 1
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
        if F_LINE_COUNT[0] <= 3 or F_LINE_COUNT[0] % 500_000 == 0:
            P(f"  F-line #{F_LINE_COUNT[0]:,} at PC=0x{pc:05X}")

# ── Fault hook ────────────────────────────────────────────────────────────────
def fault_hook(emu, access, address, size, value, _ud=None):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    page = address & ~0xFFFF
    # If the CPU is trying to EXECUTE from the faulted page, it jumped off-track.
    # Stop immediately instead of mapping zeroes (which would let it run forever).
    if (pc & ~0xFFFF) == page:
        a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
        try:
            ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
        except Exception:
            ret = 0
        P(f"  FATAL CODE-EXEC FAULT: CPU jumped to 0x{pc:08X} "
          f"(A7=0x{a7v:08X}, ret@stack=0x{ret:08X}) — stopping")
        P(f"  Last valid PCs: {[hex(p) for p in _pc_ring]}")
        emu.emu_stop(); return False
    if page not in _mapped_pages:
        _mapped_pages.add(page)
        if len(_mapped_pages) <= 5:
            P(f"  FAULT: mapping page 0x{page:08X} (PC=0x{pc:05X})")
        try:
            cpu._uc.mem_map(page, 0x10000)
            cpu._uc.mem_write(page, b"\x00" * 0x10000)
        except Exception as ex:
            P(f"  FAULT: map failed: {ex}")
            emu.emu_stop(); return False
    return True

# ── PC ring-buffer (last 30 valid-range instructions) ─────────────────────────
_pc_ring = []
def hook_record_pc(emu, address, size, _ud=None):
    _pc_ring.append(address)
    if len(_pc_ring) > 30:
        _pc_ring.pop(0)

# ── Illegal-zone code hook ─────────────────────────────────────────────────────
# Game code lives at 0x0000–0x1FFFF; exec library at 0x7C0000–0x83FFFF.
# Any execution in [0x20000, 0x7C0000) means the CPU jumped off-track.
_ILLEGAL_ZONE_FIRED = [False]
def hook_illegal_zone(emu, address, size, _ud=None):
    if _ILLEGAL_ZONE_FIRED[0]:
        return
    _ILLEGAL_ZONE_FIRED[0] = True
    a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
    a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
    d0v = emu.reg_read(m68k.UC_M68K_REG_D0)
    try:
        ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
    except Exception:
        ret = 0
    P(f"  ILLEGAL ZONE: PC=0x{address:08X} A7=0x{a7v:08X} "
      f"A4=0x{a4v:08X} D0=0x{d0v:08X} ret@stack=0x{ret:08X}")
    P(f"  Last valid PCs: {[hex(p) for p in _pc_ring]}")
    emu.emu_stop()

# ── Targeted code hooks (address-range, not all-instruction) ──────────────────
PHASE0_RET_COUNT = [0]
def hook_phase0_ret(emu, address, size, _ud=None):
    """Fires at 0x081F2: the instruction outer_driver executes after phase0_init returns."""
    PHASE0_RET_COUNT[0] += 1
    a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
    a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
    ps  = struct.unpack(">H", bytes(emu.mem_read(a4v - 0x35A2, 2)))[0]
    pc  = struct.unpack(">H", bytes(emu.mem_read(a4v - 0x4CDE, 2)))[0]
    # Read the instruction bytes at this address to verify bra target
    ib = bytes(emu.mem_read(address, 4)).hex()
    try:
        ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
    except Exception:
        ret = 0
    P(f"  phase0_init returned #{PHASE0_RET_COUNT[0]}: phase_state={ps} piece_counter={pc} "
      f"A4=0x{a4v:05X} instr={ib} A7=0x{a7v:05X} ret@stack=0x{ret:08X}")

def hook_outer_driver(emu, address, size, _ud=None):
    DRIVER_ENTRIES[0] += 1
    a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
    try:
        ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
    except Exception:
        ret = 0
    P(f"  outer_driver entry #{DRIVER_ENTRIES[0]}: called from 0x{ret:05X} (A7=0x{a7v:08X})")

def hook_phase0(emu, address, size, _ud=None):
    PHASE0_COUNT[0] += 1
    # Read return address from stack top to trace who called phase0_init
    a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
    try:
        ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
    except Exception:
        ret = 0
    P(f"  phase0_init entry #{PHASE0_COUNT[0]}: called from 0x{ret:05X} (A7=0x{a7v:08X})")

def hook_phase1(emu, address, size, _ud=None):
    PHASE1_COUNT[0] += 1
    if PHASE1_COUNT[0] <= 3:
        # Check AI path conditions
        v3660 = struct.unpack(">B", bytes(emu.mem_read(ADDR_3660, 1)))[0]
        v3668 = struct.unpack(">B", bytes(emu.mem_read(ADDR_3668, 1)))[0]
        pt0v  = struct.unpack(">H", bytes(emu.mem_read(PLAYER_TYPE_BASE, 2)))[0]
        pt1v  = struct.unpack(">H", bytes(emu.mem_read(PLAYER_TYPE_BASE + 2, 2)))[0]
        P(f"  phase1_search entry #{PHASE1_COUNT[0]}: 3660=0x{v3660:02X} 3668=0x{v3668:02X} "
          f"pt[0]={pt0v} pt[1]={pt1v}")

# Diagnostic: trace which instruction fires near phase1_search boundary
_DIAG_FIRED = {}
def hook_diag(emu, address, size, _ud=None):
    if address not in _DIAG_FIRED:
        _DIAG_FIRED[address] = 0
    _DIAG_FIRED[address] += 1
    if _DIAG_FIRED[address] <= 4:
        a7v = emu.reg_read(m68k.UC_M68K_REG_A7)
        try:
            ret = struct.unpack(">I", bytes(emu.mem_read(a7v, 4)))[0]
        except Exception:
            ret = 0
        P(f"  DIAG @0x{address:05X} #{_DIAG_FIRED[address]} A7=0x{a7v:05X} ret@stack=0x{ret:08X}")

def hook_dispatch_jsr(emu, address, size, _ud=None):
    """Fires at 0x081F4 (the jsr to phase1_search) to confirm it's reached."""
    _DIAG_FIRED.setdefault(address, 0)
    _DIAG_FIRED[address] += 1
    if _DIAG_FIRED[address] <= 3:
        a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
        ps  = struct.unpack(">H", bytes(emu.mem_read(a4v - 0x35A2, 2)))[0]
        P(f"  JSR-to-phase1 #{_DIAG_FIRED[address]} phase_state={ps} A4=0x{a4v:05X}")

def hook_minimax(emu, address, size, _ud=None):
    MINIMAX_COUNT[0] += 1
    if MINIMAX_COUNT[0] <= 5 or MINIMAX_COUNT[0] % 10_000 == 0:
        P(f"  per_piece_eval #{MINIMAX_COUNT[0]:,}")

def hook_ai_find(emu, address, size, _ud=None):
    AI_FIND_COUNT[0] += 1
    if AI_FIND_COUNT[0] <= 5:
        a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
        # Best candidate so far is at A4-0x7884 = 0x017A
        data = bytes(emu.mem_read(a4v - 0x7884, 8))
        from_sq = struct.unpack(">H", data[0:2])[0]
        to_sq   = struct.unpack(">H", data[2:4])[0]
        P(f"  ai_find_move #{AI_FIND_COUNT[0]:,}: best so far "
          f"from=0x{from_sq:02X} to=0x{to_sq:02X}")

LOOP_CHECK_COUNT = [0]
def hook_loop_check(emu, address, size, _ud=None):
    LOOP_CHECK_COUNT[0] += 1
    ms  = struct.unpack(">H", bytes(emu.mem_read(MOVE_STATE_ADDR,  2)))[0]
    ct  = struct.unpack(">H", bytes(emu.mem_read(0x0331C,          2)))[0]
    a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
    pt  = struct.unpack(">H", bytes(emu.mem_read(a4v - 0x782A + ct*2, 2)))[0]
    ps  = struct.unpack(">H", bytes(emu.mem_read(a4v - 0x35A2, 2)))[0]
    P(f"  loop_check #{LOOP_CHECK_COUNT[0]}: move_state={ms} ct={ct} pt[ct]={pt} "
      f"phase_state={ps} A4=0x{a4v:05X}")

OUTER_EXIT_COUNT = [0]
def hook_outer_exit(emu, address, size, _ud=None):
    OUTER_EXIT_COUNT[0] += 1
    P(f"  outer_driver EXIT RTS #{OUTER_EXIT_COUNT[0]} (move_state={struct.unpack('>H', bytes(emu.mem_read(MOVE_STATE_ADDR, 2)))[0]})")

def hook_phase1_rts(emu, address, size, _ud=None):
    """Fires at ai_phase1_search RTS (0x08348)."""
    DRIVER_EXITS[0] += 1
    if DRIVER_EXITS[0] <= 3 or DRIVER_EXITS[0] % 50 == 0:
        a4v = emu.reg_read(m68k.UC_M68K_REG_A4)
        data = bytes(emu.mem_read(a4v - 0x7884, 8))
        from_sq = struct.unpack(">H", data[0:2])[0]
        to_sq   = struct.unpack(">H", data[2:4])[0]
        P(f"  phase1_rts #{DRIVER_EXITS[0]}: M[0x017A]={data.hex()} "
          f"({sq88_to_alg(from_sq)}{sq88_to_alg(to_sq)})")

cpu._uc.hook_add(UC_HOOK_INTR,       intr_hook)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, fault_hook)
# Illegal-zone: game code is 0x0000-0x1FFFF; exec library 0x7C0000+.
# Any execution in [0x20000, 0x7C0000) means the CPU went off-track.
cpu._uc.hook_add(UC_HOOK_CODE, hook_illegal_zone, begin=0x020000, end=0x7C0000)
cpu._uc.hook_add(UC_HOOK_CODE, hook_outer_driver, begin=0x81DC, end=0x81DE)
cpu._uc.hook_add(UC_HOOK_CODE, hook_phase0,    begin=0x8230, end=0x8232)
cpu._uc.hook_add(UC_HOOK_CODE, hook_phase1,    begin=0x82DE, end=0x82E0)
# Diagnostic: which instruction fires near phase1_search?
cpu._uc.hook_add(UC_HOOK_CODE, hook_diag, begin=0x082DC, end=0x082E2)
# Hook at jsr-to-phase1 dispatch site
cpu._uc.hook_add(UC_HOOK_CODE, hook_dispatch_jsr, begin=0x081F4, end=0x081F6)
cpu._uc.hook_add(UC_HOOK_CODE, hook_minimax,   begin=PER_PIECE_EVAL,  end=PER_PIECE_EVAL+2)
cpu._uc.hook_add(UC_HOOK_CODE, hook_ai_find,   begin=AI_FIND_MOVE,    end=AI_FIND_MOVE+2)
cpu._uc.hook_add(UC_HOOK_CODE, hook_phase1_rts, begin=0x08348, end=0x0834A)
cpu._uc.hook_add(UC_HOOK_CODE, hook_loop_check,  begin=0x0820C, end=0x0820E)
cpu._uc.hook_add(UC_HOOK_CODE, hook_outer_exit,  begin=0x0822C, end=0x0822E)
cpu._uc.hook_add(UC_HOOK_CODE, hook_phase0_ret,  begin=0x081F2, end=0x081F4)

# ── Run init (0x07C8C) ────────────────────────────────────────────────────────
INIT_FUNC = 0x07C8C
P(f"\nRunning game init at 0x{INIT_FUNC:X}...")
try:
    cpu.emu_start(INIT_FUNC, until=SENTINEL, count=5_000_000)
    P("Init done.")
except Exception as e:
    P(f"Init stopped: {e}")

P(f"  F-lines during init: {F_LINE_COUNT[0]:,}")

# Show what init wrote at the jsr -$7fc8(a4) and jsr -$7fc2(a4) targets
# (called from per_piece_eval; these are Amiga-OS-style function-pointer calls)
for off_name, addr in [("-0x7FC8 → 0x0036", 0x0036), ("-0x7FC2 → 0x003C", 0x003C),
                       ("-0x7FC0 → 0x003E", 0x003E), ("0x8038 call-back", 0x8038)]:
    data = bytes(cpu.mem_read(addr, 4))
    P(f"  M[0x{addr:04X}] ({off_name}): {data.hex()}")

# ── Post-init patches ─────────────────────────────────────────────────────────
# NOP jsr -$7f1a(a4) at 0x082E2 inside phase1_search preamble.
cpu.mem_write(0x082E2, NOP2)
cpu.mem_write(0x00E4, b"\x4e\x75")   # belt-and-suspenders RTS at 0x00E4

v = bytes(cpu.mem_read(0x082E2, 4))
P(f"  Post-init patch 0x082E2: {v.hex()} ({'OK' if v == b'\x4e\x71\x4e\x71' else 'FAILED'})")

# RTS at 0x8818, 0x8820 (event handlers — 0x0C198 calls both).
# Also RTS at 0x8D32 (graphics loop) for belt-and-suspenders.
cpu.mem_write(0x08818, b"\x4e\x75")
cpu.mem_write(0x08820, b"\x4e\x75")
cpu.mem_write(0x08D32, b"\x4e\x75")
P(f"  RTS injected at 0x8818, 0x8820 and 0x8D32 (block all event/graphics callers)")

# ── Stub ALL Amiga OS cooperative-yield/call targets in low-memory ─────────────
# The game uses A4-relative calls (jsr d16(a4) with A4=0x7FFE) to Amiga OS
# function trampolines at low addresses.  After init these targets contain real
# Amiga OS code that we can't execute without a full OS.
#
# Rather than stub each address individually (and miss ones like 0x003E),
# blanket-write RTS to the entire range 0x0030-0x013F.  This covers:
#   0x0036 (A4-0x7FC8), 0x003C (A4-0x7FC2), 0x003E (A4-0x7FC0),
#   0x005A (A4-0x7FA4), 0x0138 (A4-0x7EC6) and any others.
# Range starts at 0x0030 to preserve the F-line vector at 0x002C-0x002F.
# Extended to 0x01FF to cover 0x0174 (A4-0x7E8A) and 0x019E (A4-0x7E60) —
# both called unconditionally by 0x0688 and above the original 0x013F ceiling.
_stub_start = 0x0030
_stub_end   = 0x0200
cpu.mem_write(_stub_start, b"\x4e\x75" * ((_stub_end - _stub_start) // 2))
P(f"  Blanket-stubbed 0x{_stub_start:04X}-0x{_stub_end - 1:04X} → RTS "
  f"(covers all A4-relative OS call targets)")

# NOTE: 0x0B210 is tst.b (a0,d0.l) — mid-function instruction; do NOT stub here.
# The earlier data-fault at 0xFFFE0000 was caused by A4 corruption from 0x003E;
# with the blanket stub, A4 stays valid and 0xB210 should execute normally.

# ── Restore board state (init may clobber it) ─────────────────────────────────
bridge.write_position("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
bridge.set_computer_color(0)
cpu.mem_write(0x025C, b"\x00"); cpu.mem_write(0x025D, b"\x00"); cpu.mem_write(0x024F, b"\x00")
cpu.mem_write(0x0331C, b"\x00\x00")   # current_turn = 0 (White = computer)
cpu.mem_write(0x024E, b"\x00")         # reset ai_state

# ── Override player type so outer_driver inner loop runs ──────────────────────
# outer_driver loops while player_type[current_turn] == 1 (human).
# Temporarily set player_type[0] = 1 so the loop runs long enough for the search.
# Iteration 1: phase0_init (init search).  Iter 2+: phase1_search (minimax steps).
PLAYER_TYPE_ADDR0 = PLAYER_TYPE_BASE         # M[0x07D4]
cpu.mem_write(PLAYER_TYPE_ADDR0, b"\x00\x01")  # player_type[0] = 1 (human)
P(f"  Set player_type[0]=1 (forces outer_driver inner loop)")

# move_state = 2 (game in progress, AI to move) — required by outer_driver
MOVE_STATE_ADDR = A4 - 0x35A4  # 0x4A5A
cpu.mem_write(MOVE_STATE_ADDR, b"\x00\x02")
P(f"  Set move_state=2")

# Force AI path: M[0x3660]=1 (AI vs human flag), M[0x3668]=0 (main eval path).
# phase1_search at 0x0830A tests tst.b M[0x3668]: if non-zero → alternative path
# (no per_piece_eval). If zero → checks player colors. With M[0x3660]=1 and
# M[0x3668]=0, phase1_search reaches per_piece_eval at 0x08332 or 0x08342.
cpu.mem_write(ADDR_3660, b"\x00\x01")   # M[0x3660] = 1
cpu.mem_write(ADDR_3668, b"\x00\x00")   # M[0x3668] = 0
P(f"  Force AI path: M[0x3660]=1, M[0x3668]=0")

F_LINE_COUNT[0] = 0   # reset for the search run

# Reset stack
sp = STACK_TOP - 4
cpu.mem_write(sp, struct.pack(">I", SENTINEL))
cpu.reg_write("A7", sp)
cpu.reg_write("A4", A4)

# ── Run outer_driver loop ──────────────────────────────────────────────────────
# outer_driver dispatches: phase_state=0→phase0_init, 1→phase1_search, 2→phase2
# With player_type[0]=1 the inner loop keeps iterating until move_state != 2.
# Phase0_init initialises the search; phase1_search evaluates pieces; phase2
# outputs the best move and clears move_state.
P(f"\nRunning outer_driver (0x{AI_OUTER_DRIVER:X}) search loop...")
try:
    cpu.emu_start(AI_OUTER_DRIVER, until=SENTINEL, count=100_000_000)
    P("outer_driver returned (hit SENTINEL).")
except Exception as e:
    P(f"outer_driver error: {e}")

# ── State after run ───────────────────────────────────────────────────────────
PHASE_STATE_ADDR = A4 - 0x35A2   # 0x4A5C
MOVE_STATE_ADDR2 = A4 - 0x35A4   # 0x4A5A
CURRENT_TURN_ADDR = 0x0331C
PIECE_COUNTER_ADDR = A4 - 0x4CDE  # 0x3320
ADDR_3660_v = struct.unpack(">H", bytes(cpu.mem_read(ADDR_3660, 2)))[0]
ADDR_3668_v = struct.unpack(">H", bytes(cpu.mem_read(ADDR_3668, 2)))[0]
phase_state = struct.unpack(">H", bytes(cpu.mem_read(PHASE_STATE_ADDR, 2)))[0]
move_state_v = struct.unpack(">H", bytes(cpu.mem_read(MOVE_STATE_ADDR2, 2)))[0]
current_turn = struct.unpack(">H", bytes(cpu.mem_read(CURRENT_TURN_ADDR, 2)))[0]
piece_ctr    = struct.unpack(">h", bytes(cpu.mem_read(PIECE_COUNTER_ADDR, 2)))[0]
pt0 = struct.unpack(">H", bytes(cpu.mem_read(PLAYER_TYPE_BASE, 2)))[0]
pt1 = struct.unpack(">H", bytes(cpu.mem_read(PLAYER_TYPE_BASE + 2, 2)))[0]
P(f"\nPost-run state:")
P(f"  phase_state={phase_state}  move_state={move_state_v}  current_turn={current_turn}")
P(f"  piece_counter={piece_ctr}  player_type[0]={pt0}  player_type[1]={pt1}")
P(f"  M[0x3660]={ADDR_3660_v}  M[0x3668]={ADDR_3668_v}")

# ── Results ────────────────────────────────────────────────────────────────────
P(f"\nDriver entries={DRIVER_ENTRIES[0]}  phase1_entries={PHASE1_COUNT[0]}")
P(f"minimax_calls={MINIMAX_COUNT[0]:,}  ai_find_calls={AI_FIND_COUNT[0]:,}")
P(f"F-lines during run: {F_LINE_COUNT[0]:,}")

data017a = bytes(cpu.mem_read(BEST_MOVE_ADDR, 8))
data365a = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
P(f"  M[0x017A] (search best): {data017a.hex()}")
P(f"  M[0x365A] (final output): {data365a.hex()}")

for label, data in [("search M[0x017A]", data017a), ("output M[0x365A]", data365a)]:
    if data != b"\x00" * 8:
        from_sq = struct.unpack(">H", data[0:2])[0]
        to_sq   = struct.unpack(">H", data[2:4])[0]
        flags   = struct.unpack(">H", data[4:6])[0]
        piece   = data[6]; legal = data[7]
        alg = f"{sq88_to_alg(from_sq)}{sq88_to_alg(to_sq)}"
        P(f"\n  [{label}] {alg}  from=0x{from_sq:02X} to=0x{to_sq:02X} "
          f"flags=0x{flags:04X} piece={piece} legal={legal}")
