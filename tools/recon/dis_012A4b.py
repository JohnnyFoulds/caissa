#!/usr/bin/env python3
"""Disassemble exactly at 0x012A4 and trace who calls it, using write hook with full stack trace."""
import sys, struct, re
sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID
import unicorn.m68k_const as m68k
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

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

# Disassemble from exactly 0x012A4
print("=== 0x012A4 (direct) ===")
for i, ins in enumerate(md.disasm(code[0x012A4:0x012A4+60], 0x012A4)):
    ea = ""
    m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str)
    if m:
        d = int(m.group(1).replace('-','').replace('$',''), 16)
        if m.group(1).startswith('-'): d = -d
        ea = f"  ; [0x{(A4 + d) & 0xFFFFFF:05X}]"
    raw = code[ins.address:ins.address + ins.size].hex()
    print(f"  0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
    if ins.mnemonic == 'rts': break
    if i >= 25: break

# Now run with stack-walk write hook
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

FIRED = [False]
def watch_hook(emu, access, address, size, value, _):
    if FIRED[0]: return
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    sp2 = emu.reg_read(m68k.UC_M68K_REG_A7)
    print(f"\nWrite to 0x{address:05X}={value:#x}  from PC=0x{pc:05X}")
    print("Stack walk (return addresses):")
    for i in range(16):
        try:
            v2 = struct.unpack('>I', bytes(emu.mem_read(sp2 + i*4, 4)))[0]
            if 0 < v2 < 0x12000:
                print(f"  sp+{i*4:2d}: 0x{v2:05X}")
        except: pass
    FIRED[0] = True
cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_hook, begin=0x0250, end=0x0270)

print("\nRunning 500K steps to catch write...")
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=500_000)
except Exception as e:
    print(f"Exception: {e}")
print(f"F-lines={INTR[0]}")
