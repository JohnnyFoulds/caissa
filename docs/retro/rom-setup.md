# ROM Setup

The Retro Engine does not ship the original binary. You must supply your own copy.

---

## Getting the binary

You need the **Amiga version** of Battle Chess (1988) — the true original. The binary
is the single `BattleChess` executable file from the Amiga disk.

For the DOS version (Phase 9, secondary target): the DOS release ships inside an
installer. See [reverse-engineering.md](reverse-engineering.md) for unpacking notes.

---

## Verifying your copy

```bash
tools/caissa-retro identify /path/to/BattleChess
```

This prints the sha256, size, and hunk layout, and tells you whether the file matches
a known-good entry in `Resources/Retro/manifest.json`.

---

## Pointing the shim at your binary

**Option 1 — environment variable (recommended):**

```bash
export CAISSA_RETRO_ROM=/path/to/BattleChess
tools/caissa-retro  # picks it up automatically
```

**Option 2 — UCI option:**

In the chess GUI, set the `EmuRomPath` option to the full path of your binary.

**Option 3 — default search path:**

The shim also searches `UserData/Retro/Roms/BattleChess` (relative to the Caissa
data directory). Copy your binary there and no configuration is needed.

---

## If your binary is not in the manifest

```bash
tools/caissa-retro identify /path/to/BattleChess
```

If the file is a real Battle Chess binary but from a different release or region, open
an issue with the sha256 output. Do not attach the binary itself.

If you want to run an unverified binary during development:

```bash
CAISSA_RETRO_ALLOW_UNKNOWN=1 tools/caissa-retro
```

Note: `--allow-unknown` strips the `EmuStrictOriginal` guarantee from the UCI `id`
string. The engine runs but the bit-exactness claim does not apply.

---

## If the binary is packed

Some copies of Battle Chess use PowerPacker or Imploder compression. The shim detects
this automatically and unpacks in memory before loading. If it cannot unpack:

```bash
tools/caissa-retro identify /path/to/BattleChess
# Look for "Packer detected: ..."
```

See [troubleshooting.md](troubleshooting.md) if unpacking fails.
