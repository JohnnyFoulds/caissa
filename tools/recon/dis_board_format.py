#!/usr/bin/env python3
"""Disassemble 0x07922 (board setup) and run a Unicorn trace to dump board state."""
import sys, importlib.util, types, struct, re
import capstone

_code_pkg = types.ModuleType('Code'); _code_pkg.__path__ = ['bin/Code']; sys.modules['Code'] = _code_pkg
_retro_pkg = types.ModuleType('Code.Retro'); _retro_pkg.__path__ = ['bin/Code/Retro']; sys.modules['Code.Retro'] = _retro_pkg

def _load(dotpath, filepath):
    spec = importlib.util.spec_from_file_location(dotpath, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotpath] = mod
    spec.loader.exec_module(mod)
    return mod

_load('Code.Retro.Types', 'bin/Code/Retro/Types.py')
_load('Code.Retro.Errors', 'bin/Code/Retro/Errors.py')
Manifest = _load('Code.Retro.Manifest', 'bin/Code/Retro/Manifest.py')
Rom = _load('Code.Retro.Rom', 'bin/Code/Retro/Rom.py')

rom_data = open(Manifest.default_rom_path(), 'rb').read()
regions = Rom.parse_amiga_hunk(rom_data)
code = rom_data[regions[0].offset:regions[0].offset + regions[0].size]
A4 = 0x7FFE
md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN + capstone.CS_MODE_M68K_000)


def a4rel(disp_str):
    d = int(disp_str.replace('-', '').replace('$', ''), 16)
    if disp_str.startswith('-'):
        d = -d
    return (A4 + d) & 0xFFFFFF


def annotate(ins):
    ea = ''
    for m in re.finditer(r'(-?\$[0-9a-fA-F]+)\(a4\)', ins.op_str):
        ea += f"  ;[0x{a4rel(m.group(1)):05X}]"
    for m in re.finditer(r'\$([0-9a-fA-F]+)\(pc\)', ins.op_str):
        target = int(m.group(1), 16)
        ea += f"  ;->0x{target:05X}"
    return ea


def dis(start, n_insns=80, label=""):
    if start >= len(code):
        print(f"\n=== 0x{start:05X} — OUTSIDE CODE ===")
        return
    print(f"\n=== 0x{start:05X}  {label} ===")
    for i, ins in enumerate(md.disasm(code[start:start + n_insns * 10], start)):
        raw = code[ins.address:ins.address + ins.size].hex()
        ann = annotate(ins)
        print(f"  0x{ins.address:05X}: [{raw:<12}] {ins.mnemonic} {ins.op_str}{ann}")
        if ins.mnemonic in ('rts', 'rte') and i > 3:
            break
        if i >= n_insns - 1:
            break


# Board init called from 0x0183E (new_game_setup): jsr $7922(pc)
dis(0x07922, 120, "board_position_init (0x07922)")

# And the one before it
dis(0x0774E, 100, "pre_board_init (0x0774E)")

# The table at 0x07922 likely uses ROM tables to set up the starting position
# Let's look at ROM bytes starting from where 0x07922 reads its data tables
print(f"\n=== ROM bytes at 0x06B0-0x06F0 (possible piece/square tables) ===")
for addr in range(0x06B0, 0x06F0, 16):
    b = code[addr:addr+16]
    print(f"  0x{addr:04X}: {' '.join(f'{x:02x}' for x in b)}")

# And ROM bytes near the start of code that might be piece placement data
print(f"\n=== ROM bytes at 0x0668-0x06A8 ===")
for addr in range(0x0668, 0x06A8, 16):
    b = code[addr:addr+16]
    print(f"  0x{addr:04X}: {' '.join(f'{x:02x}' for x in b)}")

# ----- UNICORN LIVE TRACE -----
# Run the board setup function and dump 0x030F4 after it completes
print("\n" + "="*60)
print("=== UNICORN LIVE TRACE: board state at 0x030F4 ===")
print("="*60)

