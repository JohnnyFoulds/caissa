"""Trace all JSR calls (PC transitions) to build a call graph and find when 0x0060 is called."""
import sys, struct, logging, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(_ROOT)
sys.path.insert(0, 'bin')
import types
sys.modules['psutil'] = types.ModuleType('psutil')
logging.disable(logging.CRITICAL)

from Code.Retro.Traps import AmigaTraps
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
cs = 40
code_bytes = rom_data[cs:]

md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)

def get_mnemonic(addr):
    chunk = code_bytes[addr:addr+6]
    for insn in md.disasm(chunk, addr):
        return f'{insn.mnemonic} {insn.op_str}'
    return '?'

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

state = {'count': 0, 'prev_pc': 0, 'calls': [], 'uniq_calls': {}}

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1
    n = state['count']

    # Skip BSS clear
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    prev = state['prev_pc']
    if prev and addr not in (prev, prev+2, prev+4, prev+6, prev+8):
        key = (prev, addr)
        if key not in state['uniq_calls']:
            state['uniq_calls'][key] = n
            state['calls'].append((n, prev, addr))

    state['prev_pc'] = addr

cpu.hook_add(HOOK_CODE, code_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=25000)
except Exception as e:
    pass

print(f'Instructions: {state["count"]}')
print(f'Unique branches/calls: {len(state["uniq_calls"])}')
print()
print('All unique branch targets (first visit):')
for n, from_pc, to_pc in state['calls']:
    try:
        from_mn = get_mnemonic(from_pc)
        to_mn = get_mnemonic(to_pc)
    except:
        from_mn = to_mn = '?'
    print(f'  insn={n:6d} 0x{from_pc:05X} [{from_mn:30s}] -> 0x{to_pc:05X} [{to_mn}]')
