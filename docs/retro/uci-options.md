# UCI Options

Options exposed by `tools/caissa-retro` via the UCI `option` command.

---

## `EmuLevel` (spin)

**Default:** 3  
**Range:** 1–N (exact range determined by Phase 1 recon; maps to original difficulty levels)

The difficulty level as in the original game. Each level maps to the original engine's
internal level parameter, which controls search depth or time budget.

Level 1 is the easiest (shallowest search, responds fastest). The highest level
corresponds to the original game's hardest difficulty — which on a 1988 Amiga 500 took
minutes; under emulation it takes milliseconds.

---

## `EmuClockRate` (spin)

**Default:** 100  
**Range:** 1–10000

The virtual clock rate as a percentage of the original machine's speed.

- `100` = the clock runs at the same speed as on an Amiga 500 in 1988. At difficulty
  levels that used a time cutoff, the engine thinks for exactly as many "1988 milliseconds"
  as it would have on original hardware. **This is the bit-exact setting.**
- `200` = the clock appears to tick twice as fast to the engine, halving the time the
  engine "thinks" it is spending. Effectively makes time-limited levels think at half
  the original depth.
- `50` = the clock runs at half speed; the engine thinks longer (in virtual time) on
  timed levels.

For fixed-depth levels, `EmuClockRate` has no effect.

Setting `EmuStrictOriginal true` disables any value other than 100.

---

## `EmuStrictOriginal` (check)

**Default:** false

When `true`, the engine:
- Rejects `EmuClockRate` values other than 100 with an error
- Includes `strict-original` in the UCI `id name` string
- Refuses to run on an unverified binary (overrides `CAISSA_RETRO_ALLOW_UNKNOWN`)

Use this when you want a guaranteed bit-exact experience and want the GUI to record
that fact in game metadata.

---

## `EmuRomPath` (string)

**Default:** (empty — uses `CAISSA_RETRO_ROM` env var or the default search path)

Full path to the user's binary. Useful when the GUI launches the engine in an
environment where the environment variable is not set.

---

## Example UCI handshake

```
uci
id name Battle Chess (Retro) 1988
id author Interplay (emulated)
option name EmuLevel type spin default 3 min 1 max 8
option name EmuClockRate type spin default 100 min 1 max 10000
option name EmuStrictOriginal type check default false
option name EmuRomPath type string default <empty>
uciok
```
