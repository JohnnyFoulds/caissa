#!/usr/bin/env python3
"""
Find where the AI stores the FROM/TO squares by monitoring ALL writes during
Phase0's alpha-beta search and dumping non-zero addresses after the search.
"""
import sys, struct, types, importlib.util, collections
sys.path.insert(0, "bin")
import unicorn, unicorn.m68k_const as m68k

_code_pkg = types.ModuleType('Code'); _code_pkg.__path__ = ['bin/Code']; sys.modules['Code'] = _code_pkg
_retro_pkg = types.ModuleType('Code.Retro'); _retro_pkg.__path__ = ['bin/Code/Retro']; sys.modules['Code.Retro'] = _retro_pkg
def _load(dotpath, filepath):
    spec = importlib.util.spec_from_file_location(dotpath, filepath)
    mod = importlib.util.module_from_spec(spec); sys.modules[dotpath] = mod
    spec.loader.exec_module(mod); return mod
_load('Code.Retro.Types', 'bin/Code/Retro/Types.py')
_load('Code.Retro.Errors', 'bin/Code/Retro/Errors.py')
Manifest = _load('Code.Retro.Manifest', 'bin/Code/Retro/Manifest.py')
Rom = _load('Code.Retro.Rom', 'bin/Code/Retro/Rom.py')

default_rom_path = Manifest.default_rom_path
parse_amiga_hunk = Rom.parse_amiga_hunk

rom_data = open(default_rom_path(), "rb").read()
regions = parse_amiga_hunk(rom_data)
A4 = 0x7FFE
CHIP, CHIPSIZE = 0, 0x200000
STACK_TOP, SENTINEL = 0x1F0000, 0xFFFF0000
EXEC_BASE, LIB_RANGE = 0x800000, 0x040000
ALLOC_POOL = 0x200000
SCRATCH_BUF = ALLOC_POOL + 0x50000

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
uc.mem_write(0x36B0, b"\x4e\x73")

bump = [ALLOC_POOL]

def alloc_hook(emu, addr, size, _):
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

# Phase 1: startup
uc.mem_write(0x00164, b"\x4e\x75")
uc.mem_write(0x0015C, b"\x4e\x75")
uc.mem_write(0x0015A, b"\x4e\x75")
for addr in (0x025C, 0x025D, 0x024F, 0x024E): uc.mem_write(addr, b"\x00")
uc.mem_write(0x01152, b"\x00\x00\x00\x00")
uc.mem_write(0x000C2, b"\x4e\x75")

sp0 = STACK_TOP - 4
uc.mem_write(sp0, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp0)
uc.reg_write(m68k.UC_M68K_REG_A6, EXEC_BASE)

h_code = uc.hook_add(unicorn.UC_HOOK_CODE, alloc_hook)
crash = []
def _startup_fault(e,a,ad,s,v,u): crash.append(ad); e.emu_stop(); return False
h_fault = uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, _startup_fault)
try:
    uc.emu_start(0x005A, SENTINEL, count=500_000_000)
except Exception:
    pass
uc.hook_del(h_code)
uc.hook_del(h_fault)

# Phase 2: position setup
def sq88(f, r): return r * 16 + f
def make_pt_entry(sq, color, pt):
    # PT layout (confirmed by reversing fn_0x0D700 at 0x0D77A):
    # offset 0 (word): sq  — initial/candidate square
    # offset 2 (word): sq  — FROM sq read by move generator (NOT color!)
    # offset 4 (word): 0   — scratch, cleared by fn_0x0D45A
    # offset 6 (byte): pt  — piece type checked by fn_0x0C604 and set by BOARD[sq*4]
    # offset 7 (byte): 0
    e = bytearray(8)
    struct.pack_into(">H", e, 0, sq)
    struct.pack_into(">H", e, 2, sq)   # FROM sq, not color
    e[6] = pt
    return bytes(e)

