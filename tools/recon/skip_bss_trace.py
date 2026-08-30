"""
Skip BSS clear and fill, then trace game to find when AI is called and what board state it sees.
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

state = {'count': 0, 'ai_hit': False, 'fill_hits': 0, 'writes_after_ai': []}
MAX_INSNS = 5000000

def code_hook(_emu, addr, sz, _u=None):
    state['count'] += 1

    # Skip BSS clear: when execution reaches 0x110D8 (the loop that zeroes memory),
    # redirect PC to 0x110E6 (skip the clear entirely)
    if addr == 0x110D8:
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, 0x110E6)
        return

    # Skip the 16M fill: the fill is the DBxx loop that writes 0x0278 to ALL memory.
    # The fill loop: at VA 0x000274, the CPU repeatedly executes ANDI.W instructions.
    # Actually the fill is at PC=0x000274 - a tight loop.
    # We detect it: when PC=0x000274 for a long time.
    # If we detect this, skip by jumping to the return address.
    # Better: watch for WRITES of 0x0278 to code area 0x28D4+
    # For now: watch for the fill pattern at specific PC

    # Detect AI entry at 0x81DC
    if addr == 0x81DC:
        if not state['ai_hit']:
            state['ai_hit'] = True
            a4 = cpu._uc.reg_read(mc.UC_M68K_REG_A4)
            a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
            print('AI CALLED at insn=%d A4=0x%04X A7=0x%04X' % (state['count'], a4, a7))
            # Read the move table area
            mt_addr = 0x3320
            mt_data = bytes(cpu.mem_read(mt_addr, 128))
            print('Move table [0x3320:+128]:')
            for i in range(0, 32, 8):
                row = mt_data[i:i+8]
                vals = struct.unpack('>HHHBB', row)
                print('  [%04X] count/from=%04X to=%04X flags=%04X piece=%02X legal=%02X' % (
                    mt_addr+i, vals[0], vals[1], vals[2], vals[3], vals[4]))
            # Check board-like data around A4
            print()
            print('[0x4A5C]:', struct.unpack('>H', cpu.mem_read(0x4A5C, 2))[0])
            raise Exception('AI_HIT_STOP')

cpu.hook_add(HOOK_CODE, code_hook)

# Track writes of 0x0278 to chess AI range (fill detection)
fill_state = {'last_fill_addr': 0, 'fill_count': 0}
def write_hook(_emu, _type, addr, sz, val, _u=None):
    if val in (0x0278, 0x02780278) and 0x28D4 <= addr <= 0x11D1B:
        fill_state['fill_count'] += 1
        fill_state['last_fill_addr'] = addr
        if fill_state['fill_count'] == 1:
            pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
            print('First fill write to chess AI at addr=0x%04X at insn=%d PC=0x%04X' % (
                addr, state['count'], pc))
cpu.hook_add(HOOK_MEM_WRITE, write_hook)

try:
    cpu.emu_start(0x0000, until=0xFFFF0000, count=MAX_INSNS)
except Exception as e:
    if 'AI_HIT_STOP' in str(e):
        print('\nAI entry point hit! Checking result...')
        # Read result
        result = bytes(cpu.mem_read(0x365A, 8))
        print('[0x365A]:', result.hex())
        from_sq = struct.unpack('>H', result[0:2])[0]
        to_sq = struct.unpack('>H', result[2:4])[0]
        print('from_sq=0x%04X to_sq=0x%04X' % (from_sq, to_sq))
    else:
        pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
        print('Crash: %s at PC=0x%04X insn=%d' % (e, pc, state['count']))

print()
print('Total insns:', state['count'])
if fill_state['fill_count']:
    print('Fill writes to chess AI range: %d, last addr=0x%04X' % (
        fill_state['fill_count'], fill_state['last_fill_addr']))
else:
    print('No fill writes to chess AI range (BSS clear skipped successfully)')
