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

## Findings — Amiga target (Phase 1-B complete)

### Binary identification

| Field | Value |
|---|---|
| Filename | `BattleChess` (Dragon Inc crack) |
| Size | 84 912 bytes |
| sha256 | `d4fc6137d7addf97f8a693bd53b240f1344c05fe4f9864a6930f6e298e1378bc` |
| Packer | None — unpacked flat binary |
| Container | Amiga HUNK: 1× HUNK_CODE, no HUNK_RELOC32 |
| Code offset in file | 40 bytes (0x28) — immediately after the HUNK_HEADER |
| Code size | 84 872 bytes |
| Load address | 0x000000 (pre-relocated; runs at a fixed base) |

### Global data pointer

The binary uses A4 as a global data pointer throughout. Every global variable is
accessed as a negative offset from A4.

| Register | Value | Notes |
|---|---|---|
| A4 | `0x7FFE` | Set by initialisation code at `0x1113C` |

All virtual addresses below are derived as `A4 − offset`.

### AI entry points

| Label | Address | Role |
|---|---|---|
| `ai_outer_driver` | `0x81DC` | **Use this as the entry point** — drives the complete think run |
| `state_machine_dispatch` | `0x81C8` | Routes execution to the current state handler |
| `jump_table` | `0x8198` | State → handler address table |
| `ai_phase0_init` | `0x8230` | Initialises AI state machine (state 0) |
| `ai_phase1_search` | `0x82DE` | Move generation and evaluation loop (state 1) |
| `ai_phase2_cleanup` | `0x84C4` | Post-search cleanup and move selection (state 2) |
| `state6_handler` | `0x80D4` | Handles state 6 (final selection before commit) |
| `best_move_writer` | `0x0126` | Writes the selected move to `ai_best_move` |
| `ai_find_move` | `0x901C` | Inner move-search loop |
| `per_piece_eval` | `0x94D8` | Per-piece static evaluation |
| `post_move` | `0x9808` | Finalises move after search |
| `board_0x88_check` | `0xADD0` | 0x88 off-board validity test |

### AI character: 1-ply timed state machine

The AI is **not** recursive alpha-beta. It is a flat state machine that iterates over
all legal moves, evaluates each with a static evaluator, and tracks the best-scoring
move. Difficulty levels are implemented by varying how long the state machine runs via
a VBL interrupt counter — harder levels allow more evaluation time, not deeper search.

This means:
- The AI can be fully driven by calling `ai_outer_driver` once and letting it run to
  completion; no re-entry or iterative deepening is needed.
- Determinism requires replacing the VBL counter with a `VirtualClock` that advances
  at a fixed rate independent of host speed.

### Global variables

| Virtual address | A4 offset | Name | Type |
|---|---|---|---|
| `0x365A` | `−0x49A4` | `ai_best_move` | 8-byte move struct (output) |
| `0x3322` | `−0x4CDC` | `piece_table_base` | 8 bytes/entry piece list (input) |
| `0x3320` | `−0x4CDE` | `piece_counter` | word; -1 = ready state |
| `0x331E` | `−0x4CE0` | `player1_color` | word; 0=White, 1=Black |
| `0x331C` | `−0x4CE2` | `player2_color` | word; 0=White, 1=Black |
| `0x07D4` | `−0x782A` | `player_type_base` | word array; 1=Human, 2=Computer |

### Move struct at ai_best_move (0x365A)

8 bytes, big-endian:

| Offset | Size | Field | Encoding |
|---|---|---|---|
| 0 | 2 | `from_sq` | 0x88 square index |
| 2 | 2 | `to_sq` | 0x88 square index |
| 4 | 2 | `flags` | move-type flags |
| 6 | 1 | `piece` | piece type nibble (0=empty, 1=pawn … 6=king) |
| 7 | 1 | `legal` | non-zero = legal |

### Piece table entry (8 bytes/entry, big-endian)

| Offset | Size | Field | Encoding |
|---|---|---|---|
| 0 | 2 | `square` | 0x88 square index of current position |
| 2 | 2 | `color` | 0 = White, 1 = Black |
| 4 | 1 | `piece_type` | 1=pawn, 2=knight, 3=bishop, 4=rook, 5=queen, 6=king |
| 5 | 1 | `flags` | 0 = active |
| 6 | 2 | `reserved` | 0 |