PT_BASE = 0x03322
pt_pieces = [
    (sq88(0,7),1,2),(sq88(1,7),1,3),(sq88(2,7),1,4),(sq88(3,7),1,5),(sq88(4,7),1,1),(sq88(5,7),1,4),(sq88(6,7),1,3),(sq88(7,7),1,2),
    (sq88(0,6),1,6),(sq88(1,6),1,6),(sq88(2,6),1,6),(sq88(3,6),1,6),(sq88(4,6),1,6),(sq88(5,6),1,6),(sq88(6,6),1,6),(sq88(7,6),1,6),
    (sq88(0,0),0,2),(sq88(1,0),0,3),(sq88(2,0),0,4),(sq88(3,0),0,5),(sq88(4,0),0,1),(sq88(5,0),0,4),(sq88(6,0),0,3),(sq88(7,0),0,2),
    (sq88(0,1),0,6),(sq88(1,1),0,6),(sq88(2,1),0,6),(sq88(3,1),0,6),(sq88(4,1),0,6),(sq88(5,1),0,6),(sq88(6,1),0,6),(sq88(7,1),0,6),
]
pt_data = bytearray(105 * 8)
for i,(sq,col,pt) in enumerate(pt_pieces):
    pt_data[i*8:(i+1)*8] = make_pt_entry(sq,col,pt)
uc.mem_write(PT_BASE, bytes(pt_data))
# PT[104] = search slot: pre-populate with e7 black pawn so fn_0DAF2 finds a valid sq
uc.mem_write(PT_BASE + 104*8, make_pt_entry(sq88(4,6), 1, 6))
uc.mem_write(0x0077A, make_pt_entry(sq88(4,6), 1, 6))
uc.mem_write(0x03320, struct.pack(">H", 0xFFFF))

PE_BASE = 0x0892
pe_pieces = [(sq,col,pt) for sq,col,pt in pt_pieces if col==1]
for i,(sq,col,pt) in enumerate(pe_pieces):
    pe = bytearray(32)
    struct.pack_into(">H", pe, 0, sq)
    struct.pack_into(">H", pe, 2, i)
    pe[0x0A] = pt
    nxt = (PE_BASE+(i+1)*32) if i < len(pe_pieces)-1 else 0
    struct.pack_into(">I", pe, 0x1C, nxt)
    uc.mem_write(PE_BASE+i*32, bytes(pe))

BOARD = bytearray(128*4)
def set_sq(sq,pt,col): BOARD[sq*4]=pt; BOARD[sq*4+1]=col
set_sq(sq88(0,0),2,0);set_sq(sq88(1,0),3,0);set_sq(sq88(2,0),4,0)
set_sq(sq88(3,0),5,0);set_sq(sq88(4,0),1,0);set_sq(sq88(5,0),4,0)
set_sq(sq88(6,0),3,0);set_sq(sq88(7,0),2,0)
for f in range(8): set_sq(sq88(f,1),6,0)
for f in range(8): set_sq(sq88(f,6),6,1)
set_sq(sq88(0,7),2,1);set_sq(sq88(1,7),3,1);set_sq(sq88(2,7),4,1)
set_sq(sq88(3,7),5,1);set_sq(sq88(4,7),1,1);set_sq(sq88(5,7),4,1)
set_sq(sq88(6,7),3,1);set_sq(sq88(7,7),2,1)
uc.mem_write(0x030F4, bytes(BOARD))

KING_TABLE = bytearray(64)
KING_TABLE[0] = sq88(4,0)+1; KING_TABLE[32] = sq88(4,7)+1
uc.mem_write(0x032D4, bytes(KING_TABLE))
# [0x007A2..07B1]: static ROM constants (code-as-data overlap), read by fn_0x09FC4 and fn_0x9DD0.
# Do NOT zero — ROM bytes ARE the correct values for this table.
uc.mem_write(0x048BA, struct.pack(">H",0))
uc.mem_write(0x048BC, struct.pack(">H",0))
for a in (0x04A50,0x04A54,0x04A56,0x04A58,0x048B0,0x048B2,0x048B4,0x048B6,0x048B8,0x04ADE,0x04DB0):
    uc.mem_write(a, b"\x00\x00")
uc.mem_write(0x007D2, b"\x00\x00")
uc.mem_write(0x04DBE, struct.pack(">I",0))
uc.mem_write(0x048BE, b"\x00"*8)

