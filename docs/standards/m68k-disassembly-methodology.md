# M68K Disassembly Methodology

**Purpose:** Reusable process guide for systematically disassembling and documenting an unknown
M68K binary, with emphasis on Amiga game binaries and headless emulation debugging.
Written from experience on the Battle Chess Amiga (1988, Dragon Inc crack) project.

**Scope:** Applies to any situation where you have an M68K binary and need to understand its
algorithm well enough to (a) fix emulation bugs, (b) document the algorithm in pseudo-code,
or (c) reimplement the algorithm in a higher-level language.

---

## Table of Contents

1. [Toolchain Setup](#1-toolchain-setup)
2. [Binary Characterisation](#2-binary-characterisation)
3. [IRA Pass — Structure Discovery](#3-ira-pass--structure-discovery)
4. [Entry-Point Anchoring](#4-entry-point-anchoring)
5. [Systematic Function Mapping](#5-systematic-function-mapping)
6. [6-Byte Instruction Hunting](#6-6-byte-instruction-hunting)
7. [Living Document Discipline](#7-living-document-discipline)
8. [Emulation Debugging Protocol](#8-emulation-debugging-protocol)

---

## 1. Toolchain Setup

Install ALL tools before starting work. Do not wait until you need a specific tool;
by then you will be mid-analysis with no time to debug installations.

### Required Tools

| Tool | Install | Purpose |
|---|---|---|
| **IRA v2.09** | `git clone github.com/AmigaPorts/ira && make -f Makefile.osx` (remove `-m32` on ARM64) | Amiga-format M68K reassembler; produces annotated `.asm` |
| **Ghidra 12.x** | `brew install ghidra` (requires `openjdk@21`) | NSA SRE framework; C pseudocode decompiler |
| **ghidra-amiga** | GitHub release (version must match Ghidra version exactly) | Hunk-format binary loader for Ghidra |
| **PyGhidra** | Bundled in Ghidra 11+; also `pip install pyghidra` | Python scripting interface to Ghidra — enables batch headless decompilation |
| **Capstone** | `pip install capstone` | Python M68K instruction disassembler — targeted byte-level analysis |

### IRA Build Notes (macOS ARM64)

```bash
git clone https://github.com/AmigaPorts/ira
# Remove -m32 flag (not supported on Apple Silicon ARM64):
sed -i '' 's/-m32//g' Makefile.osx
make -f Makefile.osx
cp ira ~/bin/ira   # or /usr/local/bin if writable
```

### Ghidra-Amiga Setup

1. Install Ghidra: `brew install ghidra`
2. Download the ghidra-amiga plugin zip from GitHub; version must match installed Ghidra exactly.
3. In Ghidra GUI: `File → Install Extensions` → select zip.
4. Restart Ghidra. When loading an Amiga binary, select "Amiga Hunk Format" loader.
5. **Disable** "Call-Fixup Installer" and "Non-Returning Functions" in the analysis options —
   these incorrectly mark code after JSR as unreachable in Amiga game binaries.

### PyGhidra Batch Decompile Script Template

```python
import pyghidra, pathlib

BINARY = "/path/to/valid_truncated.binary"
ENTRIES = [0x81DC, 0xC198, 0xD6D2, 0xDE7A, 0xD490, 0xC91A]  # known function starts
OUT_DIR = pathlib.Path("docs/features/retro-engine/decompiled/")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with pyghidra.open_program(BINARY) as flat_api:
    from ghidra.app.decompiler import DecompInterface
    prog = flat_api.getCurrentProgram()
    decomp = DecompInterface()
    decomp.openProgram(prog)
    
    for entry in ENTRIES:
        addr = flat_api.toAddr(entry)
        func = flat_api.getFunctionAt(addr)
        if func is None:
            func = flat_api.createFunction(addr, f"func_{entry:05x}")
        result = decomp.decompileFunction(func, 0, flat_api.getMonitor())
        if result.decompileCompleted():
            c_code = result.getDecompiledFunction().getC()
            (OUT_DIR / f"func_{entry:05x}.c").write_text(c_code)
            print(f"OK: 0x{entry:05x}")
        else:
            print(f"FAIL: 0x{entry:05x}: {result.getErrorMessage()}")
```

**Note on binary truncation**: If the binary has non-standard hunk types (e.g. Dragon Inc crack
hunk `0x14C`), IRA will refuse to process it and Ghidra may also fail. Truncate first:
```python
import pathlib
data = pathlib.Path("original.binary").read_bytes()
# Find the byte offset where non-standard hunk begins (examine with hexdump)
truncated = data[:VALID_BYTES]
pathlib.Path("valid.binary").write_bytes(truncated)
```

---

## 2. Binary Characterisation

Do this ONCE at the start, before any address analysis.

### 2.1 Hunk Structure

Amiga binaries use the AmigaOS hunk format. Use IRA's PREPROC mode or a hex editor to
identify the hunks:

```bash
ira -PREPROC -CODE=0x0000 binary.amiga
```

Expected structure for a single-segment game binary:
```
HUNK_HEADER (0x3F3)
HUNK_CODE   (0x3E9)  ← main code/data segment
HUNK_RELOC32 (0x3EC) ← relocation table (may be absent)
HUNK_END    (0x3F2)  ← terminate hunk
[non-standard trailing hunks if cracked]
```

Record:
- Code hunk load address (always 0x0000 for position-independent Amiga binaries)
- Size of code hunk in bytes
- Offset of first non-standard hunk (if any) — truncate here for IRA input
- Presence of HUNK_BSS (gives BSS segment size)

### 2.2 The A4 Register

In most Amiga game binaries, register A4 is the global base register, pointing to the centre
of a large data area. The ROM code accesses globals as `(offset, A4)` — negative offsets are
BSS (uninitialized data), positive offsets are ROM constants (jump tables, move tables, strings).

**First step**: find the entry JMP (usually at offset 0x0000 in the code hunk) and trace to the
first `LEA immediate, A4` instruction. Record `A4 = <value>`.

For Battle Chess: `A4 = 0x7FFE`. BSS at `0x3000–0x5FFE`, ROM constants at `0x8000+`.

All negative-offset globals: address = `A4 + negative_offset` = `0x7FFE + offset`.

### 2.3 Board Representation Detection

Identify the board representation early; it affects how you interpret every square access.

Signs of 0x88 representation:
- Board array indexed as `[sq * 4]` (4 bytes per square, 128 entries = 512 bytes)
- `AND.W #$0088, Dn` or `TST.W (sq & 0x88)` validity checks
- Piece move loops that add direction deltas (0x10, -0x10, 0x01, -0x01, 0x11, -0x11, etc.)

Signs of 8x8 representation:
- Board array indexed `[rank*8 + file]` (64 entries), usually `[sq]` with divide/modulo
- Range checks `0 ≤ rank < 8 AND 0 ≤ file < 8`

---

## 3. IRA Pass — Structure Discovery

### 3.1 PREPROC Mode (Initial)

```bash
ira -PREPROC -CODE=0x0000 -ENTRY=<known_addr> binary.amiga
```

Without `-ENTRY`, PREPROC will classify most code as data because the entry JMP at 0x0000
goes to a computed external address. Always provide at least one known entry point.

PREPROC produces a `.cnf` (config) file. Open it and add `SYMBOL`, `LABEL`, and `COMMENT`
directives as you identify addresses — IRA uses these in the full disassembly pass.

### 3.2 Full Disassembly

```bash
ira -CODE=0x0000 \
    -ENTRY=0x81DC -ENTRY=0xC198 -ENTRY=0xD6D2 -ENTRY=0xDE7A -ENTRY=0xD490 \
    binary.amiga
```

Produces `binary.asm`. This is your reference file — do NOT modify it. All annotations go
into the `.cnf` file and you re-run IRA to regenerate.

### 3.3 IRA Address Format

IRA comments show 5-digit hex addresses: `;081dc:`, `;0d8fe:`. When searching:
```bash
grep ';0d8fe:' binary.asm       # find exact address
grep 'LAB_06BD' binary.asm      # find label
grep 'LINK.W' binary.asm | head  # find all function entries (frame setup)
```

Function boundaries:
- **Entry**: `LINK.W A5, #n` — sets up a stack frame
- **Exit**: `UNLK A5; RTS` — tears down frame and returns
- **Leaf function**: `MOVEM.L <regs>, -(A7)` ... `MOVEM.L (A7)+, <regs>; RTS` — saves/restores registers

---

## 4. Entry-Point Anchoring

Never start at offset 0. The 0x0000 entry JMP always dispatches to Amiga OS setup code.
Start from known meaningful addresses.

### 4.1 Finding the AI Entry Point

For a chess AI binary, the AI is triggered by the "Computer plays" path. Anchor points to look for:

1. **Keyboard/joystick input handler** — usually JSR to OS dispatch at known vector
2. **"Human vs Computer" flag** — a 1/2 byte near the player config section; when = 2, triggers AI
3. **The AI outer loop** — look for a LINK.W followed by a MOVE.W #n, (A4+offset) and a BRA dispatch

For Battle Chess, the AI is at `0x81DC`:
```
LINK.W A5, #0
CLR.W (offset, A4)    ; clear phase counter
BRA.S phase_dispatch
```

### 4.2 Systematic Entry-Point Expansion

Start from the AI outer loop, then trace calls outward:

```
outer_driver(0x81DC)
  → ai_init(0x8230)
    → inner_search(0xC198)
      → build_candidate_list(0xC33A)
      → node_evaluate(0xC41C)
        → move_generator(0xC91A)
          → init_piece_search_slot(0xD45A)
      → de7a_handler(0xDE7A)
        → alpha_beta_tree_walk(LAB_06E5)
          → update_best_move_candidate(0xD6D2)
```

For each JSR target, add it as a `-ENTRY` in your IRA command and regenerate the `.asm`.
Track the call graph in your `SYMBOL` directives in the `.cnf`.

---

## 5. Systematic Function Mapping

### 5.1 Function Header Template

For EACH function, document before moving to the next:

```
Function: NAME
Address: 0xXXXX
Frame: LINK.W A5, #-N (N bytes of locals)
Arguments: (d16,A5) offsets: (8,A5)=arg0, (10,A5)=arg1, ...
Locals: (-2,A5)=retval, (-4,A5)=var1, (-12,A5)=candidate_to_sq, ...
Calls: list of JSR targets
Returns: D0 = (0=fail, 1=success), or void
Side effects: what it writes and where
Uncertain: list any addresses/behaviours still unclear
```

### 5.2 Reading Function Bodies

For each instruction, ask:
1. **What register does this touch?** Track a register table: {D0: "piece_type", A0: "board_array base", ...}
2. **Is this a control instruction?** (BEQ, BNE, BRA, BCC, etc.) If yes, where does each branch go?
3. **Is this a 6-byte instruction?** (See §6 below.) If yes, flag it and check emulator status.
4. **Is this accessing A4-relative data?** Compute `A4 + displacement` to get the actual address.
   Cross-reference with your data map.

### 5.3 Jump Table Recognition

Jump tables appear as:
```
CMP.L #N, D0             ; bounds check
BCC.S fallthrough        ; if >= N, skip
ASL.L #1, D0             ; scale by 2 (for 16-bit offsets) or #2 for 4-byte
MOVE.W (table,PC,D0.W), D0  ; load jump offset
JMP (table+2,PC,D0.W)   ; indirect jump
```

To decode:
1. Note the PC at the JMP instruction (= `table+2`)
2. Read the table words from the `.asm`
3. Target = `table+2 + int16(table_word[i])`

### 5.4 Data Table Recognition

Common patterns following functions (often mis-decoded by IRA as instructions):
- String data: runs of 2-character pairs decoded as MOVE.W/BCC/etc. instructions where the "instructions" make no logical sense
- Direction tables: small positive/negative values (0x10, -0x10, 0x11, etc.) decoded as branch offsets
- Score tables: signed word values in a sequence

IRA hint: if a block after RTS produces obviously nonsensical instructions with DC.W entries
mixed in, it is data. Check with `xxd -s <offset> -l 32 binary` to view raw bytes.

---

## 6. 6-Byte Instruction Hunting

This is the critical skill for debugging Unicorn M68K emulation.

### 6.1 Why 6-Byte Instructions Break Unicorn

Standard M68K instructions are 2 or 4 bytes. Some addressing modes require a second extension
word, making the instruction 6 bytes. Unicorn's M68K decoder sometimes reads only 4 bytes for
these, causing:
1. Wrong operand values (the extension word is not consumed)
2. PC advances by 4 instead of 6
3. The leftover 2 bytes execute as a spurious instruction

### 6.2 Which Instruction Forms Are 6 Bytes

```
MOVE.W (d16,An), (An,Xn.L)  — source offset + dest extension word
MOVE.W (An,Xn.L), (d16,An)  — source extension word + dest offset
CMPI.W #imm,  (An,Xn.L)    — immediate + extension word (ALREADY handled by _scan_cmpiw)
ADDI/SUBI/ORI/ANDI/EORI #imm, (An,Xn.L) — likewise
```

The extension word form for indexed mode `(d8, An, Xn.L)` with Xn.L (32-bit index) and d8=0:
- Extension word = `0x0800` for D0.L, `0x1800` for D1.L, etc.
- Format: `DRRRS000 dddddddd` where D=0(data)/1(addr), RRR=register, S=1(long)/0(word), d=8-bit displacement

### 6.3 Scanning for Unhandled 6-Byte Instructions

Use capstone to scan the ROM for ALL 6-byte instructions, then check which are in `_scan_cmpiw`:

```python
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
import pathlib

rom = pathlib.Path("Resources/Retro/BattleChess.amiga").read_bytes()[:73028]
base = 0
cs = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
cs.detail = True

for i in cs.disasm(rom, base):
    size = i.size
    if size == 6:
        opcode_byte = i.bytes[0]
        ext_word = int.from_bytes(i.bytes[4:6], 'big')
        print(f"0x{i.address:05X}: {i.bytes.hex()} — {i.mnemonic} {i.op_str}")
```

Group by opcode byte to find all instruction types. Cross-reference against `_scan_cmpiw`'s
`_OP_MAP_D16` dict. Any opcode byte NOT in that dict needs a new scanner case.

### 6.4 Implementing the Fix

For each unhandled 6-byte form:

1. **Add a scan entry** in `_scan_cmpiw` that identifies the form (address, operation type, operands).
2. **Add a hook case** in `_hook_cmpiw` that executes the correct semantics and sets PC to addr+6.
3. **Write a test** that verifies: the correct value is read from source, the correct address is
   written, and PC is at addr+6 after the hook fires.
4. **Verify in emulation**: add a `_mem_write` hook and check that the correct value appears at
   the correct address after the instruction.

Template for a `MOVE.W (d16,An), (An,Xn.L)` handler:
```python
# In _hook_cmpiw, add to the dispatch:
elif op == 'mov_d16an_to_indexed':
    # Source: read word from (disp16, An_src)
    src_val = cpu.mem_read(cpu.reg_read(An_src) + disp16, 2)
    src_word = int.from_bytes(src_val, 'big')
    # Destination: compute (An_dst + Xn.L)
    dest_addr = cpu.reg_read(An_dst) + cpu.reg_read(Dn_index)  # using long index
    cpu.mem_write(dest_addr, src_word.to_bytes(2, 'big'))
    # Advance PC past 6-byte instruction
    cpu.reg_write(UC_M68K_REG_PC, addr + 6)
```

### 6.5 Prioritisation

Fix 6-byte instructions in order of their impact:
1. Any instruction that loads a control-flow value (jump table index, loop counter)
2. Any instruction that writes to a result buffer (AI_BEST_MOVE_ADDR, score table)
3. Any instruction that loads direction deltas or evaluation parameters
4. Any instruction that loads a piece type or board state value

---

## 7. Living Document Discipline

### 7.1 What Goes Where

| Artefact | Where | Persistence |
|---|---|---|
| Function algorithm (pseudo-code) | `docs/features/<name>/ai_engine_map.md` | **PERMANENT** — commit immediately |
| Data layout (struct fields, offsets) | `ai_engine_map.md` §1 | **PERMANENT** — commit immediately |
| Discovered address/constant | `CLAUDE.md` under relevant section | **PERMANENT** — add before code changes |
| Emulation diagnostic finding | `CLAUDE.md` + `docs/features/<name>/progress.md` | **PERMANENT** — commit at session end |
| Raw IRA `.asm` output | Local `/tmp/` only | **EPHEMERAL** — can be regenerated from ROM + IRA |
| Ghidra C decompilation output | Local `docs/features/<name>/decompiled/` | **LOCAL ONLY** — never commit |
| Hex analysis notes | Commit to `progress.md`, NOT `/tmp` | Regenerable from binary, but your analysis is not |

### 7.2 Session End Checklist

Before `/compact`, `/clear`, or ending the session:

1. [ ] All new addresses added to `CLAUDE.md` (BSS range, constants, function entries)
2. [ ] Function algorithm documented in `ai_engine_map.md` with commit
3. [ ] `docs/features/<name>/progress.md` written with: what was accomplished, what is next, any blocking unknowns
4. [ ] `git commit` with all docs changes
5. [ ] CHANGELOG.md updated if any observable behaviour changed

### 7.3 When Compaction Fires Mid-Analysis

If context compaction fires before you finish:
1. Read `git log --oneline -5` to find last commit
2. Read `docs/features/<name>/progress.md` for last session state
3. Grep `CLAUDE.md` for the topic to find all saved constants
4. Re-run IRA at the relevant address to regenerate the section you were reading
5. Continue from where `progress.md` says to start

Do NOT re-read the entire IRA `.asm` from scratch. Start at the specific function you were
analysing. `progress.md` must say exactly which function and what question was open.

---

## 8. Emulation Debugging Protocol

For debugging a headless emulation where the emulated program produces wrong output
(e.g. wrong best move, wrong score, wrong board state).

### 8.1 Instrument Before Diagnosing

Add hooks at key addresses before running anything:

```python
# Hook any write to the result buffer
emu.hook_add(UC_HOOK_MEM_WRITE, _on_write, begin=RESULT_ADDR, end=RESULT_ADDR+4)

# Hook the abort-check instruction to count nodes
emu.hook_add(UC_HOOK_CODE, _on_abort_check, begin=ABORT_CHECK_ADDR, end=ABORT_CHECK_ADDR+4)

# Hook the final result-selection function
emu.hook_add(UC_HOOK_CODE, _on_result_write, begin=RESULT_WRITE_ADDR, end=RESULT_WRITE_ADDR+4)
```

Run once and record: what was written, when (node count), from what PC. This is your baseline.

### 8.2 The Two-Stage Diagnostic

**Stage 1: find the write site** — what PC writes the wrong value to the result buffer?

If multiple write sites fire, the LAST one wins (later writes overwrite earlier ones). The last
write before the function returns is the one that sets the final output.

**Stage 2: find why the wrong value is there** — is it a computation bug or a 6-byte decode bug?

Discriminate: does the write happen with `nodes=0`? If yes, it's INITIALISATION code writing a
placeholder before the search runs — not the search result. Real search output has `nodes > 0`.

### 8.3 Confirming a 6-Byte Bug

If you suspect a 6-byte instruction is mis-decoded:

1. Find the address in the IRA `.asm` and confirm it IS a 6-byte instruction (IRA shows full hex).
2. Add a `UC_HOOK_CODE` hook at that address. In the hook, read the relevant registers.
3. After the instruction executes (check at `addr+4` and `addr+6`): compare actual register values
   to what the instruction SHOULD have produced.
4. If PC ends at `addr+4` and the extension word `08 00` fired as `ORI.B #0, D0` at `addr+4`:
   confirmed Unicorn mis-decode.

### 8.4 Fix Verification Checklist

After implementing a `_scan_cmpiw` + `_hook_cmpiw` fix:

1. [ ] Add the address to `_scan_cmpiw`'s scan range (or add a new opcode pattern)
2. [ ] Add the operation to `_hook_cmpiw`'s dispatch
3. [ ] Write a unit test: provide mock ROM bytes, call `_scan_cmpiw`, verify the instruction is
       found and tagged with correct operation type
4. [ ] Write an integration test: run `tools/caissa-retro` with `position startpos moves e2e4`
       and verify the output is a canonical Black response (e7e5, c7c5, e7e6, c7c6, or d7d5),
       NOT `bestmove 0000` and NOT python-chess fallback g8h6
5. [ ] Smoke test (must pass before declaring done):
       ```bash
       printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro
       # Expected: bestmove <canonical Black response>
       ```

### 8.5 BSS Init Verification

If the search produces garbage that doesn't seem related to 6-byte decoding:

Check the BSS range `[0x3000..0x5FFE]` was properly pre-initialised before the search.
The game's own BSS init (at 0x8820) is NOOPed; Python must do it:
```python
cpu.mem_write(0x3000, b"\x02\x78" * (0x3000 // 2))
```
Confirm by adding a `UC_HOOK_MEM_READ` hook at a known BSS address before the search and
verifying the value is `0x0278` at search start.

---

## Appendix: Battle Chess Amiga — Known Constants

Specific to Battle Chess Amiga (Dragon Inc crack, 1988). These are confirmed; do not re-derive.

| Symbol | Value | Meaning |
|---|---|---|
| A4 base | `0x7FFE` | Global data register |
| BOARD_ARRAY | `0x30F4` | 128×4 byte board |
| PIECE_TABLE | `0x3322` | 8 bytes/entry, to_sq+0, from_sq+2 |
| PIECE_COUNTER | `0x3320` | Current iteration index |
| AI_BEST_MOVE | `0x3662` | to_sq@+0, from_sq@+2 |
| ABORT_FLAG | `0x4A4A` | Zero before search, set to 1 to exit |
| OUTER_DRIVER | `0x81DC` | Iterative deepening controller |
| INNER_SEARCH | `0xC198` | Alpha-beta driver |
| DE7A_HANDLER | `0xDE7A` | One alpha-beta pass |
| INIT_PIECE_SLOT | `0xD45A` | Sets up search slot (contains 0xD490 write) |
| UPDATE_CANDIDATE | `0xD6D2` | Move candidate generator (6-byte writes at 0xD700, 0xD8FE) |
| BSS sentinel | `0x0278` | Pre-init value for entire BSS range |
| Valid hunk size | `73028` bytes | Truncate here to drop Dragon-crack non-standard hunk |
