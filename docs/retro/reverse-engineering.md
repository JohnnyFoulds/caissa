# Reverse Engineering Notes

This document records the methodology and findings from the Phase 1 recon spike.
Updated as findings become available.

---

## Target binary

**Platform:** Amiga 68000 (primary)  
**Container format:** Amiga Hunk (HUNK_HEADER / HUNK_CODE / HUNK_BSS / HUNK_RELOC32 / HUNK_END)  
**Tools:** Ghidra 11.x with the 68000 processor spec; Unicorn Engine 2.x (UC_ARCH_M68K); Python 3.13

For the DOS target (Phase 9): DOS MZ/COM container; likely LZEXE or PKLITE packed.
Unpacking procedure: detect packer magic, run the extractor (xfd-tools or lzexe-utils),
then load the unpacked executable.

---

## Methodology

### Step 1 — Binary identification

```bash
tools/caissa-retro identify /path/to/BattleChess
```

Outputs: sha256, size, hunk table (type + size per hunk), packer detection.

### Step 2 — Ghidra headless analysis

Load the binary into Ghidra (File → Import → Amiga Hunk; processor = m68k:BE:32:68000).
Let auto-analysis run. Key searches:

- **Move generation loops** — look for loops over a piece list (6 or more iterations)
  with conditional branching based on piece type. Often near the start of the code.
- **Alpha/beta pattern** — recursive function calls with two parameters that look like
  bounds. The call depth counter is your search depth.
- **Piece-square tables** — look for 64-element (8×8) or 120-element arrays of 16-bit
  signed integers with magnitudes 0–1000. Typically in a BSS or DATA hunk.
- **Think entry point** — the function that takes a board representation and returns a
  move. Usually called from a "computer move" dispatch in the UI layer.

### Step 3 — Memory-read profiling under Unicorn

Hook all memory reads across the whole address space during a candidate think call.
This gives a complete, cheap enumeration of every region the think function touches —
you cannot miss the timer read, the board state, or any hidden globals.

```python
# Fragment from tools/retro-recon/memory_trace.py
uc.hook_add(UC_HOOK_MEM_READ, mem_read_callback)
uc.emu_start(think_entry, until=0xDEADBEEF, count=100_000_000)
```

Print a sorted table: address range → read count. Anything outside the binary's own
segments is a trap address or a hardware register.

### Step 4 — Ground truth validation

Before trusting the RE findings, compare the result of a Unicorn think call with a
move from the manual ground-truth corpus (captured from FS-UAE). If they match, the
calling convention and board struct hypothesis are correct.

---

## Findings

*(Filled in after Phase 1-B is complete.)*

### Binary identification

| Field | Value |
|---|---|
| Filename | TBD |
| Size | TBD |
| sha256 | TBD |
| Packer | TBD |
| Hunk count | TBD |

### Think entry point

| Field | Value |
|---|---|
| Address | TBD |
| Calling convention | TBD |
| Board pointer register | TBD |
| Level register/parameter | TBD |
| Return convention | TBD |

### Board struct layout

*(Field offset table — filled in Phase 1-B.)*

### Timer / clock read

| Field | Value |
|---|---|
| Timer read address | TBD |
| Context | TBD |
| Handler strategy | VirtualClock instruction-counted tick |

### External addresses accessed during think

*(Trap table — each entry becomes a stub in `Traps.py`.)*

---

## DOS target (Phase 9)

The DOS 5.25" release ships inside an installer (`file00.exe`, compressed with LZEXE
or PKLITE). Unpacking procedure:

1. Detect the packer with `detect_packer()` in `Rom.py`.
2. For LZEXE: use the `lzexe -u` tool (or reimplement the decompressor — it is 200 lines).
3. For PKLITE: use `pklite -x`.
4. Load the unpacked MZ executable.

Cross-platform comparison: after both targets are working, run the same 10 positions
through both and compare. Any divergence is documented in `docs/retro/divergences.md`.