uc.mem_write(0x085A2, b"\x60\x00\x00\xae")
uc.mem_write(0x0858C, b"\x4e\x71\x4e\x71")
uc.mem_write(0x0C1AC, b"\x4e\x71\x4e\x71")
uc.mem_write(0x0C2C8, b"\x4e\x71\x4e\x71")
uc.mem_write(0x0CAFE, b"\x4e\x71\x4e\x71")  # NOP: jsr -$7f74(a4) → [0x008A] corrupts stack via addq.w #8,a7
uc.mem_write(0x0000C, b"\x72\x01\x4e\x75")  # fn_0x000C: moveq #1,d0; rts — timer stub (starts with illegal instr)
uc.mem_write(0x082E2, b"\x4e\x71\x4e\x71")
uc.mem_write(0x00036, b"\x4e\x75"); uc.mem_write(0x0003C, b"\x4e\x75")
uc.mem_write(0x00138, b"\x4e\x75"); uc.mem_write(0x00034, b"\x4e\x75")
uc.mem_write(0x0003A, b"\x4e\x75"); uc.mem_write(0x00136, b"\x4e\x75")
uc.mem_write(0x0013C, b"\x4e\x75"); uc.mem_write(0x0013E, b"\x4e\x75")
uc.mem_write(0x0001E, b"\x4e\x75"); uc.mem_write(0x0001C, b"\x4e\x75")
uc.mem_write(0x04AA8, struct.pack(">I", SCRATCH_BUF))
uc.mem_write(0x04AA6, struct.pack(">I", SCRATCH_BUF))
uc.mem_write(0x04A5A, struct.pack(">H",2))
uc.mem_write(0x012B6, struct.pack(">H",0))
uc.mem_write(0x04A5C, struct.pack(">H",0))
uc.mem_write(0x04A5E, struct.pack(">H",0))
uc.mem_write(0x01152, struct.pack(">I", PE_BASE))
# [0x0782..0791]: direction-vector table, single-step moves (fn_0x0D758 first loop, [A4-0x787C])
uc.mem_write(0x0782, struct.pack(">8h",+0x10,-0x10,+1,-1,+0x11,-0x11,+0x0F,-0x0F))
# [0x0792..07A1]: direction-vector table, double-step moves (fn_0x0D758 second loop, [A4-0x786C])
uc.mem_write(0x0792, struct.pack(">8h",+0x20,-0x20,+2,-2,+0x22,-0x22,+0x1E,-0x1E))
# [0x07A2..07A5]: pawn direction validation table (fn_0x0D45A at 0x0D4A2, [A4-0x785C])
# index 0=white (+0x10 forward), index 1=black (-0x10 forward)
uc.mem_write(0x07A2, struct.pack(">hh",+0x10,-0x10))
uc.mem_write(0x3314, b"\x00"*(0x3322-0x3314))
# NOTE: do NOT clear 0x3722..0x3A00 — ROM bytes there are the move-gen direction table
uc.mem_write(0x07C2, struct.pack(">8H",2,3,4,5,1,4,3,2))
uc.mem_write(0x03318, struct.pack(">H", sq88(4,0)))
uc.mem_write(0x0331A, struct.pack(">H", sq88(4,7)))
uc.mem_write(0x0331E, struct.pack(">H",1))  # Black = current side to move (root)
uc.mem_write(0x0331C, struct.pack(">H",0))  # White = opponent (fn_0xC91A swaps per depth)
uc.mem_write(0x07D4, struct.pack(">H",1)); uc.mem_write(0x07D6, struct.pack(">H",1))

# Snapshot chip memory BEFORE Phase0
snapshot_before = bytes(uc.mem_read(0, 0x10000))

# Track ALL writes to chip memory (0x0000..0x10000) during dispatcher run.
# last_write[addr] = (size, val, pc) — only the final write to each address.
last_write = {}

move_output_trace = []  # ALL writes to [0x0774..0x0790] and [0x4960..0x4990]

def write_hook(emu, access, addr, size, val, _):
    if 0 <= addr < 0x10000 or 0x200000 <= addr < 0x300000:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        last_write[addr] = (size, val, pc)
        if 0x0774 <= addr <= 0x0790 or 0x4960 <= addr <= 0x4990 or 0x3660 <= addr <= 0x3672:
            move_output_trace.append((pc, addr, size, val))

last_exec_pc = [0]
_pc_ring = [0] * 32
_pc_ring_i = [0]

_DECOMP_OUTER_RTS = 0x079B2   # UNLK A5 + RTS exit of the outer decompressor fn

