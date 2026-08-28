#!/usr/bin/env python3
"""
tools/retro-recon/call_trace.py — Call the think function and decode its result.

EXPERIMENTAL — Phase 1 spike. Deleted in Phase 10.

Requires: pip install unicorn

Usage:
    python3 tools/retro-recon/call_trace.py \\
        --rom /path/to/BattleChess \\
        --entry 0x<think_addr> \\
        --board-offset 0x<struct_offset> \\
        --level 3 \\
        --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" \\
        [--budget 100000000] \\
        [--output trace.json]

This writes the start position into the candidate board struct, calls the think
function, and prints:
  - Entry registers
  - Each JSR/BSR target (potential sub-function or trap call)
  - Each write to external addresses
  - Exit registers
  - The bytes at the expected result region
  - A decoded move attempt

The trace output is OBSERVATION level only — no code bytes, no PC stream.
"""

import argparse
import json
import struct
import sys
from pathlib import Path


# Standard Amiga 68000 piece encoding (hypothesis — verify from memory_trace output)
# This will be confirmed/corrected after seeing what the engine actually writes
PIECE_EMPTY = 0
PIECE_ENCODING = {
    "P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6,   # white (hypothesis)
    "p": 9, "n": 10, "b": 11, "r": 12, "q": 13, "k": 14,  # black (hypothesis)
}


def fen_to_board_array(fen: str) -> list[int]:
    """Convert FEN to a flat 64-element board array (hypothesis encoding)."""
    board = [0] * 64
    rows = fen.split()[0].split("/")
    sq = 0
    for row in rows:
        for ch in row:
            if ch.isdigit():
                sq += int(ch)
            else:
                board[sq] = PIECE_ENCODING.get(ch, 0)
                sq += 1
    return board


def load_hunk(path: Path):
    """Load Amiga Hunk binary — same as memory_trace.py."""
    data = path.read_bytes()
    if struct.unpack_from(">I", data, 0)[0] != 0x3F3:
        raise ValueError("Not an Amiga Hunk file")

    pos = 4

    def read_long():
        nonlocal pos
        v = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return v

    lib_count = read_long()
    for _ in range(lib_count):
        n = read_long(); pos += n * 4

    total_hunks = read_long()
    first_hunk = read_long()
    last_hunk = read_long()
    num = last_hunk - first_hunk + 1
    hunk_sizes = []
    for _ in range(num):
        sz_lw = read_long()
        hunk_sizes.append((sz_lw & 0x3FFFFFFF) * 4)

    segments = []
    current_base = 0x00010000
    seg_idx = 0

    while pos < len(data) and seg_idx <= num:
        raw_type = read_long()
        hunk_type = raw_type & 0x3FFFFFFF

        if hunk_type == 0x3E9:  # CODE
            sz_lw = read_long(); size = sz_lw * 4
            seg_data = data[pos:pos + size]; pos += size
            segments.append((current_base, bytearray(seg_data), "CODE"))
            current_base += hunk_sizes[seg_idx] if seg_idx < len(hunk_sizes) else size
            current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EA:  # DATA
            sz_lw = read_long(); size = sz_lw * 4
            seg_data = data[pos:pos + size]; pos += size
            segments.append((current_base, bytearray(seg_data), "DATA"))
            current_base += hunk_sizes[seg_idx] if seg_idx < len(hunk_sizes) else size
            current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EB:  # BSS
            sz_lw = read_long(); bss_size = sz_lw * 4
            segments.append((current_base, bytearray(bss_size), "BSS"))
            current_base += bss_size; current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EC:  # RELOC32
            while True:
                n = read_long()
                if n == 0: break
                hunk_ref = read_long()
                ref_base = segments[hunk_ref][0] if hunk_ref < len(segments) else 0
                for _ in range(n):
                    offset = read_long()
                    seg_base, seg_bytes, seg_type = segments[-1]
                    old_val = struct.unpack_from(">I", seg_bytes, offset)[0]
                    struct.pack_into(">I", seg_bytes, offset, old_val + ref_base)
            continue

        elif hunk_type in (0x3F0, 0x3F1):  # SYMBOL / DEBUG
            n = read_long(); pos += n * 4; continue

        elif hunk_type == 0x3F2:  # END
            seg_idx += 1; continue
        else:
            break

    # Apply relocations (segments now have mutable bytearrays)
    return [(s, bytes(d), t) for s, d, t in segments]


