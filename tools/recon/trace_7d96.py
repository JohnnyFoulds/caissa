"""
Call 0x7D96 directly (board init + piece placement).
Then call 0x995A (rebuild piece lists from board).
Then call 0x7C5A (AI dispatch) with [0x4A5A]=0 to get a move.
Also bypass 0x00E4 (event loop).
"""
import sys, struct, logging, os, re
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types
sys.modules['psutil'] = types.ModuleType('psutil')
logging.disable(logging.CRITICAL)

from Code.Retro.Traps import AmigaTraps
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_WRITE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
A4, BSS_START, BSS_END = 0x7FFE, 0x28D4, 0xAE04
HALT = 0xFFFF0000

# Quick ROM check: piece types at [0x07C2] for each file
md2 = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
print('=== ROM piece-type table at 0x07C2 ===')
for i in range(8):
    w = struct.unpack('>H', code_bytes[0x07C2 + i*2 : 0x07C2 + i*2 + 2])[0]
    lo = w & 0xFF
    print(f'  File {i}: word=0x{w:04X}, lo_byte={lo} → piece_type')

# Make CPU
cpu = Unicorn68k()
cpu.map_region(0x000000, 0x200000)
cpu.map_region(0x200000, 0x300000)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
try: cpu.map_region(HALT & 0xFFFF0000, 0x10000)
except: pass
mapped = set()
def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True
cpu.hook_add(HOOK_MEM_INVALID, inv)
cpu.mem_write(0, code_bytes)
cpu.mem_write(BSS_START, bytes(BSS_END - BSS_START))
cpu._uc.reg_write(mc.UC_M68K_REG_A4, A4)

writes = []
phase = ['7d96']
skipped = [0]

def code_hook(_emu, addr, sz, _u=None):
    # Skip 0x98BE (called from 0x7E2C) if it's Amiga-OS dependent
    # Skip 0x17D2 called from 0x013C (which is called from 0x0138 only)
    # We don't call 0x0138; we call 0x7D96 directly
    pass  # no special handling needed for 7D96 path

# Bypass 0x6712 (unknown, might need Amiga OS), 0x98BE (graphics?), 0x17D2 (event)
BYPASSES = {
    0x98BE: 'graphics init 0x98BE',
    0x6712: 'game setup 0x6712',
}

def code_hook2(_emu, addr, sz, _u=None):
    if addr in BYPASSES:
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        skipped[0] += 1
        return
    # Bypass 0x00E4 (event check) when running AI
    if addr == 0x00E4 and phase[0] == 'ai':
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        return
    # Halt if we're in AI phase and executing too long
    if phase[0] == 'ai':
        pass  # let it run

cpu.hook_add(HOOK_CODE, code_hook2)

def write_hook(_emu, _type, addr, sz, val, _u=None):
    if BSS_START <= addr < BSS_END:
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        writes.append((addr, sz, val & 0xFFFFFFFF, pc, phase[0]))

cpu.hook_add(HOOK_MEM_WRITE, write_hook)

# ─── STEP 1: run 0x7D96 to init board ───────────────────────────────────────
print('\n=== STEP 1: Run 0x7D96 (board init) ===')
sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)

