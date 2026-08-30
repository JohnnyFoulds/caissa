"""
Instrument the search to find EXACTLY which instruction writes to 0x3662..0x3669,
and log the register state at that moment to understand the move format.
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
from unicorn import UC_HOOK_MEM_WRITE

STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
AI_INIT_ADDR = 0x8230
HALT = 0xFFFF0000
ABORT_FLAG_ADDR = 0x7FFE - 0x35B4  # 0x4A4A
BYPASS_NOOP = {0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}
PIECE_TABLE_ADDR = 0x3322
WATCH_ADDR = PIECE_TABLE_ADDR + 0x68 * 8  # 0x3662 — known best-move output

_BOARD_TYPE  = {'K':1,'Q':2,'R':3,'B':4,'N':5,'P':6,'k':1,'q':2,'r':3,'b':4,'n':5,'p':6}
_BOARD_COLOR = {'K':0,'Q':0,'R':0,'B':0,'N':0,'P':0,'k':1,'q':1,'r':1,'b':1,'n':1,'p':1}

def write_board(cpu, fen):
    board = bytearray(128 * 4)
    for ri, rs in enumerate(fen.split(' ')[0].split('/')):
        rank, file = 7 - ri, 0
        for ch in rs:
            if ch.isdigit(): file += int(ch)
            else:
                sq = rank * 16 + file
                board[sq*4] = _BOARD_TYPE[ch]; board[sq*4+1] = _BOARD_COLOR[ch]; file += 1
    cpu.mem_write(0x30F4, bytes(board))

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

mapped = set()
write_events = []   # (pc, addr, val, sz, regs)
time_check_hits = [0]
current_pc = [0]

def code_hook(_emu, addr, sz, _u=None):
    current_pc[0] = addr
    if addr == 0x008A:
        time_check_hits[0] += 1
        cpu.mem_write(ABORT_FLAG_ADDR, struct.pack('>H', 1))
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        return
    if addr in BYPASS_NOOP:
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        try:
            ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
            cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
            cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        except: pass

def write_hook(_emu, access, addr, sz, val, _u=None):
    if WATCH_ADDR <= addr < WATCH_ADDR + 8:
        pc = current_pc[0]
        regs = {}
        for rn in ['D0','D1','D2','D3','A0','A1','A5','A6']:
            r = getattr(mc, f'UC_M68K_REG_{rn}')
            regs[rn] = cpu._uc.reg_read(r)
        write_events.append((pc, addr, val, sz, dict(regs)))

def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True

cpu.hook_add(HOOK_CODE, code_hook)
cpu.hook_add(HOOK_MEM_INVALID, inv)
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)

print(f'Watching [0x{WATCH_ADDR:04X}..0x{WATCH_ADDR+7:04X}] for writes...')
try:
    cpu.emu_start(AI_INIT_ADDR, until=HALT, count=2_000_000_000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT:
        print(f'Exception at 0x{pc:04X}: {e}')

print(f'Time-check fires: {time_check_hits[0]}')
print(f'Writes to [0x{WATCH_ADDR:04X}..]: {len(write_events)}')
print()

# Show final memory at watch address
final_bytes = bytes(cpu.mem_read(WATCH_ADDR, 8))
print(f'Final 8 bytes at [0x{WATCH_ADDR:04X}]: {final_bytes.hex()}')

# Show each write event
for i, (pc, addr, val, sz, regs) in enumerate(write_events):
    offset = addr - WATCH_ADDR
    print(f'\nWrite #{i+1}: PC=0x{pc:04X} → [0x{addr:04X}+{offset}] val=0x{val:0{sz*2}X} ({sz}B)')
    for k, v in regs.items():
        print(f'  {k} = 0x{v:08X}')
    # Read context: 16 bytes around the write PC
    try:
        ctx = bytes(cpu.mem_read(pc - 4, 16))
        print(f'  mem @ PC-4: {ctx.hex()}')
    except: pass

# Read the piece table around the written entry
print(f'\n=== Final piece table entries 0x66..0x6A ===')
for idx in range(0x65, 0x6C):
    off = PIECE_TABLE_ADDR + idx * 8
    data = bytes(cpu.mem_read(off, 8))
    print(f'  entry[0x{idx:02X}] @ 0x{off:04X}: {data.hex()}')
