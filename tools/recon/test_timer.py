#!/usr/bin/env python3
"""Simulate the Amiga timer: clear [0x025C] after N steps to stop the AI search."""
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

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

def dis(emu, addr):
    if 0 < addr < len(code):
        insns = list(md.disasm(code[addr:addr+8], addr))
        if insns:
            ea = ""
            m = re.search(r'(-?\$[0-9a-fA-F]+)\(a4\)', insns[0].op_str)
            if m:
                d = int(m.group(1).replace('-','').replace('$',''), 16)
                if m.group(1).startswith('-'): d = -d
                ea = f"  [{(A4+d)&0xFFFFFF:05X}]"
            return f"{insns[0].mnemonic} {insns[0].op_str}{ea}"
    return f"(0x{addr:08X})"

def run_with_timer(timer_steps=5000):
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

    STEP = [0]; AI_STARTED_STEP = [None]; TIMER_FIRED = [False]
    MOVE_FOUND = [None]

    def code_hook(emu, addr, size, _):
        STEP[0] += 1
        # Detect when AI started: [025C] becomes 1 at 0x012A4
        if AI_STARTED_STEP[0] is None and addr == 0x012A5:  # step AFTER the write
            AI_STARTED_STEP[0] = STEP[0]
        # Fire "timer" N steps after AI started
        if (AI_STARTED_STEP[0] is not None and not TIMER_FIRED[0]
                and STEP[0] >= AI_STARTED_STEP[0] + timer_steps):
            TIMER_FIRED[0] = True
            # Clear [0x025C] = 0 (AI stop signal from timer)
            emu.mem_write(0x025C, b'\x00')
        # Check for move stored (watch [0x025F] becomes 1)
        if addr == 0x0019A:  # instruction that sets [025F]=1
            mf = bytes(emu.mem_read(0x04AD2, 1))[0]
            mt = bytes(emu.mem_read(0x04AD3, 1))[0]
            MOVE_FOUND[0] = (mf, mt, STEP[0])
            print(f"  [0x025F]=1 at step {STEP[0]}: from=0x{mf:02X} to=0x{mt:02X}")
            emu.emu_stop()
    cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

    t0 = time.perf_counter()
    try:
        cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=SENTINEL, count=10_000_000)
    except Exception as e:
        pass  # normal if we call emu_stop
    elapsed = time.perf_counter() - t0

    # Final state
    v025C = bytes(cpu.mem_read(0x025C, 1))[0]
    v025F = bytes(cpu.mem_read(0x025F, 1))[0]
    v012B6 = struct.unpack('>H', bytes(cpu.mem_read(0x012B6, 2)))[0]
    mf = bytes(cpu.mem_read(0x04AD2, 1))[0]
    mt = bytes(cpu.mem_read(0x04AD3, 1))[0]
    return {
        'timer_steps': timer_steps, 't': elapsed,
        'steps': STEP[0], 'f_lines': INTR[0],
        'ai_started': AI_STARTED_STEP[0], 'timer_fired': TIMER_FIRED[0],
        'move_found': MOVE_FOUND[0],
        '025C': v025C, '025F': v025F, '012B6': v012B6,
        'from': mf, 'to': mt,
    }

# Try different timer values
for t in [500, 1000, 2000, 5000, 10000, 50000, 200000]:
    r = run_with_timer(t)
    mf = r['from']; mt = r['to']
    uci = ""
    if not (mf & 0x88) and not (mt & 0x88):
        fr = chr(ord('a') + (mf & 7)) + str((mf >> 4) + 1)
        to = chr(ord('a') + (mt & 7)) + str((mt >> 4) + 1)
        uci = f" → {fr}{to}"
    print(f"timer={t:7d}  t={r['t']:.2f}s  [025F]={r['025F']:#x}  from=0x{mf:02X} to=0x{mt:02X}{uci}  move_found={r['move_found']}")
