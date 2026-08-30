"""
Run the exact Think.py flow: parse_amiga_hunk → map regions → write_position → emu_start(0x81DC).
Then read [0x365A] for the best move.

Key fixes applied vs earlier attempts:
 - Zero [0x07D2] = the "preset-move" flag (ROM code bytes = 0x7000 = non-zero → blocks AI)
 - Populate board array at [0x30F4] from FEN (Bridge.py only writes piece table at 0x3322)
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
from Code.Retro.Bridge import Bridge, AI_BEST_MOVE_ADDR, AI_OUTER_DRIVER_ADDR
from pathlib import Path
import unicorn.m68k_const as mc

ROM_PATH = Path(_ROOT + '/Resources/Retro/BattleChess.amiga')
A4 = 0x7FFE
SENTINEL = 0xFFFF0000
_CHIP_RAM_BASE = 0x000000
_CHIP_RAM_SIZE = 0x200000
_STACK_TOP = 0x1F0000
_GAME_LOOP_EXIT = 0x01EA
_MAX_INSTRUCTIONS = 20_000_000
STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

# Board encoding at 0x30F4: K=1,Q=2,R=3,B=4,N=5,P=6; color 0=white, 1=black
_BOARD_TYPE = {'K':1,'Q':2,'R':3,'B':4,'N':5,'P':6,
               'k':1,'q':2,'r':3,'b':4,'n':5,'p':6}
_BOARD_COLOR = {'K':0,'Q':0,'R':0,'B':0,'N':0,'P':0,
                'k':1,'q':1,'r':1,'b':1,'n':1,'p':1}

def write_board_from_fen(cpu, fen):
    """Populate [0x30F4] board array from FEN."""
    board = bytearray(128 * 4)
    ranks = fen.split(' ')[0].split('/')
    for rank_idx, rank_str in enumerate(ranks):
        rank = 7 - rank_idx  # FEN[0] = rank 8
        file = 0
        for ch in rank_str:
            if ch.isdigit():
                file += int(ch)
            else:
                sq = rank * 16 + file  # 0x88 format
                offset = sq * 4
                board[offset] = _BOARD_TYPE[ch]
                board[offset + 1] = _BOARD_COLOR[ch]
                file += 1
    cpu.mem_write(0x30F4, bytes(board))


def sq88_uci(sq):
    r, f = (sq >> 4) & 7, sq & 7
    return chr(ord('a') + f) + str(r + 1)


print('=== Loading ROM ===')
rom_data = ROM_PATH.read_bytes()
regions = parse_amiga_hunk(rom_data)
print(f'Regions: {[(r.load_address, r.size) for r in regions]}')

cpu = Unicorn68k()
cpu.map_region(_CHIP_RAM_BASE, _CHIP_RAM_SIZE)
for region in regions:
    if region.size > 0:
        cpu.mem_write(region.load_address, rom_data[region.offset:region.offset + region.size])
        print(f'  Wrote {region.size} bytes at 0x{region.load_address:X}')

cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)

traps = AmigaTraps(cpu)
traps.install()
traps.install_mem_hook()

print('\n=== Writing position ===')
bridge = Bridge(cpu)
bridge.clear_best_move()
bridge.write_position(STARTPOS)
bridge.set_computer_color(1)   # computer plays Black

# FIX 1: Zero [0x07D2] — the "preset move" flag.
# ROM code bytes at 0x07D2 = 0x7000 (non-zero).
# 0x8230 does: tst.w -$782c(a4) [= 0x07D2]; bne skip_search
# Non-zero → skips the jsr 0xC19C main search call entirely.
# Zero → normal AI path.
cpu.mem_write(0x07D2, struct.pack('>H', 0))

# FIX 2: Populate board array at [0x30F4] from FEN.
# Bridge.py write_position() only writes the piece table at 0x3322.
# The AI also uses the board array (one entry per 0x88 square).
write_board_from_fen(cpu, STARTPOS)

print(f'Piece entries written: {len(bridge.read_piece_entries())}')
print(f'[0x07D2] = 0x{struct.unpack(">H", bytes(cpu.mem_read(0x07D2, 2)))[0]:04X} (must be 0)')

# Reset A4 and stack
cpu.reg_write('A4', A4)
sp = _STACK_TOP - 4
cpu.mem_write(sp, struct.pack('>I', SENTINEL))
cpu.reg_write('A7', sp)

# Hooks
calls_8230 = [0]
calls_c19c = [0]
mapped = set()


def code_hook(_emu, addr, sz, _u=None):
    if addr == 0x8230:
        calls_8230[0] += 1
    if addr == 0xC19C:
        calls_c19c[0] += 1
    if addr == _GAME_LOOP_EXIT:
        raw = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
        from_sq, to_sq = struct.unpack('>HH', raw[:4])
        if (from_sq & 0x88) == 0 and (to_sq & 0x88) == 0 and from_sq != 0 and to_sq != 0:
            print(f'  Valid move found at 0x01EA: from=0x{from_sq:02X} to=0x{to_sq:02X}')
            cpu.emu_stop()
    # Bypass Amiga OS calls (event loop, timer, display) and pre-search init stubs
    # 0x015C: timer/event-pump — jumps into Amiga display loop
    # 0x8824: GetTime stub (stores timer delta); crashes via 0x015C → 0x005C
    # 0x8D36, 0x7CD2, 0x8582: other pre-search init that need OS
    if addr in (0x00E4, 0x0138, 0x17D2, 0x015C, 0x8824, 0x8D36, 0x7CD2, 0x8582):
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)


def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True


cpu.hook_add(HOOK_CODE, code_hook)
cpu.hook_add(HOOK_MEM_INVALID, inv)

print(f'\n=== Running 0x{AI_OUTER_DRIVER_ADDR:04X} (AI) ===')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=_MAX_INSTRUCTIONS)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if pc != SENTINEL: print(f'Exception: {e} at 0x{pc:04X}')

print(f'0x8230 hit: {calls_8230[0]}  |  0xC19C (main search) hit: {calls_c19c[0]}')

# Read best move
bm = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
print(f'\n=== Best move raw: {bm.hex()} ===')
from_sq, to_sq, flags, piece, legal = struct.unpack('>HHHBB', bm)
print(f'from_sq=0x{from_sq:04X} to_sq=0x{to_sq:04X} flags=0x{flags:04X} piece={piece} legal={legal}')

if (from_sq & 0x88) == 0 and (to_sq & 0x88) == 0 and from_sq != 0:
    print(f'  UCI: {sq88_uci(from_sq)}{sq88_uci(to_sq)}')
elif from_sq != 0:
    lo_f = from_sq & 0xFF
    lo_t = to_sq & 0xFF
    if (lo_f & 0x88) == 0 and (lo_t & 0x88) == 0:
        print(f'  UCI (low bytes): {sq88_uci(lo_f)}{sq88_uci(lo_t)}')
    else:
        print(f'  Not valid 0x88')
else:
    print(f'  NULL MOVE — AI did not produce output')

# Board sanity check
print('\n=== Board [0x30F4] (ranks 7-8, showing non-empty) ===')
for rank in range(7, -1, -1):
    row = []
    for file in range(8):
        sq = rank * 16 + file
        data = bytes(cpu.mem_read(0x30F4 + sq * 4, 4))
        t, c = data[0], data[1]
        syms = {1:'K',2:'Q',3:'R',4:'B',5:'N',6:'P'}
        row.append(f'{syms.get(t,".")}{c}' if t != 0 else '.')
    if any(row[i] != '.' for i in range(8)):
        print(f'  r{rank+1}: {" ".join(row)}')
