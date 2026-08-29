#!/usr/bin/env python3
"""Patch 0x001EC with RTS to skip visualization callback and let search complete."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
import capstone, re

CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

def run_test(patch_addresses, label):
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

    # Patch visualization callbacks with RTS (0x4E75)
    for paddr in patch_addresses:
        cpu.mem_write(paddr, b'\x4E\x75')  # RTS
        print(f"  Patched 0x{paddr:05X} → RTS", flush=True)

    sp = STACK_TOP - 4
    cpu.mem_write(sp, struct.pack('>I', SENTINEL))
    cpu.reg_write('A7', sp)

    def intr_hook(emu, intno, _):
        if intno == 11:
            pc = emu.reg_read(m68k.UC_M68K_REG_PC)
            emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
    cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)
    cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu,a,addr,s,v,_: False)

    STEP = [0]; FOUND = [None]
    MOVE_WRITES = []
    FC6_DONE = [False]

    def watch_025F(emu, access, address, size, value, _):
        if value == 1:
            mf = bytes(emu.mem_read(0x04AD2, 1))[0]
            mt = bytes(emu.mem_read(0x04AD3, 1))[0]
            pc = emu.reg_read(m68k.UC_M68K_REG_PC)
            FOUND[0] = (mf, mt, STEP[0], pc)
            print(f"\n  *** MOVE FOUND at step {STEP[0]}: PC=0x{pc:05X} from=0x{mf:02X} to=0x{mt:02X} ***", flush=True)
            emu.emu_stop()
    cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_025F, begin=0x025F, end=0x0260)

    def watch_012B6(emu, access, address, size, value, _):
        if value != 0 and address == 0x012B6:
            pc = emu.reg_read(m68k.UC_M68K_REG_PC)
            MOVE_WRITES.append((STEP[0], pc, value))
            print(f"\n  *** [012B6]={value:#x} at step {STEP[0]}, PC=0x{pc:05X} ***", flush=True)
    cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_012B6, begin=0x012B6, end=0x012B8)

    def watch_fc6_ret(emu, pc_addr, size, _):
        STEP[0] += 1
        if pc_addr == 0x012AE and not FC6_DONE[0]:
            FC6_DONE[0] = True
            print(f"\n  *** 0x0FC6 returned at step {STEP[0]} ***", flush=True)
        if STEP[0] % 500_000 == 0:
            v025C = bytes(emu.mem_read(0x025C, 1))[0]
            v012B6 = struct.unpack('>H', bytes(emu.mem_read(0x012B6, 2)))[0]
            print(f"  step={STEP[0]:8d}  PC=0x{pc_addr:05X}  [025C]={v025C:#x}  [012B6]={v012B6:#x}", flush=True)
    cpu._uc.hook_add(UC_HOOK_CODE, watch_fc6_ret)

    t0 = time.perf_counter()
    print(f"\n{label}:", flush=True)
    try:
        cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=10_000_000)
    except Exception as e:
        print(f"  Exception: {e}")
    elapsed = time.perf_counter() - t0

    mf = bytes(cpu.mem_read(0x04AD2, 1))[0]
    mt = bytes(cpu.mem_read(0x04AD3, 1))[0]
    v025F = bytes(cpu.mem_read(0x025F, 1))[0]
    v012B6 = struct.unpack('>H', bytes(cpu.mem_read(0x012B6, 2)))[0]
    v025C = bytes(cpu.mem_read(0x025C, 1))[0]
    print(f"  Done: t={elapsed:.2f}s  steps={STEP[0]}")
    print(f"  [025F]={v025F:#x}  [012B6]={v012B6:#x}  [025C]={v025C:#x}")
    print(f"  from=0x{mf:02X}  to=0x{mt:02X}")
    if FOUND[0]:
        mf2, mt2, step, pc = FOUND[0]
        # Convert 0x88-format to UCI
        # Battle Chess uses 0x88 board: file = col & 7, rank = col >> 4
        # Actually need to check what format [04AD2]/[04AD3] use
        print(f"  Move: 0x{mf2:02X} → 0x{mt2:02X}  (need format decode)")
    return FOUND[0]

# Test 1: patch only 0x001EC
run_test([0x001EC], "Test 1: patch 0x001EC with RTS")

# Test 2: also find and patch the jsr at 0x03488 target (0x05FB4)
run_test([0x001EC, 0x05FB4], "Test 2: also patch 0x05FB4")
