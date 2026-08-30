"""
Skip natural init entirely. Set A4=0x7FFE, zero BSS, call 0x7F00 directly
with a clean stack. Trace BSS reads to find board representation.
Two passes: pass-1 trace reads, pass-2 set board and read best move.
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
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_READ, HOOK_MEM_WRITE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
cs = 40
code_bytes = rom_data[cs:]
A4 = 0x7FFE
BSS_START = 0x28D4
BSS_END   = 0xAE04
HALT_ADDR = 0xFFFF0000
SP_BASE   = 0x1EFF00


def make_cpu():
    cpu = Unicorn68k()
    cpu.map_region(0x000000, 0x200000)
    cpu.map_region(0x200000, 0x300000)
    traps = AmigaTraps(cpu)
    traps.install()
    traps.install_mem_hook()
    try: cpu.map_region(0xFFFF0000, 0x10000)
    except: pass

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
    return cpu


def setup_cpu(cpu, board_data=None):
    """Load ROM, zero BSS, set registers, push halt sentinel."""
    cpu.mem_write(0, code_bytes)

    # Zero BSS region (game data area)
    cpu.mem_write(BSS_START, bytes(BSS_END - BSS_START))

    # Set registers
    cpu._uc.reg_write(mc.UC_M68K_REG_A4, A4)

    # Clean stack with sentinel halt return address
    sp = SP_BASE
    cpu.mem_write(sp - 4, struct.pack('>I', HALT_ADDR))
    sp -= 4
    cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)

    # Key AI state variables
    cpu.mem_write(0x4A5A, struct.pack('>H', 0))   # AI phase = 0 (movegen)
    cpu.mem_write(0x331C, struct.pack('>H', 0))   # turn = 0 (white to move)
    cpu.mem_write(0x331E, struct.pack('>H', 0))   # color = 0 (white)
    cpu.mem_write(0x3320, struct.pack('>H', 0))   # depth/move counter = 0
    cpu.mem_write(0x12B6, struct.pack('>H', 0))   # game active = 0

    # Initialize move table at 0x3322 (A4 - 0x4CDC)
    # Structure: word count, word capacity, then 8-byte entries
    cpu.mem_write(0x3322, struct.pack('>HH', 0, 0x0400))  # count=0, capacity=1024

    # Set piece counts at 0x32D4 (A4 - 0x4D2A): 16 pieces per side
    cpu.mem_write(0x32D4, struct.pack('B', 16))  # white: 16 pieces
    cpu.mem_write(0x32F4, struct.pack('B', 16))  # black: 16 pieces

    if board_data:
        for addr, data in board_data.items():
            if isinstance(data, bytes):
                cpu.mem_write(addr, data)
            else:
                cpu.mem_write(addr, data)


# ─── PASS 1: trace reads from BSS ───────────────────────────────────────────

print('=== PASS 1: Trace BSS reads during 0x7F00 ===')
cpu1 = make_cpu()
setup_cpu(cpu1)

reads1 = []
last_fn = [None]

def code_hook1(_emu, addr, sz, _u=None):
    fns = {0x7F00: '7F00', 0x9494: '9494', 0x94D8: '94D8', 0xA062: 'A062',
           0xABBE: 'ABBE', 0xAE1C: 'AE1C', 0x9FC4: '9FC4', 0x9DD0: '9DD0',
           0x7D96: '7D96'}
    if addr in fns:
        last_fn[0] = fns[addr]

cpu1.hook_add(HOOK_CODE, code_hook1)

def read_hook1(_emu, _type, addr, sz, val, _u=None):
    pc = cpu1._uc.reg_read(mc.UC_M68K_REG_PC)
    reads1.append((addr, sz, pc, last_fn[0]))

cpu1.hook_add(HOOK_MEM_READ, read_hook1)

try:
    cpu1.emu_start(0x7F00, until=HALT_ADDR, count=50000)
except Exception as e:
    pc = cpu1._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT_ADDR != pc and 'halt' not in str(e).lower():
        print(f'Exception: {e} at PC=0x{pc:05X}')

# Filter to BSS region reads only
bss_reads = [(a, sz, pc, fn) for a, sz, pc, fn in reads1
             if BSS_START <= a < BSS_END]

print(f'Total BSS reads: {len(bss_reads)}')
print('\nAll unique BSS read addresses (first occurrence):')
seen = set()
for addr, sz, pc, fn in bss_reads:
    if addr not in seen:
        seen.add(addr)
        rel = addr - A4 if addr > A4 else -(A4 - addr)
        sign = '+' if addr > A4 else ''
        print(f'  [0x{addr:04X}] A4{rel:+X}  sz={sz}  from PC=0x{pc:04X}  fn={fn}')

# Also show what's at key addresses after execution
print('\nMemory after pass 1 (BSS writes):')
writes1 = []
cpu_w = make_cpu()
setup_cpu(cpu_w)
def write_hook_w(_emu, _type, addr, sz, val, _u=None):
    if BSS_START <= addr < BSS_END:
        pc = cpu_w._uc.reg_read(mc.UC_M68K_REG_PC)
        writes1.append((addr, sz, val & 0xFFFFFFFF, pc))
cpu_w.hook_add(HOOK_MEM_WRITE, write_hook_w)
try:
    cpu_w.emu_start(0x7F00, until=HALT_ADDR, count=50000)
except: pass
print(f'BSS writes: {len(writes1)}')
for addr, sz, val, pc in writes1[:30]:
    rel = -(A4 - addr) if addr < A4 else (addr - A4)
    print(f'  [0x{addr:04X}] A4{rel:+X}  sz={sz}  val=0x{val:X}  pc=0x{pc:04X}')

# Best move slot
bm = struct.unpack('>HHHH', bytes(cpu_w.mem_read(0x365A, 8)))
print(f'\n[0x365A] best_move slot: from=0x{bm[0]:04X} to=0x{bm[1]:04X} ({bm})')