### Amiga OS calls trapped during think

| PC address | Exec offset | Call | Handler |
|---|---|---|---|
| `EXEC_BASE − 0xC6` | `−0xC6` | `AllocMem` | Bump-allocate from pool at `0x200000` |
| `EXEC_BASE − 0x198` | `−0x198` | `OpenLibrary` | Return `EXEC_BASE` |
| `0x4` (mem read) | n/a | `AbsExecBase` read | Write `EXEC_BASE` to `0x4` |

`EXEC_BASE = 0x800000`. All library stub addresses are in
`[EXEC_BASE − LIB_RANGE, EXEC_BASE + LIB_RANGE)` where `LIB_RANGE = 0x040000`.
This entire range is mapped as RTS stubs; calls to unknown offsets return D0=0.

### Timer / clock

The AI reads a hardware VBL counter to implement timed search cutoffs. The counter
is memory-mapped at an address in the exec library region. Strategy: `VirtualClock`
in `Traps.py` advances a deterministic tick counter at 50 Hz (PAL VBL frequency).
Any read of the timer address returns the current tick count. This makes all
difficulty levels fully reproducible regardless of host speed.

---

## Findings — ChessStuff data file

### What ChessStuff is

`ChessStuff` is the Amiga game's single data file, 722,790 bytes. It is loaded at
runtime from the floppy (or WHDLoad install) by the `BattleChess` executable via
AmigaDOS. It is not an executable; it contains:

1. **Animation data** — all piece-capture battle sequences; the bulk of the file.
2. **Opening book** — the built-in opening theory library.

The Dragon Inc crack stripped it. The bundled copy is from the WHDLoad v1.1 install
(file timestamp 2006-09-24, SHA256 `3917b158...`).

### Where the opening book sits (recon pending)

The `BattleChess` binary has two code sites that call AmigaDOS `Open("ChessStuff",…)`:

| Binary offset | Role (hypothesis) |
|---|---|
| `0x0F6FA` | Animation data load |
| `0x1302A` | Opening book load |

Both sites are followed by `Read()` calls that read specific byte ranges from the file.
The opening book's offset and length within ChessStuff have not yet been determined.
The file does not start with an IFF FORM header; the format is custom / unstructured.

**Recon task:** disassemble the code at `0x1302A`, follow the `Seek()`/`Read()` calls,
record the file offset and length of the book data, and document the book entry format
(position hash → move, or move-sequence tree, or other).

### Engine support status

Opening-book support requires:

1. AmigaDOS file I/O stubs in `Traps.py` (`Open`, `Read`, `Seek`, `Close` for the
   DOS library at offset `EXEC_BASE − 0x198`).
2. Running the game's initialisation path before calling `ai_outer_driver` (or at
   least the book-load subroutine at `0x1302A`).
3. Serving the ChessStuff data through those stubs.

Without step 1–3 the engine plays legally but ignores book moves in the opening.
Tracked as a separate feature: see `docs/features/retro-engine/` (future phase).

---

## Findings — DOS target (recon pending)

### Binary identification

