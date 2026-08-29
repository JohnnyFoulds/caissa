#!/usr/bin/env python3
"""Test different m68k CPU variants to find one that handles extension words correctly."""
import sys, struct
sys.path.insert(0, "bin")
import unicorn
import unicorn.m68k_const as m68k
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID

from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE

rom_data = open(default_rom_path(), "rb").read()
regions  = parse_amiga_hunk(rom_data)

CPU_VARIANTS = [
    ("M68K_000",    unicorn.m68k_const.UC_CPU_M68K_M68000),
    ("M68K_010",    unicorn.m68k_const.UC_CPU_M68K_M68010),
    ("M68K_EC020",  unicorn.m68k_const.UC_CPU_M68K_M68EC020),
    ("M68K_020",    unicorn.m68k_const.UC_CPU_M68K_M68020),
    ("M68K_030",    unicorn.m68k_const.UC_CPU_M68K_M68030),
    ("M68K_040",    unicorn.m68k_const.UC_CPU_M68K_M68040),
]

CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000; STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000

for name, cpu_type in CPU_VARIANTS:
    try:
        uc = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(cpu_type)
    except Exception as e:
        print(f"{name}: not available ({e})")
        continue

    uc.mem_map(CHIP_RAM_BASE, CHIP_RAM_SIZE)
    for r in regions:
        if r.size > 0:
            uc.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
    uc.mem_map(ALLOC_POOL, ALLOC_POOL_SIZE)

    A4 = A4_VALUE

    # Basic fixes
    for addr in (0x025C, 0x025D, 0x024F, 0x024E):
        uc.mem_write(addr, b"\x00")
    uc.mem_write(0x1152, b"\x00\x00\x00\x00")
    uc.mem_write(0x6FFF, b"\x00" * (0x7FFE - 0x6FFF))  # zero F-line range
    uc.mem_write(0x36B0, b"\x4e\x73")  # RTE at F-line handler

    uc.reg_write(m68k.UC_M68K_REG_A4, A4)

    # Simple AllocMem stub
    EXEC_BASE = 0x800000; LIB_RANGE = 0x040000; bump = [ALLOC_POOL]
    uc.mem_map(EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
    uc.mem_write(EXEC_BASE - LIB_RANGE, b"\x4e\x75" * LIB_RANGE)  # RTS
    def code_stub(emu, addr, size, _):
        if EXEC_BASE - LIB_RANGE <= addr < EXEC_BASE + LIB_RANGE:
            offset = addr - EXEC_BASE
            if offset == -0xC6:
                d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
                aligned = (d0 + 7) & ~7
                emu.reg_write(m68k.UC_M68K_REG_D0, bump[0])
                bump[0] += max(aligned, 8)
            elif offset == -0x198:
                emu.reg_write(m68k.UC_M68K_REG_D0, EXEC_BASE)
    uc.hook_add(unicorn.UC_HOOK_CODE, code_stub)

    # Mem hook for AbsExecBase
    def mem_stub(emu, access, address, size, value, _):
        if address == 0x4:
            emu.mem_write(0x4, EXEC_BASE.to_bytes(4, "big"))
    uc.hook_add(unicorn.UC_HOOK_MEM_READ, mem_stub)

    # Set computer=White
    PLAYER_TYPE_BASE = 0x07D4
    PLAYER2_COLOR_ADDR = 0x4A68
    uc.mem_write(PLAYER_TYPE_BASE + 0, struct.pack(">H", 2))  # White=Computer
    uc.mem_write(PLAYER_TYPE_BASE + 2, struct.pack(">H", 1))  # Black=Human
    uc.mem_write(PLAYER2_COLOR_ADDR, struct.pack(">H", 1))     # PLAYER2=Black

    sp = STACK_TOP - 4
    uc.mem_write(sp, struct.pack(">I", SENTINEL))
    uc.reg_write(m68k.UC_M68K_REG_A7, sp)

    intr_count = [0]
    def intr_h(emu, intno, _):
        intr_count[0] += 1
    def fault_h(emu, access, address, size, value, _):
        if address >= 0x200000:
            emu.emu_stop(); return False
        aligned = address & ~3
        try: emu.mem_write(aligned, b"\x00" * 4)
        except: emu.emu_stop(); return False
        return True
    uc.hook_add(UC_HOOK_INTR, intr_h)
    uc.hook_add(UC_HOOK_MEM_INVALID, fault_h)

    try:
        uc.emu_start(AI_OUTER_DRIVER_ADDR, SENTINEL, count=1_000_000)
        result = "1M instructions ok"
    except Exception as e:
        result = f"error: {e}"

    print(f"{name}: intrs={intr_count[0]:,} {result}")
