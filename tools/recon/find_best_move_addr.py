"""
Find the real AI_BEST_MOVE_ADDR by:
1. Snapshot ALL memory before the search
2. Run the search
3. Diff memory after search — persistent changes = candidate output addresses
4. Filter for valid 0x88 from/to pairs
"""
import sys, struct, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types
for _m in ['psutil', 'charset_normalizer']:
    sys.modules[_m] = types.ModuleType(_m)
sys.modules['charset_normalizer'].from_bytes = lambda *a, **k: None
import logging; logging.disable(logging.CRITICAL)

from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import Bridge
from pathlib import Path
import unicorn.m68k_const as mc

STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
AI_INIT_ADDR = 0x8230
HALT = 0xFFFF0000
ABORT_FLAG_ADDR = 0x7FFE - 0x35B4   # 0x4A4A
BYPASS_NOOP = {0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}

_BOARD_TYPE  = {'K':1,'Q':2,'R':3,'B':4,'N':5,'P':6,'k':1,'q':2,'r':3,'b':4,'n':5,'p':6}
_BOARD_COLOR = {'K':0,'Q':0,'R':0,'B':0,'N':0,'P':0,'k':1,'q':1,'r':1,'b':1,'n':1,'p':1}

def write_board(cpu, fen):
    board = bytearray(128 * 4)
    for ri, rs in enumerate(fen.split(' ')[0].split('/')):
        rank, file = 7 - ri, 0
        for ch in rs:
            if ch.isdigit():
                file += int(ch)
            else:
                sq = rank * 16 + file
                board[sq*4] = _BOARD_TYPE[ch]; board[sq*4+1] = _BOARD_COLOR[ch]; file += 1
    cpu.mem_write(0x30F4, bytes(board))

def sq88_uci(sq):
    return chr(ord('a') + (sq & 0x0F)) + str((sq >> 4) + 1)

def get_byte_at(after_dict, addr, scan_ranges):
    for base, end in scan_ranges:
        if base <= addr < end:
            return after_dict[base][addr - base]
    return None


print('=== Loading ===')
rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_data)

cpu = Unicorn68k()
cpu.map_region(0, 0x200000)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_data[r.offset:r.offset+r.size])
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()

bridge = Bridge(cpu)
bridge.clear_best_move()
bridge.write_position(STARTPOS)
bridge.set_computer_color(1)
cpu.mem_write(0x07D2, struct.pack('>H', 0))
write_board(cpu, STARTPOS)
cpu.reg_write('A4', 0x7FFE)
cpu.reg_write('A7', 0x1EFFFC)
cpu.mem_write(0x1EFFFC, struct.pack('>I', HALT))

# Snapshot memory BEFORE search
SCAN_RANGES = [(0x0000, 0x0F00), (0x3000, 0xB000)]
before = {}
for base, end in SCAN_RANGES:
    before[base] = bytes(cpu.mem_read(base, end - base))
print(f'Snapshot: {sum(e-b for b,e in SCAN_RANGES)} bytes')

# Hooks
mapped = set()
time_check_hits = [0]
search_hits = [0]
done = [False]

def code_hook(_emu, addr, sz, _u=None):
    if addr in (0xC196, 0xC198, 0xC19A, 0xC19C):
        search_hits[0] += 1
    if addr == 0x008A:
        time_check_hits[0] += 1
        cpu.mem_write(ABORT_FLAG_ADDR, struct.pack('>H', 1))
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        return
    if addr == 0x82DA and not done[0]:
        done[0] = True
        regs = {}
        for rn in ['D0','D1','D2','D3','A0','A1','A2','A3','A4','A5','A6','A7']:
            r = getattr(mc, f'UC_M68K_REG_{rn}')
            regs[rn] = cpu._uc.reg_read(r)
        print('\n=== Registers at 0x82DA (unlk a5 in AI_INIT) ===')
        for k, v in regs.items():
            print(f'  {k} = 0x{v:08X}')
    if addr in BYPASS_NOOP:
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        try:
            ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
            cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
            cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        except: pass

def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True

cpu.hook_add(HOOK_CODE, code_hook)
cpu.hook_add(HOOK_MEM_INVALID, inv)

print(f'Running from 0x{AI_INIT_ADDR:04X}...')
try:
    cpu.emu_start(AI_INIT_ADDR, until=HALT, count=2_000_000_000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT:
        print(f'Exception at PC=0x{pc:04X}: {e}')
print(f'Search hits: {search_hits[0]}, time-check fires: {time_check_hits[0]}')

# Snapshot after
after = {}
for base, end in SCAN_RANGES:
    after[base] = bytes(cpu.mem_read(base, end - base))

# Diff
changed = []
for base, end in SCAN_RANGES:
    bfr = before[base]; aft = after[base]
    for i in range(len(bfr)):
        if bfr[i] != aft[i]:
            changed.append((base + i, bfr[i], aft[i]))

print(f'\nTotal changed bytes: {len(changed)}')

# Look for adjacent 0x88 pairs forming valid moves
print('\n=== Adjacent changed-byte pairs where both are valid 0x88 squares ===')
changed_addrs = {addr: (old, new) for addr, old, new in changed}
move_candidates = []
for addr in sorted(changed_addrs):
    if addr + 1 in changed_addrs:
        f = changed_addrs[addr][1]
        t = changed_addrs[addr + 1][1]
        if (f & 0x88) == 0 and (t & 0x88) == 0 and f != 0 and t != 0 and f != t:
            uci = sq88_uci(f) + sq88_uci(t)
            fo, to = changed_addrs[addr][0], changed_addrs[addr + 1][0]
            move_candidates.append((addr, f, t, uci, fo, to))

for addr, f, t, uci, fo, to in move_candidates:
    nb = get_byte_at(after, addr + 2, SCAN_RANGES)
    nb_str = f'0x{nb:02X}' if nb is not None else '??'
    print(f'  [0x{addr:05X}]: 0x{fo:02X}->0x{f:02X}, 0x{to:02X}->0x{t:02X}  {uci}  +2={nb_str}')

# Print all changed groups (run-length compressed)
print('\n=== Changed byte groups ===')
prev_addr = -2
group_start = -1
gbf = []; gba = []
for addr, old, new in changed:
    if addr != prev_addr + 1:
        if group_start >= 0:
            print(f'  [0x{group_start:05X}] B:{bytes(gbf).hex()} A:{bytes(gba).hex()}')
        group_start = addr; gbf = [old]; gba = [new]
    else:
        gbf.append(old); gba.append(new)
    prev_addr = addr
if group_start >= 0:
    print(f'  [0x{group_start:05X}] B:{bytes(gbf).hex()} A:{bytes(gba).hex()}')
