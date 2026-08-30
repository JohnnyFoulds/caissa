"""
Memory snapshot approach: run 0x7D96, diff BSS before/after.
Also directly check ROM data table at [0x07C2] and [0x07A2].
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
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID
from pathlib import Path
import unicorn.m68k_const as mc, unicorn as uc_mod

rom_data = Path(_ROOT + '/Resources/Retro/BattleChess.amiga').read_bytes()
code_bytes = rom_data[40:]
A4, BSS_START, BSS_END = 0x7FFE, 0x28D4, 0xAE04
HALT = 0xFFFF0000

# Quick ROM data check
print('=== ROM data at [0x07A2] (piece list start indices) ===')
for i in range(4):
    w = struct.unpack('>H', code_bytes[0x07A2 + i*2 : 0x07A2 + i*2 + 2])[0]
    print(f'  [0x{0x07A2+i*2:04X}] = 0x{w:04X} ({w})')

print('\n=== ROM data at [0x07C2] (piece type table) ===')
for i in range(8):
    w = struct.unpack('>H', code_bytes[0x07C2 + i*2 : 0x07C2 + i*2 + 2])[0]
    hi = (w >> 8) & 0xFF
    lo = w & 0xFF
    print(f'  File {i}: word=0x{w:04X} hi={hi} lo={lo}')

print('\n=== ROM area disasm 0x0780-0x07E0 ===')
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
md = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
for insn in md.disasm(code_bytes[0x0780:0x07E0], 0x0780):
    print(f'  {insn.address:04X}  {insn.bytes.hex():<14s}  {insn.mnemonic} {insn.op_str}')

# Emulator setup
cpu = Unicorn68k()
cpu.map_region(0x000000, 0x200000)
cpu.map_region(0x200000, 0x300000)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
try: cpu.map_region(HALT & 0xFFFF0000, 0x10000)
except: pass
mapped = set()
def inv(emu, acc, addr, sz, val, _u=None):
    page = addr & 0xFFFF0000
    if page not in mapped:
        try: emu.mem_map(page, 0x10000); emu.mem_write(page, bytes(0x10000)); mapped.add(page)
        except: pass
    return True
cpu.hook_add(HOOK_MEM_INVALID, inv)
cpu.mem_write(0, code_bytes)
cpu.mem_write(BSS_START, bytes(BSS_END - BSS_START))
cpu._uc.reg_write(mc.UC_M68K_REG_A4, A4)

# Bypass some functions that need Amiga OS
calls = []
def code_hook(_emu, addr, sz, _u=None):
    bypasses = {0x98BE: '0x98BE graphics', 0x0017D2: '0x17D2 event', 0x00134E: '0x134E'}
    if addr in bypasses:
        a7 = cpu._uc.reg_read(mc.UC_M68K_REG_A7)
        ret = struct.unpack('>I', bytes(cpu.mem_read(a7, 4)))[0]
        cpu._uc.reg_write(mc.UC_M68K_REG_A7, a7 + 4)
        cpu._uc.reg_write(mc.UC_M68K_REG_PC, ret)
        calls.append(f'Bypassed {bypasses[addr]}')
    elif addr in (0x7D96, 0x7E28, 0x7EBA, 0x7ED4, 0x995A, 0x98BE, 0x995A):
        calls.append(f'Called 0x{addr:04X}')
cpu.hook_add(HOOK_CODE, code_hook)

sp = 0x1EFF00 - 4
cpu.mem_write(sp, struct.pack('>I', HALT))
cpu._uc.reg_write(mc.UC_M68K_REG_A7, sp)

# Snapshot before
before_bss = bytes(cpu.mem_read(BSS_START, BSS_END - BSS_START))

print('\n=== Running 0x7D96 ===')
try:
    cpu.emu_start(0x7D96, until=HALT, count=500000)
except Exception as e:
    pc = cpu._uc.reg_read(mc.UC_M68K_REG_PC)
    if HALT != pc: print(f'Stopped: {e} at PC=0x{pc:04X}')

# Snapshot after
after_bss = bytes(cpu.mem_read(BSS_START, BSS_END - BSS_START))

print(f'Calls/bypasses: {calls[:20]}')

# Diff
diffs = []
for i, (b, a) in enumerate(zip(before_bss, after_bss)):
    if b != a:
        diffs.append((BSS_START + i, b, a))

print(f'\nBSS changes: {len(diffs)}')
for addr, old, new in diffs[:50]:
    rel = addr - A4 if addr > A4 else -(A4 - addr)
    print(f'  [0x{addr:04X}] A4{rel:+X}: 0x{old:02X} → 0x{new:02X}')

# Board state at [0x30F4]
print('\n=== Board [0x30F4] after 0x7D96 ===')
board_changed = False
for rank in range(7, -1, -1):
    row = []
    for file in range(8):
        sq = rank * 16 + file
        addr = 0x30F4 + sq * 4
        data = bytes(cpu.mem_read(addr, 4))
        ptype, color = data[0], data[1]
        if ptype == 0:
            row.append('.')
        else:
            board_changed = True
            syms = {1:'K',2:'Q',3:'R',4:'B',5:'N',6:'P',7:'?',8:'?'}
            s = (syms.get(ptype,'X') if color==0 else syms.get(ptype,'x').lower())
            row.append(f'{ptype}/{color}')
    print(f'  r{rank+1}: {" ".join(row)}')

if not board_changed:
    print('  (board is empty)')
