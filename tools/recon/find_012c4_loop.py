#!/usr/bin/env python3
"""Find what keeps looping back to 0x012C4."""
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
PROGRESS_CALLBACK_JSRS = [0x3040, 0x30FA, 0x3556, 0x3A8E, 0x3BE4, 0x3CE6, 0x3DBC]

rom_data = open(default_rom_path(), 'rb').read()
regions = parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)


def dis1(addr):
    if 0 < addr < len(code):
        insns = list(md.disasm(code[addr:addr + 8], addr))
        if insns:
            ea = ''
            for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str):
                d = int(m.group(1).replace('-', '').replace('$', ''), 16)
                if m.group(1).startswith('-'):
                    d = -d
                ea += f"  ;[0x{(A4 + d) & 0xFFFFFF:05X}]"
            return f"{insns[0].mnemonic} {insns[0].op_str}{ea}"
    return f"0x{addr:05X}(???)"


cpu = Unicorn68k()
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for r in regions:
    if r.size > 0:
        cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
cpu.map_region(HW_BASE, HW_SIZE)
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
traps = AmigaTraps(cpu); traps.install(); traps.install_mem_hook()
cpu.map_region(0x300000, EXEC_START - 0x300000)
cpu.map_region(EXEC_END, HW_BASE - EXEC_END)
cpu.map_region(0x1000000, 0x7F000000)
cpu.map_region(0xFF000000, 0x00FF0000)

cpu.reg_write('A4', A4)
bridge = Bridge(cpu)
bridge.write_position('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
bridge.set_computer_color(0)

for addr in (0x025C, 0x025D, 0x024F, 0x024E, 0x025E, 0x025F):
    cpu.mem_write(addr, b'\x00')
cpu.mem_write(0x012B6, struct.pack('>H', 0))
cpu.mem_write(0x04AD5, b'\x00')
cpu.mem_write(0x0331C, struct.pack('>H', 0))
cpu.mem_write(0x001EC, b'\x4E\x75')
for paddr in PROGRESS_CALLBACK_JSRS:
    cpu.mem_write(paddr, b'\x4E\x71\x4E\x71')

sp = STACK_TOP - 4
cpu.mem_write(sp + 0, struct.pack('>I', SENTINEL))
cpu.mem_write(sp + 4, struct.pack('>I', PIECE_TABLE_ADDR))
cpu.mem_write(sp + 8, struct.pack('>H', 0x01))
cpu.reg_write('A7', sp)

cpu._uc.hook_add(UC_HOOK_INTR,
    lambda emu, intno, _: emu.reg_write(m68k.UC_M68K_REG_PC,
        emu.reg_read(m68k.UC_M68K_REG_PC) + 2) if intno == 11 else None)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu, a, addr, s, v, _: False)

STEP = [0]
RECENT = []
COUNT_012C4 = [0]
STOP_AFTER = 3  # dump after 2nd hit to 0x012C4


def code_hook(emu, addr, size, _):
    STEP[0] += 1
    RECENT.append(addr)
    if len(RECENT) > 40:
        RECENT.pop(0)

    if addr == 0x012C4:
        COUNT_012C4[0] += 1
        if COUNT_012C4[0] >= STOP_AFTER:
            sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
            print(f"\n  === 0x012C4 visit #{COUNT_012C4[0]} at step {STEP[0]}  SP=0x{sp_now:05X} ===")
            print(f"  Last {len(RECENT)} instructions before this:")
            for a in RECENT[-30:]:
                print(f"    0x{a:05X}: {dis1(a)}")
            if COUNT_012C4[0] >= STOP_AFTER + 1:
                emu.emu_stop()


cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

t0 = time.perf_counter()
try:
    cpu.emu_start(0x01294, until=SENTINEL, count=5_000_000)
except Exception as e:
    print(f"Exception: {e}")
elapsed = time.perf_counter() - t0

final_pc = cpu._uc.reg_read(m68k.UC_M68K_REG_PC)
final_sp = cpu._uc.reg_read(m68k.UC_M68K_REG_A7)
print(f"\nDone: t={elapsed:.2f}s  steps={STEP[0]:,}")
print(f"final_PC=0x{final_pc:05X}  SP=0x{final_sp:05X}")
print(f"Total 0x012C4 visits: {COUNT_012C4[0]}")
