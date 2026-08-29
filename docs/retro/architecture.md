# Retro Engine — Technical Architecture

How a 1988 chess game becomes a UCI engine in 2026.

---

## Is this a known technique?

Yes — each piece is well-established in its own domain. The combination is novel.

**CPU emulation as a preservation tool** has been the backbone of retro gaming for
30+ years. MAME (arcade hardware), Dolphin (GameCube/Wii), PCSX2 (PlayStation 2),
FS-UAE (Amiga) — all of them run original machine code verbatim inside a CPU
emulator. The reason is always the same: bit-exactness by construction. The
alternative — reimplementing the original system from scratch — always diverges in
subtle ways that are invisible until you run the reimplementation side-by-side and
notice it behaves differently on input 47.

**Unicorn Engine** is a well-known security research and reverse-engineering tool.
It is built on QEMU's CPU cores, stripped of all device emulation, leaving just the
bare instruction executor. Security researchers use it constantly for:

- **Fuzzing closed-source binaries** — run them under emulation, inject malformed
  input, watch them fault, find vulnerabilities
- **Malware analysis** — execute suspicious code safely in total isolation
- **CTF (Capture The Flag) challenges** — emulate firmware or embedded binaries to
  extract secrets or bypass checks
- **Shellcode development and testing** — run raw machine code without a full OS

**Partial emulation / binary lifting** — the specific technique of calling into one
function in a binary you do not have source for, stubbing its OS dependencies with
hooks, marshalling inputs into its internal format, and reading results back — is
textbook in the security and reverse-engineering world. Tools like angr, Qiling, and
Triton are built around exactly this idea.

**What is unusual here** is the combination: a security research tool (Unicorn)
applied in a preservation context (retro chess engine) exposed over a modern protocol
(UCI). The chess engine world has never done this — engines are always reimplemented
(Stockfish, Komodo, etc. are all written from scratch). The retro preservation world
emulates whole systems (a full Amiga with OS, graphics, sound, disk I/O) rather than
isolating a single function. This project takes the security researcher's scalpel and
uses it on a chess AI: extract one function from a 1988 binary, stub its OS
dependencies with Python hooks, and make it speak UCI.

The individual techniques are decades old. The application is new.

---

## The core idea

The straightforward approach to preserving Battle Chess's chess AI would be to
read the 1988 source code (or decompile the binary) and reimplement it in Python
or C. This does not work. A reimplementation has a long tail of subtle divergences:
an off-by-one in a piece-square table, a different tie-break when two moves score
equal, an integer overflow that no longer overflows in modern arithmetic. Each
divergence is invisible until you compare the reimplemented engine move-by-move
against the original and notice it plays differently on position 47.

The approach used here: **do not reimplement. Run the original machine code verbatim.**

The original Amiga 68000 binary — compiled in 1988, shipped on floppy disk, cracked
by Dragon Inc — is loaded into a CPU emulator (Unicorn Engine, a QEMU-derived
multi-architecture CPU emulation library). The emulator executes each instruction
exactly as the original Motorola 68000 would. Bit-exactness holds by construction:
same opcodes, same arithmetic, same data, same moves.

The performance problem (Battle Chess on real 1988 hardware: minutes per move) is
solved for free. A 2026 processor executes 68000 instructions in nanoseconds. A
search that took four minutes on a 7 MHz 68000 takes milliseconds under emulation
on a 3.5 GHz modern core.

---

## What runs and what doesn't

Battle Chess is a full game: animated piece battles, sound effects, a graphical
board, menu navigation. None of that is relevant to playing chess. The goal is
to extract the AI's best-move decision and surface it over UCI. Everything else
is noise.

The binary is not cut up or patched. It runs as-is. But only the AI subsystem is
driven. The display, sound, and input loops never execute — we call directly into
the AI entry point, let it compute a move, read the result from its output buffer,
and stop before the game loop does anything else.

AmigaOS is not present. The binary makes a handful of OS calls (AllocMem,
OpenLibrary) during initialisation. These are intercepted by a code hook and
answered with plausible fake return values. The binary never notices.

