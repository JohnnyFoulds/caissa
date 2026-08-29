#!/usr/bin/env python3
"""Call 0x01294 directly, bypassing the 0x17D2→0x00234→jsr[0x00108] non-returning chain.

0x01294 (0x01294–0x01384) is a clean LINK/RTS function that:
  1. Sets [025C]=1 (ai_busy)
  2. Calls jsr 0x0FC6 (alpha-beta search)
  3. Processes result: calls 0x01032 which sets [012B6] from [04A94]
  4. Clears [025C]=0
  5. RTS

Stack layout when entering 0x01294 (after a notional JSR):
  SP+0: SENTINEL (return addr)
  SP+4: pos_ptr  (long arg)
  SP+8: level_word (word arg)

Key findings:
  - [0x331C] must be 0 for White-to-move (computer=White) — Bridge sets it wrong (=1)
  - 0x05FB4 may call the "progress callback" at 0x001A6 which loops via 0x0274
"""
import sys, struct, time
sys.path.insert(0, 'bin')
from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
import unicorn.m68k_const as m68k
from Code.Retro.Manifest import default_rom_path
from Code.Retro.Rom import parse_amiga_hunk
from Code.Retro.Bridge import (
    A4 as A4_VALUE,
    PIECE_TABLE_ADDR,
    Bridge,
)
from Code.Retro.Traps import AmigaTraps, ALLOC_POOL, ALLOC_POOL_SIZE, EXEC_BASE, LIB_RANGE
from Code.Retro.Cpus.Unicorn68k import Unicorn68k
import capstone, re

CHIP_RAM_BASE = 0
CHIP_RAM_SIZE = 0x200000
STACK_TOP     = 0x1F0000
SENTINEL      = 0xFFFF0000
HW_BASE       = 0xBFC000
HW_SIZE       = 0x404000
EXEC_START    = EXEC_BASE - LIB_RANGE
EXEC_END      = EXEC_BASE + LIB_RANGE
A4            = A4_VALUE

rom_data = open(default_rom_path(), 'rb').read()
regions  = parse_amiga_hunk(rom_data)
code     = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
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
    return '???'

