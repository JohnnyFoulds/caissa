#!/usr/bin/env python3
"""Watch all writes to 0x025C-0x025F over 5M steps, print full log."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
import capstone, re

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE
EXEC_END   = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

cpu = Unicorn68k()
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0: cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
cpu.map_region(HW_BASE, HW_SIZE)
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
cpu.map_region(0x300000, EXEC_START - 0x300000)
cpu.map_region(EXEC_END,  HW_BASE - EXEC_END)
cpu.map_region(0x1000000, 0x7F000000)
cpu.map_region(0xFF000000, 0x00FF0000)

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
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu,a,addr,s,v,_: False)

# PC sample every 100K steps
STEPS = [0]
HIST = {}
def code_hook(emu, addr, size, _):
    STEPS[0] += 1
    if STEPS[0] % 100_000 == 0:
        HIST[STEPS[0]] = addr
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

WRITES = []
def watch_hook(emu, access, address, size, value, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    dis = ""
    if 0 < pc < len(code):
        insns = list(md.disasm(code[pc:pc+8], pc))
        if insns: dis = f"{insns[0].mnemonic} {insns[0].op_str}"
    WRITES.append(f"step={STEPS[0]:7d}  addr=0x{address:05X} val=0x{value:02X}  PC=0x{pc:05X}: {dis}")
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_hook, begin=0x0250, end=0x0270)

t0 = time.perf_counter()
print('Running 5M steps...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=5_000_000)
except Exception as e:
    print(f'Exception: {e}')
elapsed = time.perf_counter() - t0

print(f't={elapsed:.2f}s  F-lines={INTR[0]}  total_writes={len(WRITES)}')
print(f'\nAll writes to 0x0250-0x0270:')
for w in WRITES:
    print(f'  {w}')

print(f'\nPC at 100K-step intervals:')
for step, pc in sorted(HIST.items())[:30]:
    print(f'  step={step:7d}: PC=0x{pc:05X}')

print(f'\nFinal state:')
for a in (0x025C, 0x025D, 0x025F, 0x04AD2, 0x04AD3):
    v = bytes(cpu.mem_read(a, 1))[0]
    print(f'  [0x{a:05X}] = 0x{v:02X}')
