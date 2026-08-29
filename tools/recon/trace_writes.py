#!/usr/bin/env python3
"""Trace what the startup code writes to the problematic low-address globals.

Runs from 0x000000 for up to 5M instructions with write hooks on addresses
we know are causing crashes: 0x025C, 0x025D, 0x024F, 0x1152.
Also watches the BSS area below 0x28D4 for any writes.
"""
import sys, struct
sys.path.insert(0, "bin")

from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
import unicorn.m68k_const as m68k

from pathlib import Path
from Code.Retro.Manifest import default_rom_path, verify
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

CHIP_RAM_BASE = 0x000000
CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000
SENTINEL = 0xFFFF0000
A4 = A4_VALUE  # 0x7FFE

rom_path = default_rom_path()
rom_data = open(rom_path, "rb").read()
regions = parse_amiga_hunk(rom_data)

cpu = Unicorn68k()
cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
for region in regions:
    if region.size > 0:
        cpu.mem_write(region.load_address, rom_data[region.offset:region.offset + region.size])
cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)

traps = AmigaTraps(cpu)
traps.install()
traps.install_mem_hook()
cpu.reg_write("A4", A4)

# Addresses of interest (all are global data, pre-init garbage in ROM)
WATCH = {
    0x025C: "flag1 (A4-0x7DA2)",
    0x025D: "flag2 (A4-0x7DA1)",
    0x024F: "flag3 (A4-0x7DAF)",
    0x1152: "linked-list head (A4-0x6EAC)",
    0x07D4: "player_type[White]",
    0x07D6: "player_type[Black]",
    0x12B6: "done_flag (A4-0x6D48)",
    0x4A5A: "move_state (A4-0x35A4)",
    0x4A5C: "phase_counter (A4-0x35A2)",
}

writes = []  # (pc, addr, size, value)
stop_pc = [None]

def mem_write_hook(emu, access, address, size, value, user_data):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    # Watch any write to addresses below 0x28D4 (the "small data" area)
    if address < 0x28D4:
        label = WATCH.get(address, f"low-addr 0x{address:04X}")
        writes.append((pc, address, size, value))
        print(f"  WRITE: PC=0x{pc:05X} → [{label}]=0x{value:0{size*2}X} (size={size})")

cpu._uc.hook_add(UC_HOOK_MEM_WRITE, mem_write_hook)

# Stop when we hit the main game loop dispatch (0x0638) twice
game_loop_visits = [0]
stop_addr = [False]

def code_hook(emu, address, size, user_data):
    if address == 0x0638:
        game_loop_visits[0] += 1
        if game_loop_visits[0] >= 2:
            stop_addr[0] = True
            emu.emu_stop()
    # Also stop at any infinite loops we might hit
    elif address == 0x110E0 and game_loop_visits[0] == 0:
        pass  # BSS zero loop, let it run

cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

fault_info = [None]
def fault_hook(emu, access, address, size, value, user_data):
    pc = emu.reg_read(m68k.UC_M68K_REG_PC)
    fault_info[0] = (pc, address, size)
    print(f"  FAULT: PC=0x{pc:05X} → addr=0x{address:08X} size={size}")
    emu.emu_stop()

cpu._uc.hook_add(UC_HOOK_MEM_INVALID, fault_hook)

import struct as _struct
sp = STACK_TOP - 4
cpu.mem_write(sp, _struct.pack(">I", SENTINEL))
cpu.reg_write("A7", sp)

print("Running from 0x0000 (game startup)...")
try:
    cpu.emu_start(0x0000, until=SENTINEL, count=10_000_000)
    print("Emulation stopped cleanly.")
except Exception as e:
    print(f"Emulation error: {e}")

print(f"\nGame loop visits: {game_loop_visits[0]}")
print(f"Stop reason: {'fault' if fault_info[0] else 'stop_addr' if stop_addr[0] else 'count/sentinel'}")

if fault_info[0]:
    pc, addr, sz = fault_info[0]
    print(f"Fault at PC=0x{pc:05X}, memory addr=0x{addr:08X}")

print(f"\nTotal writes to low-addr area: {len(writes)}")

# Show final values of all watched addresses
print("\nFinal values of watched globals:")
for addr, label in sorted(WATCH.items()):
    raw = bytes(cpu._uc.mem_read(addr, 4))
    val = _struct.unpack(">I", raw)[0]
    print(f"  0x{addr:04X} {label}: 0x{val:08X}")