def disasm_range(start, n=40, stop_at_rts=True):
    print(f"  === 0x{start:05X} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n*8], start)):
        ea = ''
        for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
            d = int(m.group(1).replace('-','').replace('$',''), 16)
            if m.group(1).startswith('-'): d = -d
            ea += f"  ;[0x{(A4+d)&0xFFFFFF:05X}]"
        raw = code[ins.address:ins.address+ins.size].hex()
        print(f"    0x{ins.address:05X}: [{raw}] {ins.mnemonic} {ins.op_str}{ea}")
        if stop_at_rts and ins.mnemonic == 'rts' and i > 3: break
        if i >= n-1: break

# Disassemble the second visualization target
print("=== Disassembly of 0x05FB4 (jsr $2b2a(pc) from 0x03488) ===")
disasm_range(0x05FB4, 60)

# Disassemble the first 20 instructions around 0x001A6 (D0=0xA1 progress dispatch)
print("\n=== 0x001A6 — D0=0xA1 progress dispatch ===")
disasm_range(0x0018C, 50, stop_at_rts=False)


def run_direct(pos_ptr, level_word, label, max_steps=2_000_000,
               patch_rts=None, patch_nop=None, fix_331c=False, patch_001ee=False,
               stop_on_013e=True):
    """Run 0x01294 directly with pos_ptr and level_word on the stack."""
    print(f"\n{'='*70}")
    print(f"{label}")
    print(f"  pos_ptr=0x{pos_ptr:08X}  level=0x{level_word:04X}  "
          f"fix_331c={fix_331c}  patch_001ee={patch_001ee}", flush=True)

    cpu = Unicorn68k()
    cpu.map_region(CHIP_RAM_BASE, CHIP_RAM_SIZE)
    for r in regions:
        if r.size > 0:
            cpu.mem_write(r.load_address, rom_data[r.offset:r.offset + r.size])
    cpu.map_region(HW_BASE, HW_SIZE)
    cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)
    traps = AmigaTraps(cpu)
    traps.install()
    traps.install_mem_hook()
    cpu.map_region(0x300000, EXEC_START - 0x300000)
    cpu.map_region(EXEC_END, HW_BASE - EXEC_END)
    cpu.map_region(0x1000000, 0x7F000000)
    cpu.map_region(0xFF000000, 0x00FF0000)

    cpu.reg_write('A4', A4)
    bridge = Bridge(cpu)
    bridge.write_position('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
    bridge.set_computer_color(0)

    # Clear state flags
    for addr in (0x025C, 0x025D, 0x024F, 0x024E, 0x025E, 0x025F):
        cpu.mem_write(addr, b'\x00')
    cpu.mem_write(0x012B6, struct.pack('>H', 0))
    # Force level=1 mode
    cpu.mem_write(0x04AD5, b'\x00')

    # Fix: [0x331C] should be 0 (computer's color index = White = 0)
    # Bridge incorrectly sets it to 1 (= Black). With fix: 0.
    if fix_331c:
        cpu.mem_write(0x0331C, struct.pack('>H', 0))
        print("  Fixed [0x331C]=0 (computer=White)")

    # Patch visualization callback at 0x001EC (called from 0x03484)
    cpu.mem_write(0x001EC, b'\x4E\x75')
    # Patch 0x001EE: beq.w $274 → nop;nop (4 bytes: 4e71 4e71)
    # This prevents looping when [012B6]=0 during progress callback
    if patch_001ee:
        cpu.mem_write(0x001EE, b'\x4E\x71\x4E\x71')
        print("  Patched 0x001EE (beq.w $274) → nop;nop")

    if patch_rts:
        for paddr in patch_rts:
            cpu.mem_write(paddr, b'\x4E\x75')
            print(f"  Patch 0x{paddr:05X} → RTS")
    if patch_nop:
        for paddr in patch_nop:
            cpu.mem_write(paddr, b'\x4E\x71\x4E\x71')
            print(f"  Patch 0x{paddr:05X} → nop;nop")

    # Stack: SP → [SENTINEL | pos_ptr | level_word]
    sp = STACK_TOP - 4
    cpu.mem_write(sp + 0, struct.pack('>I', SENTINEL))
    cpu.mem_write(sp + 4, struct.pack('>I', pos_ptr))
    cpu.mem_write(sp + 8, struct.pack('>H', level_word))
    cpu.reg_write('A7', sp)

    def intr_hook(emu, intno, _):
        if intno == 11:
            pc = emu.reg_read(m68k.UC_M68K_REG_PC)
            emu.reg_write(m68k.UC_M68K_REG_PC, pc + 2)
    cpu._uc.hook_add(UC_HOOK_INTR, intr_hook)
    cpu._uc.hook_add(UC_HOOK_MEM_INVALID, lambda emu, a, addr, s, v, _: False)

    STEP = [0]
    RECENT = []
    EVENTS = []

    def watch_writes(emu, access, address, size, value, _):
        pc = emu.reg_read(m68k.UC_M68K_REG_PC)
        msg = None
        if address == 0x025C:
            msg = f"[025C]={value:#x}  (ai_busy)"
        elif address == 0x012B6 and value != 0:
            msg = f"[012B6]={value:#x}  *** DONE FLAG SET! ***"
        elif address == 0x025F and value != 0:
            msg = f"[025F]={value:#x}  *** MOVE FOUND! ***"
        elif address == 0x025E:
            msg = f"[025E]={value:#x}  (search_running)"
        if msg:
            print(f"    step={STEP[0]:8d}  PC=0x{pc:05X}  WRITE {msg}")
            EVENTS.append((STEP[0], pc, address, value))
    cpu._uc.hook_add(UC_HOOK_MEM_WRITE, watch_writes, begin=0, end=0x30000)

    def code_hook(emu, addr, size, _):
        STEP[0] += 1
        RECENT.append(addr)
        if len(RECENT) > 30:
            RECENT.pop(0)
        if STEP[0] % 500_000 == 0:
            v025C  = bytes(emu.mem_read(0x025C, 1))[0]
            v012B6 = struct.unpack('>H', bytes(emu.mem_read(0x012B6, 2)))[0]
            sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
            print(f"  step={STEP[0]:8d}  PC=0x{addr:05X}  [025C]={v025C:#x}  "
                  f"[012B6]={v012B6:#x}  SP=0x{sp_now:05X}", flush=True)
        if addr in (0x013E, 0x0274):
            sp_now = emu.reg_read(m68k.UC_M68K_REG_A7)
            v012B6 = struct.unpack('>H', bytes(emu.mem_read(0x012B6, 2)))[0]
            print(f"\n  *** LOOP ENTRY at 0x{addr:05X}  step={STEP[0]}  "
                  f"SP=0x{sp_now:05X}  [012B6]={v012B6:#x} ***")
            for a in RECENT[-20:]:
                print(f"    0x{a:05X}: {dis1(a)}")
            if stop_on_013e and addr == 0x013E:
                emu.emu_stop()
    cpu._uc.hook_add(UC_HOOK_CODE, code_hook)

    t0 = time.perf_counter()
    try:
        cpu.emu_start(0x01294, until=SENTINEL, count=max_steps)
    except Exception as e:
        print(f"  Exception: {e}")
    elapsed = time.perf_counter() - t0

    final_pc  = cpu._uc.reg_read(m68k.UC_M68K_REG_PC)
    from_sq   = bytes(cpu.mem_read(0x04AD2, 1))[0]
    to_sq     = bytes(cpu.mem_read(0x04AD3, 1))[0]
    v025F     = bytes(cpu.mem_read(0x025F, 1))[0]
    v012B6    = struct.unpack('>H', bytes(cpu.mem_read(0x012B6, 2)))[0]
    v025C     = bytes(cpu.mem_read(0x025C, 1))[0]
    final_sp  = cpu._uc.reg_read(m68k.UC_M68K_REG_A7)

    print(f"\n  Done: t={elapsed:.2f}s  steps={STEP[0]:,}")
    print(f"  final_PC=0x{final_pc:05X}  SP=0x{final_sp:05X}")
    print(f"  [025C]={v025C:#x}  [012B6]={v012B6:#x}  [025F]={v025F:#x}")
    print(f"  [04AD2]={from_sq:#04x}  [04AD3]={to_sq:#04x}")

    if final_pc == SENTINEL and v012B6 != 0:
        def sq88_to_alg(sq):
            file = sq & 0x0F
            rank = (sq >> 4) & 0x07
            return f"{chr(ord('a') + file)}{rank + 1}" if (sq & 0x88 == 0) else f"0x{sq:02X}(?)"
        print(f"\n  *** SUCCESS: returned to SENTINEL, [012B6]={v012B6:#x} ***")
        print(f"  Move: {sq88_to_alg(from_sq)} → {sq88_to_alg(to_sq)}")
    elif final_pc == SENTINEL:
        print(f"\n  Returned to SENTINEL but [012B6]=0 — search ran but no result")
    else:
        print(f"\n  STUCK at 0x{final_pc:05X}")
    return final_pc, v012B6


# All 7 occurrences of jsr -$7e3c(a4) ;[0x001C2] in the visualization code
# These call into the middle of the event-loop progress callback — NOP them all
PROGRESS_CALLBACK_JSRS = [0x3040, 0x30FA, 0x3556, 0x3A8E, 0x3BE4, 0x3CE6, 0x3DBC]


def run_with_nop_callbacks(pos_ptr, level_word, label, **kwargs):
    """Run direct call with all 7 progress-callback jsr's NOP'd (nop;nop, 4 bytes)."""
    return run_direct(pos_ptr, level_word, label,
                      patch_nop=PROGRESS_CALLBACK_JSRS, **kwargs)


# Test 1: baseline — patch 0x001EC only (original failure case)
run_direct(PIECE_TABLE_ADDR, 0x16, "Test 1: baseline, patch 0x001EC only",
           stop_on_013e=False, max_steps=500_000)

# Test 2: NOP all 7 progress-callback jsr's (core fix)
run_with_nop_callbacks(PIECE_TABLE_ADDR, 0x16,
                       "Test 2: NOP all 7 jsr[0x001C2] progress callbacks")

# Test 3: NOP callbacks + fix [0x331C]=0
run_with_nop_callbacks(PIECE_TABLE_ADDR, 0x16,
                       "Test 3: NOP callbacks + fix [0x331C]=0",
                       fix_331c=True)

# Test 4: all fixes + NOP the [012B6]=0 beq guard
run_with_nop_callbacks(PIECE_TABLE_ADDR, 0x16,
                       "Test 4: NOP callbacks + fix [0x331C] + NOP beq@001EE",
                       fix_331c=True, patch_001ee=True)

# Test 5: level=1 (shallow search), all fixes
run_with_nop_callbacks(PIECE_TABLE_ADDR, 0x01,
                       "Test 5: level=1, NOP callbacks + all fixes",
                       fix_331c=True, patch_001ee=True)
