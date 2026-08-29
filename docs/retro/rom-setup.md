# ROM Setup

Both the Amiga and DOS binaries are committed to the repository at
`Resources/Retro/`. The engine finds them automatically — no configuration
is needed for standard use.

---

## Bundled files

| File | Type | SHA256 (first 16 chars) |
|---|---|---|
| `Resources/Retro/BattleChess.amiga` | Amiga 68000 executable (Dragon Inc crack, 1988) | `d4fc6137d7addf97` |
| `Resources/Retro/BattleChess.dos` | DOS x86 executable (1.2 MB floppy, 1988-12-10) | `c32d4f6bc732b67e` |
| `Resources/Retro/ChessStuff` | Amiga game data (animations + opening book) | `3917b15831cc6198` |

`Code.Retro.Manifest.default_rom_path()` resolves the Amiga binary automatically.
The engine uses it without any environment variable or GUI setting.

### ChessStuff — the data companion

`ChessStuff` is the Amiga game's data file, loaded at startup via AmigaDOS
`Open("ChessStuff", ...)`. It contains two things:

1. **Animation data** — all piece-capture battle animations (the majority of the 706 KB file).
2. **Opening book** — the built-in opening theory library referenced in the manual.

The Dragon Inc crack (our `BattleChess.amiga`) stripped this file from the floppy;
the bundled copy comes from the WHDLoad v1.1 install (2006, verified against the
retail disk content). The opening book data is embedded somewhere within
`ChessStuff` at an offset not yet identified by recon (tracked in
`docs/retro/reverse-engineering.md`).

---

## Using a different copy

If you want to use your own copy of the binary (e.g., ripped from a Steam/GOG install):

**Option 1 — environment variable:**

```bash
export CAISSA_RETRO_ROM=/path/to/your/BattleChess
tools/caissa-retro
```

**Option 2 — UCI setoption:**

```
setoption name EmuRomPath value /path/to/your/BattleChess
```

The engine verifies the SHA256 of whatever binary you point at. If it matches an
entry in `Resources/Retro/manifest.json`, it loads. If it does not match, it refuses
with an error and the SHA256 it found, so you can report the new digest.

---

## Verifying a binary

```bash
python3 -c "
import sys; sys.path.insert(0,'bin')
from Code.Retro.Manifest import sha256_file, load
digest = sha256_file('/path/to/BattleChess')
print('sha256:', digest)
entries = load()
match = next((e for e in entries if e['sha256'] == digest), None)
print('manifest:', match['label'] if match else 'NOT IN MANIFEST')
"
```

---

## If the binary is packed

Some copies of Battle Chess use PowerPacker or Imploder compression on the Amiga.
`Rom.detect_packer()` checks for the common signatures. If packing is detected,
the error message names the packer and points to suitable unpacking tools
(`ppami`, `imploder`, or a UAE-based extractor).

The bundled Amiga binary and the DOS floppy binary are both unpacked.