The opening book and animations live in a companion data file called
`ChessStuff` (722 KB). The Dragon Inc crack stripped this file from the
floppy; it is available from a WHDLoad install and is bundled at
`Resources/Retro/ChessStuff`. The AI think path works without it — book
lookup fails silently and the engine falls through to the 1-ply search for
every position. Full opening book support requires implementing AmigaDOS
`Open`/`Read`/`Close` stubs in `Traps.py` and running the book-init code
path before each think call. See the `ChessStuff` section in
`docs/retro/reverse-engineering.md`.

---

## Memory layout

The Amiga loaded the binary at virtual address 0x000000 in chip RAM. We replicate
this exactly: 2 MB of flat memory, the code written at offset 0, globals accessed
as offsets from A4 = 0x7FFE.

```
Virtual address space (2 MB chip RAM)
──────────────────────────────────────
0x000000 – 0x011D1B   HUNK_CODE block (72 988 bytes; confirmed by hunktool)
0x011D1C – 0x014B87   Dragon-crack code (non-standard; not in hunk format,
                       not currently loaded; includes opening-book loader at 0x1302A)
0x014B88 – 0x0DFFFF   zero-filled (Unicorn initialises mapped memory to zero)
0x0E0000 – 0x0EFFFF   stack (64 KB; grows downward from 0x0F0000)
0x0F0000 – 0x1FFFFF   remaining chip RAM
──────────────────────────────────────
0x200000 – 0x2FFFFF   AllocMem pool (mapped separately; Amiga exec allocator)
0x7C0000 – 0x83FFFF   Amiga exec library stubs (mapped by AmigaTraps.install())
                       Filled with RTS (0x4E75) instructions; calls intercepted
                       by a HOOK_CODE handler before the RTS executes.
```

A4 = 0x7FFE is the global data pointer. All game globals are accessed as
`A4 - constant`, so writing a value to, say, the piece table means writing
to `0x7FFE - 0x4CDC = 0x3322`.

### Layout Paradox (OPEN QUESTION — resolve via A4b)

The startup routine at `0x110CC–0x110E2` does this:

```
lea.l -$572a(a4), a1    ; a1 = 0x7FFE - 0x572A = 0x28D4
lea.l -$572a(a4), a2    ; a2 = 0x28D4
cmpa.l a1, a2           ; compare identical registers
bne.b $110e6            ; always NOT taken (a1 == a2 always)
move.w #$214b, d1       ; 8523 — clear 8524 longs = 34096 bytes
move.l d2, (a1)+
dbra d1, $110e0         ; fill 0x28D4 .. 0xAE04 with d2
```

If this loop executed with `D2 = 0`, it would zero-fill `0x28D4–0xAE04`, which
**contains known AI code**: `0x79B4`, `0x81DC`, `0x94D8`, `0xADD0`.

The branch `bne.b $110e6` compares `A1` against itself — it can never be taken,
so the loop always runs. This makes no sense on real hardware.

Three possible explanations (exactly one must be true):

1. **The hunk does not load at 0x000000.** If the real load address is higher (say
   `0x20000`), all documented offsets would be shifted. The Dragon crack's pre-
   relocation would have embedded the correct addresses for that load base.

2. **The clear loop is an unpatched linker template** that ran on the original
   Amiga in a state where `D2` was non-zero, or the BSS region was located elsewhere
   and the compiler intended to clear something other than AI code.

3. **Our reading of the memory layout is wrong in some other way** (e.g. the
   addresses come from a different binary version).

**This means no absolute virtual address in this document (or `manifest.json`) is
fully trusted until A4b resolves it from a real FS-UAE memory dump.** The AI entry
points (0x81DC etc.) are within HUNK_CODE, so they are correct relative to the
hunk base — but whether the hunk base is 0x000000 on real hardware is the open
question.

---

## Key addresses (Amiga binary, SHA256 d4fc6137...)

Found during Phase 1-B reverse-engineering (Ghidra 11 + memory-trace profiling).

### AI entry points

