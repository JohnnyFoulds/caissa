"""
Hook 0x00E4 to bypass event loop, set AI state=0 (movegen), trace ALL reads
during move generation to find board array format and location.
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

state = {
    'count': 0,
    'phase': 'init',
    'reads': [],
    'writes': [],
    'calls': [],
    'inject_done': False,
}

# Phase boundaries
INIT_DONE_INSN = 215  # after crack init calls 0x7C5A

def code_hook(_emu, addr, sz, _u=None):
    n = state['count']
    state['count'] = n + 1

    # Skip BSS clear
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    # Hook 0x00E4 — bypass event loop: just RTS
    if addr == 0x00E4 and state['phase'] != 'init':
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret_addr_bytes = bytes(cpu.mem_read(a7, 4))
        ret_addr = struct.unpack('>I', ret_addr_bytes)[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret_addr)
        state['calls'].append(f'[insn={state["count"]}] BYPASSED 0x00E4 → return to 0x{ret_addr:05X}')
        return

    # After init phase, inject board state and call AI
    if n == INIT_DONE_INSN and not state['inject_done']:
        state['inject_done'] = True
        state['phase'] = 'ai'
        _inject_board_state()
        # Jump directly to 0x7C5A (AI dispatch)
        state['calls'].append(f'[insn={n}] Injecting board state and jumping to 0x7C5A')
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x7C5A)
        return

    if state['phase'] == 'ai':
        if n > INIT_DONE_INSN + 5000:
            raise Exception('AI_TIMEOUT')
        # Track function calls
        if addr in (0x7F00, 0x94D8, 0xA062, 0xABBE, 0xAE1C, 0x8230, 0x9494, 0x81DC, 0x7F96):
            state['calls'].append(f'[insn={state["count"]}] CALL 0x{addr:04X}')
        # Check for best move result at 0x365A
        if addr == 0x81DC or addr == 0x8230:
            pass  # will handle via read hook

cpu.hook_add(HOOK_CODE, code_hook)

def _inject_board_state():
    """Set up starting chess position and AI state variables."""

    # [0x4A5A] = 0 → move gen phase (A4 - 0x35A4 = 0x4A5A)
    cpu.mem_write(0x4A5A, struct.pack('>H', 0))

    # [0x331C] = 0 → turn 0 (white to move) (A4 - 0x4CE2 = 0x331C)
    cpu.mem_write(0x331C, struct.pack('>H', 0))

    # [0x331E] = 0 → color 0 (white) (A4 - 0x4CE0 = 0x331E)
    cpu.mem_write(0x331E, struct.pack('>H', 0))

    # [0x3320] = 0 → move counter (A4 - 0x4CDE = 0x3320)
    cpu.mem_write(0x3320, struct.pack('>H', 0))

    # [0x12B6] = 0 → game active (A4 - 0x6D48 = 0x12B6)
    cpu.mem_write(0x12B6, struct.pack('>H', 0))

    # Initialize move table at 0x3322: capacity in first word
    # 0x3322 is A4 - 0x4CDC, move table start
    cpu.mem_write(0x3322, struct.pack('>H', 0x0400))  # capacity
    cpu.mem_write(0x3324, struct.pack('>H', 0))       # count = 0

    # Set piece counts at 0x32D4 (A4 - 0x4D2A):
    # [0x32D4] = 16 (white has 16 pieces), [0x32F4] = 16 (black)
    # Standard start position: 8 pawns + 2 rooks + 2 knights + 2 bishops + 1 queen + 1 king = 16
    cpu.mem_write(0x32D4, bytes([16]))   # white piece count
    cpu.mem_write(0x32F4, bytes([16]))   # black piece count

    # Set up a SIMPLE board: just white king on e1, black king on e8
    # to check if the AI can handle minimal data
    # First, zero out the entire BSS region (28D4-AE04)
    bss_size = 0xAE04 - 0x28D4
    cpu.mem_write(0x28D4, bytes(bss_size))

    # Restore key values after BSS zero
    cpu.mem_write(0x4A5A, struct.pack('>H', 0))
    cpu.mem_write(0x331C, struct.pack('>H', 0))
    cpu.mem_write(0x331E, struct.pack('>H', 0))
    cpu.mem_write(0x3320, struct.pack('>H', 0))
    cpu.mem_write(0x3322, struct.pack('>H', 0x0400))

    print(f'Board state injected. BSS zeroed, AI state set to movegen.')
    print(f'  [0x4A5A] = {struct.unpack(">H", bytes(cpu.mem_read(0x4A5A, 2)))[0]} (AI phase)')
    print(f'  [0x331C] = {struct.unpack(">H", bytes(cpu.mem_read(0x331C, 2)))[0]} (turn)')

def read_hook(_emu, _type, addr, sz, val, _u=None):
    if state['phase'] == 'ai' and 0x28D4 <= addr < 0xAE04:
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        state['reads'].append((state['count'], addr, sz, pc))

def write_hook(_emu, _type, addr, sz, val, _u=None):
    if state['phase'] == 'ai':
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        state['writes'].append((state['count'], addr, sz, val & 0xFFFFFFFF, pc))

cpu.hook_add(HOOK_MEM_READ, read_hook)
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=25000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    insn = state['count']
    if 'AI_TIMEOUT' not in str(e):
        print(f'Exception: {e} at PC=0x{pc:05X} insn={insn}')
    else:
        print(f'AI timeout (5000 insns past injection) at PC=0x{pc:05X}')

print('\n--- Call trace ---')
for c in state['calls'][:40]:
    print(c)

# Show unique BSS read addresses during AI phase
print(f'\n--- BSS reads during AI phase ({len(state["reads"])} total) ---')
addr_freq = {}
for n, addr, sz, pc in state['reads']:
    key = (addr & ~3)  # group by 4-byte aligned
    addr_freq[key] = addr_freq.get(key, 0) + 1

# Sort by frequency (most-read = most important)
sorted_addrs = sorted(addr_freq.items(), key=lambda x: -x[1])
print(f'Top 40 most-read BSS addresses (4-byte groups):')
for addr, freq in sorted_addrs[:40]:
    rel = addr - A4 if addr > A4 else -(A4 - addr)
    print(f'  [0x{addr:04X}] A4{rel:+07X} : {freq} reads')

# Show first 100 unique read addresses in order
print(f'\nFirst 80 reads (in order, first occurrence only):')
seen = set()
for n, addr, sz, pc in state['reads'][:200]:
    if addr not in seen:
        seen.add(addr)
        rel = -(A4 - addr) if addr < A4 else (addr - A4)
        print(f'  insn={n:5d} [0x{addr:04X}] A4{rel:+07X} sz={sz} from PC=0x{pc:05X}')

# Check if best move was produced
print('\n--- Best move check ---')
try:
    bm_bytes = bytes(cpu.mem_read(0x365A, 8))
    print(f'[0x365A] (AI_BEST_MOVE): {bm_bytes.hex()}')
    from_sq = struct.unpack('>H', bm_bytes[0:2])[0]
    to_sq   = struct.unpack('>H', bm_bytes[2:4])[0]
    print(f'  raw from=0x{from_sq:04X} to=0x{to_sq:04X}')
except Exception as e:
    print(f'Could not read best move: {e}')

# Show BSS writes too (what the AI PRODUCES)
print(f'\n--- BSS writes during AI phase (first 30) ---')
for n, addr, sz, val, pc in state['writes'][:30]:
    if 0x28D4 <= addr < 0xAE04:
        rel = -(A4 - addr) if addr < A4 else (addr - A4)
        print(f'  insn={n:5d} [0x{addr:04X}] A4{rel:+07X} sz={sz} val=0x{val:08X} pc=0x{pc:05X}')
