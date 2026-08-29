#!/usr/bin/env python3
"""Find WHERE inside 0x0FC6's recursion the progress callback at 0x001A6 is called.

The callback at 0x001A6 (D0=0xA1 "copy board + set search_running") is reached
from within 0x0FC6's search tree. We need to find the exact call chain.

Strategy:
  - Set hook on first entry to 0x001DA (the dispatch that leads to 0x001A6)
  - At that point, dump: SP, return-address chain, and the 5 PCs before it
  - Also find which sub-function in 0x3218 calls into the dispatch
"""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, PIECE_TABLE_ADDR, Bridge
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
    if 0 <= addr < len(code):
        insns = list(md.disasm(code[addr:addr + 8], addr))
        if insns:
            ea = ''
            for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str):
                d = int(m.group(1).replace('-', '').replace('$', ''), 16)
                if m.group(1).startswith('-'): d = -d
                ea += f"  ;[0x{(A4+d)&0xFFFFFF:05X}]"
            return f"{insns[0].mnemonic} {insns[0].op_str}{ea}"
    return f"0x{addr:05X}(???)"

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
for addr in (0x025C, 0x025D, 0x024F, 0x024E, 0x025E, 0x025F):
    cpu.mem_write(addr, b'\x00')
cpu.mem_write(0x04AD5, b'\x00')

# Patch visualization callback at 0x001EC
cpu.mem_write(0x001EC, b'\x4E\x75')

# Stack setup for direct call to 0x01294
sp = STACK_TOP - 4
cpu.mem_write(sp + 0, struct.pack('>I', SENTINEL))
cpu.mem_write(sp + 4, struct.pack('>I', PIECE_TABLE_ADDR))
cpu.mem_write(sp + 8, struct.pack('>H', 0x16))
cpu.reg_write('A7', sp)

def intr_hook(emu, intno, _):
    if intno == 11:
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu, a, addr, s, v, _: False)

STEP = [0]
RECENT = []
TRIGGERED = [False]

def code_hook(emu, addr, size, _):
    STEP[0] += 1
    RECENT.append(addr)
    if len(RECENT) > 80:
        RECENT.pop(0)

    if not TRIGGERED[0] and addr == 0x001DA:
        TRIGGERED[0] = True
        sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
        a5 = emu.reg_read(m68k.UC_M68K_REG_A5)

        print(f"\n=== FIRST HIT TO 0x001DA at step {STEP[0]} ===")
        print(f"  SP=0x{sp_now:05X}  A5=0x{a5:05X}")

        # Dump last 60 PCs before this point
        print(f"\n  Last {len(RECENT)} PCs before 0x001DA:")
        for a in RECENT[-60:]:
            print(f"    0x{a:05X}: {dis1(a)}")

        # Dump call stack: read potential return addresses from stack
        print(f"\n  Call stack (stack contents from SP to SP+0x80):")
        for off in range(0, 0x80, 4):
            try:
                val = struct.unpack('>I', bytes(emu.mem_read(sp_now + off, 4)))[0]
                inrange = 0 < val < len(code)
                print(f"    SP+{off:#04x}: 0x{val:08X}  {'← in code: ' + dis1(val) if inrange else ''}")
            except Exception:
                pass

        # What is D0 at this point?
        d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
        print(f"\n  D0=0x{d0:08X}  (for dispatch: D0-0xA1={d0-0xA1:#x})")

        emu.emu_stop()

cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

print("Tracing direct call to 0x01294 until first hit to 0x001DA...")
t0 = time.perf_counter()
try:
    cpu.emu_start(0x01294, until=SENTINEL, count=200_000)
except Exception as e:
    print(f"Exception: {e}")
print(f"Done in {time.perf_counter()-t0:.2f}s  steps={STEP[0]}")
