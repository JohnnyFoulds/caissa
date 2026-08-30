"""Snapshot BSS memory just before the 16M fill to find board layout."""
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

state = {'count': 0, 'snapshot': None}
SNAPSHOT_INSN = 5000000  # well before the fill

def restore_ai():
    chunk = rom_data[cs + 0x28D4:cs + 0x011D1C]
    cpu.mem_write(0x28D4, chunk)

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1
    if state['count'] == 17202:
        restore_ai()
    if state['count'] == SNAPSHOT_INSN and state['snapshot'] is None:
        # Snapshot all BSS and code memory
        state['snapshot'] = {
            'a4': cpu._uc.reg_read(mc.UC_M68K_REG_A4),
            'a7': cpu._uc.reg_read(mc.UC_M68K_REG_A7),
            'pc': addr,
            'mem_0278': bytes(cpu.mem_read(0x0278, 0x4000)),   # BSS low: 0x0278-0x4277
            'mem_4000': bytes(cpu.mem_read(0x4000, 0x4000)),   # BSS mid: 0x4000-0x7FFF
            'mem_8000': bytes(cpu.mem_read(0x8000, 0x4000)),   # includes 0x8000-0xBFFF
        }
        print('Snapshot taken at insn=%d PC=0x%04X A4=0x%04X A7=0x%04X' % (
            state['count'], addr,
            state['snapshot']['a4'],
            state['snapshot']['a7']))
        raise Exception('SNAPSHOT_DONE')
cpu.hook_add(HOOK_CODE, code_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=SNAPSHOT_INSN + 10)
except Exception as e:
    if 'SNAPSHOT_DONE' not in str(e):
        print('Crash:', e, 'at insn=%d' % state['count'])

snap = state['snapshot']
if not snap:
    print('No snapshot taken')
    sys.exit(1)

# Analyze the snapshot - look for non-0x0278 and non-0 patterns
# that look like a chess board (piece codes)
print('\nSearching for board-like patterns in BSS...')

def find_chess_patterns(data, base_addr):
    """Look for sequences that look like chess piece data."""
    results = []
    # Scan for WORD values that are small non-zero and not 0x0278
    for offset in range(0, len(data)-16, 2):
        # A valid board would have piece codes 0-6 or 0-7 for 8 squares
        vals = [struct.unpack_from('>H', data, offset + i*2)[0] for i in range(8)]
        # Check if these look like piece codes (0-8 range, not all same)
        non_zero = [v for v in vals if v != 0]
        non_empty = [v for v in vals if v not in (0, 0x0278)]
        if len(non_empty) >= 3 and all(v < 0x10 for v in non_empty):
            results.append((base_addr + offset, vals))
    return results

for region_name, mem_data, base in [
    ('0x0278-0x4277', snap['mem_0278'], 0x0278),
    ('0x4000-0x7FFF', snap['mem_4000'], 0x4000),
    ('0x8000-0xBFFF', snap['mem_8000'], 0x8000),
]:
    patterns = find_chess_patterns(mem_data, base)
    if patterns:
        print(f'\n{region_name}: {len(patterns)} possible board rows')
        for addr, vals in patterns[:10]:
            hex_vals = ' '.join('%04X' % v for v in vals)
            print(f'  0x{addr:04X}: [{hex_vals}]')
    else:
        print(f'\n{region_name}: no board-like patterns')

# Also show raw bytes at key A4-relative addresses
print('\nA4-relative areas (A4=0x%04X):' % snap['a4'])
a4 = snap['a4']
for offset, name in [(-0x4CDE, 'move_counter[0x3320]'), (-0x4CDC, 'move_table[0x3322]'),
                     (-0x35A2, '[0x4A5C]'), (-0x3DE2, '[0x421C]'), (-0x7FA2, '[0x5C]')]:
    addr = a4 + offset
    if 0x0278 <= addr <= 0x8000:
        region = 'mem_0278' if addr < 0x2278 else ('mem_3000' if addr < 0x5000 else 'mem_6000')
        base = 0x0278 if addr < 0x2278 else (0x3000 if addr < 0x5000 else 0x6000)
        idx = addr - base
        if 0 <= idx <= len(snap[region]) - 4:
            val = struct.unpack_from('>I', snap[region], idx)[0]
            print('  %s @ 0x%04X = 0x%08X' % (name, addr, val))
