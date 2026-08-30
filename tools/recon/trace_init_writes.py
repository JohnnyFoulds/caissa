"""Trace ALL memory writes during crack trailer init (insns 100-500) to find board setup."""
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

state = {'count': 0, 'writes': []}

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return
    if state['count'] > 500:
        raise Exception('DONE')

cpu.hook_add(HOOK_CODE, code_hook)

def write_hook(_emu, _type, addr, sz, val, _u=None):
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    state['writes'].append((state['count'], addr, sz, val & 0xFFFFFFFF, pc))
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=600)
except Exception as e:
    if 'DONE' not in str(e):
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        print(f'Exception: {e} at PC=0x{pc:04X} insn={state["count"]}')

print(f'Total writes in first 500 insns: {len(state["writes"])}')
a4 = 0x7FFE
print('\nAll writes:')
for n, addr, sz, val, pc in state['writes']:
    if addr > a4:
        rel = f'+0x{addr-a4:04X}'
    else:
        rel = f'-0x{a4-addr:04X}'
    print(f'  insn={n:4d} [0x{addr:05X}] A4{rel} sz={sz} val=0x{val:08X} pc=0x{pc:05X}')

# Also snapshot memory at key addresses after 500 insns
print('\nMemory after 500 insns:')
for label, addr, size in [
    ('[0x4A5A] AI dispatch', 0x4A5A, 2),
    ('[0x12B6] game active', 0x12B6, 2),
    ('[0x331C] turn index', 0x331C, 2),
    ('[0x07D4] player types', 0x07D4, 4),
    ('Move table [0x3320]', 0x3320, 4),
    ('[0x025F] move signal', 0x025F, 2),
    ('[0xADC2] SP save', 0xADC2, 4),
    ('[0xADC6] ExecBase', 0xADC6, 4),
    ('AllocMem result [0xADCE]', 0xADCE, 4),
]:
    try:
        val = bytes(cpu.mem_read(addr, size))
        # Check if this is ROM code bytes or actual data
        orig = code_bytes[addr:addr+size] if addr < len(code_bytes) else None
        changed = ' [CHANGED from ROM]' if orig and bytes(orig) != val else ' [ROM code bytes]'
        print(f'  {label}: {val.hex()}{changed}')
    except:
        pass

# Print PC/register state at end
pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
a4_val = cpu._uc.reg_read(mc.UC_M68K_REG_A4)
a7_val = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
print(f'\nFinal state: PC=0x{pc:05X} A4=0x{a4_val:04X} A7=0x{a7_val:06X}')
