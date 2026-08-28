# Retro Engine

The Retro Engine wraps the chess engine from Battle Chess (Interplay, 1988) as a
UCI-compatible engine, running the original 68000 machine code verbatim under CPU
emulation. It plays identically to the 1988 original and responds in milliseconds.

## Quick links

- [Legal policy](legal.md) — what may be committed; the ROM model
- [ROM setup](rom-setup.md) — how to point the shim at your copy of the binary
- [UCI options](uci-options.md) — `EmuLevel`, `EmuClockRate`, `EmuStrictOriginal`
- [Reverse engineering notes](reverse-engineering.md) — how the think function was found
- [Testing guide](testing.md) — four test tiers; running without a ROM
- [Troubleshooting](troubleshooting.md) — common errors and fixes

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

## Status

See [feature_steps.md](../features/retro-engine/feature_steps.md) for current phase.
