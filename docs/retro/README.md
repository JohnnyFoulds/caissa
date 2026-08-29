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

## Status

Both binaries are committed to `Resources/Retro/`. The Amiga engine is being wired
and tested end-to-end. The DOS engine awaits the x86 recon phase.

Feature archive: `docs/features/_archive/retro-engine/`.