| Label | Address | Purpose |
|---|---|---|
| `ai_outer_driver` | `0x81DC` | Top-level AI driver — call this for a complete think |
| `ai_phase0_init` | `0x8230` | Initialises AI state machine |
| `ai_phase1_search` | `0x82DE` | Move generation and evaluation loop |
| `ai_phase2_cleanup` | `0x84C4` | Post-search cleanup and move selection |
| `state_machine_dispatch` | `0x81C8` | Routes execution to the current state handler |
| `state6_handler` | `0x80D4` | Handles state 6 (final move selection) |
| `best_move_writer` | `0x0126` | Writes the chosen move to `ai_best_move` |
| `ai_find_move` | `0x901C` | Inner move-search loop |
| `per_piece_eval` | `0x94D8` | Per-piece static evaluation |
| `post_move` | `0x9808` | Finalises move after search |
| `board_0x88_check` | `0xADD0` | Validates a square using the 0x88 technique |

### Global variables (A4-relative)

| Virtual address | A4 offset | Name | Type | Purpose |
|---|---|---|---|---|
| `0x365A` | `-0x49A4` | `ai_best_move` | 8 bytes | AI output: the chosen move |
| `0x3322` | `-0x4CDC` | `piece_table_base` | 8 bytes/entry | Active piece list |
| `0x3320` | `-0x4CDE` | `piece_counter` | word | Piece iteration index; -1 = ready |
| `0x331E` | `-0x4CE0` | `player1_color` | word | 0=White, 1=Black (side to move) |
| `0x331C` | `-0x4CE2` | `player2_color` | word | 0=White, 1=Black (other side) |
| `0x07D4` | `-0x782A` | `player_type_base` | word array | 1=Human, 2=Computer per side |

---

## The AI: a 1-ply state machine

Battle Chess does not use recursive alpha-beta search with iterative deepening.
The difficulty levels use a **timed state machine** with 1-ply lookahead:

1. **Phase 0 init** (`0x8230`) — set up state, clear move candidates
2. **Phase 1 search** (`0x82DE`) — iterate over all pieces, generate all legal
   moves, evaluate each with `per_piece_eval`, track the best-scoring candidate
3. **Phase 2 cleanup** (`0x84C4`) — finalise selection, write to `ai_best_move`

"Difficulty levels" are implemented by varying how long the engine thinks before
committing. Harder levels let the state machine run more iterations (via a VBL
interrupt counter); easier levels cut it short. This is why the original game was
so slow on hard: it was not searching deeper, it was looping longer evaluating the
same 1-ply moves.

The binary's string table contains **nine** levels ("Level 1" through "Level 9"),
exposed via the `EmuLevel` UCI option (range 1–9). The `Level` enum in
`Code.Retro.Types` mirrors them as `L1`–`L9`.

For deterministic emulation, a `VirtualClock` replaces the Amiga hardware VBL
timer. The clock advances at a fixed rate regardless of host speed, making every
difficulty level fully reproducible.

---

## Fake Amiga OS (AmigaTraps)

When the binary calls `AllocMem` or `OpenLibrary`, it jumps to an address in the
exec library vector table (exec base ± offset). In real AmigaOS those addresses
contain JSR stubs that reach ROM functions. In our emulation, we fill that entire
address range with RTS (0x4E75) instructions and register a `HOOK_CODE` callback.

When the emulator is about to execute any instruction in `[0x7C0000, 0x840000)`,
the Python callback fires first. It checks the current PC against known offsets:

```
exec_base - 0xC6   →  AllocMem: bump-allocate from pool at 0x200000
exec_base - 0x198  →  OpenLibrary: return exec_base (a valid-looking library)
anything else      →  return 0 (harmless for FreeMem, unknown calls)
```

The callback writes the return value into D0, then returns. The RTS at the stub
address fires next, popping the return address from A7 and resuming the caller.
The binary has called and returned from "AmigaOS" without anything except our
Python hook actually running.

A second hook (`HOOK_MEM_READ`) watches address `0x4` — the Amiga `AbsExecBase`
pointer. When the binary reads it during initialisation, the hook writes
`EXEC_BASE (0x800000)` there so the binary finds a valid exec base.

---

## Calling into the AI

Before each think call:

1. **Clear `ai_best_move`** at `0x365A` — zero all 8 bytes so we can detect when
   the AI has written a new result.
2. **Write the position** — parse the FEN string, build a piece-table at `0x3322`,
   set player colours at `0x331E/0x331C`, set `piece_counter` to -1 (ready state).
