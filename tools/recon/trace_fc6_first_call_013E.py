#!/usr/bin/env python3
"""Find the FIRST call to 0x013E/0x0274 from within 0x0FC6, and trace those 50 steps."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
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

def dis1(addr):
    if 0 < addr < len(code):
        insns = list(md.disasm(code[addr:addr+8], addr))
        if insns:
            ea = ''
            for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str):
                d = int(m.group(1).replace('-','').replace('$',''), 16)
                if m.group(1).startswith('-'): d = -d
                ea += f"  ;[0x{(A4+d)&0xFFFFFF:05X}]"
            return f"{insns[0].mnemonic} {insns[0].op_str}{ea}"
    return f"???"

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

def intr_hook(emu, intno, _):
    if intno == 11:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu,a,addr,s,v,_: False)

STEP = [0]
IN_FC6 = [False]
DEPTH = [0]
FOUND = [False]
TRACE_AFTER = [False]
TRACE_COUNT = [0]

# Use a ring buffer of last 100 PCs before the hit
RECENT = []

def code_hook(emu, addr, size, _):
    STEP[0] += 1

    # Track call depth from 0x0FC6
    if addr == 0x0FC6:
        IN_FC6[0] = True
        DEPTH[0] = 0

    if IN_FC6[0]:
        insns = list(md.disasm(code[addr:addr+size], addr)) if 0 < addr < len(code) else []
        if insns:
            ins = insns[0]
            if ins.mnemonic in ('jsr', 'bsr'):
                DEPTH[0] += 1
            elif ins.mnemonic == 'rts':
                if DEPTH[0] > 0:
                    DEPTH[0] -= 1
                else:
                    # 0x0FC6 returned!
                    print(f"\n*** 0x0FC6 RETURNED at step {STEP[0]}! D0=0x{emu.reg_read(m68k.UC_M68K_REG_D0):08X}")
                    FOUND[0] = True
                    emu.emu_stop()

        # Capture recent PCs for context
        RECENT.append((STEP[0], addr, DEPTH[0]))
        if len(RECENT) > 200:
            RECENT.pop(0)

        # Detect first hit to 0x013E or 0x0108 (the thunks)
        if not FOUND[0] and addr in (0x013E, 0x00108, 0x0274, 0x0000):
            FOUND[0] = True
            print(f"\n*** First hit to 0x{addr:05X} ({dis1(addr)}) at step {STEP[0]}, depth={DEPTH[0]}")
            print(f"    A7=0x{emu.reg_read(m68k.UC_M68K_REG_A7):08X}")
            # Show last 100 instructions
            print(f"\nLast 100 instructions before hit:")
            for s, a, d in RECENT[-100:]:
                print(f"  step={s:7d} depth={d:3d}  0x{a:05X}: {dis1(a)}")
            # Continue for 20 more steps to see what happens
            TRACE_AFTER[0] = True

    if TRACE_AFTER[0]:
        TRACE_COUNT[0] += 1
        if TRACE_COUNT[0] <= 30:
            print(f"  +{TRACE_COUNT[0]:2d}  step={STEP[0]:7d}  0x{addr:05X}: {dis1(addr)}  A7=0x{emu.reg_read(m68k.UC_M68K_REG_A7):08X}")
        else:
            emu.emu_stop()

cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

t0 = time.perf_counter()
print("Running until first 0x013E call from within 0x0FC6 (up to 5M steps)...")
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=5_000_000)
except Exception as e:
    print(f"Exception: {e}")
elapsed = time.perf_counter() - t0
print(f"\nDone: t={elapsed:.2f}s  steps={STEP[0]}  in_fc6={IN_FC6[0]}  found={FOUND[0]}")
