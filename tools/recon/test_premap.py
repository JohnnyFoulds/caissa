#!/usr/bin/env python3
"""Test full pre-mapped address space (no dynamic fault hook)."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UcError
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP     = 0x1F0000;  SENTINEL = 0xFFFF0000
HW_BASE       = 0xBFC000;  HW_SIZE  = 0x404000   # covers up to 0x1000000
EXEC_START    = EXEC_BASE - LIB_RANGE             # 0x7C0000
EXEC_END      = EXEC_BASE + LIB_RANGE             # 0x840000
A4            = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
cpu      = Unicorn68k()

# core regions
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0: cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
cpu.map_region(HW_BASE, HW_SIZE)
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()

# fill gaps so no fault hook needed
cpu.map_region(0x300000, EXEC_START - 0x300000)   # 0x300000..0x7C0000
cpu.map_region(EXEC_END,  HW_BASE - EXEC_END)     # 0x840000..0xBFC000
cpu.map_region(0x1000000, 0x7F000000)              # beyond Amiga 24-bit space
print("All gaps pre-mapped (EXEC_START=0x{:X} EXEC_END=0x{:X})".format(EXEC_START, EXEC_END))

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

FAULTS = [0]
def fault_hook(emu, access, address, size, value, _):
    FAULTS[0] += 1
    if FAULTS[0] <= 5:
        print(f"  FAULT addr=0x{address:08X}", flush=True)
    return False
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, fault_hook)

t0 = time.perf_counter()
print('Running (50M steps)...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=50_000_000)
except Exception as e:
    print(f'Exception: {e}')

elapsed = time.perf_counter() - t0
mf   = bytes(cpu.mem_read(0x04AD2, 1))[0]
mt   = bytes(cpu.mem_read(0x04AD3, 1))[0]
df   = bytes(cpu.mem_read(0x025F, 1))[0]
done = struct.unpack('>H', bytes(cpu.mem_read(A4 - 0x6D48, 2)))[0]
print(f't={elapsed:.2f}s  F-lines={INTR[0]:,}  faults={FAULTS[0]}')
print(f'done={done:#x}  [0025F]={df:#x}  from=0x{mf:02X}  to=0x{mt:02X}')
if not (mf & 0x88) and not (mt & 0x88):
    fr = chr(ord('a') + (mf & 7)) + str((mf >> 4) + 1)
    to = chr(ord('a') + (mt & 7)) + str((mt >> 4) + 1)
    print(f'UCI: bestmove {fr}{to}')