3. **Set player types** — `player_type_base` table at `0x07D4` marks one side as
   Computer (2) and the other as Human (1).
4. **Restore A4** to `0x7FFE` and **set SP** to `0x1F0000 - 4`.
5. **Push a sentinel return address** (`0xFFFF0000`) onto the stack. When the AI's
   outermost RTS fires, it will pop this address and jump there. Unicorn's
   `emu_start(..., until=0xFFFF0000)` treats that as the stop condition.
6. Call `emu_start(0x81DC, until=0xFFFF0000)`.

The emulator runs the 68000 code until PC == `0xFFFF0000`, then returns. We read
the 8 bytes at `0x365A` and decode the move.

---

## Board representation: 0x88

The binary uses the classic 0x88 board encoding. A valid square index `sq` satisfies
`sq & 0x88 == 0`. The index is `rank * 16 + file` where rank and file are both 0–7.

```
sq  = rank * 16 + file       0x88 index
a1  = 0*16 + 0 = 0x00        0x00 & 0x88 == 0  ✓
h1  = 0*16 + 7 = 0x07        0x07 & 0x88 == 0  ✓
a8  = 7*16 + 0 = 0x70        0x70 & 0x88 == 0  ✓
h8  = 7*16 + 7 = 0x77        0x77 & 0x88 == 0  ✓
off = 0*16 + 8 = 0x08        0x08 & 0x88 != 0  off-board ✗
```

Off-board detection with a single AND instruction — this is why 0x88 was popular
in 1980s chess programs.

---

## Piece table format

Each entry is 8 bytes, big-endian:

```
offset  size  field        encoding
0       2     square       0x88 index of the piece's current square
2       2     color        0 = White, 1 = Black
4       1     piece_type   1=pawn, 2=knight, 3=bishop, 4=rook, 5=queen, 6=king
5       1     flags        0 = active
6       2     reserved     0
```

The piece table is populated by `Bridge.write_position()` from the FEN string.
Up to 32 entries (16 per side), zero-padded.

---

## Move struct format (ai_best_move at 0x365A)

The AI writes its chosen move as 8 bytes, big-endian:

```
offset  size  field   encoding
0       2     from_sq  0x88 source square
2       2     to_sq    0x88 destination square
4       2     flags    move-type flags (capture, promotion, etc.)
6       1     piece    piece type nibble
7       1     legal    non-zero = legal move
```

`Bridge.read_best_move()` reads these 8 bytes and converts from/to to algebraic
notation via `sq88_to_alg()` to produce the UCI move string (e.g. `e2e4`).

---

## Code structure

```
bin/Code/Retro/
├── Types.py          Frozen dataclasses. Zero third-party imports.
│                       Platform, RomId, MemRegion, MoveSpec, Level, ThinkResult
├── Errors.py         RetroError hierarchy (inherits CaissaError)
├── Manifest.py       manifest.json load + sha256 verify + default_rom_path()
├── Rom.py            Amiga HUNK + DOS MZ container parsers; packer detection
├── Cpu.py            Abstract CPU seam — zero Unicorn import
├── Fakes.py          FakeCpu (scripted trace replay) for unit tests
├── Cpus/
│   ├── Unicorn68k.py  ONLY module allowed to import unicorn (N-RETRO-2)
│   ├── UnicornX86.py  DOS x86 scaffold (Phase 9)
│   └── Availability.py  unicorn probe + actionable error
├── Traps.py          AmigaTraps (OS call stubs) + VirtualClock
├── Bridge.py         FEN ↔ Battle Chess board struct marshalling
├── Think.py          Orchestrator: ROM load → emulation → move
├── Oracle.py         Corpus record/replay for bit-exactness regression tests
├── Uci.py            UCI protocol shim (stdin/stdout state machine)
└── Fakes.py          FakeCpu + scripted trace support for unit tests

tools/caissa-retro    Executable entry point (#!/usr/bin/env python3)
Resources/Retro/
├── manifest.json     Known-good binary digests + all key offsets
├── BattleChess.amiga Amiga 68000 binary (Dragon Inc crack, 1988)
├── BattleChess.dos   DOS x86 binary (1988 floppy release)
└── Corpus/           Recorded (fen, level) → move for regression testing
```

---

