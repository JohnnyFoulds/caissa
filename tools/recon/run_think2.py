"""
Fixed run_think with correct entry/bypass addresses.
All addresses were 4 bytes high due to hunk offset being 0x28 (40) not 0x24 (36).

Correct addresses (from actual loaded memory):
  AI_OUTER_DRIVER = 0x81DC  (link.w a5, #0  -- real function entry)
  AI_INIT         = 0x8230  (link.w a5, #0  -- real AI init entry)
  SEARCH          = 0xC198  (jsr from 0x825A)
  [0x07D2] check  = 0x824C  (tst.w -$782c(a4) ; same address, different offset)
  Bypass funcs    = 0x8820, 0x8D32, 0x7CCE, 0x857E  (all -4 from previous)
"""
import sys, struct, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types; sys.modules['psutil'] = types.ModuleType('psutil')
import logging; logging.disable(logging.CRITICAL)

from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import Bridge, AI_BEST_MOVE_ADDR
from pathlib import Path
import unicorn.m68k_const as mc

STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
# Call AI_INIT (0x8230) directly — avoids the outer driver's infinite iterative-deepening loop.
# 0x8230 = link.w + 4 bypassed OS inits + ONE search call (0xC198) + return.
AI_OUTER_DRIVER_ADDR = 0x8230
HALT = 0xFFFF0000
# All Amiga OS stubs that must be bypassed:
# 0x015C, 0x8820: timer/event pump (0x8820 calls 0x015C; search also calls 0x8820 directly)
# 0x00E4, 0x0138, 0x17D2: other OS stubs
# 0x8D32, 0x7CCE, 0x857E: pre-search inits
# OS function pointer stubs (A4=0x7FFE; addresses = A4 + offset):
# 0x8820: timer init (called from 0x8234 pre-search inits AND from 0xC1B6 in search)
# 0x8D32, 0x7CCE, 0x857E: other pre-search inits
# 0x005A: jsr -0x7FA4(a4) in search — OS event pump; crashes (and.l -(a2),d5 w/ A2=0)
# 0x008A: jsr -0x7F74(a4) in search — TIME CHECK function; sets abort flag [0x4A4A]
# 0x015C, 0x00E4, 0x0138, 0x17D2: other OS stubs
BYPASS_NOOP = {0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}

# [0x4A4A] = A4 - 0x35B4 = abort-search flag; set to 1 to stop iterative deepening
ABORT_FLAG_ADDR = 0x7FFE - 0x35B4  # = 0x4A4A

_BOARD_TYPE = {'K':1,'Q':2,'R':3,'B':4,'N':5,'P':6,'k':1,'q':2,'r':3,'b':4,'n':5,'p':6}
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
                board[sq*4] = _BOARD_TYPE[ch]
                board[sq*4+1] = _BOARD_COLOR[ch]
                file += 1
    cpu.mem_write(0x30F4, bytes(board))


def sq88_uci(sq):
    return chr(ord('a') + (sq & 7)) + str((sq >> 4) + 1)


print('=== Loading ROM ===')
rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_data)
print(f'Regions: {[(hex(r.load_address), r.size, hex(r.offset)) for r in regions]}')

cpu = Unicorn68k()
cpu.map_region(0, 0x200000)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_data[r.offset:r.offset+r.size])
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()

print('=== Writing position ===')
bridge = Bridge(cpu)
bridge.clear_best_move()
bridge.write_position(STARTPOS)
bridge.set_computer_color(1)
cpu.mem_write(0x07D2, struct.pack('>H', 0))
write_board(cpu, STARTPOS)

cpu.reg_write('A4', 0x7FFE)
cpu.reg_write('A7', 0x1EFFFC)
cpu.mem_write(0x1EFFFC, struct.pack('>I', HALT))

mapped = set()
search_hits = [0]
c19x_addr = [None]
time_check_hits = [0]
write_log = {}   # addr -> (value, size) - last write to each address
best_move_writes = []  # writes to 0x3600..0x3800 area with PC


def code_hook(_emu, addr, sz, _u=None):
    if addr in (0xC196, 0xC198, 0xC19A, 0xC19C):
        search_hits[0] += 1
        if c19x_addr[0] is None:
            c19x_addr[0] = addr
            a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
            print(f'SEARCH FIRST HIT: PC=0x{addr:04X} A7=0x{a7:08X}')

    if addr == 0x008A:
        # TIME CHECK — set abort flag so search stops after one depth iteration
        time_check_hits[0] += 1
        cpu.mem_write(ABORT_FLAG_ADDR, struct.pack('>H', 1))
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        try:
            ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
            cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
            cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        except Exception as exc:
            print(f'BYPASS FAIL 0x008A: {exc}')
        return

    if addr in BYPASS_NOOP:
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        try:
            ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
            cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
            cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        except Exception as exc:
            print(f'BYPASS FAIL 0x{addr:04X}: {exc}')


