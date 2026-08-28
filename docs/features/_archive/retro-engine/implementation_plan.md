# Retro Engine — Implementation Plan

**Spec reference:** [feature_spec.md](feature_spec.md)  
**Phase tracker:** [feature_steps.md](feature_steps.md)

---

## Current State (as of 2026-08-28)

Phase 0 (Documentation & Process) is the current phase. No production code exists.
The SDD artefacts are being written now. All test names for all phases are recorded in
`feature_steps.md` as `xfail(strict=True)` stubs to be created in Phase 2 (the first
phase that creates a test file).

---

## How to use this plan

1. `make test` red — write the Phase N-A test cases first (they fail because code does not exist)
2. Write the production code for Session N-A
3. **Gate C** — human diff review before committing
4. `make test` green
5. `make lint` zero
6. Update living docs (phase status in `feature_steps.md`)
7. Commit with `type(retro): Phase N-A — <description>`
8. GOTO 1 or open PR

**One branch = one phase = one PR.**

---

## Files to Create / Modify

| File | Action | Phase |
|---|---|---|
| `docs/features/retro-engine/initial_idea.md` | create | 0 |
| `docs/features/retro-engine/feature_spec.md` | create | 0 |
| `docs/features/retro-engine/feature_steps.md` | create | 0 |
| `docs/features/retro-engine/implementation_plan.md` | create | 0 |
| `docs/features/retro-engine/decisions.md` | create | 0 |
| `docs/features/retro-engine/recon_findings.md` | create | 1 |
| `docs/retro/README.md` | create | 0 |
| `docs/retro/legal.md` | create | 0 |
| `docs/retro/rom-setup.md` | create | 0 |
| `docs/retro/uci-options.md` | create | 0 |
| `docs/retro/reverse-engineering.md` | create | 0 |
| `docs/retro/testing.md` | create | 0 |
| `docs/retro/troubleshooting.md` | create | 0 |
| `docs/retro/divergences.md` | create | 9 |
| `Resources/Retro/.gitkeep` | create | 0 |
| `Resources/Retro/Corpus/.gitkeep` | create | 0 |
| `Resources/Retro/manifest.json` | create | 3 |
| `Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl` | create | 1 |
| `Resources/Retro/Corpus/groundtruth-dos-manual.jsonl` | create | 9 |
| `tools/retro-recon/` | create | 1 → delete | 10 |
| `tools/caissa-retro` | create | 8 |
| `bin/Code/Base/CaissaErrors.py` | create | 2 |
| `bin/Code/Retro/__init__.py` | create | 2 |
| `bin/Code/Retro/Types.py` | create | 2 |
| `bin/Code/Retro/Errors.py` | create | 2 |
| `bin/Code/Retro/Cpus/__init__.py` | create | 2 |
| `bin/Code/Retro/Cpus/Availability.py` | create | 2 |
| `bin/Code/Retro/Fakes.py` | create (hunk builder) | 3; extend (ScriptedCpu, FakeClock) | 4 |
| `bin/Code/Retro/Manifest.py` | create | 3 |
| `bin/Code/Retro/Rom.py` | create | 3 |
| `bin/Code/Retro/Cpu.py` | create | 4 |
| `bin/Code/Retro/Cpus/Unicorn68k.py` | create | 4 |
| `bin/Code/Retro/Cpus/UnicornX86.py` | create stub | 4; implement | 9 |
| `bin/Code/Retro/Traps.py` | create | 5 |
| `bin/Code/Retro/Bridge.py` | create | 6 |
| `bin/Code/Retro/Profiles.py` | create stub | 6; populate with Phase 1 offsets | 6 |
| `bin/Code/Retro/Think.py` | create | 7 |
| `bin/Code/Retro/Oracle.py` | create | 7 |
| `bin/Code/Retro/Trace.py` | create | 7 |
| `bin/Code/Retro/Uci.py` | create | 8 |
| `bin/Code/Rpa/Errors.py` | edit (re-export CaissaError) | 2 |
| `bin/OS/darwin/OSEngines.py` | edit (_EXTRA_ENGINES) | 8 |
| `bin/OS/darwin/Engines/SOURCES.md` | edit | 8 |
| `docs/engines.md` | edit | 8 |
| `pytest.ini` | edit | 2 |
| `ruff.toml` | edit | 2 |
| `Makefile` | edit | 2 |
| `.gitignore` | edit | 0 |
| `requirements-retro.txt` | create | 2 |
| `CHANGELOG.md` | edit per phase | 0+ |
| `tests/unit/retro/__init__.py` | create | 2 |
| `tests/unit/retro/test_foundations.py` | create | 2 |
| `tests/unit/retro/test_rom.py` | create | 3 |
| `tests/unit/retro/test_cpu.py` | create | 4 |
| `tests/unit/retro/test_traps.py` | create | 5 |
| `tests/unit/retro/test_clock.py` | create | 5 |
| `tests/unit/retro/test_bridge.py` | create | 6 |
| `tests/unit/retro/test_think.py` | create | 7 |
| `tests/unit/retro/test_oracle.py` | create | 7 |
| `tests/unit/retro/test_uci.py` | create | 8 |
| `tests/unit/retro/test_dos.py` | create | 9 |
| `tests/unit/retro/test_completeness.py` | create | 10 |
| `tests/unit/retro/_fixtures/traces/` | create | 7 |
| `tests/unit/retro/_fixtures/uci/` | create | 8 |
| `docs/features/retro-engine/production_readiness.md` | create | 10 |

