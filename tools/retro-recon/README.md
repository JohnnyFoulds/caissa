# retro-recon — Phase 1 Spike Tools

**EXPERIMENTAL — Phase 1 spike. These tools are deleted in Phase 10.**

Throwaway tooling for the Battle Chess reverse-engineering recon spike.
The only durable output from this phase is `recon_findings.md` and the
corpus entries in `Resources/Retro/Corpus/`.

---

## Workflow

### Phase 1-A — Ground truth (do this first)

Run Battle Chess in FS-UAE. For each position, let the engine think, then record the move:

```bash
python3 tools/retro-recon/record_corpus.py \
    --output Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl \
    --target amiga
```

Record at least:
- Start position at levels 1, 2, 3
- 3–4 mid-game positions at level 1
- Optionally: the same positions at a second level

Without ground truth, you cannot tell whether the Unicorn trace is producing
correct moves or consistent wrong ones. Do this first.

### Phase 1-B — Binary identification

```bash
python3 tools/retro-recon/identify.py /path/to/BattleChess
```

This requires only the binary — no unicorn. It prints the sha256, hunk table,
and packer detection. Run this first to confirm you have the right file.

### Phase 1-B — Memory read profiling (requires unicorn)

```bash
pip install unicorn
python3 tools/retro-recon/memory_trace.py \
    --rom /path/to/BattleChess \
    --entry 0x<candidate_address> \
    --budget 50000000 \
    --output /tmp/reads.json
```

Hook all memory reads to map what the think function touches. Look for:
- The board struct region (high read count, inside the binary)
- External addresses (highlighted as `*** TRAP CANDIDATE ***`)
- The timer read site (an external address read many times in a tight range)

### Phase 1-B — Call trace and move decode (requires unicorn)

```bash
python3 tools/retro-recon/call_trace.py \
    --rom /path/to/BattleChess \
    --entry 0x<think_address> \
    --board-offset 0x<board_struct_address> \
    --level 3 \
    --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" \
    --output /tmp/trace.json
```

This writes the start position into the board struct and calls the think function.
The move hypothesis uses D0 bits[5:0] as `from_square` and bits[11:6] as `to_square`
(common m68k chess convention) — adjust if the result does not match the corpus.

The `--output` file is an **observation-level trace** (no code bytes) and is safe to commit.

---

## Finding the think function in Ghidra

1. Load the binary: File → Import → select the `BattleChess` file → processor = `m68k:BE:32:68000`
2. Let auto-analysis run (takes ~1 minute)
3. Look for:
   - **Alpha/beta search**: a recursive function with two parameters that look like bounds
     (`alpha` and `beta` are typically in D0/D1 or A0/A1 or passed on the stack)
   - **Move loop**: a loop that iterates over 60–64 items (the board squares)
   - **Depth counter**: an integer that decrements on recursive calls
4. The think entry point is usually called from a single dispatch site that checks
   "is it the computer's turn?" — search for a function called only once per move

Good Ghidra queries to try:
- Search for constants 100, 200, 900 (likely queen/rook/bishop values in centipawns)
- Search for the value 64 (board size constant)
- Search for patterns like `MOVE.L D0,-(A7)` (pushing to stack for recursive call)

---

## Kill criteria

Phase 1 passes only if all five hold:

1. Binary loads cleanly (no unresolved packer)
2. A recursive function with alpha/beta signature is identified
3. Static evaluation tables (piece-square) are present and plausible
4. Board struct is mapped well enough for a field offset table
5. One call_trace result matches a Phase 1-A corpus entry

If criteria 1–5 are not all met after the time-box (~12 h), stop and re-spec.
