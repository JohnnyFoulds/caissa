#!/usr/bin/env python3
"""Find when 0x0FC6 returns and trace the 100 steps after it, then find all writes to ALL memory."""
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

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE
FC6_RET = 0x012AE   # return address from 0x0FC6

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

STEP = [0]
FC6_RETURNED = [False]
PRINT_AFTER = [False]
PRINT_COUNT = [0]

def code_hook(emu, addr, size, _):
    STEP[0] += 1
    if addr == FC6_RET and not FC6_RETURNED[0]:
        FC6_RETURNED[0] = True
        PRINT_AFTER[0] = True
        d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
        d1 = emu.reg_read(m68k.UC_M68K_REG_D1)
        a7 = emu.reg_read(m68k.UC_M68K_REG_A7)
        print(f"\n*** 0x0FC6 RETURNED at step {STEP[0]} ***")
        print(f"    D0=0x{d0:08X}  D1=0x{d1:08X}  A7=0x{a7:06X}")
        print(f"    [0x025C]={bytes(emu.mem_read(0x025C,1))[0]:#x}  [0x012B6]={struct.unpack('>H', bytes(emu.mem_read(0x012B6,2)))[0]:#x}")
    if PRINT_AFTER[0] and PRINT_COUNT[0] < 150:
        PRINT_COUNT[0] += 1
        ea = ""
        if 0 < addr < len(code):
            insns = list(md.disasm(code[addr:addr+8], addr))
            if insns:
                m2 = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str)
                if m2:
                    d = int(m2.group(1).replace('-','').replace('$',''), 16)
                    if m2.group(1).startswith('-'): d = -d
                    ea = f"  [{(A4+d)&0xFFFFFF:05X}]"
                dis = f"{insns[0].mnemonic} {insns[0].op_str}{ea}"
            else:
                dis = "???"
        else:
            dis = f"(outside: 0x{addr:08X})"
        print(f"  {STEP[0]:6d}  0x{addr:05X}: {dis}")
        if PRINT_COUNT[0] == 150:
            print("  --- stopping trace ---")
            emu.emu_stop()
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

# Also watch all writes to the game-state area (0x012B0-0x012C0 and 0x04AC0-0x04B00, 0x025C-0x0270)
ALL_WRITES = []
def any_write(emu, access, address, size, value, _):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    if FC6_RETURNED[0]:
        dis = ""
        if 0 < pc < len(code):
            insns = list(md.disasm(code[pc:pc+8], pc))
            if insns: dis = f"{insns[0].mnemonic} {insns[0].op_str}"
        ALL_WRITES.append(f"  step={STEP[0]:6d} [0x{address:05X}]={value:#04x}  PC=0x{pc:05X}: {dis}")
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, any_write, begin=0x0000, end=0x1000)  # watch low memory including flags
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, any_write, begin=0x04A00, end=0x04B00)  # watch move area

t0 = time.perf_counter()
print('Running until 0x0FC6 returns (up to 500K steps)...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000)
except Exception as e:
    print(f'Exception: {e}')
elapsed = time.perf_counter() - t0
print(f'\nt={elapsed:.2f}s  F-lines={INTR[0]}  step={STEP[0]}')
if FC6_RETURNED[0]:
    print(f'\nWrites after 0x0FC6 returned:')
    for w in ALL_WRITES[:50]:
        print(w)
else:
    print("0x0FC6 did NOT return within 500K steps")
    pc = struct.unpack('>I', bytes(cpu.mem_read(cpu.reg_read(m68k.UC_M68K_REG_A7), 4)))[0]
    print(f"Top of stack (return addr): 0x{pc:08X}")
