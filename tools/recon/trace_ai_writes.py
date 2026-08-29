#!/usr/bin/env python3
"""Run AI search (0x0FC6 area) and watch ALL writes to the important flag area."""
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
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
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

# Step 1: run up to where [0x025C] = 1 (first 100 steps)
INTR = [0]
def intr_hook(emu, intno, _):
    if intno == 11:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
        INTR[0] += 1
cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu,a,addr,s,v,_: False)

PHASE = ['init']
STEP = [0]
def code_hook(emu, addr, size, _):
    STEP[0] += 1
    # Capture PC after the write to [0x025C]
    if PHASE[0] == 'ai_running' and STEP[0] % 1000 == 0:
        pass  # quiet during AI
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

WATCHING = [False]
WRITES = []
def watch_wide(emu, access, address, size, value, _):
    if not WATCHING[0]: return
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    dis = ""
    if 0 < pc < len(code):
        insns = list(md.disasm(code[pc:pc+8], pc))
        if insns: dis = f"{insns[0].mnemonic} {insns[0].op_str}"
    WRITES.append((STEP[0], address, value, pc, dis))
    if len(WRITES) >= 200:
        emu.emu_stop()
# Watch: done flags, move flags, key addresses around 0x04AD0-0x04AE0, 0x012B0-0x012C0
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_wide, begin=0x012B0, end=0x012C0)

WRITE_025C = [False]
def watch_025c(emu, access, address, size, value, _):
    if not WRITE_025C[0]:
        WRITE_025C[0] = True
        PHASE[0] = 'ai_running'
        WATCHING[0] = True  # Start wide watching AFTER [0x025C] is set
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_025c, begin=0x025C, end=0x025D)

# Also watch the move-result area
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_wide, begin=0x04AC0, end=0x04AE0)
# And [0x025F]
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_wide, begin=0x025F, end=0x0260)

print("Running with wide write watch after AI starts...")
t0 = time.perf_counter()
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=2_000_000)
except Exception as e:
    print(f'Exception: {e}')
elapsed = time.perf_counter() - t0
print(f't={elapsed:.2f}s  F-lines={INTR[0]}  steps={STEP[0]}')

print(f"\nWrites to 0x012B0-0x012C0, 0x04AC0-0x04AE0, 0x025F after [0x025C]=1:")
for step, addr, val, pc, dis in WRITES[:100]:
    print(f"  step={step:7d}  [0x{addr:05X}]={val:#04x}  PC=0x{pc:05X}: {dis}")

# Final values
print("\nFinal values:")
for a in (0x025C, 0x025F, 0x012B6, 0x04AD2, 0x04AD3):
    v = struct.unpack('>H', bytes(cpu.mem_read(a, 2)))[0]
    print(f"  [0x{a:05X}] = 0x{v:04X}")