def _pc_track(emu, addr, size, _):
    last_exec_pc[0] = addr
    _pc_ring[_pc_ring_i[0] & 31] = addr
    _pc_ring_i[0] += 1
    # Outer decompressor function exits here — install all accumulated bytes.
    if addr == _DECOMP_OUTER_RTS and not _decomp_done[0] and _decomp_pending_final:
        _decomp_install()
    if addr == SENTINEL:
        emu.emu_stop()
    if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
        off = addr - EXEC_BASE
        if off == -0xC6:
            d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
            emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
            bump[0] += max((d0+7)&~7, 8)
        elif off == -0x198:
            emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)

def _invalid_insn_hook(emu, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    b = bytes(emu.mem_read(pc, 4))
    print(f"  INVALID INSN at 0x{pc:05X}: {b.hex()}")
    emu.emu_stop()
    return False

fault_writes = []
def fault_hook(emu, access, addr, size, val, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    fault_writes.append((pc, addr))
    if access == unicorn.UC_MEM_FETCH_UNMAPPED:
        emu.emu_stop(); return False  # bad code fetch — always fatal
    page = addr & ~0xFFF
    try:
        uc.mem_map(page, 0x1000)
    except Exception:
        pass
    return True

uc.hook_add(unicorn.UC_HOOK_CODE, _pc_track)
uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_hook)
uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, fault_hook)
uc.hook_add(unicorn.UC_HOOK_INSN_INVALID, _invalid_insn_hook)

# ── Self-modifying decompressor protection ─────────────────────────────────
# fn_0x079B4..0x079ED is a "lazy decompressor": the first call decompresses
# game code into its own address range, replacing itself with the real function.
# On real 68000 hardware this works because the prefetch queue keeps the loop
# body live; Unicorn has no prefetch, so modified bytes are fetched immediately
# and the loop body is destroyed mid-execution.
#
# Fix:
#   1. Save originals of the loop body (0x079B4..0x079ED) before Phase0.
#   2. MEM_WRITE hook: for writes into that range, record the intended byte but
#      ALSO queue a restoration so the loop body stays intact.
#   3. CODE hook (range-limited): at every instruction inside the loop, flush
#      any queued restores so the CPU always sees the original loop code.
#   4. When D6 == 0 at the loop header (exit condition), install all the saved
#      decompressed bytes and retire both hooks.
# ───────────────────────────────────────────────────────────────────────────
DECOMP_LOOP = 0x079B4          # tst.l d6 / beq.b exit
DECOMP_END  = 0x07A80          # wide enough to cover outer decompressor output
_decomp_backup = bytes(uc.mem_read(DECOMP_LOOP, DECOMP_END - DECOMP_LOOP))
_decomp_pending_orig  = {}     # addr -> original byte (queued for restore)
_decomp_pending_final = {}     # addr -> intended byte (to install at exit)
_decomp_started = [False]
_decomp_done    = [False]
_decomp_write_log = []         # first 32 writes for diagnostic

def _decomp_write_guard(emu, access, addr, size, val, _):
    if _decomp_done[0]:
        return
    # Check if any written bytes overlap the decompressor range
    end_addr = addr + size
    if end_addr <= DECOMP_LOOP or addr >= DECOMP_END:
        return
    _decomp_started[0] = True
    # Extract individual bytes: 68000 is big-endian so byte at addr+k is
    # (val >> (8*(size-1-k))) & 0xFF
    for k in range(size):
        ba = addr + k
        if DECOMP_LOOP <= ba < DECOMP_END:
            bv = (val >> (8 * (size - 1 - k))) & 0xFF
            if ba not in _decomp_pending_orig:
                _decomp_pending_orig[ba] = _decomp_backup[ba - DECOMP_LOOP]
            _decomp_pending_final[ba] = bv
    if len(_decomp_write_log) < 32:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        a1 = emu.reg_read(m68k.UC_M68K_REG_A1)
        d6 = emu.reg_read(m68k.UC_M68K_REG_D6)
        _decomp_write_log.append((pc, addr, size, val, a1, d6))

def _decomp_install():
    # The outer decompressor just ran and wrote its output into DECOMP_LOOP+.
    # We don't want that output — Phase1 startup already installed the correct
    # decompressed inner-function bytes.  Restore the Phase1 snapshot.
    uc.mem_write(DECOMP_LOOP, _decomp_backup)
    _decomp_pending_final.clear()
    _decomp_done[0] = True
    print(f"  [decomp] Restored Phase1 snapshot ({len(_decomp_backup)} bytes) at "
          f"0x{DECOMP_LOOP:05X}..0x{DECOMP_LOOP+len(_decomp_backup)-1:05X}")

