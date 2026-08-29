#!/usr/bin/env python3
import sys, struct, re
sys.path.insert(0, 'bin')
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
import capstone

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)

print("=== Decode at 0x001DC-0x001F0 ===")
for ins in md.disasm(code[0x001DC:0x001F4], 0x001DC):
    m = re.match(r'^\$([0-9a-fA-F]+)$', ins.op_str.strip())
    print(f"  0x{ins.address:05X}: [{code[ins.address:ins.address+ins.size].hex()}]"
          f" mnem={ins.mnemonic!r} op={ins.op_str!r}  match={bool(m)}")

# Broader scan - entire ROM for any branch landing at 0x001A6
targets = set(range(0x001A0, 0x001CD))
print(f"\n=== Full ROM scan for branches to 0x001A0-0x001CC ===")
hits = []
for addr in range(0, len(code) - 4, 2):
    insns = list(md.disasm(code[addr:addr+8], addr))
    if not insns: continue
    ins = insns[0]
    if ins.mnemonic not in ('bra','bsr','beq','bne','blt','bgt','ble','bge',
                             'bhi','bls','bpl','bmi','bcs','bcc','jsr','jmp',
                             'dbra','dbf'): continue
    m = re.match(r'^\$([0-9a-fA-F]+)$', ins.op_str.strip())
    if m:
        t = int(m.group(1), 16)
        if t in targets:
            hits.append((addr, ins.mnemonic, ins.op_str, t))
print(f"  Found {len(hits)} hits:")
for addr, mn, op, t in sorted(hits):
    print(f"  0x{addr:05X}: {mn} {op}  -> 0x{t:05X}")

# Also: what is the instruction at 0x001E0?
print(f"\n=== Bytes at 0x001E0: {code[0x001E0:0x001E4].hex()} ===")
for ins in md.disasm(code[0x001E0:0x001E8], 0x001E0):
    print(f"  0x{ins.address:05X}: {ins.mnemonic} {ins.op_str}")
    break

# Try to trace WHAT IS EXECUTING at step ~128600 using a hook that records
# the 10 instructions before hitting 0x001C6 for the first time
print("\n=== Actual execution trace: 20 PCs before first write to [025E] ===")
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
import unicorn.m68k_const as m68k
from Code.Retro.Bridge import A4 as A4_VALUE, PIECE_TABLE_ADDR, Bridge
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k

CHIP_RAM_BASE = 0; CHIP_RAM_SIZE = 0x200000
STACK_TOP = 0x1F0000; SENTINEL = 0xFFFF0000
HW_BASE = 0xBFC000; HW_SIZE = 0x404000
EXEC_START = EXEC_BASE - LIB_RANGE; EXEC_END = EXEC_BASE + LIB_RANGE
A4 = A4_VALUE

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
bridge = Bridge(cpu); bridge.write_position('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
bridge.set_computer_color(0)
for addr in (0x025C, 0x025D, 0x024F, 0x024E, 0x025E, 0x025F): cpu.mem_write(addr, b'\x00')
cpu.mem_write(0x04AD5, b'\x00')
cpu.mem_write(0x001EC, b'\x4E\x75')

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

STEP = [0]; RECENT = []; DONE = [False]

def code_hook(emu, addr, size, _):
    STEP[0] += 1
    RECENT.append(addr)
    if len(RECENT) > 120: RECENT.pop(0)
    # Wider range: trigger if any of 0x001A0-0x001CC is hit
    if not DONE[0] and 0x001A0 <= addr <= 0x001CC:
        DONE[0] = True
        sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
        a5 = emu.reg_read(m68k.UC_M68K_REG_A5)
        d0 = emu.reg_read(m68k.UC_M68K_REG_D0)
        print(f"  First hit to range 0x001A0-0x001CC: addr=0x{addr:05X}  step={STEP[0]}")
        print(f"  SP=0x{sp_now:05X}  A5=0x{a5:05X}  D0=0x{d0:08X}")
        print(f"  Last {len(RECENT)} PCs:")
        for a in RECENT[-100:]:
            insns = list(md.disasm(code[a:a+8], a)) if 0 < a < len(code) else []
            label = f"{insns[0].mnemonic} {insns[0].op_str}" if insns else "???"
            print(f"    0x{a:05X}: {label}")
        print("\n  Call stack contents SP to SP+0x90:")
        for off in range(0, 0x90, 4):
            try:
                val = struct.unpack('>I', bytes(emu.mem_read(sp_now + off, 4)))[0]
                inrange = 0 < val < 0x12000
                lbl = ''
                if inrange:
                    ii = list(md.disasm(code[val:val+8], val))
                    lbl = f"  <- {ii[0].mnemonic} {ii[0].op_str}" if ii else "  <- ???"
                print(f"    SP+{off:#04x}: 0x{val:08X}{lbl}")
            except Exception:
                pass
        emu.emu_stop()
cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

try:
    cpu.emu_start(0x01294, until=SENTINEL, count=200_000)
except Exception as e:
    print(f"Exception: {e}")
print(f"steps={STEP[0]}")
