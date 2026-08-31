# Plan: Fix caissa-retro canonical opening response

## What this plan addresses

Four problems identified in code review:

1. **Engine produces wrong move** — `caissa-retro` falls back to python-chess (g8h6) instead of playing a canonical Black response to 1.e4 (e7e5 / c7c5 / e7e6 / c7c6 / d7d5).
2. **Work is lost every context compression** — investigation findings are not committed to CLAUDE.md or git; each session re-discovers the same addresses.
3. **No commit discipline** — 309 lines of Think.py changes accumulated across multiple sessions without a single commit.
4. **Piecemeal disassembly** — the M68K binary is disassembled one address at a time in response to surprises; no complete model exists.

This plan fixes all four: complete disassembly first, findings to CLAUDE.md immediately, commit after each step, then fix.

---

## Context

Battle Chess Amiga binary runs under Unicorn M68K emulator in `bin/Code/Retro/Think.py`. The AI writes its best move to `AI_BEST_MOVE_ADDR = 0x3662`. Currently the emulation ends with `best=94620002` (garbage) — `to_sq=0x9462` (off-board sentinel) and `from_sq=0x0002` (c1 Bishop, a white piece). Engine falls back to python-chess.

**What is now known** (from `_mem_write` hook diagnostics, committed to CLAUDE.md):

- Garbage write comes from two sites:
  - **PC=0xD490** — 4-byte `move.w $8(a5), (a2)` — writes from_sq (0x0002) to AI_BEST_MOVE_ADDR — fires with `nodes=0`
  - **PC=0xD8FE** — 6-byte `move.w -$c(a5), (a0, d0.l)` — writes to_sq (0x9462) — fires with `nodes=0`

- Both fire **before** any alpha-beta node is counted. The 31 search nodes run but produce no valid update.

- The function containing 0xD8FE starts at **0xD6D2** (`link.w a5, #-$c`). At 0xD700 there is another 6-byte `move.w $8(a5), (a0, d0.l)` writing the from_sq field. Both are `MOVE.W (d16,An), (An, Dn.L)` — 6-byte instruction forms.

- `_scan_cmpiw` in `Think.py` handles 6-byte `CMPI.W/ORI/ANDI/SUBI/ADDI/EORI` forms, but **NOT** `MOVE.W (d16,An), (An,Dn.L)` forms. These are mis-decoded by Unicorn M68K (advances PC by 4 instead of 6), leaving the extension word `0800` to execute as a separate `ORI.B #0, D0` instruction.

**Working hypothesis**: The 6-byte `MOVE.W` forms in the best-move update function (0xD6D2+) are mis-decoded by Unicorn, causing wrong values to be written to AI_BEST_MOVE_ADDR. Extending `_scan_cmpiw` to handle these forms will allow the search to write valid moves.

---

## Commit discipline rules (non-negotiable, apply to every step)

1. **CLAUDE.md first** — any calibrated constant, confirmed address, or key finding goes into CLAUDE.md before any code changes. Not at end of session. Not in a comment. CLAUDE.md only.
2. **Commit after each step** — every step below ends with a git commit. No accumulation of multi-step changes.
3. **Plan written to repo as step 0** — this plan is the first commit. If context compresses, `git log` + `docs/features/retro-engine/plan_phase11_fix.md` + CLAUDE.md are the full picture.
4. **No diagnostic scripts** — `diag_*.py` files are forbidden. Findings go to CLAUDE.md immediately. A script that is not a test and not a tool is a CLAUDE.md entry waiting to happen.
5. **Fork agents for investigation** — any multi-step research task (disassembly, binary analysis) runs in a fork agent so tool noise stays out of main context. The fork writes its conclusions to CLAUDE.md and commits before returning.

---

## Toolchain research findings (deep research — 2026-08-31)

No existing Battle Chess Amiga AI disassembly exists publicly. Tool evaluation below.

### Tier 1 — Primary tools (install and use for this project)

| Tool | Purpose | Status | Install |
|---|---|---|---|
| **IRA v2.09** | M68K reassembler → annotated `.asm` | **INSTALLED** (`~/bin/ira`) | Built from `github.com/AmigaPorts/ira` without `-m32` flag (ARM64 macOS) |
| **Ghidra 12.1.3** | NSA SRE framework → C pseudocode via decompiler | **NOT INSTALLED** | `brew install ghidra` (needs `openjdk@21`) |
| **ghidra-amiga plugin** | Amiga hunk loader for Ghidra | **NOT INSTALLED** | `BartmanAbyss/ghidra-amiga` — latest release is for Ghidra 12.0.1; brew has 12.1.3 — need version-matched release |
| **PyGhidra** | CPython interface to Ghidra API — scriptable headless decompilation, no GUI | **NOT INSTALLED** | Bundled in Ghidra 11+; also `pip install pyghidra`. Requires Ghidra installed first |
| **capstone 5.0** | Targeted instruction disassembly from Python | **INSTALLED** (venv) | Already in `.venv` |