_guard_log = []  # first 10 code-guard restore events

def _decomp_code_guard(emu, addr, size, _):
    if _decomp_done[0]:
        return
    # Flush restorations: keep inner loop body intact so the CPU always sees
    # the original instructions (not the decompressed bytes being written in).
    if _decomp_pending_orig:
        if len(_guard_log) < 10:
            snap = {a: (emu.mem_read(a, 1)[0], b) for a, b in _decomp_pending_orig.items()
                    if abs(a - 0x079CE) <= 4}
            if snap:
                _guard_log.append((addr, dict(snap)))
        for a, b in list(_decomp_pending_orig.items()):
            emu.mem_write(a, bytes([b]))
        _decomp_pending_orig.clear()
    # Exit detection is in _pc_track (addr == 0x079B2 = RTS of outer function).

uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, _decomp_write_guard)
uc.hook_add(unicorn.UC_HOOK_CODE, _decomp_code_guard,
            begin=DECOMP_LOOP, end=0x07A5F)   # covers inner loop + outer loop
# ─────────────────────────────────────────────────────────────────────────────

uc.reg_write(m68k.UC_M68K_REG_A4, A4)

# Pre-compute ROM load offset so we can restore code corrupted by the
# move-score table overlap (A4+0x020C = 0x820A falls inside the dispatcher
# entry at 0x081DC).  Phase0 writes score data there; Phase1 needs clean code.
_rom_region = regions[0]
def restore_rom(start, length):
    """Write original ROM bytes back to emulated memory."""
    rom_off = _rom_region.offset + (start - _rom_region.load_address)
    uc.mem_write(start, rom_data[rom_off:rom_off + length])

# fn_0x81DC is a multi-step state machine: one phase per call.
# Phase0 sets [0x04A5C]=1; Phase1 (which calls fn_0x94D8 to commit the move)
# clears [0x04A5C]=0.  Loop until Phase1 has run.
# Phase0 via dispatcher (0x081DC): runs the alpha-beta search, stores FROM in
# [0x048BE], sets [0x04A5C]=1.  fn_0x8820/fn_0x8D32 corrupt the dispatcher's
# own jump table at 0x08200, so the internal loop never reaches Phase1.
# Solution: call Phase1 (0x082DE) DIRECTLY after Phase0.  Phase1 has its own
# link/unlk frame and doesn't need the outer dispatcher frame.
print("Step 1 — Phase0 via dispatcher ...")
sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)
uc.reg_write(m68k.UC_M68K_REG_A4, A4)
try:
    uc.emu_start(0x081DC, SENTINEL, count=300_000_000)
except Exception as e:
    print(f"  Phase0 error: {e}  last_pc=0x{last_exec_pc[0]:05X}")
    n = _pc_ring_i[0]
    ring_pcs = [_pc_ring[(n - 32 + k) & 31] for k in range(32)]
    print(f"  Last 32 PCs: {[hex(p) for p in ring_pcs]}")
    if _decomp_write_log:
        print(f"  Decomp writes ({len(_decomp_write_log)} logged of total):")
        for wpc, waddr, wsz, wval, wa1, wd6 in _decomp_write_log:
            print(f"    PC=0x{wpc:05X} addr=0x{waddr:05X} size={wsz} val={wval:0{wsz*2}X} A1=0x{wa1:05X} D6={wd6:08X}")
    if _guard_log:
        print(f"  Guard restore events near 0x079CE:")
        for gaddr, snap in _guard_log:
            print(f"    at 0x{gaddr:05X}: {' '.join(f'0x{a:05X} was=0x{w:02X} restore=0x{r:02X}' for a,(w,r) in sorted(snap.items()))}")
    b_at_79CE = bytes(uc.mem_read(0x079CE, 4))
    print(f"  Bytes at 0x079CE now: {b_at_79CE.hex()}")
flag0 = struct.unpack(">H", bytes(uc.mem_read(0x04A5C, 2)))[0]
print(f"  Done: PC=0x{uc.reg_read(m68k.UC_M68K_REG_PC):05X}  [0x04A5C]={flag0}")

