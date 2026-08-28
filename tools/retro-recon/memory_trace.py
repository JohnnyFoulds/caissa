#!/usr/bin/env python3
"""
tools/retro-recon/memory_trace.py — Profile all memory reads during a think call.

EXPERIMENTAL — Phase 1 spike. Deleted in Phase 10.

Requires: pip install unicorn capstone

Usage:
    python3 tools/retro-recon/memory_trace.py \\
        --rom /path/to/BattleChess \\
        --entry 0x<think_addr> \\
        [--budget 50000000] \\
        [--stack 0x80000] \\
        [--output reads.json]

This hooks ALL memory reads across the whole address space during the candidate
think call. This is cheap (a single hook covers everything) and gives a total
enumeration of every region the think function touches. You cannot miss the timer
read, the board state, or any hidden globals.

Output:
  A sorted table: address range → read count + first-occurrence context.
  Regions outside the binary's own segments are highlighted as trap candidates.
  JSON output includes the full read list for further analysis.
"""

import argparse
import json
import struct
import sys
from pathlib import Path
from collections import defaultdict


def load_hunk(path: Path):
    """
    Parse Amiga Hunk format. Returns (load_address, segments, entry_offset).
    segments: list of (virtual_start, data_bytes, type)
    We pick a load address of 0x00010000 for the first code hunk.
    """
    data = path.read_bytes()

    # Validate header
    if struct.unpack_from(">I", data, 0)[0] != 0x3F3:
        raise ValueError("Not an Amiga Hunk file (HUNK_HEADER expected)")

    pos = 4

    def read_long():
        nonlocal pos
        v = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return v

    lib_count = read_long()
    for _ in range(lib_count):
        n = read_long()
        pos += n * 4

    total_hunks = read_long()
    first_hunk = read_long()
    last_hunk = read_long()
    num = last_hunk - first_hunk + 1

    hunk_sizes = []
    for _ in range(num):
        sz_lw = read_long()
        hunk_sizes.append((sz_lw & 0x3FFFFFFF) * 4)

    segments = []
    base = 0x00010000  # arbitrary load address for first hunk
    current_base = base
    seg_idx = 0

    while pos < len(data) and seg_idx <= num:
        raw_type = read_long()
        hunk_type = raw_type & 0x3FFFFFFF

        if hunk_type == 0x3E9:  # HUNK_CODE
            sz_lw = read_long()
            size = sz_lw * 4
            seg_data = data[pos:pos + size]
            pos += size
            segments.append((current_base, seg_data, "CODE"))
            current_base += hunk_sizes[seg_idx] if seg_idx < len(hunk_sizes) else size
            current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EA:  # HUNK_DATA
            sz_lw = read_long()
            size = sz_lw * 4
            seg_data = data[pos:pos + size]
            pos += size
            segments.append((current_base, seg_data, "DATA"))
            current_base += hunk_sizes[seg_idx] if seg_idx < len(hunk_sizes) else size
            current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EB:  # HUNK_BSS
            sz_lw = read_long()
            bss_size = sz_lw * 4
            segments.append((current_base, bytes(bss_size), "BSS"))
            current_base += bss_size
            current_base = (current_base + 3) & ~3

        elif hunk_type == 0x3EC:  # HUNK_RELOC32
            while True:
                n = read_long()
                if n == 0:
                    break
                hunk_ref = read_long()
                ref_base = segments[hunk_ref][0] if hunk_ref < len(segments) else 0
                for _ in range(n):
                    offset = read_long()
                    seg_base, seg_bytes, seg_type = segments[-1]
                    seg_list = bytearray(seg_bytes)
                    old_val = struct.unpack_from(">I", seg_list, offset)[0]
                    new_val = old_val + ref_base
                    struct.pack_into(">I", seg_list, offset, new_val)
                    segments[-1] = (seg_base, bytes(seg_list), seg_type)
            continue

        elif hunk_type == 0x3F0:  # HUNK_SYMBOL
            while True:
                n = read_long()
                if n == 0:
                    break
                pos += n * 4
                read_long()
            continue

        elif hunk_type == 0x3F1:  # HUNK_DEBUG
            n = read_long()
            pos += n * 4
            continue

        elif hunk_type == 0x3F2:  # HUNK_END
            seg_idx += 1
            continue
        else:
            break

    return base, segments


