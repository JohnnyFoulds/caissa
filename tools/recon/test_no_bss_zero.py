"""
Test: load ROM without zeroing BSS (that was destroying the AI engine code).
The BSS range 0x28D4..0xAE04 contains live game code — do NOT zero it.
"""
import sys, struct, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types; sys.modules['psutil'] = types.ModuleType('psutil')
import logging; logging.disable(logging.CRITICAL)
from Code.Retro.Traps import AmigaTraps
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
A4 = 0x7FFE
HALT = 0xFFFF0000

cpu = Unicorn68k()
cpu.map_region(0x000000, 0x200000)
cpu.map_region(0x200000, 0x300000)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
mapped = set()
def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True
cpu.hook_add(HOOK_MEM_INVALID, inv)

# Load ROM WITHOUT zeroing the code region.
# Only zero the board array and game state (data, not code).
cpu.mem_write(0, code_bytes)
# Board [0x30F4]: 128 squares × 4 bytes; ROM has code bytes here, need zeroing for empty board
cpu.mem_write(0x30F4, bytes(128 * 4))
# Piece lists/counts and move table data regions
cpu.mem_write(0x3314, bytes(0x400))   # game state: 0x3314-0x3714
# Also zero some init vars that might contain garbage
cpu.mem_write(0x28D4, bytes(0x200))   # small region at BSS start
cpu._uc.reg_write(mc.UC_M68K_REG_A4, A4)

calls = []
def code_hook(_emu, addr, sz, _u=None):
    if addr in (0x7D96, 0x7E28, 0x7EBA, 0x7ED4, 0x995A, 0x7C5A, 0x7F00):
        calls.append(f'0x{addr:04X}')
    # Bypass graphics/OS calls
    if addr in (0x98BE, 0x6712, 0x0138):
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)

cpu.hook_add(HOOK_CODE, code_hook)

sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)

print('=== STEP 1: Running 0x7D96 (board init) ===')
try:
    cpu.emu_start(0x7D96, until=HALT, count=500000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT: print(f'Exception: {e} at 0x{pc:04X}')

print(f'Functions called: {calls}')

print('\n=== Board [0x30F4] after 0x7D96 ===')
any_piece = False
for rank in range(7, -1, -1):
    row = []
    for file in range(8):
        sq = rank * 16 + file
        addr = 0x30F4 + sq * 4
        data = bytes(cpu.mem_read(addr, 4))
        ptype, color = data[0], data[1]
        if ptype != 0:
            any_piece = True
            syms = {1:'K',2:'Q',3:'R',4:'B',5:'N',6:'P'}
            s = (syms.get(ptype,'?') if color==0 else syms.get(ptype,'?').lower())
            row.append(f'{s}{ptype}/{color}')
        else:
            row.append('.')
    print(f'  r{rank+1}: {" ".join(row)}')

if not any_piece:
    print('  (board empty after 7D96 — trying fallback: manual board setup)')

print('\n=== Key state ===')
for label, addr, sz in [('[0x3318]', 0x3318, 2), ('[0x331A]', 0x331A, 2),
                         ('[0x331C]', 0x331C, 2), ('[0x3320]', 0x3320, 2),
                         ('[0x4A5A]', 0x4A5A, 2)]:
    d = bytes(cpu.mem_read(addr, sz))
    v = struct.unpack('>H', d)[0]
    print(f'  {label} = 0x{v:04X}')

# Now run the AI
calls.clear()
print('\n=== STEP 2: Run AI (keeping [0x4A5A]=2 set by 7D96 = full search) ===')
# Do NOT reset [0x4A5A] — 0x7D96 set it to 2 (full search mode)

sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)

# Also bypass 0x00E4 (event loop check inside AI)
def ai_hook(_emu, addr, sz, _u=None):
    if addr in (0x7D96, 0x7E28, 0x7EBA, 0x7ED4, 0x995A, 0x7C5A, 0x7F00, 0x7F96, 0x81DC):
        calls.append(f'0x{addr:04X}')
    if addr in (0x00E4, 0x98BE, 0x6712, 0x0138):
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)

cpu.hook_add(HOOK_CODE, ai_hook)

print('=== STEP 3: Running 0x7C5A (AI dispatch, [0x4A5A]=2 = full search) ===')
try:
    cpu.emu_start(0x7C5A, until=HALT, count=5000000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT: print(f'Exception: {e} at 0x{pc:04X}')

print(f'AI functions called (first 20): {calls[:20]}')

# Read the entire move table area around [0x365A]
print('\n=== Move table dump around [0x365A] ===')
bm_region = bytes(cpu.mem_read(0x3650, 32))
for i in range(0, 32, 8):
    entry = bm_region[i:i+8]
    addr = 0x3650 + i
    print(f'  [0x{addr:04X}]: {entry.hex()}')

# Try all possible byte offsets for (from_sq, to_sq)
bm_full = bytes(cpu.mem_read(0x3322, 0x400))
print('\n=== Scanning move table for valid 0x88 moves ===')
found = []
for i in range(0, 0x400-3, 2):
    f = bm_full[i]
    t = bm_full[i+1]
    if (f & 0x88) == 0 and (t & 0x88) == 0 and f != 0 and t != 0:
        sq_f = 0x3322 + i
        found.append((sq_f, f, t))

print(f'Found {len(found)} valid (from,to) pairs')
for addr, f, t in found[:20]:
    r1,c1 = f>>4, f&0xF
    r2,c2 = t>>4, t&0xF
    uci = f'{chr(97+c1)}{r1+1}{chr(97+c2)}{r2+1}'
    print(f'  [0x{addr:04X}]: from=0x{f:02X}={chr(97+c1)}{r1+1} to=0x{t:02X}={chr(97+c2)}{r2+1} → {uci}')

# Also check key state after AI
print('\n=== Key state after AI ===')
for label, addr in [('[0x365A]', 0x365A), ('[0x4A5A]', 0x4A5A),
                     ('[0x3318]', 0x3318), ('[0x331A]', 0x331A)]:
    d = bytes(cpu.mem_read(addr, 4))
    print(f'  {label}: {d.hex()}')
