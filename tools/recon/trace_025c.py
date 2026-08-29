#!/usr/bin/env python3
"""Trace who writes to [0x025C] (the AI-busy flag)."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_WRITE, UcError
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
import capstone, re

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP     = 0x1F0000;  SENTINEL = 0xFFFF0000
HW_BASE       = 0xBFC000;  HW_SIZE  = 0x404000
EXEC_START    = EXEC_BASE - LIB_RANGE   # 0x7C0000
EXEC_END      = EXEC_BASE + LIB_RANGE   # 0x840000
A4            = A4_VALUE

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

# Print ROM byte at [0x025C] before zero
rom_byte = bytes(cpu.mem_read(0x025C, 1))[0]
print(f"ROM byte at [0x025C] before zero: 0x{rom_byte:02X} (we zeroed it: 0x00)")

def get_caller_chain(emu, depth=4):
    """Walk stack to reconstruct call chain."""
    sp = emu.reg_read(m68k.UC_M68K_REG_A7)
    addrs = []
    for i in range(depth):
        try:
            val = struct.unpack('>I', bytes(emu.mem_read(sp + i * 4, 4)))[0]
            if 0 < val < len(code): addrs.append(val)
        except: pass
    return addrs

INTR = [0]
def intr_hook(emu, intno, _):
    if intno == 11:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
        INTR[0] += 1
cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)

FAULT = [0]
def fault_hook(emu, access, address, size, value, _):
    FAULT[0] += 1
    return False
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, fault_hook)

# Spy on ALL writes to 0x025C-0x025F (the flags area)
WRITE_LOG = []
def watch_hook(emu, access, address, size, value, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    # find instruction at PC
    dis = ""
    if 0 < pc < len(code):
        insns = list(md.disasm(code[pc:pc+8], pc))
        if insns: dis = f"{insns[0].mnemonic} {insns[0].op_str}"
    callers = get_caller_chain(emu)
    callers_str = " <- ".join(f"0x{c:05X}" for c in callers)
    WRITE_LOG.append(f"  addr=0x{address:05X} val=0x{value:02X}  PC=0x{pc:05X}: {dis}  stack=[{callers_str}]")
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_hook, begin=0x0250, end=0x0270)

t0 = time.perf_counter()
print('Running (500K steps)...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000)
except Exception as e:
    print(f'Exception: {e}')
elapsed = time.perf_counter() - t0

print(f"\nt={elapsed:.2f}s  F-lines={INTR[0]}  faults={FAULT[0]}")
print(f"Writes to 0x0250-0x0270 ({len(WRITE_LOG)} total):")
for line in WRITE_LOG[-30:]:
    print(line)

v = bytes(cpu.mem_read(0x025C, 1))[0]
print(f"\n[0x025C] after 500K steps: 0x{v:02X}")
