#!/usr/bin/env python3
"""Count how many times 0x015C (the game-loop function) is called from WITHIN 0x0FC6."""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import A4 as A4_VALUE, AI_OUTER_DRIVER_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

CHIP_RAM_BASE = 0;  CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]

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

# Track the game-loop "tick" function at 0x015C
# Each time it's entered, count it and check if the AI has stored a result
GAME_LOOP_HITS = [0]
AI_DONE_STEP = [None]
STEP = [0]
FIRST_HITS = []
LAST_PC = [0]

def code_hook(emu, addr, size, _):
    STEP[0] += 1
    LAST_PC[0] = addr
    if addr == 0x015C:
        GAME_LOOP_HITS[0] += 1
        if len(FIRST_HITS) < 5:
            a7 = emu.reg_read(m68k.UC_M68K_REG_A7)
            FIRST_HITS.append((STEP[0], a7))
        # Check if AI has a result
        done = struct.unpack('>H', bytes(emu.mem_read(0x012B6, 2)))[0]
        move_f = bytes(emu.mem_read(0x025F, 1))[0]
        move_from = bytes(emu.mem_read(0x04AD2, 1))[0]
        move_to = bytes(emu.mem_read(0x04AD3, 1))[0]
        if (done != 0 or move_f != 0 and move_f != 0x14) and AI_DONE_STEP[0] is None:
            AI_DONE_STEP[0] = STEP[0]
            print(f"\n*** AI result at step {STEP[0]}: done={done:#x} [025F]={move_f:#x} from=0x{move_from:02X} to=0x{move_to:02X}")
            emu.emu_stop()
        if GAME_LOOP_HITS[0] % 100 == 0:
            print(f"  game-loop tick #{GAME_LOOP_HITS[0]:5d}  step={STEP[0]:7d}  done={done:#x} [025F]={move_f:#x} from=0x{move_from:02X} to=0x{move_to:02X}",
                  flush=True)
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

t0 = time.perf_counter()
print('Running 2M steps, watching game-loop ticks...')
try:
    cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=2_000_000)
except Exception as e:
    print(f'Exception: {e}')
elapsed = time.perf_counter() - t0
print(f'\nt={elapsed:.2f}s  F-lines={INTR[0]}  game-loop-hits={GAME_LOOP_HITS[0]}  last_PC=0x{LAST_PC[0]:05X}')
print(f'First 5 game-loop hits: {[(s,f"sp=0x{a7:06X}") for s,a7 in FIRST_HITS]}')
