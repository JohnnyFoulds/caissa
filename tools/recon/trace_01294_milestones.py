#!/usr/bin/env python3
"""Trace milestone instructions inside 0x01294 to find where it's stuck."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, PIECE_TABLE_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE
PROGRESS_CALLBACK_JSRS = [0x3040, 0x30FA, 0x3556, 0x3A8E, 0x3BE4, 0x3CE6, 0x3DBC]

rom_data = open(default_rom_path(), 'rb').read()
regions = parse_amiga_hunk(rom_data)

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
cpu.mem_write(sp + 8, struct.pack('>H', 0x01))  # level=1 for speed
cpu.reg_write('A7', sp)

cpu._uc.hook_add(UC_HOOK_INTR,
    lambda emu, intno, _: emu.reg_write(m68k.UC_M68K_REG_PC,
        emu.reg_read(m68k.UC_M68K_REG_PC) + 2) if intno == 11 else None)
cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu, a, addr, s, v, _: False)

STEP = [0]
MILESTONES = {
    0x012AA: "about to call jsr 0x0FC6 (alpha-beta)",
    0x012AE: "RETURNED from 0x0FC6 — search done!",
    0x012B2: "entered piece-count loop",
    0x012BE: "exited piece-count loop",
    0x012C4: "moveq #$1a, d7 (count was < 26)",
    0x012C6: "addq.w #1 d7",
    0x012F8: "about to call jsr 0x02A1C (visualization)",
    0x012FC: "returned from 0x02A1C",
    0x01320: "about to call jsr [0x0022E]",
    0x01324: "returned from jsr [0x0022E] (1st)",
    0x01348: "about to call jsr [0x0022E] (2nd)",
    0x0134C: "returned from jsr [0x0022E] (2nd)",
    0x01350: "event-poll loop top",
    0x01354: "event-poll cmp",
    0x01376: "about to call jsr 0x01032 (finalize)",
    0x0137A: "clearing [025C] (search done)",
    0x01384: "RTS from 0x01294 — back to SENTINEL!",
}
FIRED = set()


def code_hook(emu, addr, size, _):
    STEP[0] += 1
    if addr in MILESTONES and addr not in FIRED:
        FIRED.add(addr)
        sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
        d7 = emu.reg_read(m68k.UC_M68K_REG_D7)
        print(f"  step={STEP[0]:8d}  PC=0x{addr:05X}  SP=0x{sp_now:05X}  D7=0x{d7:08X}  "
              f"→ {MILESTONES[addr]}")
    if STEP[0] % 500_000 == 0:
        sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
        print(f"  step={STEP[0]:8d}  PC=0x{addr:05X}  SP=0x{sp_now:05X}", flush=True)


cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

t0 = time.perf_counter()
try:
    cpu.emu_start(0x01294, until=SENTINEL, count=2_000_000)
except Exception as e:
    print(f"Exception: {e}")
elapsed = time.perf_counter() - t0

final_pc = cpu._uc.reg_read(m68k.UC_M68K_REG_PC)
final_sp = cpu._uc.reg_read(m68k.UC_M68K_REG_A7)
print(f"\nDone: t={elapsed:.2f}s  steps={STEP[0]:,}")
print(f"final_PC=0x{final_pc:05X}  SP=0x{final_sp:05X}")
print(f"Fired milestones: {sorted(hex(m) for m in FIRED)}")