try:
    import unicorn
    from unicorn import UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_MODE_M68K_000
    from unicorn.m68k_const import UC_M68K_REG_A4, UC_M68K_REG_A7, UC_M68K_REG_PC
    import unicorn.unicorn_const as uc_const

    BOARD_BASE = 0x030F4
    BOARD_SIZE = 64 * 4  # 256 bytes
    CHIP_RAM = 0x000000
    CHIP_SIZE = 0x200000

    mu = unicorn.Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)

    # Map chip RAM (2 MB)
    mu.mem_map(CHIP_RAM, CHIP_SIZE)

    # Write ROM code
    for region in regions:
        if region.size > 0:
            mu.mem_write(region.load_address,
                         rom_data[region.offset: region.offset + region.size])

    mu.reg_write(UC_M68K_REG_A4, A4)

    # Stack
    STACK_TOP = 0x1F0000
    SENTINEL = 0xFFFF0000

    # Map sentinel page
    mu.mem_map(0xFFFF0000, 0x10000)

    # Set up a5 (frame pointer for 0x07922 which expects args on stack)
    # 0x07922 takes: arg1 = longword (board data ptr), arg2 = word ($1a4=420 = initial ply?)
    # From 0x0183E at line 0x01942:
    #   pea.l $1a4.w     → push 0x1a4
    #   move.l -$31e4(a4), -(a7)  → push [0x04E1A] = ptr to game data
    #   jsr $7922(pc)
    #
    # We need [0x04E1A] to point somewhere valid. Set up a dummy.
    # Actually: 0x0183E at line 0x01864 writes: move.l -$3556(a4), (a0, d0.l)
    # which stores a ptr to [0x04AA8] into [0x04E1A].
    # [0x04AA8] starts at some allocated memory area.
    # For our trace, let's call 0x0774E first (simpler, sets up some state)
    # then try 0x07922.

    # Actually: let's try a different approach. Run 0x0857E directly, which
    # scans board at 0x030F4 and builds piece entries. But we need 0x030F4 data first.

    # Instead: let's hook ALL writes to 0x030F4..0x031F3 and run from 0x0183E
    # with a hook to catch any Amiga OS calls that we need to stub.

    # First: what's at 0x030F4 BEFORE any init?
    board_before = mu.mem_read(BOARD_BASE, BOARD_SIZE)
    print(f"\nBoard at 0x030F4 (before init) — all zeros: {all(b == 0 for b in board_before)}")

    # Track writes to board area
    writes_to_board = []

    def hook_mem_write(uc, access, address, size, value, user_data):
        if BOARD_BASE <= address < BOARD_BASE + BOARD_SIZE:
            sq = (address - BOARD_BASE) // 4
            offset_in_sq = (address - BOARD_BASE) % 4
            writes_to_board.append((address, size, value, sq, offset_in_sq))

    mu.hook_add(uc_const.UC_HOOK_MEM_WRITE, hook_mem_write)

    # Trap invalid memory access to help debug
    def hook_mem_invalid(uc, access, address, size, value, user_data):
        pc = uc.reg_read(UC_M68K_REG_PC)
        print(f"  INVALID MEM ACCESS at 0x{address:08X} (size={size}) from PC=0x{pc:05X}")
        return False  # stop emulation

    mu.hook_add(uc_const.UC_HOOK_MEM_READ_UNMAPPED | uc_const.UC_HOOK_MEM_WRITE_UNMAPPED
                | uc_const.UC_HOOK_MEM_FETCH_UNMAPPED, hook_mem_invalid)

    # Set up the [0x04E1A] pointer needed by 0x07922
    # From the analysis: 0x04E1A holds a ptr into game state. For the starting
    # position, let's compute what it should be.
    # At 0x01844: copy [0x04AA4] to [0x04AA8]
    # At 0x01850: add 0x9C40 to [0x04AA8]  (= some heap offset)
    # At 0x01864: store [0x04AA8] to [0x04E1A + d4*4] (for d4=0..3)
    # So [0x04E1A] = the pre-computed heap address.
    # For our trace, we'll just write a valid-looking pointer.

    # Let's point [0x04E1A] at address 0x100000 (in our 2MB chip RAM)
    import struct as st
    mu.mem_write(0x04E1A, st.pack(">I", 0x100000))

    # Also set up [0x04AA8] (referenced by 0x07922 as -$3556(a4))
    # and [0x04AA4] (-$355a(a4))
    mu.mem_write(0x04AA4, st.pack(">I", 0x100000))
    mu.mem_write(0x04AA8, st.pack(">I", 0x100000 + 0x9C40))  # 0x19C40

    # Push args for 0x07922: (longword ptr, word $1a4)
    sp = STACK_TOP - 12
    mu.mem_write(sp, st.pack(">I", SENTINEL))  # return address
    mu.mem_write(sp + 4, st.pack(">I", 0x100000))  # arg1: ptr to game state
    mu.mem_write(sp + 8, st.pack(">H", 0x01A4))  # arg2: 0x1a4
    mu.reg_write(UC_M68K_REG_A7, sp)

    print(f"\nRunning 0x07922 (board position init) ...")
    try:
        mu.emu_start(0x07922, 0xFFFF0000, count=500_000)
        print("  Finished cleanly")
    except unicorn.UcError as e:
        pc = mu.reg_read(UC_M68K_REG_PC)
        print(f"  Stopped: {e}, PC=0x{pc:05X}")

    if writes_to_board:
        print(f"\n  Writes to board area (0x030F4): {len(writes_to_board)}")
        for (addr, size, val, sq, off) in writes_to_board[:40]:
            print(f"    sq[{sq:2d}]+{off}: addr=0x{addr:06X}, size={size}, val=0x{val:X}")
    else:
        print("  No writes to 0x030F4 area")

    # Dump board state after
    board_after = bytes(mu.mem_read(BOARD_BASE, BOARD_SIZE))
    print(f"\nBoard state at 0x030F4 after 0x07922:")
    print(f"  All zeros: {all(b == 0 for b in board_after)}")
    for sq in range(64):
        entry = board_after[sq*4:(sq*4)+4]
        if any(entry):
            rank = sq // 8
            file = sq % 8
            col = chr(ord('a') + file)
            print(f"  sq{sq:2d} ({col}{rank+1}): {entry.hex()}  t={entry[0]} idx={entry[1]} c={entry[2]:02x}{entry[3]:02x}")

    # Also dump 0x0892 (piece entry table)
    print(f"\nPiece entries at 0x0892 after 0x07922:")
    piece_entries = bytes(mu.mem_read(0x0892, 32 * 32))
    for i in range(32):
        e = piece_entries[i*32:(i+1)*32]
        if any(e):
            print(f"  entry[{i:2d}]: {e[:8].hex()} ...  w0={int.from_bytes(e[0:2],'big'):#06x} w1={int.from_bytes(e[2:4],'big'):#06x} b10={e[10]:#04x} l14={int.from_bytes(e[20:24],'big'):#010x} l1c={int.from_bytes(e[28:32],'big'):#010x}")

except ImportError:
    print("unicorn not available — install with: pip install unicorn")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