print("Step 2 — Phase1 directly (0x082DE) ...")
sp = STACK_TOP - 4
uc.mem_write(sp, struct.pack(">I", SENTINEL))
uc.reg_write(m68k.UC_M68K_REG_A7, sp)
uc.reg_write(m68k.UC_M68K_REG_A4, A4)
try:
    uc.emu_start(0x082DE, SENTINEL, count=5_000_000)
except Exception as e:
    print(f"  Phase1 error: {e}  last_pc=0x{last_exec_pc[0]:05X}")
flag1 = struct.unpack(">H", bytes(uc.mem_read(0x04A5C, 2)))[0]
print(f"  Done: PC=0x{uc.reg_read(m68k.UC_M68K_REG_PC):05X}  [0x04A5C]={flag1}")

# Show last writes during dispatcher run to chip memory
# Focus on addresses that got small values consistent with squares (0x00-0x77)
# or flags (0, 1, 2) written by "result-storing" code (PC >= 0x081DC)
print(f"\nAll final writes to chip memory: {len(last_write)} addresses")
# Show writes where the PC was in the dispatcher/Phase0/Phase1 range (0x081DC..0x084C3)
result_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
                 if 0x081DC <= pc <= 0x084C3}
print(f"Writes from dispatcher/Phase0/Phase1 code (0x081DC..0x084C3): {len(result_writes)}")
for addr in sorted(result_writes.keys()):
    sz, val, pc = result_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# Writes from fn_0x94D8 region (0x094D8..0x0A000) — this is the move-commit function
result94d8 = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
              if 0x094D8 <= pc <= 0x0A000}
print(f"\nWrites from fn_0x94D8 region (0x094D8..0x0A000): {len(result94d8)}")
for addr in sorted(result94d8.keys()):
    sz, val, pc = result94d8[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# Also show any chip address that was written with a value that looks like a square (0x00..0x77)
# by any code in the post-search phase (PC in 0x082xx area or 0x083xx area)
print("\nWrites with square-like values (0x00..0x77) anywhere in chip memory:")
for addr in sorted(last_write.keys()):
    sz, val, pc = last_write[addr]
    if sz <= 2 and 0 <= val <= 0x77 and val != 0:
        print(f"  [0x{addr:05X}] sz={sz} val=0x{val:02X}={val} (sq: file={val&0xF} rank={val>>4}) written_by=0x{pc:05X}")

# Candidate result addresses from early recon
print("\nCandidate result addresses:")
for label, addr in [("[0x012C2] FROM?", 0x012C2), ("[0x012C4] TO?", 0x012C4),
                    ("[0x012C0]", 0x012C0), ("[0x012C6]", 0x012C6),
                    ("[0x048BE] FROM piece", 0x048BE), ("[0x048C6] TO piece?", 0x048C6),
                    ("[0x04980] Phase1 copy", 0x04980)]:
    raw = bytes(uc.mem_read(addr, 8 if "piece" in label or "copy" in label else 2))
    print(f"  {label}: {raw.hex()}")

# Compare snapshot
snapshot_after = bytes(uc.mem_read(0, 0x10000))
print("\nChanges in 0x0000..0x10000 after dispatcher run:")
changes = []
for i in range(0, 0x10000, 4):
    b_before = snapshot_before[i:i+4]
    b_after = snapshot_after[i:i+4]
    if b_before != b_after:
        vb = struct.unpack(">I", b_before)[0]
        va = struct.unpack(">I", b_after)[0]
        changes.append((i, vb, va))

print(f"  {len(changes)} addresses changed")
for addr, vb, va in changes:
    print(f"  [0x{addr:05X}] 0x{vb:08X} → 0x{va:08X}")

# Show key state
print(f"\n[0x048BE] (FROM piece): {bytes(uc.mem_read(0x048BE,8)).hex()}")
print(f"[0x03662] (PT[104]):   {bytes(uc.mem_read(0x03662,8)).hex()}")
print(f"[0x03322] (PT[0]):     {bytes(uc.mem_read(0x03322,8)).hex()}")
import struct as _s
pt104 = bytes(uc.mem_read(0x03662, 8))
pt0   = bytes(uc.mem_read(0x03322, 8))
sq104, col104, pt_type104 = _s.unpack(">HHB", pt104[:5])
sq0,   col0,   pt_type0   = _s.unpack(">HHB", pt0[:5])
def sq_name(sq): return "abcdefgh"[sq&0xF] + str((sq>>4)+1) if 0<=sq<=0x77 else f"INVALID({sq:#x})"
print(f"  PT[104]: sq={sq_name(sq104)} color={col104} pt={pt_type104}")
print(f"  PT[0]:   sq={sq_name(sq0)} color={col0} pt={pt_type0}")
# Show any writes TO PT[104] during run
pt104_writes = [(pc, v) for (addr,(sz,v,pc)) in last_write.items()
                if 0x03662 <= addr <= 0x03669]
if pt104_writes:
    print(f"  Writes to PT[104] during run: {pt104_writes}")
if fault_writes:
    print(f"\nFaults ({len(fault_writes)}): {fault_writes[:10]}")

# Scan board for where the black pawn went (pt=6, col=1)
print("\nBoard scan — all squares with black pieces (col=1) after run:")
BOARD_BASE = 0x030F4
board_after = bytes(uc.mem_read(BOARD_BASE, 128*4))
for sq in range(128):
    if sq & 0x88:  # off-board in 0x88 encoding
        continue
    pt  = board_after[sq*4]
    col = board_after[sq*4+1]
    if col == 1 and pt != 0:
        f = sq & 0x0F; r = (sq >> 4)
        name = "abcdefgh"[f] + str(r+1) if f < 8 else f"off{sq:#x}"
        print(f"  sq=0x{sq:02X} ({name}): pt={pt}")

# Scan PT[0..31] for black pawn to find TO square
print("\nPT entries for black pawns after run:")
for i in range(64):
    raw = bytes(uc.mem_read(0x03322 + i*8, 8))
    sq2, col2, pt2 = struct.unpack(">HHB", raw[:5])
    if col2 == 1 and pt2 == 6:
        f = sq2 & 0xF; r = sq2 >> 4
        name = "abcdefgh"[f] + str(r+1) if f < 8 and 0 <= sq2 <= 0x77 else f"0x{sq2:04X}"
        print(f"  PT[{i}]: sq={name}({sq2:#x}) col={col2} pt={pt2}  raw={raw.hex()}")

# Show [0x0077A] — current active piece after Phase1
print(f"\n[0x0077A] active piece after run: {bytes(uc.mem_read(0x0077A,8)).hex()}")
sq_active = struct.unpack(">H", bytes(uc.mem_read(0x0077A, 2)))[0]
print(f"  sq=0x{sq_active:02X} = {sq_name(sq_active)}")

# Show writes from fn_0x9442 (search evaluator, stores best-move result)
search_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
                 if 0x09442 <= pc <= 0x094D7}
