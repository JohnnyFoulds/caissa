# UCI Options

Options exposed by `tools/caissa-retro` via the UCI `option` command.

---

## `EmuLevel` (spin)

**Default:** 1  
**Range:** 1–9 (maps directly to the original's "Level 1" through "Level 9" labels)

The difficulty level as in the original game. The binary contains nine levels labelled
"Level 1"–"Level 9" in its string table; each maps to the same integer passed to the
timed AI state machine. Higher numbers allow more virtual clock time per move, resulting
in stronger play.

Level 1 is the easiest (least search time, responds fastest). Level 9 corresponds to the
original's hardest difficulty — which on a 1988 Amiga 500 took minutes; under emulation
it takes milliseconds regardless of level.

---

## `EmuClockRate` (spin)

**Default:** 100  
**Range:** 1–200

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

**Default:** true

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
option name EmuLevel type spin default 1 min 1 max 9
option name EmuClockRate type spin default 100 min 1 max 200
option name EmuStrictOriginal type check default true
option name EmuRomPath type string default <empty>
uciok
```
