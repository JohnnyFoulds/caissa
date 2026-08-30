"""Trace execution after the BSS fill to find board init code."""
import sys, struct, logging, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types
sys.modules['psutil'] = types.ModuleType('psutil')
logging.disable(logging.CRITICAL)

from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Traps import AmigaTraps
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_WRITE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
cs = 40

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
cpu.mem_write(0, rom_data[cs:])

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

state = {'count': 0, 'prev_pc': 0, 'unique_pcs': set(), 'calls': [], 'writes': []}
fill_end_insn = 16380001

def restore_ai():
    chunk = rom_data[cs + 0x28D4:cs + 0x011D1C]
    cpu.mem_write(0x28D4, chunk)

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1
    if state['count'] == 17202:
        restore_ai()
    if state['count'] > fill_end_insn:
        state['unique_pcs'].add(addr)
        prev = state['prev_pc']
        if prev and addr not in (prev+2, prev+4, prev+6):
            state['calls'].append((state['count'], prev, addr))
    state['prev_pc'] = addr
cpu.hook_add(HOOK_CODE, code_hook)

def write_hook(_emu, _type, addr, sz, val, _u=None):
    if state['count'] > fill_end_insn and 0x0278 <= addr <= 0x11D1B:
        if val not in (0x0278, 0, 0xFFFF, 0x0000):
            state['writes'].append((state['count'], addr, sz, val, cpu._uc.reg_read(mc.UC_M68K_REG_PC)))
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=17000000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    print('Crash: %s at PC=0x%04X insn=%d' % (e, pc, state['count']))

print('Instructions after fill:', state['count'] - fill_end_insn)
print('Unique PCs after fill:', len(state['unique_pcs']))
if state['unique_pcs']:
    pcs = sorted(state['unique_pcs'])
    print('PC range: 0x%04X - 0x%04X' % (min(pcs), max(pcs)))
    ranges = []
    start = pcs[0]; end = pcs[0]
    for p in pcs[1:]:
        if p <= end + 10:
            end = p
        else:
            ranges.append((start, end))
            start = p; end = p
    ranges.append((start, end))
    print('Code regions visited (%d):' % len(ranges))
    for s, e in ranges[:30]:
        print('  0x%04X - 0x%04X (%d bytes)' % (s, e, e-s+1))

print()
print('Non-trivial writes after fill (%d):' % len(state['writes']))
for insn, addr, sz, val, pc in state['writes'][:20]:
    print('  insn=%d [0x%04X] sz=%d val=0x%04X pc=0x%04X' % (insn, addr, sz, val, pc))
