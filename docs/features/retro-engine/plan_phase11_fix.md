# Plan: Fix caissa-retro canonical opening response

## What this plan addresses

Four problems identified across multiple sessions:

1. **Engine produces wrong move** — `caissa-retro` falls back to python-chess (g8h6) instead of playing a canonical Black response to 1.e4 (e7e5 / c7c5 / e7e6 / c7c6 / d7d5).
2. **Work is lost every context compression** — investigation findings are not committed to CLAUDE.md or git; each session re-discovers the same addresses.
3. **No commit discipline** — 309 lines of Think.py changes accumulated across multiple sessions without a single commit.
4. **Piecemeal disassembly** — the M68K binary is disassembled one address at a time in response to surprises; no complete model exists.

This plan fixes all four: complete disassembly first, findings to CLAUDE.md immediately, commit after each step, then fix.

---

## Context

Battle Chess Amiga binary runs under Unicorn M68K emulator in `bin/Code/Retro/Think.py`. The AI
writes its best move to `AI_BEST_MOVE_ADDR = 0x3662`. Currently the emulation ends with
`best=94620002` (garbage) — `to_sq=0x9462` (off-board) and `from_sq=0x0002` (c1 Bishop, White
piece). Engine falls back to python-chess.

**Root cause confirmed** (from `_mem_write` hook diagnostics + complete IRA disassembly, 2026-08-31):

- Garbage write at PC=0xD8FE — `MOVE.W (-12,A5), (0, A0, D0.L)` — 6-byte instruction
- Also at PC=0xD700, 0xD7B2, 0xD830, 0xD8AE — all 6-byte `MOVE.W` forms in `update_best_move_candidate` (0xD6D2)
- `_scan_cmpiw` handles 6-byte `CMPI.W/ORI/ANDI/SUBI/ADDI/EORI` forms (op bytes 0x00–0x0C) but NOT `MOVE.W` (op byte 0x31)
- Unicorn mis-executes these as 4-byte instructions: direction deltas are loaded incorrectly, candidate squares are garbage
- The direction-load instruction at 0xD8AE is also 6-byte (different form: source indexed, dest frame-relative) — produces wrong direction delta, which cascades into garbage candidate_to_sq 0x9462

See `docs/features/retro-engine/ai_engine_map.md` for the complete model.

---

## Commit discipline rules (non-negotiable)

1. **CLAUDE.md first** — any calibrated constant or confirmed address goes into CLAUDE.md before any code changes.
2. **Commit after each step** — no accumulation of multi-step changes.
3. **This plan is step 0** — first commit. If context compresses: `git log` + this file + CLAUDE.md = full picture.
4. **No diagnostic scripts** — findings go to CLAUDE.md immediately.
5. **Fork agents for investigation** — any multi-step research task runs in a fork; fork writes conclusions to CLAUDE.md and commits.

---

## Tools installed / available

| Tool | Status | Location |
|---|---|---|
| IRA v2.09 | INSTALLED | `~/bin/ira` |
| capstone 5.0 | INSTALLED | `.venv` |
| Ghidra | NOT YET INSTALLED | `brew install openjdk@21 ghidra` |
| ghidra-amiga plugin | NOT YET INSTALLED | GitHub: `BartmanAbyss/ghidra-amiga` |
| PyGhidra | NOT YET INSTALLED | `pip install pyghidra` |

See `docs/standards/m68k-disassembly-methodology.md` §1 for install details.

**SECURITY RULE**: No original binary, disk image, or extracted code segment may be committed. IRA `.asm` output and Ghidra C output are LOCAL ONLY.

---

## Steps

### Step 0 — Write plan + documents to repo (DONE)

- [x] `docs/features/retro-engine/plan_phase11_fix.md` — this file
- [x] `docs/features/retro-engine/ai_engine_map.md` — complete formal engine map  
- [x] `docs/standards/m68k-disassembly-methodology.md` — reusable methodology guide
- [x] `docs/features/retro-engine/progress.md` — updated with root cause

**Commit**: `docs(retro): formal AI engine map, disassembly methodology, Phase 11 plan`

### Step 0a — Install Ghidra + ghidra-amiga plugin (optional, for deeper future analysis)