## The purity hierarchy

New Caissa code must not drag heavy dependencies into the application startup path.
The Retro layer enforces this with a tiered import rule:

| Tier | Module | May import |
|---|---|---|
| Dependency-free | `Types.py`, `Errors.py` | stdlib only |
| Pure | `Manifest.py`, `Rom.py`, `Cpu.py`, `Bridge.py` | stdlib + dependency-free |
| Unicorn-only | `Cpus/Unicorn68k.py`, `Cpus/UnicornX86.py` | unicorn (and nothing else from Retro) |
| Adapter | `Traps.py`, `Think.py`, `Oracle.py`, `Fakes.py` | all of the above |
| Protocol | `Uci.py` | everything; runs as a subprocess |

Invariant N-RETRO-2: `unicorn` appears only in `Cpus/`. Importing `Code.Retro` at
application startup pulls in zero unicorn cost (N-RETRO-3; enforced by a subprocess
import test).

---

## The DOS target

The DOS binary (`BattleChess.dos`, 83 415 bytes, SHA256 `c32d4f6b...`) is the x86
port of the same game. Same chess AI, different instruction set and memory model.

Differences from the Amiga target:

| Aspect | Amiga 68000 | DOS x86 |
|---|---|---|
| Instruction set | M68K (32-bit, RISC-like) | 8086/8088 (16-bit, CISC) |
| Memory model | Flat 32-bit | Segmented (CS/DS/SS/ES) |
| Unicorn mode | `UC_ARCH_M68K`, `UC_MODE_BIG_ENDIAN` | `UC_ARCH_X86`, `UC_MODE_16` |
| OS stubs | Amiga exec (AllocMem, OpenLibrary) | DOS INT 21h |
| Global pointer | A4 = 0x7FFE | TBD (recon required) |
| AI entry point | 0x81DC | TBD (recon required) |

The x86 emulation is scaffolded in `Cpus/UnicornX86.py`; the full wiring awaits
the DOS recon phase (same methodology as Phase 1-B for the Amiga).

---

## Determinism guarantee

Given the same (FEN, level, clock_rate) triple, the engine produces the same move
every time, across restarts, across machines. This holds because:

1. The code is deterministic (no RNG, no hash salting in the original).
2. All timing is driven by `VirtualClock`, not wall-clock time.
3. Memory is zero-initialised before each think call's board write.

The corpus in `Resources/Retro/Corpus/` is the regression net: N recorded
(FEN, level) → move pairs. `make test-retro-rom` replays each one and asserts
the engine produces an identical move.

---

## What "bit-exact" means and does not mean

**Means:** for any position that the original 1988 engine would reach in its search,
this engine makes the same move selection — including blunders, including the same
evaluation of sacrifices, including the same tie-break behaviour.

**Does not mean:** the intermediate game state (display, animations, audio events) is
reproduced. The game loop is not driven; only the AI subsystem executes.

**Does not mean:** cross-platform identity between Amiga and DOS. The two ports were
compiled independently. The same position may produce different moves on the two
targets. This is expected and documented in `docs/retro/divergences.md`.

---

## Why this is novel

The individual techniques — CPU emulation, binary lifting, OS stubbing — are
decades old and well-documented. The application is new.

**Every chess engine ever released is a reimplementation.** Stockfish, Komodo,
Leela Chess Zero, Crafty, GNU Chess, and every historical engine that tried to
recreate an older program — all written from scratch. Reimplementations diverge.
An off-by-one in a piece-square table, a different tie-break order, an integer
overflow that no longer overflows on 64-bit arithmetic — each one changes how the
engine plays. Nobody has ever taken an original 1988 chess engine binary and made
it play chess in 2026 by running the actual machine code verbatim. This is the
first example of that.

**The play style is preserved exactly, including the flaws.** This matters more
than it sounds. Modern engines play at superhuman levels and all converge toward
the same objective style. What is missing from the ecosystem is engines that play
*badly in interesting ways* — engines with recognisable weaknesses, coherent but
flawed strategies, and the kind of tactical blindness that a human improving player
can learn to exploit. Battle Chess at NOVICE is genuinely instructive in a way that
Stockfish at depth 1 is not: Stockfish at depth 1 plays randomly. The 1988 AI has
a coherent (if weak) evaluation function. It will consistently undervalue certain
structures, consistently overlook certain tactical patterns, and consistently fall
for certain traps — the same ones, every time, because it is the same code.

