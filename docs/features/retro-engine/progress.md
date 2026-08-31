# Retro Engine — Investigation Progress

**Last updated:** 2026-08-31

## What was accomplished (current session)

### Infrastructure fixes (committed, working)
- Dragon-crack trailing bytes are now loaded as `DRAGON_CRACK` region at the correct load address
- `_scan_cmpiw` scans both `HUNK_CODE` and `DRAGON_CRACK` regions
- Outer driver loop: replaced node-count abort with `_hook_de7a` (fires at 0xDE7A, sets abort flag after N calls)
- BSS pre-init (0x0278 sentinel), `_BYPASS_NOOP` additions for timer stubs
- `_hook_tc` / `_hook_de7a` / `_hook_loop_check` / `_hook_player_check` all working
- Phase 0 runs, loop=2, de7a fires 30 times, nodes=31, 81f2=1 ✓

### Diagnostic work (not yet producing a valid move)
Engine output currently: `loop=2 820c=2 tc=1 de7a=30 nodes=31 81f2=1 c198=1 final=10001000 best=94620002` → falls back to python-chess g8h6.

## Current understanding of why the AI never writes a valid move

### Two write sites at AI_BEST_MOVE_ADDR (0x3662), both before any search nodes run

**Site 1: PC=0xD490** — writes `to_sq=0x0002` or `to_sq=0x0000` repeatedly (nodes=0).
- D1 = 0x0002 or 0x0000 at write time
- This is BEFORE any search node is counted
- Probably an initialisation loop iterating over pieces in the piece table

**Site 2: PC=0xD8FE** — writes `to_sq=0x9462` (garbage), D1=0x00009462 (nodes=0).
- Also before any search nodes
- 0x9462 has bit 7 set (invalid 0x88 board square — off-board)
- The final value `best=94620002` (to_sq=0x9462, from_sq=0x0002) comes from this site

### Root cause hypothesis
Both write sites (0xD490 and 0xD8FE) appear to be **initialisation code** that runs before the alpha-beta search starts. The game's normal startup initialises the piece table's movement candidates. In the real game, this init runs once at game start (with proper Amiga OS calls). In our headless setup, this init code runs on EVERY think() call, writing garbage because:
- The piece-iteration variables ([0x3320] etc.) are in a partially-initialised state
- The "search stack" entries at PIECE_TABLE[0x68+] get overwritten with nonsense before any actual search

### The `_SEARCH_STACK_SENTINEL` fix (0x1000)
This was correct in intent: stopping the "no-write" path at 0xD99A that triggered when `to_sq=0` (a1) mapped to an occupied Rook. BUT the sentinel gets overwritten by the init code at 0xD8FE before the actual search runs.

### Key data point: nodes=31
`de7a=30, nodes=31` means the alpha-beta DOES run (0xDE7A fires 30 times, one node per DE7A). So the search IS executing. But AI_BEST_MOVE_ADDR gets overwritten with garbage AFTER the search runs (or during phase 1 which runs after 0x81F2).

Wait — actually nodes=0 at BOTH write sites per the log. And total nodes=31 in the summary. This means:
- Write sites fire BEFORE 0xC2CE (the abort check / node counter) is reached
- But nodes=31 total means 0xC2CE fires 31 times during the actual search
- The search DOES run (31 nodes) but writes nothing valid to AI_BEST_MOVE_ADDR

## What to investigate next

### Option A: Disassemble 0xD490 and 0xD8FE
Read the ROM bytes at those two addresses and understand what the code does:
```bash
xxd -s $((0xD490 + 0x28)) -l 32 Resources/Retro/BattleChess.amiga
xxd -s $((0xD8FE + 0x28)) -l 32 Resources/Retro/BattleChess.amiga
```
Then ask: is this init code that we could/should bypass?

### Option B: Read AI_BEST_MOVE_ADDR BEFORE phase 1 runs
The 0x81F2 hook fires after phase 0 (inner search) returns. We already stop there IF a valid move is found. But: the actual search (31 nodes) may write valid moves to AI_BEST_MOVE_ADDR DURING the search, then the init code at 0xD490/0xD8FE overwrites with garbage AFTER.

Add a snapshot in `_hook_abort_check` that fires at each node: if `AI_BEST_MOVE_ADDR` has a valid move at node 31, we have it. The `_write_snapshot` already does this via `_hook_abort_check` — but it only checks after the fact. Does AI_BEST_MOVE_ADDR ever have a valid move during the search?

**Key question**: are the 0xD490/0xD8FE writes happening DURING the 31-node search, or AFTER it (during phase 1 cleanup)?

### Option C: Completely bypass the outer driver phases
Start emulation at AI_INIT_ADDR (0x8230) directly, not AI_OUTER_DRIVER_ADDR (0x81DC). Phase 0 runs the inner search. Stop at 0xC198 return. Read AI_BEST_MOVE_ADDR at that point. This was the original approach and might avoid phase 1 corruption entirely.

## Known good calibrated constants
- BSS [0x3000..0x5FFE] pre-init to 0x0278 ✓
- _ABORT_FLAG_ADDR = 0x4A4A ✓ (zero before search)
- _WAIT_FLAG_ADDR = 0x4A92 ✓ (zero before search)
- _LOOP_FLAG_ADDR = 0x4A5A ✓ (set to 2 before search)
- _SEARCH_COMPLETE_FLAG_ADDR = 0x8270 ✓ (zero before search)
- AI_BEST_MOVE_ADDR = 0x3662 ✓ (confirmed by hook)
- DE7A fires 30 times with threshold=30 → search runs ✓
- nodes=31 → alpha-beta executes 31 nodes ✓
- 0x81F2 fires → phase 0 returns normally ✓
