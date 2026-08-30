"""
Test the two confirmed fixes:
1. Piece table sq at offset +2 (not +0)
2. Pawn direction table at 0x07A2 initialized to correct values

Run this before updating Bridge.py to confirm the move becomes valid.
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
from pathlib import Path
import unicorn.m68k_const as mc
from unicorn import UC_HOOK_MEM_WRITE

STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
AI_INIT_ADDR     = 0x8230
HALT             = 0xFFFF0000
ABORT_FLAG_ADDR  = 0x7FFE - 0x35B4   # 0x4A4A
BYPASS_NOOP      = {0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2}

# Memory layout constants (A4=0x7FFE)
PIECE_TABLE_ADDR   = 0x3322   # A4 - 0x4CDC
BOARD_ARRAY_ADDR   = 0x30F4   # A4 - 0x4F0A  (128 entries * 4 bytes each)
PAWN_DIR_TABLE     = 0x07A2   # A4 - 0x785C  (2 words: [0]=white dir, [1]=black dir)
SEARCH_SKIP_FLAG   = 0x07D2   # A4 - 0x782C  (non-zero = skip search)
PIECE_COUNTER_ADDR = 0x3320   # A4 - 0x4CDE
PLAYER1_COLOR_ADDR = 0x331E   # A4 - 0x4CE0
PLAYER2_COLOR_ADDR = 0x331C   # A4 - 0x4CE2

# The AI writes best move at: PIECE_TABLE + (PIECE_COUNTER_runtime + 0x68) * 8
# With PIECE_COUNTER=0 during search: index=0x68, address=0x3662
AI_BEST_MOVE_ADDR  = PIECE_TABLE_ADDR + 0x68 * 8  # 0x3662

# Piece type mapping (game's board-array encoding, from recon)
_PT = {'K':1,'Q':2,'R':3,'B':4,'N':5,'P':6,'k':1,'q':2,'r':3,'b':4,'n':5,'p':6}
_PC = {'K':0,'Q':0,'R':0,'B':0,'N':0,'P':0,'k':1,'q':1,'r':1,'b':1,'n':1,'p':1}


def write_board_array(cpu, fen):
    """Write BOARD_ARRAY: [sq*4+0]=type, [sq*4+1]=color, [sq*4+2..3]=0."""
    board = bytearray(128 * 4)
    for ri, rs in enumerate(fen.split(' ')[0].split('/')):
        rank = 7 - ri
        file = 0
        for ch in rs:
            if ch.isdigit():
                file += int(ch)
            elif ch in _PT:
                sq = rank * 16 + file
                board[sq * 4]     = _PT[ch]
                board[sq * 4 + 1] = _PC[ch]
                file += 1
    cpu.mem_write(BOARD_ARRAY_ADDR, bytes(board))


def write_piece_table_fixed(cpu, fen):
    """Write piece table with sq at offset +2 (the CORRECT format from disassembly).

    Each 8-byte entry:
      offset 0 (WORD): 0  — TO square, filled during search
      offset 2 (WORD): sq — FROM square (current position)
      offset 4-7:      0  — search state, filled during search
    """
    cpu.mem_write(PIECE_TABLE_ADDR, b'\x00' * 32 * 8)
    idx = 0
    for ri, rs in enumerate(fen.split(' ')[0].split('/')):
        rank = 7 - ri
        file = 0
        for ch in rs:
            if ch.isdigit():
                file += int(ch)
            elif ch in _PT:
                sq = rank * 16 + file
                # TO=0, FROM=sq, then 4 zero bytes
                entry = struct.pack('>HH4x', 0, sq)
                cpu.mem_write(PIECE_TABLE_ADDR + idx * 8, entry)
                idx += 1
                file += 1


def sq88_uci(sq):
    return chr(ord('a') + (sq & 0x0F)) + str((sq >> 4) + 1)


print('=== Loading ROM ===')
rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
regions = parse_amiga_hunk(rom_data)

cpu = Unicorn68k()
cpu.map_region(0, 0x200000)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()

print('=== Writing position (FIXED format) ===')
# Board array: all pieces for occupancy checks
write_board_array(cpu, STARTPOS)

# Piece table: sq at offset +2 (FIXED)
write_piece_table_fixed(cpu, STARTPOS)

# Pawn direction table: correct chess move deltas (FIXED)
# [0x07A2] = +0x0010 (white pawn moves north = +1 rank)
# [0x07A4] = 0xFFF0  (black pawn moves south = -1 rank = -0x10)
cpu.mem_write(PAWN_DIR_TABLE, struct.pack('>HH', 0x0010, 0xFFF0))
print(f'  Wrote pawn direction table: white=+0x10, black=-0x10 (0xFFF0)')

# Search skip flag = 0 (allow search to run)
cpu.mem_write(SEARCH_SKIP_FLAG, struct.pack('>H', 0))

# PIECE_COUNTER = -1 (initial state)
cpu.mem_write(PIECE_COUNTER_ADDR, struct.pack('>h', -1))

# Player colors: white to move → side=0, player1=0(white), player2=1(black)
cpu.mem_write(PLAYER1_COLOR_ADDR, struct.pack('>H', 0))  # side to move = white
cpu.mem_write(PLAYER2_COLOR_ADDR, struct.pack('>H', 1))  # other side = black

# Computer = black (1); human = white (0)
cpu.mem_write(0x07D4, struct.pack('>H', 1))  # player[0] = white = human
cpu.mem_write(0x07D6, struct.pack('>H', 2))  # player[1] = black = computer

cpu.reg_write('A4', 0x7FFE)
cpu.reg_write('A7', 0x1EFFFC)
cpu.mem_write(0x1EFFFC, struct.pack('>I', HALT))

# Show piece table (first few entries)
print('\n=== Piece table (first 8 entries, fixed format) ===')
for i in range(8):
    off = PIECE_TABLE_ADDR + i * 8
    data = bytes(cpu.mem_read(off, 8))
    to_sq = struct.unpack('>H', data[0:2])[0]
    from_sq = struct.unpack('>H', data[2:4])[0]
    valid = 'valid' if (from_sq & 0x88) == 0 and from_sq != 0 else 'ZERO/invalid'
    sq_str = sq88_uci(from_sq) if (from_sq & 0x88) == 0 and from_sq else '??'
    print(f'  entry[{i:2d}]: to=0x{to_sq:04X} from=0x{from_sq:04X}({sq_str}) [{valid}]  raw={data.hex()}')

mapped = set()
write_events = []
current_pc = [0]
time_check_hits = [0]

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
    if AI_BEST_MOVE_ADDR <= addr < AI_BEST_MOVE_ADDR + 8:
        pc = current_pc[0]
        regs = {}
        for rn in ['D0', 'D1', 'D2', 'D3', 'A0', 'A1']:
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

print(f'\n=== Running AI from 0x{AI_INIT_ADDR:04X} ===')
try:
    cpu.emu_start(AI_INIT_ADDR, until=HALT, count=2_000_000_000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != HALT:
        print(f'Exception at 0x{pc:04X}: {e}')

print(f'Time-check fires: {time_check_hits[0]}')
print(f'Writes to best-move entry: {len(write_events)}')

final = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
print(f'\nFinal 8 bytes at AI_BEST_MOVE_ADDR 0x{AI_BEST_MOVE_ADDR:04X}: {final.hex()}')
to_sq   = struct.unpack('>H', final[0:2])[0]
from_sq = struct.unpack('>H', final[2:4])[0]
print(f'  to_sq   = 0x{to_sq:04X}  valid={not bool(to_sq & 0x88)}')
print(f'  from_sq = 0x{from_sq:04X}  valid={not bool(from_sq & 0x88)}')

if (from_sq & 0x88) == 0 and (to_sq & 0x88) == 0 and from_sq and to_sq:
    uci = sq88_uci(from_sq) + sq88_uci(to_sq)
    print(f'\n*** SUCCESS: bestmove {uci} ***')
else:
    print(f'\n*** FAIL: invalid from/to squares ***')
    # Show last few writes for debugging
    for i, (pc, addr, val, sz, regs) in enumerate(write_events[-5:]):
        offset = addr - AI_BEST_MOVE_ADDR
        print(f'  write [{i}]: PC=0x{pc:04X} [+{offset}] val=0x{val:04X} ({sz}B) D0=0x{regs["D0"]:04X} D3=0x{regs["D3"]:04X}')
