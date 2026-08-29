#!/usr/bin/env python3
"""PC histogram: find where the AI spends its time (2M steps)."""
import sys, struct, time, collections
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UcError
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
import capstone

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP     = 0x1F0000;  SENTINEL = 0xFFFF0000
HW_BASE       = 0xBFC000;  HW_SIZE  = 0x404000
EXEC_START    = EXEC_BASE - LIB_RANGE   # 0x7C0000
EXEC_END      = EXEC_BASE + LIB_RANGE   # 0x840000
A4            = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
cpu      = Unicorn68k()
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0: cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
cpu.map_region(HW_BASE, HW_SIZE)
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
cpu.map_region(0x300000, EXEC_START - 0x300000)
cpu.map_region(EXEC_END,  HW_BASE - EXEC_END)
cpu.map_region(0x1000000, 0x7F000000)
cpu.map_region(0xFF000000, 0x00FF0000)  # top of 32-bit for 0xFFFFFF78

cpu.reg_write('A4', A4)
bridge = Bridge(cpu)
bridge.write_position('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
bridge.set_computer_color(0)
for addr in (0x025C, 0x025D, 0x024F, 0x024E):
    cpu.mem_write(addr, b'\x00')
sp = STACK_TOP - 4
cpu.mem_write(sp, struct.pack('>I', SENTINEL))
cpu.reg_write('A7', sp)

INTR = [0]
def intr_hook(emu, intno, _):
    if intno == 11:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
        INTR[0] += 1
cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)

# Sample PC every 10000 steps (cheap: just count mod)
HIST = collections.Counter()
SAMPLE_EVERY = 10000
STEPS = [0]
def code_hook(emu, addr, size, _):
    STEPS[0] += 1
    if STEPS[0] % SAMPLE_EVERY == 0:
        HIST[addr] += 1
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

t0 = time.perf_counter()
print('Sampling 2M steps...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=2_000_000)
except Exception as e:
    print(f'Exception: {e}')

elapsed = time.perf_counter() - t0
print(f't={elapsed:.2f}s  F-lines={INTR[0]}  samples={sum(HIST.values())}')
print('\nTop-20 hot PCs:')
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)
for addr, cnt in HIST.most_common(20):
    if 0 <= addr < len(code):
        insns = list(md.disasm(code[addr:addr+8], addr))
        dis = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else "?"
    else:
        dis = "(outside ROM)"
    print(f"  0x{addr:05X}: {cnt:5d}×  {dis}")
