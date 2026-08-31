# Retro Engine — Investigation Progress

**Last updated:** 2026-08-31

---

## Status: Root cause confirmed; fix ready to implement

The engine fallback to python-chess (g8h6) is caused by mis-decoded 6-byte `MOVE.W` instructions
in the move-candidate generator (`update_best_move_candidate` at 0xD6D2). The complete model is
documented in `ai_engine_map.md`. This progress file tracks session handoff only.

---

## What was accomplished this session (2026-08-31)

1. **Complete IRA disassembly** of all AI functions — 25k line `.asm` produced (local `/tmp/` only).
   Key functions fully mapped: `outer_driver` (0x81DC), `ai_init` (0x8230), `inner_search` (0xC198),
   `de7a_handler` (0xDE7A), `init_piece_search_slot` (0xD45A), `update_best_move_candidate` (0xD6D2).

2. **Root cause confirmed** — multiple 6-byte `MOVE.W (d16,An),(An,Dn.L)` and
   `MOVE.W (An,Dn.L),(d16,An)` forms at addresses 0xD700, 0xD7B2, 0xD77E, 0xD830, 0xD8AE, 0xD8FE
   are not in `_scan_cmpiw` (which only handles op bytes 0x00–0x0C, not 0x31). Unicorn mis-decodes
   these: direction deltas are loaded incorrectly → garbage candidate squares → garbage `best=94620002`.

3. **Formal documents written and committed**:
   - `docs/features/retro-engine/ai_engine_map.md` — complete engine map with pseudo-code,
     4 Mermaid flowcharts, write-site table, 6-byte instruction inventory, Python port notes
   - `docs/standards/m68k-disassembly-methodology.md` — reusable M68K RE methodology
   - `docs/features/retro-engine/plan_phase11_fix.md` — complete fix plan with commit checkpoints

4. **Previous diagnostic findings (from prior sessions)** confirmed correct:
   - `loop=2 820c=2 tc=1 de7a=30 nodes=31 81f2=1` — outer driver phases work ✓
   - Write site at 0xD490 (4-byte, OK) writes `from_sq` placeholder — harmless init ✓
   - Write site at 0xD8FE (6-byte, BROKEN) produces `to_sq=0x9462` — root cause ✓

---

## What is next

**Step 1** (`bin/Code/Retro/Think.py`) — extend `_scan_cmpiw` with two new scan patterns:

- **Pattern A** (op byte `0x31`, source = d16 addressing, dest = indexed with extension `0x0800`):
  - 0xD700 — writes from_sq to from_sq field
  - 0xD7B2 — writes candidate to to_sq field (queen/king path)
  - 0xD830 — writes candidate to to_sq field (rook/bishop ray path)
  - 0xD8FE — writes candidate to to_sq field (pawn path, confirmed garbage write site)

- **Pattern B** (source = indexed with extension `0x0800`, dest = d16 displacement):
  - 0xD8AE — loads direction delta into frame local[-10,A5]
  - 0xD77E — loads direction delta for queen/king path

Then extend `_hook_cmpiw` to handle both forms correctly.

**Step 2** — smoke test: `printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro`
must produce `bestmove` in `{e7e5, c7c5, e7e6, c7c6, d7d5}`.

**Step 3** — `make test` + add `retro_rom` corpus test.

---

## Blocking unknowns

None. Root cause is confirmed. The fix path is clear.

If smoke test fails after the `_scan_cmpiw` fix: install Ghidra + ghidra-amiga + PyGhidra
(see `docs/standards/m68k-disassembly-methodology.md` §1) and run PyGhidra batch decompile
to find any remaining unhandled 6-byte forms. The plan file documents the exact install steps.

---

## Infrastructure working (do not change without testing)

- BSS `[0x3000..0x5FFE]` pre-init to `0x0278` ✓
- `_ABORT_FLAG_ADDR = 0x4A4A` — zero before search ✓
- `_LOOP_FLAG_ADDR = 0x4A5A` — set to 2 ✓
- `_SEARCH_COMPLETE_FLAG_ADDR = 0x8270` — zero before search ✓
- `_hook_de7a`: sets abort flag after `_de7a_threshold` (30) calls ✓
- `_hook_loop_check`, `_hook_player_check`: handle 6-byte CMPI.W at 0x820C, 0x8220 ✓
- `_hook_tc`: NOOP for timer stub at 0x008A ✓
- `AI_BEST_MOVE_ADDR = 0x3662` confirmed correct by mem_write hook ✓

---

## Prior session diagnostic output (for reference)

```
loop=2 820c=2 tc=1 de7a=30 nodes=31 81f2=1 c198=1 final=10001000 best=94620002
```
- `final=10001000` — sentinel values (0x1000 in to_sq slots, 0x1000 = sentinel placeholder)
- `best=94620002` — to_sq=0x9462 (garbage, off-board), from_sq=0x0002 (c1 Bishop, wrong color)
- Engine correctly rejects this and falls back to python-chess
