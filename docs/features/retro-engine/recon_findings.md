# Retro Engine — Recon Findings (Phase 1-B)

**Status:** IN PROGRESS — spike ongoing  
**Phase:** 1 — Recon Spike (GO / KILL)  
**Branch:** `spike/retro-recon`

Fill this document as Phase 1-B progresses. It is the only durable output from
the spike. All five kill criteria must be checked before Phase 2 begins.

---

## Kill Criteria Status

| # | Criterion | Status |
|---|---|---|
| 1 | Binary loads cleanly; Ghidra produces sane m68k disassembly | ⬜ TBD |
| 2 | Recursive function with alpha/beta signature identified | ⬜ TBD |
| 3 | Static evaluation tables (piece values / piece-square) located and plausible | ⬜ TBD |
| 4 | Board-struct mapped well enough for a field offset table | ⬜ TBD |
| 5 | One think call from startpos returns a move matching a 1-A corpus entry | ⬜ TBD |

**GO / KILL decision:** ⬜ Pending

---

## Binary Identification

Run: `python3 tools/retro-recon/identify.py /path/to/BattleChess`

| Field | Value |
|---|---|
| Filename | TBD |
| Size (bytes) | TBD |
| SHA256 | TBD |
| Format | TBD (Amiga Hunk / DOS MZ) |
| Packer detected | TBD (None / PowerPacker / Imploder) |

### Hunk table

| # | Type | Offset | Size | Notes |
|---|---|---|---|---|
| 0 | TBD | TBD | TBD | |
| 1 | TBD | TBD | TBD | |

---

## Candidate Think Entry Point

| Field | Value |
|---|---|
| Address | TBD |
| Justification | TBD (e.g. "single call site from move-dispatch function at 0xXXXX; recursive with 2 stack params looking like alpha/beta") |

### Calling convention hypothesis

| Parameter | Register / stack offset | Notes |
|---|---|---|
| Board pointer | TBD | e.g. A0 |
| Depth / level | TBD | e.g. D0 |
| Alpha | TBD | |
| Beta | TBD | |

### Return value

| Field | Register | Notes |
|---|---|---|
| Move (from square) | TBD | e.g. D0 bits [5:0] |
| Move (to square) | TBD | e.g. D0 bits [11:6] |
| Move type / promotion | TBD | |

---

## Board Struct Layout

Run: memory_trace.py, observe which address range is read most frequently.

Board struct base address: **TBD**

| Offset | Size | Field | Notes |
|---|---|---|---|
| +0x00 | TBD | Piece array start | 64 squares? 120 (0x88 board)? |
| +TBD | TBD | Side to move | 0=white, 1=black? |
| +TBD | TBD | Castling rights | TBD encoding |
| +TBD | TBD | En passant square | TBD |
| +TBD | TBD | Move count | TBD |

### Piece encoding

| Piece | Value | Notes |
|---|---|---|
| Empty | TBD | |
| White Pawn | TBD | |
| White Knight | TBD | |
| White Bishop | TBD | |
| White Rook | TBD | |
| White Queen | TBD | |
| White King | TBD | |
| Black Pawn | TBD | |
| ... | ... | |

---

## Timer / Clock Read Site

Run: memory_trace.py and look for external addresses with many reads in a tight loop.

| Field | Value |
|---|---|
| Timer address | TBD |
| Read count (think from startpos) | TBD |
| Context (what instruction reads it) | TBD |
| Handler strategy | VirtualClock instruction-counted tick |

If no timer read is found: the engine uses fixed-depth search. Note "**NONE — fixed-depth engine**"
here and mark `VirtualClock` as a no-op adapter in Phase 5.

---

## External Addresses (Trap Table)

From memory_trace.py `*** TRAP CANDIDATE ***` output.
Each becomes a stub handler in `bin/Code/Retro/Traps.py`.

| Address | Access count | Amiga library | Function | Handler strategy |
|---|---|---|---|---|
| TBD | TBD | exec.library | AllocMem | Return pre-allocated block |
| TBD | TBD | exec.library | FreeMem | No-op |
| TBD | TBD | (timer) | ReadEClock / VBeamPos | Return virtual clock tick |

---

## Evaluation Tables

Locations of the static piece-square and material-value tables in the binary.

| Table | Address | Size | Notes |
|---|---|---|---|
| Material values (per piece type) | TBD | TBD | |
| Piece-square table (pawns) | TBD | TBD | |
| Piece-square table (knights) | TBD | TBD | |
| Piece-square table (combined) | TBD | TBD | |

Sample values (to verify they are plausible chess values):
- Pawn = TBD (expect ~100)
- Knight = TBD (expect ~300)
- Bishop = TBD (expect ~300)
- Rook = TBD (expect ~500)
- Queen = TBD (expect ~900)

---

## Observation Trace — Start Position, Level 3

Captured by: `python3 tools/retro-recon/call_trace.py --output /tmp/trace.json ...`

```json
{
  "kind": "observation",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "target": "amiga",
  "level": 3,
  "entry_regs": "TBD",
  "exit_regs": "TBD",
  "instr_count": "TBD",
  "external_writes": "TBD",
  "hypothesis_move": "TBD"
}
```

**Ground truth match:** TBD — compare `hypothesis_move` against the Phase 1-A corpus entry
for the same (fen, level) pair.

---

## Phase 1-A Ground Truth Summary

Populated by `record_corpus.py` → `Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl`.

| FEN (truncated) | Level | Move observed | Notes |
|---|---|---|---|
| TBD | TBD | TBD | start position |

---

## Decisions Made / Updated

| Decision | Resolution | Notes |
|---|---|---|
| D2 — which Amiga release | TBD (sha256 of confirmed binary) | |
| D4 — arbitrary FEN accepted? | TBD (can the struct be written directly?) | |
| D5 — Unicorn 68000 fidelity | TBD (does startpos move match?) | |

---

## Notes / Surprises

*(Fill in during the spike — anything unexpected that the later phases need to know.)*

---

## Next Steps after GO

1. Update `Resources/Retro/manifest.json` with the confirmed sha256 and offsets
2. Add resolved values to `docs/features/retro-engine/decisions.md` (D2, D4, D5)
3. Proceed to Phase 2 (`chore/retro-foundations`) — write `Types.py` and `Errors.py`
