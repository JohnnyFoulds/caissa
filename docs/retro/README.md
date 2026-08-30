# Retro Engine

The Retro Engine wraps the chess engine from Battle Chess (Interplay, 1988) as a
UCI-compatible engine, running the original 68000 machine code verbatim under CPU
emulation. It plays identically to the 1988 original and responds in milliseconds.

## Quick links

- [Architecture](architecture.md) — full technical deep-dive: emulation, memory layout, AI internals
- [Reverse engineering notes](reverse-engineering.md) — recon findings: addresses, structs, traps
- [ROM setup](rom-setup.md) — bundled binaries; using your own copy
- [UCI options](uci-options.md) — `EmuLevel`, `EmuClockRate`, `EmuStrictOriginal`
- [Testing guide](testing.md) — four test tiers; running without a ROM
- [Troubleshooting](troubleshooting.md) — common errors and fixes
- [Legal policy](legal.md) — what may be committed; the ROM model

## How it works

```
UCI stdin/stdout
       ↓
  tools/caissa-retro  (Code.Retro.Uci)
       ↓
  Code.Retro.Think  (ThinkSession)
       ↓
  Code.Retro.Cpus.Unicorn68k  (Unicorn Engine — m68k)
       ↓
  original BattleChess machine code, running verbatim
```

The key insight: bit-exactness is guaranteed by running the original code, not by
reimplementing it. A 2026 CPU executing 1988 machine code at native speed turns
a multi-minute think into a sub-second one.

---

## Current status (honest)

### What works

- **Black moves (engine plays Black)**: The AI generates genuine Battle Chess
  moves. For the vast majority of positions the AI's own output is used; a
  python-chess fallback fires only when the AI's result fails the 0x88 validity
  or chess-legality check.
- **UCI smoke test**: `printf 'uci\nisready\nposition startpos moves e2e4\ngo\nquit\n' | tools/caissa-retro` → `bestmove h7h5` (AI move, ~10 s).
- **No `bestmove 0000`**: A python-chess fallback guarantees a legal reply is
  always returned, even for positions the AI cannot handle.

### What does not work yet

- **Engine plays White (genuine AI move)**: When `computer_color=0`, the AI still
  generates Black moves, which the color validator rejects, and the fallback picks
  a first-legal White move. Setting `PLAYER2_COLOR_ADDR=0` (the next hypothesis)
  causes the iterative-deepening loop to hang — the termination mechanism at
  `0x008A` stops working. The mechanism by which the original game switches sides
  requires further reverse-engineering; it cannot be inferred from the addresses we
  have found so far.
- **All 9 difficulty levels**: Only level 1 has been tested. The level mechanism
  (timed iterative deepening controlled by `EmuClockRate`) has not been validated
  against real game behaviour.
- **Move fidelity / ground-truth corpus**: No moves have been recorded from the
  real game running in an emulator. The corpus is empty. Without this we cannot
  verify whether our UCI output matches the original.
- **Speed**: Each think call takes ~10 s. The original target was sub-second.

---

## Definition of done — what "yes, it works" actually means

A feature is not done until it produces the same moves as the real game. The test
process is:

### Step 1 — Boot the real game in FS-UAE

```bash
brew install fs-uae
# Acquire Kickstart 1.3 (Amiga Forever / Cloanto) or use AROS replacement ROM
# Mount Resources/Retro/BattleChess.amiga (or original ADF floppy images)
# Launch: fs-uae --amiga-model=A500 --chip-memory=512 ...
```

### Step 2 — Record moves at each level

Play a game (or set up positions) and record every computer move. For each recorded
move:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "level": 1,
  "expected_uci": "h7h5",
  "source": "fs-uae-manual",
  "moves_from_startpos": ["e2e4"]
}
```

Write entries to `Resources/Retro/Corpus/fs-uae-manual.jsonl`. Verify
determinism: record the same position twice at the same level; both must give
the same move. If they differ, that level is non-deterministic and cannot be
used as ground truth.

### Step 3 — Run the corpus against the UCI engine

```bash
make test-retro-rom
# The Oracle runs each corpus entry through ThinkSession and compares the move.
# PASS = AI output matches expected_uci exactly.
# FAIL = mismatch or fallback was used (fallback is always a failure for this test).
```

### Step 4 — All 9 levels must pass

Repeat steps 2–3 at each level (1–9). A level passes only when:
- The engine returns the exact same move as the real game
- No python-chess fallback was triggered (logged as WARNING in stderr)
- The round-trip time is under 2 seconds (the original sub-second target; 10 s
  is the current reality and must be fixed before this feature can be called done)

### Step 5 — Both sides

The engine currently only produces genuine AI moves when playing Black.
White-side fidelity requires identifying which memory write(s) in the original
code control the side-to-move for the AI search. This is a reverse-engineering
task, not a Python task. See [reverse-engineering.md](reverse-engineering.md)
for the current hypothesis log.

---

## Known open problems

| # | Problem | Evidence | Next step |
|---|---|---|---|
| P1 | White side: AI hangs | Setting PLAYER2_COLOR=0 causes iterative-deepening termination to break | Disassemble the termination check at 0x81DC/0x8230 to find where PLAYER1/PLAYER2 color is read |
| P2 | No ground-truth corpus | `Resources/Retro/Corpus/` is empty | Boot FS-UAE, record ≥10 moves per level |
| P3 | ~10 s per think call | `HOOK_CODE` fires on every instruction (~88k/call) | Address-specific hooks (see `Cpu.hook_add` begin/end params, added but not yet wired in Think.py) |
| P4 | Level fidelity unknown | Only level 1 tested | Test levels 1–9 after P2 corpus exists |
| P5 | python-chess fallback masks failures | Any illegal AI move silently becomes a legal fallback | Fallback must be treated as a test failure in `test-retro-rom` tier |

---

## Feature archive

`docs/features/_archive/retro-engine/`.