def run_call_trace(rom_path: Path, entry: int, board_offset: int, level: int,
                   fen: str, budget: int, output_path: Path | None) -> None:
    try:
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_M68K_000
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID
        from unicorn.m68k_const import (UC_M68K_REG_PC, UC_M68K_REG_SP, UC_M68K_REG_A7,
                                         UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                                         UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
                                         UC_M68K_REG_D6, UC_M68K_REG_D7,
                                         UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2,
                                         UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5,
                                         UC_M68K_REG_A6)
        from unicorn import UcError
    except ImportError:
        print("ERROR: unicorn not installed. Run: pip install unicorn", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {rom_path} ...")
    segments = load_hunk(rom_path)
    for seg_base, seg_data, seg_type in segments:
        print(f"  {seg_type}  0x{seg_base:X}  {len(seg_data):,} bytes")

    seg_ranges = [(s, s + len(d), t) for s, d, t in segments]

    def segment_name(addr: int) -> str:
        for start, end, stype in seg_ranges:
            if start <= addr < end:
                return stype
        return "EXTERNAL"

    # Build the board array from FEN
    board = fen_to_board_array(fen)
    print(f"\nFEN: {fen}")
    print(f"Board array (hypothesis encoding):")
    for rank in range(8):
        row = board[rank * 8:(rank + 1) * 8]
        print(f"  rank {8 - rank}: {row}")

    # Initialise Unicorn
    uc = Uc(UC_ARCH_M68K, UC_MODE_M68K_000)

    all_bases = [s for s, _, _ in segments]
    all_ends = [s + len(d) for s, d, _ in segments]
    mem_start = min(all_bases) & ~0xFFFFF
    mem_end = (max(all_ends) + 0x200000) & ~0xFFFFF
    uc.mem_map(mem_start, mem_end - mem_start)
    for seg_base, seg_data, _ in segments:
        uc.mem_write(seg_base, seg_data)

    stack_addr = 0x0A0000
    stack_size = 0x10000
    uc.mem_map(stack_addr, stack_size)
    stack_top = stack_addr + stack_size - 4
    uc.reg_write(UC_M68K_REG_A7, stack_top)

    # Map page at 0 for exception vectors
    if mem_start > 0:
        uc.mem_map(0, 0x1000)
        uc.mem_write(0, bytes([0x4E, 0x75] * 512))  # RTS everywhere

    # Write board data at the candidate struct offset
    if board_offset:
        # Write board as 64 16-bit big-endian values (hypothesis — adjust if wrong)
        board_bytes = struct.pack(">64H", *board)
        uc.mem_write(board_offset, board_bytes)
        print(f"\nWrote board struct at 0x{board_offset:X} ({len(board_bytes)} bytes)")

    # Trap tracking
    call_log = []    # (pc, target, type) — JSR/BSR calls
    write_log = []   # (pc, address, size, value) — writes to external regions
    trap_hits = []   # addresses called outside binary
    pc_current = [0]

    # Detect JSR/BSR by watching for specific opcodes
    JSR_OPCODE_PREFIX = 0x4E80  # JSR Ax forms; full: 0x4E90, 0x4EA8, etc.

    def hook_code(uc_inst, address, size, user_data):
        pc_current[0] = address
        # Read the instruction word
        try:
            instr_bytes = uc_inst.mem_read(address, 2)
            word = struct.unpack(">H", bytes(instr_bytes))[0]
            # JSR = 0x4E90..0x4EBF (various addressing modes)
            # BSR = 0x6100..0x61FF
            is_jsr = (word & 0xFF80) == 0x4E80 or (word >> 8) == 0x4E
            is_bsr = (word >> 8) == 0x61
            if is_jsr or is_bsr:
                # Approximate target from stack/register — just log the call site
                call_log.append({
                    "caller_pc": address,
                    "type": "JSR" if is_jsr else "BSR",
                    "opcode": f"0x{word:04X}",
                    "caller_segment": segment_name(address),
                })
        except Exception:
            pass

    def hook_mem_write(uc_inst, access, address, size, value, user_data):
        seg = segment_name(address)
        if seg == "EXTERNAL":
            write_log.append({
                "pc": pc_current[0],
                "address": address,
                "size": size,
                "value": value,
            })

    def hook_mem_invalid(uc_inst, access, address, size, value, user_data):
        print(f"  [FAULT] Invalid access at 0x{address:X} (PC=0x{pc_current[0]:X})")
        return False

    uc.hook_add(UC_HOOK_CODE, hook_code)
    uc.hook_add(UC_HOOK_MEM_WRITE, hook_mem_write)
    uc.hook_add(UC_HOOK_MEM_INVALID, hook_mem_invalid)

    # Snapshot entry registers
    def read_regs():
        return {
            "D0": uc.reg_read(UC_M68K_REG_D0), "D1": uc.reg_read(UC_M68K_REG_D1),
            "D2": uc.reg_read(UC_M68K_REG_D2), "D3": uc.reg_read(UC_M68K_REG_D3),
            "D4": uc.reg_read(UC_M68K_REG_D4), "D5": uc.reg_read(UC_M68K_REG_D5),
            "D6": uc.reg_read(UC_M68K_REG_D6), "D7": uc.reg_read(UC_M68K_REG_D7),
            "A0": uc.reg_read(UC_M68K_REG_A0), "A1": uc.reg_read(UC_M68K_REG_A1),
            "A2": uc.reg_read(UC_M68K_REG_A2), "A3": uc.reg_read(UC_M68K_REG_A3),
            "A4": uc.reg_read(UC_M68K_REG_A4), "A5": uc.reg_read(UC_M68K_REG_A5),
            "A6": uc.reg_read(UC_M68K_REG_A6), "SP": uc.reg_read(UC_M68K_REG_A7),
        }

    entry_regs = read_regs()
    print(f"\nEntry registers:")
    for name, val in entry_regs.items():
        print(f"  {name} = 0x{val:08X}")

    print(f"\nRunning think from 0x{entry:X} (budget: {budget:,}) ...")
    instr_count = [0]

    def hook_count(uc_inst, address, size, user_data):
        instr_count[0] += 1

    uc.hook_add(UC_HOOK_CODE, hook_count)

    try:
        uc.emu_start(entry, 0, count=budget)
    except UcError as e:
        print(f"  Stopped: {e}")

    exit_regs = read_regs()
    pc_final = uc.reg_read(UC_M68K_REG_PC)

    print(f"\nExit registers (PC=0x{pc_final:X}):")
    for name, val in exit_regs.items():
        changed = val != entry_regs[name]
        marker = " <-- CHANGED" if changed else ""
        print(f"  {name} = 0x{val:08X}{marker}")

    print(f"\nInstructions executed: {instr_count[0]:,}")
    print(f"Call sites logged: {len(call_log)}")
    print(f"External writes: {len(write_log)}")

    if write_log:
        print("\nExternal address writes (trap outputs):")
        for w in write_log[:20]:
            print(f"  PC=0x{w['pc']:X}  addr=0x{w['address']:X}  size={w['size']}  val=0x{w['value']:X}")

    # Try to read back what looks like a move from D0/D1 or a result struct
    d0 = exit_regs["D0"]
    d1 = exit_regs["D1"]
    print(f"\nResult registers (likely move encoding):")
    print(f"  D0 = 0x{d0:08X} ({d0})")
    print(f"  D1 = 0x{d1:08X} ({d1})")

    # Naive move decode attempt: from square = bits 5:0 of D0, to square = bits 11:6
    from_sq = d0 & 0x3F
    to_sq = (d0 >> 6) & 0x3F
    files = "abcdefgh"
    ranks = "12345678"

    def sq_to_uci(sq: int) -> str:
        if 0 <= sq <= 63:
            return files[sq % 8] + ranks[sq // 8]
        return f"?{sq}"

    print(f"\nHypothesis move decode (D0, from_bits[5:0] / to_bits[11:6]):")
    print(f"  from={from_sq} ({sq_to_uci(from_sq)})  to={to_sq} ({sq_to_uci(to_sq)})")
    print(f"  UCI: {sq_to_uci(from_sq)}{sq_to_uci(to_sq)}")
    print(f"\n*** Verify this against a FS-UAE ground-truth corpus entry! ***")

    if output_path:
        result = {
            "kind": "observation",
            "rom": str(rom_path),
            "entry": entry,
            "board_offset": board_offset,
            "level": level,
            "fen": fen,
            "budget": budget,
            "entry_regs": {k: f"0x{v:08X}" for k, v in entry_regs.items()},
            "exit_regs": {k: f"0x{v:08X}" for k, v in exit_regs.items()},
            "instr_count": instr_count[0],
            "external_writes": write_log[:50],
            "call_site_count": len(call_log),
            "hypothesis_move": f"{sq_to_uci(from_sq)}{sq_to_uci(to_sq)}",
        }
        output_path.write_text(json.dumps(result, indent=2))
        print(f"\nObservation trace written to: {output_path}")
        print("NOTE: This trace contains NO code bytes and is safe to commit.")


def main():
    parser = argparse.ArgumentParser(
        description="Trace a Battle Chess think call and attempt to decode the result")
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--entry", required=True, type=lambda x: int(x, 0),
                        help="Think function entry address")
    parser.add_argument("--board-offset", type=lambda x: int(x, 0), default=0,
                        help="Board struct address (from memory_trace output)")
    parser.add_argument("--level", type=int, default=3, help="Difficulty level (1-8)")
    parser.add_argument("--fen", default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                        help="Position FEN")
    parser.add_argument("--budget", type=int, default=100_000_000)
    parser.add_argument("--output", type=Path, default=None,
                        help="Write observation trace JSON here")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        sys.exit(1)

    run_call_trace(args.rom, args.entry, args.board_offset, args.level,
                   args.fen, args.budget, args.output)


if __name__ == "__main__":
    main()
