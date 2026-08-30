"""Find the game loop and input handling after init."""
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

state = {'count': 0, 'warm': False, 'prev_pc': 0, 'loop_pcs': {}, 'reads_hw': []}

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1

    # Skip BSS clear
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    # After init (insn > 20000), track PCs
    if state['count'] > 20000:
        state['warm'] = True
        # Count visits per PC
        state['loop_pcs'][addr] = state['loop_pcs'].get(addr, 0) + 1

    state['prev_pc'] = addr

cpu.hook_add(HOOK_CODE, code_hook)

# Track reads from hardware register area (input polling)
def read_hook(_emu, _type, addr, sz, val, _u=None):
    if state['warm'] and (0xBFE000 <= addr or 0xDFF000 <= addr <= 0xDFF1FF):
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        state['reads_hw'].append((state['count'], addr, sz, pc))
cpu.hook_add(HOOK_MEM_READ, read_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=200000)
except Exception as e:
    pass

print('Instructions: %d' % state['count'])
print()

# Show top hottest PCs (game loop)
hot_pcs = sorted(state['loop_pcs'].items(), key=lambda x: -x[1])[:30]
print('Hottest PCs (game loop):')
for pc, cnt in hot_pcs[:20]:
    print('  PC=0x%04X: %d visits' % (pc, cnt))

print()
print('Hardware register reads: %d' % len(state['reads_hw']))
if state['reads_hw']:
    # Show unique read addresses
    from collections import Counter
    hw_addrs = Counter((addr, pc) for _, addr, _, pc in state['reads_hw'])
    print('Unique hw reads (addr, pc):')
    for (addr, pc), cnt in hw_addrs.most_common(15):
        print('  [0x%06X] from PC=0x%04X: %d times' % (addr, pc, cnt))
