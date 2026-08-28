# Retro Engine — Decision Log

Decisions referenced in the spec and implementation as `D-n`.
Living document; updated as each decision is resolved.

| ID | Question | Decision | Rationale | Phase resolved |
|---|---|---|---|---|
| D1 | Where does `CaissaError` live? `Code.Retro` coupling to `Code.Rpa.Errors` for one class is wrong. | Promote to `bin/Code/Base/CaissaErrors.py`; `Code.Rpa.Errors` re-exports it for backward compat. | Two independent domains must not couple through a third domain's module. `Code.Base` is the right home for repo-wide foundations. | 2 |
| D2 | Which Amiga release is the primary manifest target? | **Dragon Inc crack, SHA256 `d4fc6137…`**, 84 912 bytes, single HUNK_CODE, pre-relocated, base 0x00000000. Emulation granularity revised from isolated-function-call to **whole-binary headless emulation** (state-machine architecture makes isolation impractical — confirmed in Phase 1-B). Bridge.py drives the full game loop, injects board position, and reads best move from `-$49A4(A4)`. | Phase 1-B confirmed: no clean think-function entry point; whole-binary emulation required. | 1 |
| D3 | Are (position, level, move) corpus records committable? | Yes — treated as factual data (a list of moves), not code. Documented in `docs/retro/legal.md`. | Same legal theory as committing a game score. No code bytes; no derived bytecode; just move notation. | 0 |
| D4 | Can the think function accept arbitrary FEN positions, or does it require full derived state? | **Primary path: move-replay from startpos.** The 1-ply state-machine iterates the global piece table at `-$4CDC(A4)`; Bridge.py must write piece entries and set `piece_counter (-$4CDE)`. Full derived state (incremental eval, hash) is unknown — deferred to Phase 6 testing. If struct-write corrupts state, fall back to game-replay from startpos to the target position. | Phase 1-B: AI is 1-ply, no alpha-beta; isolated function call impossible; board must be injected and the game loop driven. | 1 |
| D5 | Unicorn's m68k models 68020+/ColdFire. Does Battle Chess rely on 68000-specific flag semantics? | TBD in Phase 4 differential testing vs FS-UAE. If divergence found: swap `Cpus/Unicorn68k.py` for a Musashi backend via cffi, no other changes. | The `Cpu.py` seam exists precisely for this substitution. | 4 |