---

## Phase 0 — Documentation & Process

*(Delivered on this PR — `docs/retro-engine`. See `feature_steps.md` §Phase 0.)*

---

## Phase 1 — Recon Spike (GO / KILL)

### Session 1-A — Ground Truth Capture (manual, FS-UAE)

**Files to create/edit:**
- `Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl` (create)

**Scope:** Run Battle Chess in FS-UAE. Play at least 10 distinct positions from
startpos × 2 difficulty levels. Record each as a JSONL line.

**What to implement:**

1. Install FS-UAE (Amiga 500 + KickStart 1.3 config); boot Battle Chess.
2. For each position, set up the position by playing through the moves, then let the
   engine think. Record the move made.
3. Each corpus line:
   ```json
   {"fen": "...", "target": "amiga", "level": 3, "move": "e2e4",
    "observed_seconds": 45, "instr": null,
    "source": "fs-uae-manual", "captured_at": "2026-...", "notes": "start position"}
   ```
4. Include at least: start position at levels 1, 2, 3; 3–4 mid-game positions at level 1.

**Tests this session makes green:** N/A — produces a data file, not test-covered code.

**Spec refs:** BR-2, §6 ROM/Legal Policy (corpus entries are factual data).

**Definition of done:**
- [ ] At least 10 corpus entries with `source: "fs-uae-manual"` committed
- [ ] Each entry has been verified by playing the position again and confirming the same move
- [ ] Notes field documents the position context
- [ ] File passes JSON parsing

**Suggested commit:** `docs(retro): Phase 1-A — manual ground truth corpus (10 positions)`

---

### Session 1-B — Ghidra / Unicorn RE Spike

**Files to create/edit:**
- `tools/retro-recon/` (create — `identify.py`, `memory_trace.py`, `call_trace.py`)
- `docs/features/retro-engine/recon_findings.md` (create — the durable output)

**Scope:** Ghidra headless + Unicorn on the Amiga binary. Locate the think function.
All code here is throwaway dev tooling. The only durable output is `recon_findings.md`.

**What to implement:**

1. **Binary identification.**
   `tools/retro-recon/identify.py /path/to/BattleChess`:
   - Print sha256, size, HUNK_HEADER table (each hunk: type, size, offset)
   - Detect packer (PowerPacker = `PP20` magic; Imploder = `IMP!`)
   - Print the first 32 bytes of each code hunk in hex

2. **Memory trace.**
   `tools/retro-recon/memory_trace.py --rom /path/to/BattleChess --entry 0x<ADDR>`:
   - Load the binary under Unicorn (UC_ARCH_M68K, UC_MODE_M68K_000)
   - Hook ALL memory reads across the whole address space (cheap; catches everything)
   - Call the candidate entry, run for N million instructions
   - Print a sorted table: address range → read count. Cluster by region (code, data, bss, stack)
   - Print every unique address accessed outside the binary's own segments (trap candidates)

