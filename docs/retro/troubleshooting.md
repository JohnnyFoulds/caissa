# Troubleshooting

---

## `RomNotFoundError: no ROM found`

The shim could not locate a binary. Try:

```bash
export CAISSA_RETRO_ROM=/path/to/BattleChess
tools/caissa-retro
```

Or copy the binary to `UserData/Retro/Roms/BattleChess`.

---

## `RomHashMismatchError: sha256 <hash> not in manifest`

Your binary is not in the known-good manifest. Try:

```bash
tools/caissa-retro identify /path/to/BattleChess
```

If the file looks correct but comes from a different release or region, open an issue
with the `identify` output. Do not attach the binary.

To run anyway (bit-exactness not guaranteed):

```bash
CAISSA_RETRO_ALLOW_UNKNOWN=1 tools/caissa-retro
```

---

## `RomPackedError: binary is packed with PowerPacker`

The shim detected a packed binary and could not unpack it. Options:

1. Use `ppunpack` (available in most Amiga emulation toolkits) to create an unpacked
   copy, then point the shim at that.
2. Extract the binary from a full-system emulator: boot in FS-UAE, run the game until
   the binary is fully loaded, then use the FS-UAE memory dump to extract the in-memory
   image.

---

## `CpuUnavailableError: unicorn is not installed`

Install the CPU emulator:

```bash
pip install -r requirements-retro.txt
```

Or install unicorn separately:

```bash
pip install unicorn>=2.0
```

---

## `EmulationFaultError: fault at PC=0x... registers=...`

The emulated engine crashed. Possible causes:

1. **Wrong binary variant** — the struct offsets in `Profiles.py` are calibrated to a
   specific release. If your binary is a different release and matched via
   `CAISSA_RETRO_ALLOW_UNKNOWN`, the offsets may be wrong.
2. **Missing trap handler** — the engine called an Amiga library function that has no
   stub. Check the register dump for a library base pointer being used.
3. **Unicorn m68k fidelity gap** — a rare opcode or flag-setting edge case. Open an
   issue with the full register dump.

---

## UCI handshake accepted but `go` returns `bestmove 0000`

The handshake succeeded but no ROM is loaded. Check:

1. Is `CAISSA_RETRO_ROM` set?
2. Is the binary sha256-verified (`tools/caissa-retro identify`)?
3. Does the GUI pass the `EmuRomPath` option correctly?

The `info string` line preceding `bestmove 0000` will contain a detailed error message.

---

## `make test` fails with `No module named unicorn`

This is expected — `make test` runs the `retro` tier which does not need `unicorn`.

For the emulator tier:

```bash
pip install -r requirements-retro.txt
make test-retro-emu
```

---

## `test_no_tracked_file_matches_manifest_hash` fails

This means a file in the git tree has a sha256 that appears in `manifest.json`. This
is a copyright violation if it got that way. The test fails intentionally to block
the commit.

Remove the file from the repository and do not commit it.