**It is a cultural artefact, not just a program.** Battle Chess sold over a million
copies across Amiga, DOS, Mac, and console platforms. Millions of people learned
chess by losing to it. The specific play style of this specific binary — its
blunders, its strengths at the opening, the exact positions where it falls apart —
is something people remember. A reimplementation approximates that. This is it.

**The cross-platform forensics are new territory.** Once both the Amiga and DOS
ports are running, feeding them the same positions and comparing the outputs is a
forensic look at how a 1988 codebase was ported across CPU architectures by
Interplay's team. Any divergences reveal something about the porting process —
bugs introduced, optimisations changed, evaluation tables tweaked. That comparison
has never been done because nobody has had both engines running in a controlled
environment before.

**The methodology is reusable.** Any game from the 8-bit/16-bit era that shipped
a chess engine (Chess Master, Sargon, Chessmaster, and dozens of others) could be
preserved using exactly this approach: Ghidra recon to find the AI entry point,
Unicorn to run it, a thin bridge to marshal FEN in and UCI out. This project
documents the methodology end-to-end, making it straightforward to apply to other
targets.

---

## Prior art and related work

### CPU emulation libraries

**Unicorn Engine** (`unicorn-engine.org`) — the CPU emulation framework used here.
Built by extracting QEMU's CPU cores (x86, ARM, MIPS, SPARC, M68K, and others) and
wrapping them in a clean embeddable API. Originally released at Black Hat USA 2015 by
Nguyen Anh Quynh. Supports hooks at the instruction, memory read/write, and fault
level — which is what makes the OS-stub approach possible. Version 2.x (used here)
added `ctl_set_cpu_model()` for selecting specific CPU variants like the 68000.

**QEMU** (`qemu.org`) — the full-system emulator that Unicorn's CPU cores are derived
from. QEMU emulates complete machines (CPU + memory + devices + OS); Unicorn strips it
down to the CPU alone for embedding.

**Capstone** (`capstone-engine.org`) — the companion disassembly library to Unicorn,
same author. Used in the recon tooling to print instruction traces during binary
analysis. Not required at runtime.

### Binary analysis and lifting tools

**Ghidra** (`ghidra-sre.org`) — the NSA-released reverse-engineering suite. Used in
Phase 1-B to disassemble the Amiga binary, trace the AI call graph, and locate the
key addresses. Supports Amiga HUNK format natively with the 68000 processor spec.

**angr** (`angr.io`) — a Python binary analysis framework built on Unicorn (and its
own IR lifter). Angr goes further than this project: it can symbolically execute
binaries to find paths and constraints. This project uses Unicorn directly because
concrete execution is sufficient — we know what the binary does, we just need to run it.

**Qiling** (`qiling.io`) — a full-system emulation framework built on Unicorn that
provides a complete OS personality (Linux, Windows, macOS, FreeBSD) on top of the CPU
layer. Similar in spirit to the `AmigaTraps` approach here, but at full OS scale.

### Retro preservation

**MAME** (`mamedev.org`) — the canonical example of the "run original code" preservation
philosophy. MAME emulates thousands of arcade boards by running the original ROMs under
emulated CPUs. Its ROM model (user-supplied, hash-verified against a known database) is
the direct inspiration for `Resources/Retro/manifest.json` and `Manifest.verify()`.

**FS-UAE** — the Amiga emulator used as the ground-truth reference during Phase 1-B
recon. Running Battle Chess under FS-UAE with a real AmigaOS image lets you observe
the original game making moves, which you can then compare against the Unicorn
emulation to validate the bridge code.

### Chess engine context

Every other computer chess engine ever released is a *reimplementation*: Stockfish,
Komodo, Leela, Crafty, Fritz — all written from scratch. This is the first known
example of a chess engine that runs original 1988 machine code under CPU emulation to
guarantee bit-exact preservation of the original's play style and weaknesses.

The closest analogy in other domains: MAME running the original Pac-Man ROMs rather
than a Pac-Man clone. Same principle; different application domain.