| Field | Value |
|---|---|
| Filename | `CHESS.EXE` (1.2 MB 5.25" floppy, 1988-12-10) |
| Size | 83 415 bytes |
| sha256 | `c32d4f6bc732b67efa65d55bc5813bc74dcfb52b8616894b57ed7aeeeed2a1cd` |
| Packer | None — clean MZ binary, zero relocation entries |
| Container | MS-DOS MZ executable |
| Entry CS:IP | `0x1413:0x0012` (segment setup stub at end of file) |
| Source | Internet Archive `battle-chess_DOS` — 1.2 MB 5.25" floppy image |

The entry point is a self-relocating segment setup stub at the end of the file
(file offset 82 754). This is the standard pattern for large segmented DOS programs
that use a loader stub to set up CS/DS/ES/SS before jumping into the main code.

### Open questions (recon required before wiring x86 emulation)

- What is the x86 equivalent of the Amiga AI entry point (`0x81DC`)?
- How is the board represented? Does it also use 0x88, or a different encoding?
- Where is the best-move output written? What is its layout?
- What is the global data addressing convention (equivalent of A4 = 0x7FFE)?
- Which DOS INT 21h calls (or direct I/O) does the AI make during think?

### Methodology for DOS recon

Same as the Amiga phase:

1. Load `CHESS.EXE` into Ghidra with `x86:LE:16:Real Mode` processor.
2. Let auto-analysis run; note the entry stub sets up segments before jumping to main.
3. Search for the chess AI using the same heuristics: piece-list iteration loops,
   score-tracking variables, the "best move so far" write pattern.
4. Run under `Cpus/UnicornX86.py` with memory-trace profiling to confirm addresses.
5. Compare 10 positions against the Amiga target; document any divergences.

Cross-platform comparison: after both targets are working, run the same positions
through both and compare. Any divergence is documented in `docs/retro/divergences.md`.

---

## Phase A ground-truth attempt — documented negative result (A5)

**Date:** 2026-08-29  
**Status:** BLOCKED — A5 criterion met; stop and report.

The plan's global stop rule: *"If Phase A does not yield ≥1 recorded move and a memory dump
within one working session, stop and report rather than starting another patch-and-rerun loop."*

### Attempt 1 — `vamos` (amitools 0.9.x)

`vamos` is an AmigaOS API stub runner that implements exec/dos library calls in Python on a
Musashi 68000 core. It handles HUNK loading, relocation, and standard library calls.

Problem: the game accesses Amiga custom chip registers early in startup.

```
vamos BattleChess.clean
InvalidMemoryAccessError: Invalid Memory Access R(2): ff807a
PC=ffff807c  A4=00000000
```

`PC=0xFFFF807C` is in the Kickstart ROM area — the startup code jumps into exec library vectors
that vamos routes to ROM-space addresses it never maps.  `A4=0x00000000` confirms startup
hadn't reached `lea.l $7ffe.l, a4` at `0x1113C` yet.

**With `-H ignore`** (silently ignore hardware chip-register I/O): same crash.
The `-H` flag handles custom chip I/O at `0xDFF000`-range; it does not map the ROM exec-vector
area at `0xFFFF.xxxx`.  Code *execution* from unmapped ROM space is not an I/O issue.

**Root cause:** vamos stubs only a subset of exec/dos functions and doesn't provide a
Kickstart ROM image. The 1988 hardware-banging startup calls into exec vectors routed through
ROM space before the chess AI is ever reached.

### Attempt 2 — `fs-uae` 3.2.35 with AROS replacement ROM

FS-UAE (full Amiga system emulator) bundles the free AROS Kickstart replacement ROMs in its
data archive:
- `aros-amiga-m68k-rom.bin` (524288 bytes, SHA `3ad2601f`)
- `aros-amiga-m68k-ext.bin` (524288 bytes, SHA `a63586e4`)

Config: A500, 512K chip RAM, `hard_drive_0 = /tmp/amiga_bc/` (contains `BattleChess` +
`ChessStuff`), startup-sequence `DH0:BattleChess`.

**Result:** AROS loaded (memory map printed, filesystem autoconfig ran), then:

```
-- stub -- my_resolvesoftlink
res_initcode context = 0x0
UAE: Calling uae_quit
```

AROS quit before executing the startup-sequence.  `my_resolvesoftlink` is a filesystem
operation AROS calls during boot that FS-UAE's AROS support layer returns as an unimplemented
stub, triggering a clean exit.  AROS cannot run AmigaDOS programs without a full Workbench
environment it never received.

**Root cause:** Running an AmigaDOS binary from a bare directory hard drive under AROS
requires a complete Workbench disk or a pre-configured AROS installation volume. The minimal
directory-only hard drive does not provide the Workbench shell (`NewShell`, `Execute`,
`Assign`) that AmigaDOS needs to process a startup-sequence.

### Path forward — three options

| Option | Effort | Probability |
|---|---|---|
| **Amiga Forever** (licensed Kickstart 1.3) | Low (~$15 purchase) | High — this is the correct ROM |
| **AROS + full Workbench setup** | Medium (download AROS One 68k HDF image) | Unknown — 1988 game compatibility |
| **DOSBox-X + DOS CHESS.EXE** | Medium (x86 recon needed) | Moderate — different binary, same AI logic |

For the Kickstart route: FS-UAE is already installed and configured; swapping in Kickstart 1.3
(from Amiga Forever or any licensed copy) is one config line change.

**This plan cannot close until Phase A yields ≥1 recorded corpus entry and a memory dump.**
Phase C (Unicorn reproducing a move) is explicitly blocked until then.