3. **Call trace.**
   `tools/retro-recon/call_trace.py --rom /path --entry 0x<ADDR> --fen "rnbqkbnr/.../8 w KQkq - 0 1" --level 3`:
   - Inject the start position into the candidate board-struct area (from hypothesis)
   - Run until RETURN or budget (100M instructions)
   - Print entry registers, each JSR target, each external address access (potential trap), exit registers, the bytes at the result region

4. **`recon_findings.md`** — fill with:
   - Binary identification table (filename, size, sha256, hunk layout)
   - Candidate think entry address and justification (why this function)
   - Calling convention hypothesis (which register = board ptr, which = level)
   - Board-struct field offset table
   - Timer/clock read site (address + context), or confirmation that none exists
   - Complete list of external addresses accessed during think (each is a trap to stub)
   - One verbatim observation-trace entry for the start position at level 1
   - Confirmation: the decoded move matches a `source: "fs-uae-manual"` corpus entry

**Tests this session makes green:** N/A — spike. Output is `recon_findings.md`.

**Spec refs:** §4, §5.2, §7, FR-9, D4, D5.

**Definition of done:**
- [ ] `recon_findings.md` filled with all required sections
- [ ] Kill criteria 1–5 all pass (documented in the findings)
- [ ] The corpus entry from step 4 agrees with a 1-A ground-truth entry
- [ ] `tools/retro-recon/` has an experimental banner: `"EXPERIMENTAL — Phase 1 spike. Deleted in Phase 10."`
- [ ] `recon_findings.md` committed; scratch tooling committed but clearly marked

**Suggested commit:** `docs(retro): Phase 1-B — recon spike findings; think function located`

---

## Phase 2 — Foundations

*(Detailed session breakdown written when Phase 1 is complete.)*

---

## Phases 3–10

*(Session breakdowns written when each phase becomes current, generated from the
Piece Plan prompt in `docs/claude_code/prompts.md`.)*

---

## Final Verification

```bash
make test            # retro marker green; no ROM, no unicorn needed
make lint            # zero findings on bin/Code/Retro/**
make cov-retro       # ≥ 90% branch
make retro-doctor    # unicorn + ROM status
make test-retro-emu  # with unicorn
export CAISSA_RETRO_ROM=/path/to/BattleChess
make test-retro-rom  # corpus replay; all moves match ground truth
printf 'uci\nquit\n' | tools/caissa-retro   # uciok within 2 s, no ROM required
```

---

## Session Summary Table

| Session | Phase | What it delivers | New tests |
|---|---|---|---|
| 1-A | 1 | Ground truth corpus (≥10 positions, FS-UAE) | 0 |
| 1-B | 1 | Recon findings doc; think entry located | 0 |
| 2-A | 2 | CaissaError promotion; Types.py + Errors.py + Availability | ~8 |
| 2-B | 2 | ruff/pytest/Makefile config; retro markers | ~0 (config tests in 2-A) |
| 3-A | 3 | Manifest.py + manifest.json schema | ~7 |
| 3-B | 3 | Rom.py hunk parser + Fakes.build_synthetic_hunk | ~7 |
| 4-A | 4 | Cpu.py seam + ScriptedCpu | ~4 |
| 4-B | 4 | Cpus/Unicorn68k.py + emulator tests | ~6 |
| 5-A | 5 | Traps.py + TrapRegistry | ~4 |
| 5-B | 5 | VirtualClock + FakeClock | ~3 |
| 6-A | 6 | Bridge.py + Profiles.py stub | ~6 |
| 7-A | 7 | Think.py + Trace.py | ~5 |
| 7-B | 7 | Oracle.py + corpus verification | ~4 |
| 8-A | 8 | Uci.py + golden transcript tests | ~8 |
| 8-B | 8 | tools/caissa-retro + OSEngines registration | ~2 |
| 9-A | 9 | UnicornX86.py + DOS hunk unpacking | ~5 |
| 9-B | 9 | DOS corpus + divergence report | ~0 (data) |
| 10-A | 10 | Completeness + classical invariant tests; Gate E | ~3 |

**Total: ~18 sessions, ~72 tests.**
