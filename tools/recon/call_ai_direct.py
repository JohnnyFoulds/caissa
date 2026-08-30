"""
Call the AI directly at 0x0096 after init, bypassing the game loop.
Trace what it does and if it produces a move.
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

state = {'count': 0, 'phase': 'init', 'jsr_targets': {}, 'loop_pcs': {}}

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1

    # Skip BSS clear
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    if state['phase'] == 'init' and state['count'] > 22000:
        # Init done — manually inject game state and jump to AI
        state['phase'] = 'ai_setup'
        a4 = cpu._uc.reg_read(mc.UC_M68K_REG_A4)
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        pc = addr
        print(f'Init done at insn={state["count"]} PC=0x{pc:04X} A4=0x{a4:04X} A7=0x{a7:05X}')

        # Set game state flags required by outer loop (not needed for direct call)
        # but set board for starting position just in case
        # The board is at A4-relative address — we need to find it
        # For now, just set the minimum flags and call 0x0096

        # Place a return address on stack (so if AI returns, it goes to our sentinel)
        sentinel = 0xFFFF0000
        a7 = a7 - 4
        cpu.mem_write(a7, struct.pack('>I', sentinel))
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7)

        # Jump to AI entry at 0x0096
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x0096)
        print('Jumping to AI at 0x0096')
        return

    if state['phase'] == 'ai_setup':
        state['phase'] = 'ai_running'

    if state['phase'] == 'ai_running':
        state['loop_pcs'][addr] = state['loop_pcs'].get(addr, 0) + 1
        if state['count'] % 100000 == 0:
            a4 = cpu._uc.reg_read(mc.UC_M68K_REG_A4)
            print(f'  AI insn={state["count"]} PC=0x{addr:04X} A4=0x{a4:04X}')

cpu.hook_add(HOOK_CODE, code_hook)

# Track crashes / returns to sentinel
crash_state = {'first_crash': None}
def write_hook(_emu, _type, addr, sz, val, _u=None):
    pass
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

MAX_INSNS = 1000000
try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=MAX_INSNS + 22000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    print(f'Exception: {e} at PC=0x{pc:04X} insn={state["count"]}')

print(f'\nTotal insns: {state["count"]}')
print(f'Phase reached: {state["phase"]}')

# Show hottest PCs in AI phase
if state['loop_pcs']:
    hot = sorted(state['loop_pcs'].items(), key=lambda x: -x[1])[:20]
    print('\nHottest AI PCs:')
    for pc, cnt in hot:
        print(f'  PC=0x{pc:04X}: {cnt}')

# Check result area
print('\nResult memory check:')
a4 = 0x7FFE
for label, addr in [
    ('move_counter [0x3320]', 0x3320),
    ('[0x365A] AI_BEST_MOVE', 0x365A),
    ('[0x4A44] to_sq_buf', 0x4A44),
    ('[0x4A42] from_sq_buf', 0x4A42),
    ('[0x4AD2] from_sq', 0x4AD2),
    ('[0x4AD3] to_sq', 0x4AD3),
]:
    try:
        val = bytes(cpu.mem_read(addr, 4))
        w = struct.unpack('>HH', val)
        print(f'  {label}: {val.hex()} = ({w[0]:#06x}, {w[1]:#06x})')
    except Exception as e:
        print(f'  {label}: ERROR {e}')