### Why each tool matters

**IRA**: The gold standard for Amiga-specific disassembly. Understands hunk format natively, identifies code vs data regions (PREPROC), produces reassemblable `.asm`. Already working — used to produce `/tmp/bc_entry.asm` (25k lines). Key limitation: Dragon-crack non-standard hunk requires truncating to 73028 bytes first; handled.

**Ghidra + ghidra-amiga + PyGhidra**: The critical tool. Ghidra's decompiler produces **C pseudocode** for each function — this is the map we need. With `PyGhidra`, we can script this headlessly: load the binary, register known function entry points, call `DecompInterface.decompileFunction()` on each, write C output to a file. No GUI. This produces the algorithm documentation much faster than hand-tracing IRA assembly.

From the Ghidra+Amiga Tetracorp guide: untick "Call-Fixup Installer" and "Non-Returning Functions" when analyzing Assembly-written Amiga games — otherwise code after JSR is incorrectly marked non-reachable.

**PyGhidra pattern** (for the decompile script we'll write):
```python
import pyghidra
with pyghidra.open_program("/path/to/binary") as flat_api:
    from ghidra.app.decompiler import DecompInterface
    decomp = DecompInterface()
    decomp.openProgram(flat_api.getCurrentProgram())
    for func_addr in [0x81DC, 0xC198, 0xD6D2, 0xDE7A, 0xD490, 0xC91A]:
        addr = flat_api.toAddr(func_addr)
        func = flat_api.getFunctionAt(addr) or flat_api.createFunction(addr, f"func_{func_addr:04X}")
        result = decomp.decompileFunction(func, 0, monitor)
        print(result.getDecompiledFunction().getC())
```

**capstone**: Best for targeted byte-level analysis — verify specific instructions, scan for 6-byte patterns, check `_scan_cmpiw` coverage. Already integrated into `Think.py`.

### Tier 2 — Reference resources

| Resource | What it provides |
|---|---|
| **chessprogramming.org/0x88** | Full 0x88 board representation spec — directly maps to BC board encoding |
| **chessprogramming.org/Piece-Square_Tables** | Algorithm context for 1988-era engines |
| **Unicorn GitHub issues #1502** | Known M68K instruction failures — confirms our 6-byte problem class |
| **Tetracorp Amiga RE guides** | Best practice for Amiga binary analysis with IRA + Ghidra |
| **IRA ira_config.doc** | How to add SYMBOL/LABEL/COMMENT directives to iteratively annotate the .cnf |

### Tier 3 — Considered but not needed

- **Cutter (GUI)**: Uses rz-ghidra decompiler without Java. Good interactive tool but not scriptable enough for batch function decompilation.
- **RetDec**: LLVM-based decompiler, M68K support unclear, effectively dormant since 2022.
- **IDA Pro**: Best Amiga disassembler per Hex-Rays docs, but commercial (~$3000). Ghidra is equivalent for our purposes.
- **radare2/rizin**: Terminal-based RE framework, Amiga hunk support limited.

### What is NOT installed yet

Ghidra (the key decompiler tool) requires: `brew install openjdk@21 ghidra` plus download and install the `ghidra-amiga` plugin zip. This should take ~10 minutes. **Install as Step 0a before Step 1.**

**SECURITY RULE**: `No original binary, disk image, or extracted code segment may be committed.` The `.asm` IRA output and Ghidra C decompilation output are LOCAL ONLY — never committed to the repo. What IS committed: the formal pseudo-code algorithm document described in Step 1.

---

## Steps

### Step 0 — Write plan + tools doc to repo, commit

File: `docs/features/retro-engine/plan_phase11_fix.md` — this plan (prose version)  
File: `docs/standards/re-toolchain.md` — the toolchain research from "Toolchain research findings" above, with install commands  
Commit: `docs(retro): plan Phase 11 fix + RE toolchain reference`

### Step 0a — Install Ghidra + ghidra-amiga plugin

**Why**: Ghidra produces C pseudocode from M68K assembly. PyGhidra scripts it headlessly. This is the key tool for building the algorithm map quickly and correctly.

**Version constraint**: `ghidra-amiga` latest release (20260128) targets Ghidra 12.0.1. Brew has 12.1.3. Options:
1. `brew install ghidra` (12.1.3) and check if 12.0.1 plugin loads — Ghidra plugins often load across minor versions  
2. Or install Ghidra 12.0.1 directly from GitHub releases if the plugin fails

**Install sequence**:
```bash
brew install openjdk@21 ghidra
# Verify
ghidra --version   # or find the ghidraRun script

# Download ghidra-amiga plugin
curl -L https://github.com/BartmanAbyss/ghidra-amiga/releases/download/20260128/ghidra_12.0.1_PUBLIC_20260128_ghidra-amiga.zip \
     -o /tmp/ghidra-amiga.zip

# Install PyGhidra (Python scripting interface)
pip install pyghidra   # or: /Users/johannes/code/lucaschess/.venv/bin/pip install pyghidra

# Point PyGhidra at Ghidra install
export GHIDRA_INSTALL_DIR=$(brew --prefix ghidra)/libexec
```

**Verify**:
```bash
python3 -c "import pyghidra; print('pyghidra ok')"
```

**Commit**: `chore(tools): install Ghidra + ghidra-amiga + PyGhidra for M68K analysis`  
(Record the exact Ghidra version and plugin zip URL in `docs/standards/re-toolchain.md`)

### Step 0b — Empirically establish: Dragon-crack ROM vs original ROM

**Motivation**: The current `Resources/Retro/BattleChess.amiga` is a Dragon Inc crack. Cracks typically:
- Patch copy-protection checks (usually harmless to gameplay)
- Sometimes modify timing, loader, or intro code
- May alter BSS/init routines
- Introduce non-standard hunk structures (confirmed: `0x14C` trailing hunk at offset 73028)

The original Interplay release might have a cleaner hunk structure (standard `HUNK_END`), no trailing Dragon-crack bytes, and potentially different or cleaner init/boot code paths.

**What to determine empirically**:

1. **Locate the original ROM**: Check if a non-cracked ADF is available (Archive.org has `Battle_Chess_1988_Interplay` without `cr Dragon_Inc`). If so, extract the game binary from it.

2. **Compare hunk structures**: Run IRA on both. Does the original have a proper `HUNK_END`? Does it lack the `DRAGON_CRACK` region? Are there structural differences in the code hunks?

3. **Compare code at key AI addresses**: Do the critical addresses (0x81DC outer driver, 0xD6D2 update function, 0xD490, 0xD8FE) have identical bytes in both? If identical → crack only touched non-AI code (copy protection). If different → we must understand what changed.

4. **Does the original binary run correctly under Unicorn?** Try emulating with the original ROM using the same `Think.py` setup. Does it produce a different (possibly valid) result?

5. **Verdict**: State which ROM to use going forward and why. Update `Resources/Retro/README.md` (or CLAUDE.md) with the rationale.

**Commit** (if ROM is switched): `chore(retro): switch to original ROM — [reason]`  
**Commit** (if crack is kept): `docs(retro): empirically confirmed Dragon-crack ROM is correct — [reason]`

### Step 1 — Install IRA, produce complete disassembly, write formal map document

**Sub-step 1a — Install IRA** (compile from source):
```bash
git clone https://github.com/AmigaPorts/ira /tmp/ira-build
cd /tmp/ira-build && make
cp ira /usr/local/bin/ira   # or ~/bin
```

**Sub-step 1b — Run IRA on the BC binary** (already done; local only, never committed):
```bash
# IRA is installed at ~/bin/ira
# Binary must be truncated to valid hunk portion (73028 bytes) due to Dragon-crack trailer
python3 -c "open('/tmp/bc_valid.amiga','wb').write(open('Resources/Retro/BattleChess.amiga','rb').read()[:73028])"
~/bin/ira -A -KEEPZH -NEWSTYLE -COMPAT=bi -ENTRY=81DC -ENTRY=C198 -ENTRY=DE7A -ENTRY=D6D2 -ENTRY=D400 /tmp/bc_valid.amiga /tmp/bc_entry.asm
# Produces: /tmp/bc_entry.asm  (25k lines, ~22k lines of code — LOCAL only)
```

**Sub-step 1b2 — Run PyGhidra decompile script** (produces C pseudocode; local only):
```python
# tools/decompile_bc.py — write this script and run it (DO NOT COMMIT output)
import pyghidra, os
GHIDRA_DIR = os.environ.get("GHIDRA_INSTALL_DIR", "")
AI_FUNCTIONS = {0x81DC: "outer_driver", 0xC198: "inner_search", 0xDE7A: "de7a_handler",
                0xD6D2: "update_best_move_candidate", 0xC91A: "move_generator"}
with pyghidra.open_program("/tmp/bc_valid.amiga") as flat_api:
    from ghidra.app.decompiler import DecompInterface
    from ghidra.util.task import ConsoleTaskMonitor
    monitor = ConsoleTaskMonitor()
    prog = flat_api.getCurrentProgram()
    decomp = DecompInterface()
    decomp.openProgram(prog)
    for addr, name in AI_FUNCTIONS.items():
        func_addr = flat_api.toAddr(addr)
        func = flat_api.getFunctionAt(func_addr) or flat_api.createFunction(func_addr, name)
        result = decomp.decompileFunction(func, 60, monitor)
        c_code = result.getDecompiledFunction().getC()
        open(f"/tmp/bc_{name}.c", "w").write(c_code)
        print(f"Decompiled {name} → /tmp/bc_{name}.c")
```
This gives us **compiler-quality C pseudocode** for each AI function. The `.c` files are LOCAL ONLY.

**Sub-step 1c — Systematic study of AI section** using a fork agent:

The fork receives both the IRA `.asm` and the PyGhidra `.c` files and studies these regions:

| Region | ROM range | Why |
|---|---|---|
| Outer driver | 0x81DC–0x8500 | Phases 0/1/2 control flow |
| Inner search entry | 0xC198–0xC400 | Main loop, DE7A gate, abort check |
| DE7A handler | 0xDE7A–0xDF00 | Alpha-beta iteration driver |
| Best-move function | 0xD400–0xDA00 | Contains 0xD490, 0xD6D2, 0xD8FE |
| Move-gen callee | whatever 0xD904 JSR targets | Score evaluation |
| PIECE_TABLE fields | Bridge.py constants | For annotation |

**Sub-step 1d — Write formal map document** (committed to repo):

File: `docs/features/retro-engine/ai_engine_map.md`

**Audience**: future implementors who will port this engine to Python. Every decision, data layout, and algorithm must be documented precisely enough to write equivalent Python without touching the ROM.

This document contains:

1. **Board representation**: 0x88 layout, piece codes, PIECE_TABLE (`0x3322`) slot structure — field names, byte offsets, widths. `from_sq`/`to_sq` encoding (0–0x77, 0x88-masked = invalid).

2. **AI data structures**: what `AI_BEST_MOVE_ADDR = 0x3662` stores; how PIECE_TABLE[0x68+] serves as the search stack; what `[0x3320]` indexes; BSS layout for the relevant region.

3. **Algorithm pseudo-code**: one pseudo-C block per function, no M68K syntax, ROM addresses as inline comments:
   ```c
   /* 0xD6D2 — update_best_move_candidate(slot, from_sq, to_sq) */
   void update_best_move_candidate(int slot, int from_sq, int to_sq) {
       piece_table[0x68 + slot].from_sq = from_sq; /* 0xD700 */
       piece_table[0x68 + slot].to_sq   = to_sq;   /* 0xD8FE */
   }
   ```

4. **Mermaid flowcharts** (rendered on GitHub, not ASCII art):
   - **Outer driver control flow** (`0x81DC`): phases 0/1/2 decision tree — when each phase runs, what it returns, loop conditions
   - **Alpha-beta search loop** (`0xC198` → `0xDE7A` → abort): nodes, depth iteration, how the abort flag exits the loop
   - **Best-move update function** (`0xD6D2`): call graph, data flow in/out, when called vs. search-start vs. per-node
   - **Engine call graph**: top-down tree from outer driver to leaf functions, annotated with ROM addresses

5. **Complete write-site table**: every instruction that writes to AI_BEST_MOVE_ADDR or PIECE_TABLE[0x68+] — address, opcode size, operand description, execution timing (init / per-node / phase-end), correct/buggy under current Unicorn.

6. **6-byte instruction inventory**: all 6-byte instructions in the AI section. For each: address, mnemonic, whether in `_scan_cmpiw`, whether Unicorn mis-decodes it.

7. **Root cause verdict**: clear statement of what causes `best=94620002`.

8. **Python port notes** (for future Phase): data structure equivalents, init sequence, search loop skeleton, anything non-obvious that the pseudo-code glosses over.

**Commit**: `docs(retro): formal AI engine map — board repr, flowcharts, algorithm, write-site table`

**Sub-step 1e — Write living methodology document** (committed to repo):

File: `docs/standards/m68k-disassembly-methodology.md`

**Purpose**: reusable process document for any future Amiga M68K binary analysis task. One-time effort, saves multiple sessions of re-deriving the approach.

Sections:
1. **Toolchain setup**: IRA install (compile from AmigaPorts/ira), Ghidra + ghidra-amiga plugin, capstone Python bindings — when to use each
2. **Hunk binary structure**: code/data/BSS hunks, load addresses, Dragon-crack non-standard trailing bytes — what to look for
3. **First-pass analysis**: IRA PREPROC run → .asm → identify code vs data boundaries
4. **Function identification**: entry point from known call sites → walk callee tree → rename labels iteratively; sign: `LINK A5 / UNLK A5` frame convention
5. **Data structure reverse engineering**: trace writes to a known address → identify field layout → infer struct
6. **6-byte instruction problem with Unicorn M68K**: which forms are affected, how `_scan_cmpiw` works, how to extend it, test pattern
7. **Validation**: run the emulator with diagnostic hooks → confirm hypotheses before writing any fix
8. **Documentation discipline**: what goes to CLAUDE.md (calibrated constants), what goes to `ai_engine_map.md` (algorithm), what stays local only (raw .asm)

**Commit**: `docs(standards): M68K disassembly methodology for Amiga RE tasks`

### Step 2 — Extend `_scan_cmpiw` to handle `MOVE.W (d16,An), (An,Dn.L)` forms

**File**: `bin/Code/Retro/Think.py`

The scanner at `_scan_cmpiw()` currently handles:
- `CMPI.W #imm, (d16,An)` — 6-byte form
- `ORI/ANDI/SUBI/ADDI/EORI #imm, (d16,An)` — 6-byte form
- `CMPI.W #imm, (An,Xn)` — 6-byte form

**Add**:
- `MOVE.W (d16,An), (An,Dn.L)` — 6-byte form. Encoding: first byte `0x31`, second byte `0xAD` (source = `-$C(A5)`) or `0x6D` (source = `$8(A5)`), two bytes disp16, then extension word `0x0800` (D0.L index, no scale, zero displacement). Scan pattern: `31 {xD|xA} [2-byte disp] 08 00`.
- Additional 6-byte `MOVE.W` forms found in the complete inventory (Step 1, item 5).

**Also verify** (in `_hook_cmpiw`): does the existing hook correctly emulate the `MOVE.W` operation? The hook handles ORI/ANDI/SUBI/ADDI/EORI/CMP operations. A `'mov'` dispatch case must be added to cover `MOVE.W` semantics.

**Update CLAUDE.md** with the full `_scan_cmpiw` extended opcode list before writing any code.

**Commit**: `fix(retro): extend _scan_cmpiw to handle MOVE.W 6-byte indexed forms`

### Step 3 — Smoke test: verify canonical opening response

```bash
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | \
  /Users/johannes/code/lucaschess/.venv/bin/python3 tools/caissa-retro 2>&1
```

Expected: `bestmove` is one of `{e7e5, c7c5, e7e6, c7c6, d7d5}`, NOT `g8h6`, NOT `0000`.

Also run from startpos (engine plays White):
```bash
printf 'uci\nisready\nposition startpos\ngo\nquit\n' | \
  /Users/johannes/code/lucaschess/.venv/bin/python3 tools/caissa-retro 2>&1
```

If smoke test fails: return to Step 1 — the map document is incomplete. **Do NOT hack further without a complete model.**

### Step 4 — `make test` passes, add `retro_rom` corpus test

```bash
make test    # must pass: all unit tests, no new failures
```

Add to `tests/unit/retro/test_think.py` (marker: `retro_rom`):

```python
@pytest.mark.retro_rom
def test_think_startpos_after_e4_canonical():
    """Engine must play a canonical Black response to 1.e4."""
    session = ThinkSession(rom_path=...)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    result = session.think(ThinkRequest(fen=fen, level=EmuLevel.LEVEL_1))
    move = result.move_uci
    assert move in {"e7e5", "c7c5", "e7e6", "c7c6", "d7d5"}, f"non-canonical: {move}"
```

**Commit**: `test(retro): add retro_rom canonical opening assertion`

### Step 5 — Housekeeping + PR

- Add `*.adf` to `.gitignore` (untracked `ChessSaves.adf`)
- Update `CHANGELOG.md` under `[Unreleased] → Fixed`
- Remove `_SEARCH_STACK_SENTINEL` workaround if no longer needed (Step 1 will confirm)

**PR**: target `main`, title `fix(retro): canonical opening response via complete 6-byte MOVE.W emulation`

### Step 2 — Extend `_scan_cmpiw` to handle `MOVE.W (d16,An), (An,Dn.L)` forms

**File**: `bin/Code/Retro/Think.py`

The scanner at `_scan_cmpiw()` currently handles:
- `CMPI.W #imm, (d16,An)` — 6-byte form
- `ORI/ANDI/SUBI/ADDI/EORI #imm, (d16,An)` — 6-byte form
- `CMPI.W #imm, (An,Xn)` — 6-byte form

**Add**:
- `MOVE.W (d16,An), (An,Dn.L)` — 6-byte form (opcode byte `31`, source = d16 addressing, dest = indexed register). Encoding: `31 xD disp16 ext_word` where `ext_word = 0800` (D0.L, no scale, disp=0).
- Potentially other `MOVE.W` variant 6-byte forms found in Step 1.

The hook for these forms in `_hook_cmpiw` already handles the general case for 6-byte instructions. The scanner just needs to recognize the new opcode pattern and add it to `_cmpiw_info`.

**Also verify**: does the existing `_hook_cmpiw` correctly emulate the `MOVE.W` operation, or does it only handle immediate-source operations? If it only handles ORI/ANDI/SUBI/ADDI/EORI/CMP, add `'mov'` operation dispatch.

**Commit**: `fix(retro): extend _scan_cmpiw to handle MOVE.W 6-byte indexed forms`

### Step 3 — Smoke test: verify canonical opening response

```bash
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | \
  /Users/johannes/code/lucaschess/.venv/bin/python3 tools/caissa-retro 2>&1
```

Expected: `bestmove` is one of `{e7e5, c7c5, e7e6, c7c6, d7d5}`, NOT `g8h6`, NOT `0000`.

Also run:
```bash
printf 'uci\nisready\nposition startpos\ngo\nquit\n' | \
  /Users/johannes/code/lucaschess/.venv/bin/python3 tools/caissa-retro 2>&1
```
Engine plays White from startpos — result must be a legal White first move.

If smoke test fails: return to Step 1 — the disassembly model is incomplete. Do NOT hack further without a complete model.

### Step 4 — `make test` passes, add `retro_rom` corpus test

```bash
make test    # must pass: all unit tests, no new failures
```

Add to `tests/unit/retro/test_think.py` (marker: `retro_rom`):

```python
@pytest.mark.retro_rom
def test_think_startpos_after_e4_canonical():
    """Engine must play a canonical Black response to 1.e4."""
    session = ThinkSession(rom_path=...)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    result = session.think(ThinkRequest(fen=fen, level=EmuLevel.LEVEL_1))
    move = result.move_uci
    assert move in {"e7e5", "c7c5", "e7e6", "c7c6", "d7d5"}, f"non-canonical: {move}"
```

**Commit**: `test(retro): add retro_rom canonical opening assertion`

### Step 5 — Housekeeping + PR

- Add `*.adf` to `.gitignore` if not already there (untracked `ChessSaves.adf`)
- Update `CHANGELOG.md` under `[Unreleased] → Fixed`
- Remove the `_SEARCH_STACK_SENTINEL` workaround if it's no longer needed (Step 1 will confirm)
- Revert `_OUTER_LOOP_PASSES` back to sensible values once the real fix is confirmed

**PR**: target `main`, title `fix(retro): canonical opening response via complete 6-byte MOVE.W emulation`

---

## What is NOT in this plan

- Phase B (live RPA comparison) — deferred until Phase A produces a canonical move
- Phase C (full game / promotion) — deferred
- Phase D (EmuClockRate wiring) — deferred
- EmuClockRate default correction (50→100) — deferred; don't touch Uci.py until the engine works

These are documented in the existing `docs/features/retro-engine/feature_steps.md` as future phases.

---

## Verification

```bash
# Step 3 gate: canonical opening
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro
# → bestmove e7e5   (or c7c5, e7e6, c7c6, d7d5)

# Step 4 gate: unit tests pass
make test

# Step 4 gate: retro_rom corpus test
python3 -m pytest tests/unit/retro/test_think.py -v -m retro_rom -k canonical
```
