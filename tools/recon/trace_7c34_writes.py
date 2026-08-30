"""
Call 0x7C34 (AI init) and 0x7D96 (piece table init) directly with clean state.
Trace ALL BSS writes to find what gets initialized and where the board goes.
Also scan ROM for starting-position piece data patterns.
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
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_WRITE, HOOK_MEM_READ, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
cs = 40
code_bytes = rom_data[cs:]
A4 = 0x7FFE
BSS_START, BSS_END = 0x28D4, 0xAE04
HALT = 0xFFFF0000

# ─── ROM scan for starting-position patterns ─────────────────────────────────
print('=== ROM scan for starting-position piece tables ===')
# Standard starting position in various encodings
# Looking for rook(4)/knight(2)/bishop(3)/queen(5)/king(6) pattern
# Try offsets 0..10 and colors 0/1
for piece_enc in [(1,2,3,4,5,6), (0,1,2,3,4,5), (2,3,4,5,6,7)]:
    P,K,B,R,Q,Kg = piece_enc
    row1 = bytes([R,K,B,Q,Kg,B,K,R])  # rank 1: RNBQKBNR
    found = False
    for i in range(len(code_bytes)-8):
        if code_bytes[i:i+8] == row1:
            print(f'  Pawn={P} Knight={K} Bishop={B} Rook={R} Queen={Q} King={Kg}')
            print(f'  Found RNBQKBNR at ROM offset 0x{i:05X}')
            found = True
    if found:
        break
else:
    print('  No RNBQKBNR pattern found. Trying other patterns...')
    # Look for any 8-byte pattern with values 1-6 in right arrangement
    for i in range(len(code_bytes)-64):
        chunk = code_bytes[i:i+8]
        vals = set(chunk)
        if len(vals) >= 4 and max(chunk) <= 10 and min(chunk) >= 1:
            if chunk[0] == chunk[7] and chunk[1] == chunk[6]:  # symmetric
                print(f'  Symmetric 8-byte at 0x{i:05X}: {list(chunk)}')

# Also look for any runs of small values (1-6) at BSS-sized chunks in ROM
print('\nLooking for rank patterns (values 1-6 only) at 8-byte boundaries:')
count = 0
for i in range(0, min(len(code_bytes), 0x12000), 8):
    chunk = code_bytes[i:i+8]
    if all(1 <= b <= 6 for b in chunk) and len(set(chunk)) >= 3:
        print(f'  0x{i:05X}: {list(chunk)}')
        count += 1
        if count > 10: break

# ─── Emulator: trace 0x7C34 writes ───────────────────────────────────────────
print('\n=== Emulator: trace BSS writes from 0x7C34 (AI init) ===')

def make_and_setup():
    cpu = Unicorn68k()
    cpu.map_region(0x000000, 0x200000)
    cpu.map_region(0x200000, 0x300000)
    traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
    try: cpu.map_region(0xFFFF0000, 0x10000)
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
    sp = 0x1EFF00 - 4
    cpu.mem_write(sp, struct.pack('>I', HALT))
    cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)
    return cpu

cpu = make_and_setup()
writes = []
calls = []

def code_hook(_emu, addr, sz, _u=None):
    fn_names = {0x7C34:'7C34',0x7C8C:'7C8C',0x7D96:'7D96',0x9DD0:'9DD0',
                0x7E28:'7E28',0x7EBA:'7EBA',0x6712:'6712',0x0138:'0138',
                0x84CC:'84CC'}
    if addr in fn_names:
        calls.append(f'  CALL 0x{addr:04X} ({fn_names[addr]})')

cpu.hook_add(HOOK_CODE, code_hook)

def write_hook(_emu, _type, addr, sz, val, _u=None):
    if BSS_START <= addr < BSS_END:
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        writes.append((addr, sz, val & 0xFFFFFFFF, pc))

cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x7C34, until=HALT, count=200000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT != pc:
        print(f'Exception: {e} at PC=0x{pc:04X}')

print(f'Functions called: {len(calls)}')
for c in calls[:30]: print(c)

print(f'\nBSS writes from 0x7C34: {len(writes)}')
for addr, sz, val, pc in writes[:60]:
    rel = -(A4 - addr) if addr < A4 else (addr - A4)
    print(f'  [0x{addr:04X}] A4{rel:+X}  sz={sz}  val=0x{val:08X}  pc=0x{pc:04X}')

# Now dump key BSS areas
print('\n=== BSS state after 0x7C34 ===')
for label, start, size in [
    ('Piece counts [0x3314]', 0x3314, 8),
    ('Turn/phase  [0x331C]', 0x331C, 8),
    ('Move table  [0x3322]', 0x3322, 16),
    ('Piece cnt2  [0x32D4]', 0x32D4, 16),
    ('PieceList30F4 [0x30F4]', 0x30F4, 64),
]:
    data = bytes(cpu.mem_read(start, size))
    print(f'  {label}: {data.hex()}')
