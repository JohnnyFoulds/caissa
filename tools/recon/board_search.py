"""
Search ROM for chess board data: starting position patterns, piece tables,
and early-game writes to BSS areas.
"""
import sys, struct, logging, os
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

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
cs = 40
code_bytes = rom_data[cs:]  # 84872 bytes loaded at VA 0

print('=== Static ROM search for board/piece data ===')

# Look for sequences of small non-zero bytes that look like starting position
# The starting position rank 1: R,N,B,Q,K,B,N,R = some encoding of {1..6}
# Starting position rank 2: 8 pawns

# Strategy 1: search for 16 consecutive non-zero bytes < 8, where
# exactly 8 look like major pieces and 8 look like pawns
def search_for_board_table(data, base_va=0):
    """Search for a hardcoded board table in the ROM."""
    hits = []
    for i in range(0, len(data) - 128, 2):
        # Try reading 16 consecutive bytes as two ranks (pieces + pawns)
        chunk = data[i:i+16]
        if all(0 < b < 8 for b in chunk):
            # All 16 bytes are in piece code range 1-7
            rank1 = list(chunk[:8])
            rank2 = list(chunk[8:])
            # rank2 should be all same (pawns)
            if len(set(rank2)) == 1 and len(set(rank1)) > 3:
                hits.append((base_va + i, rank1, rank2))
    return hits

hits = search_for_board_table(code_bytes)
if hits:
    print(f'\nFound {len(hits)} possible rank1+rank2 tables:')
    for va, r1, r2 in hits[:10]:
        print(f'  VA 0x{va:04X}: rank1={r1} rank2={r2}')
else:
    print('No rank1+rank2 tables found')

# Strategy 2: search for the 0x88 board pattern
# 0x88 board: 128 bytes/words, every 8 squares valid, then 8 guard squares
# Valid piece codes are small, guard squares are 0 or sentinel
print('\n--- Strategy 2: 0x88 board header search ---')
for i in range(0, len(code_bytes) - 256, 2):
    chunk = bytes(code_bytes[i:i+128])
    # Check first 8 bytes (rank 1 pieces)
    rank1 = chunk[0:8]
    rank2 = chunk[16:24]  # rank 2 in 0x88 (skip 8 guard bytes)
    if (all(0 < b < 8 for b in rank1) and
        all(0 < b < 8 for b in rank2) and
        len(set(rank2)) == 1):
        va = i
        print(f'  VA 0x{va:04X}: rank1_bytes={list(rank1)} rank2_bytes={list(rank2)}')

# Strategy 3: search for 0x88 board with WORD entries
print('\n--- Strategy 3: 0x88 board (word entries) ---')
for i in range(0, len(code_bytes) - 256, 2):
    chunk = struct.unpack_from('>16H', code_bytes, i)  # 16 words (2 ranks of 0x88)
    rank1 = chunk[0:8]
    rank2 = chunk[16:24]  # skip 8 guard words
    if len(chunk) < 24: continue
    chunk16 = struct.unpack_from('>24H', code_bytes, i)
    rank1 = chunk16[0:8]
    rank2 = chunk16[16:24]
    if (all(0 < w < 8 for w in rank1) and
        all(0 < w < 8 for w in rank2) and
        len(set(rank2)) == 1):
        va = i
        print(f'  VA 0x{va:04X}: rank1_words={list(rank1)} rank2_words={list(rank2)}')

print('\n=== Early BSS write trace (first 100K insns) ===')
cpu = Unicorn68k()
cpu.map_region(0x000000, 0x200000)
cpu.map_region(0x200000, 0x300000)
traps = AmigaTraps(cpu)
traps.install(); traps.install_mem_hook()
for base in [0xDFF000, 0xBFE000, 0xBFD000, 0xBFEC00]:
    page = base & 0xFFFF0000
    try: cpu.map_region(page, 0x10000)
    except: pass
try: cpu.map_region(0xFFFF0000, 0x10000)
except: pass
cpu.mem_write(0, code_bytes)

sp_init = 0x1F0000 - 4
cpu.mem_write(sp_init, struct.pack('>I', 0xFFFF0000))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp_init)

mapped_pages = set()
def invalid_handler(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped_pages:
        try:
            emu.mem_map(page, 0x10000)
            emu.mem_write(page, bytes(0x10000))
            mapped_pages.add(page)
        except: pass
    return True
cpu.hook_add(HOOK_MEM_INVALID, invalid_handler)

state = {'count': 0, 'writes': []}

def write_hook(_emu, _type, addr, sz, val, _u=None):
    if 0x0278 <= addr <= 0x1F0000:
        if val not in (0, 0x0278, 0xFFFF):
            pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
            state['writes'].append((state['count'], addr, sz, val & 0xFFFFFFFF, pc))

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1
cpu.hook_add(HOOK_CODE, code_hook)
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=100000)
except Exception as e:
    pass

print(f'Writes to BSS in first 100K insns: {len(state["writes"])}')
for insn, addr, sz, val, pc in state['writes'][:50]:
    print(f'  insn={insn:6d} [{addr:#06x}] sz={sz} val={val:#010x} pc={pc:#06x}')

# Now show what's in the BSS at insn 100K
print('\nBSS values at insn=100K (non-zero, non-0x0278):')
a4 = cpu._uc.reg_read(mc.UC_M68K_REG_A4)
a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
print(f'A4=0x{a4:04X} A7=0x{a7:05X} PC=0x{pc:04X}')

mem_snap = bytes(cpu.mem_read(0x0278, 0x8000))
found = []
for i in range(0, len(mem_snap)-1, 2):
    w = struct.unpack_from('>H', mem_snap, i)[0]
    if w not in (0, 0x0278):
        found.append((0x0278 + i, w))
if found:
    print(f'  {len(found)} non-default values:')
    for addr, val in found[:30]:
        print(f'    [{addr:#06x}] = {val:#06x}')
else:
    print('  All values are 0 or 0x0278 (default)')