print(f"\nWrites from fn_0x9442 search range (0x09442..0x094D7): {len(search_writes)}")
for addr in sorted(search_writes.keys()):
    sz, val, pc = search_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# Show writes from fn_0x0C198 range (0x0C198..0x0DAFF)
c198_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
               if 0x0C198 <= pc <= 0x0DAFF}
print(f"\nWrites from fn_0x0C198 range (0x0C198..0x0DAFF): {len(c198_writes)}")
for addr in sorted(c198_writes.keys()):
    sz, val, pc = c198_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# Show what's at the key search-result area after Phase0
print(f"\nSearch-result area [0x048B0..048D0]:")
raw = bytes(uc.mem_read(0x048B0, 0x20))
for i in range(0, 0x20, 2):
    w = struct.unpack(">H", raw[i:i+2])[0]
    print(f"  [0x{0x048B0+i:05X}] = 0x{w:04X} ({w})")

# Look for TO square: e5=0x44 or e6=0x54 written by any fn
TO_SQ_CANDIDATES = {0x44, 0x54}
print("\nWrites of TO square candidates (e5=0x44 or e6=0x54):")
hits = [(addr, sz, val, pc) for addr, (sz, val, pc) in last_write.items()
        if val in TO_SQ_CANDIDATES and sz <= 2]
for addr, sz, val, pc in sorted(hits, key=lambda x: x[0]):
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:02X} ({val}) written_by=0x{pc:05X}")
if not hits:
    print("  (none found)")