def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True


from unicorn import UC_HOOK_MEM_WRITE

def write_hook(_emu, access, addr, sz, val, _u=None):
    if 0x3000 <= addr < 0x7000 and search_hits[0] > 0:
        write_log[addr] = (val, sz)

cpu.hook_add(HOOK_CODE, code_hook)
cpu.hook_add(HOOK_MEM_INVALID, inv)
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)

print(f'\n=== Running from 0x{AI_OUTER_DRIVER_ADDR:04X} ===')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=HALT, count=2_000_000_000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT:
        print(f'Exception: {e} at PC=0x{pc:04X}')

print(f'\nSearch function reached: {search_hits[0]} times')
print(f'Time check fired: {time_check_hits[0]} times')
if c19x_addr[0]:
    print(f'Search entry point: 0x{c19x_addr[0]:04X}')

bm = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
print(f'\nBest move raw at 0x{AI_BEST_MOVE_ADDR:04X}: {bm.hex()}')
from_sq, to_sq = struct.unpack('>HH', bm[:4])
print(f'from=0x{from_sq:04X} to=0x{to_sq:04X}')
if (from_sq & 0x88) == 0 and (to_sq & 0x88) == 0 and from_sq:
    print(f'UCI: {sq88_uci(from_sq)}{sq88_uci(to_sq)}')

# Scan 0x3000..0x6000 for valid 0x88 from/to pairs written by the search
print('\n=== Scanning 0x3000..0x6000 for valid 0x88 move pairs ===')
scan = bytes(cpu.mem_read(0x3000, 0x3000))
r0 = regions[0]
orig_off = r0.offset + 0x3000
orig = rom_data[orig_off:orig_off+0x3000]
found = []
for i in range(0, min(len(scan), 0x3000) - 3, 2):
    f = scan[i]; t = scan[i+1]
    if (f & 0x88) == 0 and (t & 0x88) == 0 and f != 0 and t != 0 and f != t:
        addr = 0x3000 + i
        was_f = orig[i] if i < len(orig) else 0xff
        was_t = orig[i+1] if i+1 < len(orig) else 0xff
        if f != was_f or t != was_t:  # only show values CHANGED from ROM
            r1,c1 = f>>4, f&0xF; rr,cc = t>>4, t&0xF
            uci = f'{chr(97+c1)}{r1+1}{chr(97+cc)}{rr+1}'
            found.append((addr, f, t, uci))

print(f'Changed valid pairs: {len(found)}')
for addr, f, t, uci in found[:30]:
    print(f'  [0x{addr:04X}]: 0x{f:02X} -> 0x{t:02X}  ({uci})')

# Show writes where current memory at addr contains valid 0x88 from/to
print('\n=== Write log: addresses with valid 0x88 pairs ===')
for addr in sorted(write_log):
    try:
        mem = bytes(cpu.mem_read(addr, 4))
        f, t = mem[0], mem[1]
        if (f & 0x88) == 0 and (t & 0x88) == 0 and f and t and f != t:
            rr,cc = f>>4, f&0xF; rr2,cc2 = t>>4, t&0xF
            uci = f'{chr(97+cc)}{rr+1}{chr(97+cc2)}{rr2+1}'
            print(f'  [0x{addr:04X}]: {mem[:4].hex()} = {uci}')
    except: pass

print(f'\n[0x3320] PIECE_COUNTER = 0x{struct.unpack(">H", bytes(cpu.mem_read(0x3320, 2)))[0]:04X}')
print(f'[0x07D2] preset flag   = 0x{struct.unpack(">H", bytes(cpu.mem_read(0x07D2, 2)))[0]:04X}')
print(f'[0x4A4A] abort flag    = 0x{struct.unpack(">H", bytes(cpu.mem_read(0x4A4A, 2)))[0]:04X}')

# Also dump area near [0x365A]
print('\n=== Memory around 0x3640..0x3680 ===')
for base in range(0x3640, 0x3680, 16):
    raw = bytes(cpu.mem_read(base, 16))
    print(f'  0x{base:04X}: {raw.hex(" ")}')
