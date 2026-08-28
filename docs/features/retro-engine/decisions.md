# Retro Engine — Decision Log

Decisions referenced in the spec and implementation as `D-n`.
Living document; updated as each decision is resolved.

| ID | Question | Decision | Rationale | Phase resolved |
|---|---|---|---|---|
| D1 | Where does `CaissaError` live? `Code.Retro` coupling to `Code.Rpa.Errors` for one class is wrong. | Promote to `bin/Code/Base/CaissaErrors.py`; `Code.Rpa.Errors` re-exports it for backward compat. | Two independent domains must not couple through a third domain's module. `Code.Base` is the right home for repo-wide foundations. | 2 |
| D2 | Which Amiga release is the primary manifest target? | TBD in Phase 1-A when the binary is identified and sha256-hashed. | Cannot resolve without the binary in hand. | 1 |
| D3 | Are (position, level, move) corpus records committable? | Yes — treated as factual data (a list of moves), not code. Documented in `docs/retro/legal.md`. | Same legal theory as committing a game score. No code bytes; no derived bytecode; just move notation. | 0 |
| D4 | Can the think function accept arbitrary FEN positions, or does it require full derived state? | TBD in Phase 1-B recon. Fallback: use move-replay from startpos as the primary path; arbitrary FEN as a validated fast path. | The engine likely maintains Zobrist hash, piece lists, incremental eval. A naive struct write may silently corrupt them. Verify in Phase 1. | 1 |
| D5 | Unicorn's m68k models 68020+/ColdFire. Does Battle Chess rely on 68000-specific flag semantics? | TBD in Phase 4 differential testing vs FS-UAE. If divergence found: swap `Cpus/Unicorn68k.py` for a Musashi backend via cffi, no other changes. | The `Cpu.py` seam exists precisely for this substitution. | 4 |