```bash
brew install openjdk@21 ghidra
# Check Ghidra version, download matching ghidra-amiga plugin zip from GitHub
# Install via Ghidra GUI: File → Install Extensions
pip install pyghidra
export GHIDRA_INSTALL_DIR=$(brew --prefix ghidra)/libexec
```

This enables C pseudocode decompilation — useful if the `_scan_cmpiw` fix doesn't fully resolve
the issue and deeper function analysis is needed.

**Commit**: `chore(tools): install Ghidra + ghidra-amiga + PyGhidra for M68K analysis`

### Step 1 — Extend `_scan_cmpiw` to handle 6-byte `MOVE.W` indexed forms

**File**: `bin/Code/Retro/Think.py`

Two new scan patterns are needed (see `ai_engine_map.md` §6 for complete inventory):

**Pattern A** — `MOVE.W (d16,An), (0, Am, Dn.L)`: source is frame-relative offset, destination is
indexed register.
- Opcode byte: `0x31`  
- Source byte: `0xAD` = (d16, A5); `0x6D` = (d16, A3); etc.
- Bytes 2–3: source displacement (signed 16-bit)
- Bytes 4–5: extension word `0x0800` = D0.L, scale=0, disp=0

Addresses to cover: 0xD700, 0xD7B2, 0xD830, 0xD8FE.

**Pattern B** — `MOVE.W (0, Am, Dn.L), (d16, An)`: source is indexed register, destination is
frame-relative.
- Source extension word at bytes 2–3: `0x0800` (D0.L)
- Destination displacement at bytes 4–5

Address to cover: 0xD8AE (direction-delta loader).

The existing `_hook_cmpiw` already has a `'mov'` case (lines 672–678) for MOVE.W semantics.
Verify it handles both read-from-indexed and write-to-indexed forms. Add a `'mov_indexed_src'`
case if the source-indexed form needs separate handling.

**Update CLAUDE.md `_scan_cmpiw` section before writing any code.**

**Commit**: `fix(retro): extend _scan_cmpiw to handle MOVE.W 6-byte indexed forms`

### Step 2 — Smoke test: verify canonical opening response

```bash
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro
# Expected: bestmove <one of e7e5, c7c5, e7e6, c7c6, d7d5>
# Must NOT be: bestmove 0000, bestmove g8h6
```

Also verify engine plays White:
```bash
printf 'uci\nisready\nposition startpos\ngo\nquit\n' | tools/caissa-retro
# Expected: bestmove <legal White first move>
```

If smoke test fails → return to Step 0a (Ghidra decompilation) to find additional unhandled
6-byte forms. **Do NOT proceed with partial fixes.**

**Record observed output in PR body as evidence.**

### Step 3 — `make test` passes, add `retro_rom` corpus test

```bash
make test    # must pass with no new failures
```

Add to `tests/unit/retro/test_think.py`:

```python
@pytest.mark.retro_rom
def test_think_after_e4_canonical_black_response():
    """Engine must play a canonical Black response to 1.e4."""
    session = ThinkSession(rom_path=...)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    result = session.think(ThinkRequest(fen=fen, level=EmuLevel.LEVEL_1))
    assert result.move_uci in {"e7e5", "c7c5", "e7e6", "c7c6", "d7d5"}, \
        f"non-canonical: {result.move_uci}"
```

**Commit**: `test(retro): add retro_rom canonical opening assertion`

### Step 4 — Housekeeping + PR

- Add `*.adf` to `.gitignore` (untracked `ChessSaves.adf`)
- Update `CHANGELOG.md` under `[Unreleased] → Fixed`
- Remove `_SEARCH_STACK_SENTINEL` workaround if no longer needed (confirm during Step 1)

**PR**: target `main`, title: `fix(retro): canonical opening response via 6-byte MOVE.W emulation`

---

## What is NOT in this plan

- Phase B (live RPA comparison game) — deferred until engine produces canonical moves
- Phase C (full game / promotion testing) — deferred
- Phase D (EmuClockRate wiring) — deferred
- EmuClockRate default correction (50→100) — deferred; don't touch until engine works

---

## Verification gates

```bash
# Gate 1 (Step 2): canonical Black response
printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro
# → bestmove e7e5 (or c7c5, e7e6, c7c6, d7d5)

# Gate 2 (Step 3): all tests pass
make test

# Gate 3 (Step 3): retro_rom corpus test
python3 -m pytest tests/unit/retro/test_think.py -v -m retro_rom
```
