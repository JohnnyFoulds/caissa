"""
Trace writes during 0x84CC (board setup) and 0x7C34/0x7C8C (AI setup).
Find where the board array is and what values are written.
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
code_bytes = rom_data[cs:]

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
    'in_board_setup': False,
    'writes': [],
    'phase': 'init',
    'call_stack': [],
    'hit_7c34': False,
    'hit_84cc': False,
}

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1

    # Skip BSS clear
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    # Track entry into key functions
    if addr == 0x7C34 and not state['hit_7c34']:
        state['hit_7c34'] = True
        print(f'[insn={state["count"]}] Entered 0x7C34 (AI setup)')
        state['phase'] = 'ai_setup'

    if addr == 0x84CC and not state['hit_84cc']:
        state['hit_84cc'] = True
        print(f'[insn={state["count"]}] Entered 0x84CC (board setup)')
        state['phase'] = 'board_setup'
        state['in_board_setup'] = True

    if addr == 0x7C5A and state['phase'] == 'board_setup':
        print(f'[insn={state["count"]}] Back to AI loop 0x7C5A (board setup done)')
        state['phase'] = 'ai_loop'
        state['in_board_setup'] = False
        raise Exception('BOARD_SETUP_DONE')

cpu.hook_add(HOOK_CODE, code_hook)

def write_hook(_emu, _type, addr, sz, val, _u=None):
    # Track all writes when in board setup phase
    if state['phase'] in ('board_setup', 'ai_setup'):
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        state['writes'].append((state['count'], addr, sz, val & 0xFFFFFFFF, pc, state['phase']))
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=10000)
except Exception as e:
    if 'BOARD_SETUP_DONE' in str(e):
        print(f'\nBoard setup complete!')
    else:
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        print(f'Exception: {e} at PC=0x{pc:04X} insn={state["count"]}')

print(f'\nTotal writes during board/AI setup: {len(state["writes"])}')
print('\nAll writes:')
for n, addr, sz, val, pc, phase in state['writes']:
    a4 = 0x7FFE
    a4rel = addr - a4 if addr <= a4 else None
    if a4rel is not None:
        relstr = f' (A4{a4rel:+d})'
    else:
        relstr = f' (A4+0x{addr-a4:04X})' if addr > a4 else ''
    print(f'  [{phase}] insn={n:4d} [0x{addr:04X}]{relstr} sz={sz} val=0x{val:08X} pc=0x{pc:04X}')

# Snapshot key areas after setup
print('\n\nMemory snapshot after board setup:')
for label, addr, size in [
    ('Move table [0x3322]', 0x3322, 24),
    ('[0x4A5A] AI state', 0x4A5A, 2),
    ('[0x4A5C] search mode?', 0x4A5C, 2),
    ('[0x12B6] game flag', 0x12B6, 2),
    ('[0x331C] turn', 0x331C, 2),
    ('[0x07D4] player type', 0x07D4, 4),
    ('[0x025F] move signal', 0x025F, 1),
]:
    try:
        val = bytes(cpu.mem_read(addr, size))
        print(f'  {label}: {val.hex()}')
    except:
        pass