# Also: dump the first 0x20 bytes at [A4-0x3740] = [0x048BE] area (16 bytes for 2 PT entries)
print(f"\n[0x048BE..048D0] raw (FROM piece + next 8 bytes):")
raw2 = bytes(uc.mem_read(0x048BE, 24))
print(f"  {raw2.hex()}")
# decode first entry
sq_f, col_f, pt_f = struct.unpack(">HHB", raw2[:5])
print(f"  FROM: sq=0x{sq_f:02X} col={col_f} pt={pt_f}")
sq_t, col_t, pt_t = struct.unpack(">HHB", raw2[8:13])
print(f"  +8:   sq=0x{sq_t:02X} col={col_t} pt={pt_t}  raw={raw2[8:16].hex()}")

# Dump fn_0x9494 result area: what did the depth-1 search produce?
# [A4-0x4CDE] = [0x3320] = depth counter after run
depth_after = struct.unpack(">H", bytes(uc.mem_read(0x3320, 2)))[0]
print(f"\n[0x3320] depth counter after run: {depth_after} (0x{depth_after:04X})")

# Dump move record buffer area (A4-0x77A2 pointer = [0x085C])
buf_ptr = struct.unpack(">I", bytes(uc.mem_read(0x085C, 4)))[0]
print(f"\nMove buffer ptr [0x085C] = 0x{buf_ptr:08X}")
# The buffer starts at ALLOC_POOL = 0x200000; buf_ptr is current end
# Walk backwards one record (0xE0 bytes) to see last written record
if ALLOC_POOL <= buf_ptr < ALLOC_POOL + 0x100000:
    rec_start = buf_ptr - 0xE0
    print(f"  Last record starts at 0x{rec_start:08X}")
    rec = bytes(uc.mem_read(rec_start, 0x20))
    print(f"  First 0x20 bytes: {rec.hex()}")
    alpha_r, beta_r, ctr_r = struct.unpack(">HHH", rec[:6])
    print(f"  alpha={alpha_r} beta={beta_r} ctr={ctr_r}")
    from_ptr = struct.unpack(">I", rec[12:16])[0]
    print(f"  FROM piece ptr = 0x{from_ptr:08X}")
    if 0 < from_ptr < 0x10000:
        from_raw = bytes(uc.mem_read(from_ptr, 8))
        print(f"  FROM piece: {from_raw.hex()}")

# Dump cc4a writes if any (including ALLOC_POOL writes)
cc4a_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
               if 0x0CC4A <= pc <= 0x0CFFF}
print(f"\nWrites from fn_0xCC4A range (0x0CC4A..0x0CFFF): {len(cc4a_writes)}")
for addr in sorted(cc4a_writes.keys()):
    sz, val, pc = cc4a_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# All writes to ALLOC_POOL area
pool_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
               if 0x200000 <= addr < 0x300000}
print(f"\nWrites to ALLOC_POOL (0x200000..0x2FFFFF): {len(pool_writes)}")
for addr in sorted(pool_writes.keys())[:40]:
    sz, val, pc = pool_writes[addr]
    print(f"  [0x{addr:06X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")
if len(pool_writes) > 40:
    print(f"  ... ({len(pool_writes)-40} more)")

# All writes whose PC is in fn_0xABBE (recursive search)
abbe_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
               if 0x0ABBE <= pc <= 0x0B500}
print(f"\nWrites from fn_0xABBE range (0x0ABBE..0x0B500): {len(abbe_writes)}")
for addr in sorted(abbe_writes.keys()):
    sz, val, pc = abbe_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")

# Trace writes to move-output areas
print(f"\nAll writes to FROM_piece area [0x077A..0x0782] and PT[104] [0x3662..0x3671]:")
print(f"  ({len(move_output_trace)} total writes to watched areas)")
for pc, addr, sz, val in move_output_trace:
    print(f"  PC=0x{pc:05X} → [0x{addr:05X}] sz={sz} val=0x{val:08X}")

# What are ALL addresses written to by Phase0 in range 0x3000..0x4000?
range_writes = {addr: (sz, val, pc) for addr, (sz, val, pc) in last_write.items()
                if 0x3000 <= addr < 0x4000}
print(f"\nAll writes to 0x3000..0x4000: {len(range_writes)} addresses")
for addr in sorted(range_writes.keys()):
    sz, val, pc = range_writes[addr]
    print(f"  [0x{addr:05X}] sz={sz} val=0x{val:08X}  written_by=0x{pc:05X}")