try:
    cpu.emu_start(0x7D96, until=HALT, count=100000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT != pc: print(f'Step 1 exception: {e} at PC=0x{pc:04X}')

print(f'7D96 complete. BSS writes: {len(writes)}, bypasses: {skipped[0]}')
brd_writes = [w for w in writes if 0x30F4 <= w[0] < 0x30F4 + 0x200]
print(f'Board ([0x30F4]) writes: {len(brd_writes)}')

# ─── STEP 2: run 0x995A to rebuild piece lists ──────────────────────────────
print('\n=== STEP 2: Run 0x995A (rebuild piece lists) ===')
phase[0] = '995a'
prev_count = len(writes)
sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)
try:
    cpu.emu_start(0x995A, until=HALT, count=100000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT != pc: print(f'Step 2 exception: {e} at PC=0x{pc:04X}')

new_writes = writes[prev_count:]
print(f'995A complete. New BSS writes: {len(new_writes)}')
for addr, sz, val, pc, p in new_writes[:20]:
    rel = -(A4 - addr) if addr < A4 else (addr - A4)
    print(f'  [0x{addr:04X}] A4{rel:+X}  sz={sz}  val=0x{val:08X}  pc=0x{pc:04X}')

# ─── STEP 3: init move table at 0x3322 ──────────────────────────────────────
print('\n=== STEP 3: Init move table ===')
# [0x3322] = move table: {count=0, capacity=0x400}
cpu.mem_write(0x3322, struct.pack('>HH', 0, 0x0400))
cpu.mem_write(0x4A5A, struct.pack('>H', 0))   # AI phase = 0 (movegen)
cpu.mem_write(0x331C, struct.pack('>H', 0))   # turn = white
cpu.mem_write(0x331E, struct.pack('>H', 0))   # color = white
cpu.mem_write(0x3320, struct.pack('>H', 0))   # depth = 0
cpu.mem_write(0x12B6, struct.pack('>H', 0))   # game active = 0

# ─── STEP 4: run AI ─────────────────────────────────────────────────────────
print('\n=== STEP 4: Run AI (0x7C5A) ===')
phase[0] = 'ai'
sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)
try:
    cpu.emu_start(0x7C5A, until=HALT, count=500000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT != pc: print(f'Step 4 exception: {e} at PC=0x{pc:04X}')

print('\n=== Board state [0x30F4] after setup ===')
# Print the 8x8 board in 0x88 format
for rank in range(7, -1, -1):
    row = []
    for file in range(8):
        sq = rank * 16 + file  # 0x88 square
        addr = 0x30F4 + sq * 4
        data = bytes(cpu.mem_read(addr, 4))
        ptype = data[0]
        color = data[1]
        if ptype == 0:
            row.append('.')
        else:
            syms = {1:'K', 2:'Q', 3:'R', 4:'B', 5:'N', 6:'P'}
            syms2 = {1:'k', 2:'q', 3:'r', 4:'b', 5:'n', 6:'p'}
            sym = (syms if color==0 else syms2).get(ptype, f'?{ptype}')
            row.append(sym)
    print(f'  rank {rank+1}: {" ".join(row)}')

print('\n=== Key state after 0x7D96 + 0x995A ===')
for label, addr, sz in [
    ('[0x3318] white cnt', 0x3318, 2),
    ('[0x331A] black cnt', 0x331A, 2),
    ('[0x331C] turn',      0x331C, 2),
    ('[0x4A5A] AI phase',  0x4A5A, 2),
    ('[0x3322] move tbl',  0x3322, 8),
    ('[0x365A] best move', 0x365A, 8),
]:
    data = bytes(cpu.mem_read(addr, sz))
    vals = struct.unpack(f'>{sz//2}H', data) if sz % 2 == 0 else (data,)
    print(f'  {label}: {data.hex()} {list(vals)}')

# Decode best move
bm = bytes(cpu.mem_read(0x365A, 8))
from_sq = struct.unpack('>H', bm[0:2])[0]
to_sq   = struct.unpack('>H', bm[2:4])[0]
print(f'\n=== Best move raw: from=0x{from_sq:04X} to=0x{to_sq:04X} ===')

def sq88_to_uci(sq):
    rank = sq >> 4
    file = sq & 0x0F
    if rank > 7 or file > 7: return f'?({sq:#x})'
    return chr(ord('a') + file) + str(rank + 1)

if from_sq <= 0x77 and to_sq <= 0x77 and (from_sq & 0x88) == 0 and (to_sq & 0x88) == 0:
    print(f'  UCI: {sq88_to_uci(from_sq)}{sq88_to_uci(to_sq)}')
else:
    print(f'  Not valid 0x88 squares. Raw: {bm.hex()}')