def run_memory_trace(rom_path: Path, entry: int, budget: int, stack_addr: int,
                     output_path: Path | None) -> None:
    try:
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_M68K_000
        from unicorn import UC_HOOK_MEM_READ, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
        from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_SP, UC_M68K_REG_A7
        from unicorn import UcError
    except ImportError:
        print("ERROR: unicorn not installed. Run: pip install unicorn", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {rom_path} ...")
    base, segments = load_hunk(rom_path)
    print(f"  Loaded {len(segments)} segment(s), base address 0x{base:X}")
    for seg_base, seg_data, seg_type in segments:
        print(f"    {seg_type}  0x{seg_base:X} – 0x{seg_base + len(seg_data):X}  ({len(seg_data):,} bytes)")

    print(f"Entry point: 0x{entry:X}")
    print(f"Instruction budget: {budget:,}")
    print()

    # Build segment range set for quick lookup
    seg_ranges = [(s, s + len(d), t) for s, d, t in segments]

    def segment_name(addr: int) -> str:
        for start, end, stype in seg_ranges:
            if start <= addr < end:
                return stype
        return "EXTERNAL"

    # Initialise Unicorn
    uc = Uc(UC_ARCH_M68K, UC_MODE_M68K_000)

    # Map memory for all segments + a generous surrounding area
    # We map one large flat region covering all segments
    all_bases = [s for s, _, _ in segments]
    all_ends = [s + len(d) for s, d, _ in segments]
    mem_start = min(all_bases) & ~0xFFFFF  # align to 1 MB
    mem_end = (max(all_ends) + 0x100000) & ~0xFFFFF
    uc.mem_map(mem_start, mem_end - mem_start)

    # Write each segment
    for seg_base, seg_data, _ in segments:
        uc.mem_write(seg_base, seg_data)

    # Map and set up stack
    stack_size = 0x10000
    uc.mem_map(stack_addr, stack_size)
    stack_top = stack_addr + stack_size - 4
    uc.reg_write(UC_M68K_REG_A7, stack_top)

    # Write a TRAP instruction at 0x0 and 0x4 to catch NULL pointer calls
    # In m68k, address 0x0 is the initial stack pointer, 0x4 is initial PC
    # For our purposes, map a small page at 0x0 for exception vectors
    if mem_start > 0:
        uc.mem_map(0, 0x1000)
        # Fill with RTS (0x4E75) so any accidental call returns
        uc.mem_write(0, bytes([0x4E, 0x75] * 512))

    # Memory read tracker
    reads: list[tuple[int, int, int]] = []  # (pc, address, size)
    pc_at_read = [0]

    def hook_code_pc(uc_inst, address, size, user_data):
        pc_at_read[0] = address

    def hook_mem_read(uc_inst, access, address, size, value, user_data):
        reads.append((pc_at_read[0], address, size))

    def hook_mem_invalid(uc_inst, access, address, size, value, user_data):
        print(f"  [FAULT] Invalid memory access at 0x{address:X} from PC=0x{pc_at_read[0]:X}")
        return False  # stop emulation

    uc.hook_add(UC_HOOK_CODE, hook_code_pc)
    uc.hook_add(UC_HOOK_MEM_READ, hook_mem_read)
    uc.hook_add(UC_HOOK_MEM_INVALID, hook_mem_invalid)

    # Run
    print(f"Emulating from 0x{entry:X} for up to {budget:,} instructions ...")
    try:
        uc.emu_start(entry, 0, count=budget)
    except UcError as e:
        print(f"  Emulation stopped: {e}")

    pc_final = uc.reg_read(UC_M68K_REG_PC)
    print(f"  Final PC: 0x{pc_final:X}")
    print(f"  Total memory reads recorded: {len(reads):,}")
    print()

    # Aggregate by address → count, noting which reads are external (trap candidates)
    addr_counts: dict[int, int] = defaultdict(int)
    addr_first_pc: dict[int, int] = {}
    for read_pc, addr, size in reads:
        addr_counts[addr] += 1
        if addr not in addr_first_pc:
            addr_first_pc[addr] = read_pc

    # Group into ranges (consecutive addresses with reads)
    sorted_addrs = sorted(addr_counts.keys())
    ranges = []
    if sorted_addrs:
        rstart = sorted_addrs[0]
        rend = sorted_addrs[0]
        rcount = addr_counts[sorted_addrs[0]]
        for a in sorted_addrs[1:]:
            if a <= rend + 8:
                rend = a
                rcount += addr_counts[a]
            else:
                ranges.append((rstart, rend, rcount))
                rstart = a
                rend = a
                rcount = addr_counts[a]
        ranges.append((rstart, rend, rcount))

    print("Memory read regions (sorted by address):")
    print(f"  {'Start':>10}  {'End':>10}  {'Reads':>8}  {'Segment':>10}  Note")
    print(f"  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*10}  ----")

    external_addresses = []
    for rstart, rend, rcount in sorted(ranges, key=lambda x: -x[2])[:60]:
        seg = segment_name(rstart)
        note = "*** TRAP CANDIDATE ***" if seg == "EXTERNAL" else ""
        print(f"  0x{rstart:08X}  0x{rend:08X}  {rcount:>8,}  {seg:>10}  {note}")
        if seg == "EXTERNAL":
            external_addresses.append({
                "address": rstart,
                "end": rend,
                "reads": rcount,
                "first_pc": addr_first_pc.get(rstart, 0),
            })

    print()
    print(f"External (trap candidate) addresses: {len(external_addresses)}")
    for ea in external_addresses:
        print(f"  0x{ea['address']:08X}  (first read from PC=0x{ea['first_pc']:08X},  {ea['reads']} reads)")

    if output_path:
        result = {
            "rom": str(rom_path),
            "entry": entry,
            "budget": budget,
            "reads_total": len(reads),
            "regions": [{"start": r, "end": e, "count": c, "segment": segment_name(r)} for r, e, c in ranges],
            "external_addresses": external_addresses,
        }
        output_path.write_text(json.dumps(result, indent=2))
        print(f"\nFull results written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Profile memory reads during a Battle Chess think call (Amiga 68000)")
    parser.add_argument("--rom", required=True, type=Path, help="Path to BattleChess binary")
    parser.add_argument("--entry", required=True, type=lambda x: int(x, 0),
                        help="Think function entry address (e.g. 0x1234)")
    parser.add_argument("--budget", type=int, default=50_000_000,
                        help="Max instructions (default: 50M)")
    parser.add_argument("--stack", type=lambda x: int(x, 0), default=0x080000,
                        help="Stack memory address (default: 0x080000)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write JSON results to this file")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        sys.exit(1)

    run_memory_trace(args.rom, args.entry, args.budget, args.stack, args.output)


if __name__ == "__main__":
    main()
