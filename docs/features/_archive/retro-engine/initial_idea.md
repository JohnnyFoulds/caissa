# Retro Engine — Initial Idea

**Status:** FROZEN — scope locked 2026-08-28  
**Frozen by:** Johannes Foulds  
**Next artefact:** [feature_spec.md](feature_spec.md)

---

## Problem Statement

Battle Chess (Interplay, 1988) shipped a chess engine that was, by modern standards,
awful — and unbearably slow. On its hard levels it took minutes per move on period
hardware. That engine has a distinctive personality: predictable, beatable, nostalgic.
Playing against something that strong engines crushed in 1990 is a different experience
from playing against a deliberately-tuned weak modern engine.

The problem is that there is no legal, usable version of it. Running the original
game today requires a full Amiga emulator, the whole game's UI, and patience. There
is no way to plug the engine into a modern chess tool.

The goal is to preserve that engine *exactly* — same moves, same blunders, same
personality — while making it respond in microseconds, and expose it over UCI so it
can be plugged into Caissa and any modern tool (Arena, CuteChess, Banksia).

The insight driving the design: **do not reimplement the engine.** A reimplementation
from a Ghidra decompile has a long tail of subtle divergences — an off-by-one in a
piece-square table, a different tie-break order, an integer overflow that no longer
overflows. Instead, run the *original machine code verbatim* under a CPU emulator
(Unicorn Engine), calling only the isolated "think" function. Bit-exactness then holds
by construction rather than by careful transcription, and a modern CPU executing 1988
machine code at native speed solves the slowness problem.

This is greenfield: no public reverse-engineering of Battle Chess exists.

---

## Business Requirements

| ID | Requirement |
|---|---|
| BR-1 | Expose the Battle Chess (1988) chess engine as a UCI-compatible engine usable from Caissa and any other standard chess GUI or tool. |
| BR-2 | The engine's move selection **MUST** be bit-exact to the original: same position, same level, same deterministic input → same move, always. |
| BR-3 | Move generation **MUST** be fast — at worst seconds, not minutes — on modern hardware, at every difficulty level. |
| BR-4 | **No original binary, disk image, or extracted code segment may be committed** to the repository. The user supplies their own copy; the engine verifies it by sha256 before loading. |

---

## Confirmed Decisions (at scope-lock)

| Decision | Choice |
|---|---|
| Emulation approach | Run original machine code verbatim under Unicorn Engine — do not reimplement |
| Primary target | Amiga 68000 binary (the true 1988 original); DOS x86 port validated second |
| Emulation granularity | Isolated think function only — stub just the OS calls that function makes |
| Timed-level determinism | Feed a deterministic simulated timer (fixed virtual clock); expose rate as a UCI option |
| Binary distribution | User-supplied, sha256-verified against a committed manifest of known-good hashes |
| Location | Caissa sub-project — `bin/Code/Retro/`; spec in `docs/features/retro-engine/` |
| Phase structure | Phase 0 doc/process; Phase 1 recon spike (GO/KILL gate); Phases 2–10 build |
| First phase after spike | Foundations (Types/Errors/Makefile) — build after the spike proves feasibility |

---

## Open Questions (to be resolved in feature_spec.md)

| # | Question |
|---|---|
| D1 | Where does `CaissaError` live? Currently `bin/Code/Rpa/Errors.py`. `Code.Retro` coupling to `Code.Rpa` for one exception class is ugly. Resolve: stay or promote to `bin/Code/Base/CaissaErrors.py`. |
| D2 | Which Amiga release constitutes "the original"? There were at least two disk variants. Resolve: choose one as the primary manifest target; document others as alt-hashes. |
| D3 | Committing move-corpus data: is recording N (position, level) → move pairs from the original committtable? Resolve: consult legal.md — treat as factual data (a list of moves), not code. |
| D4 | Can the think function accept arbitrary FEN positions? The engine may keep derived state (Zobrist hash, piece lists) that a naive struct write silently corrupts. Resolve: in Phase 1 recon. |
| D5 | Unicorn's m68k core models 68020+/ColdFire. If the 1988 Amiga binary relies on 68000-specific flag semantics, a Musashi (MAME) backend may be needed. Resolve: differential testing in Phase 4. |
