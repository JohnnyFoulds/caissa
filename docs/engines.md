# Engines

Caissa ships with **14 native Apple Silicon engines** that work out of the box — no Docker,
no Homebrew, no build tools needed after cloning.  An optional Docker bridge expands the roster
to ~105 engines.

---

## Native engines (no Docker required)

These binaries are committed in Git LFS under `bin/OS/darwin/Engines/` and run directly on
Apple Silicon.

| Engine | Version | Notes |
|---|---|---|
| Stockfish | 18 | NNUE nets beside the binary; ~2900 Elo |
| Lc0 | 0.32.1 | Neural network engine, Metal backend; `791556.pb.gz` net included |
| Maia-1100 … Maia-2200 (10 levels) | — | Human-like play; shares the Lc0 binary |
| irina | current | Compact, fast engine |
| Drawfish | 74d10eb | Stockfish derivative: stalemate counts as a win |

Provenance, build flags and sha256 for each binary:
[`bin/OS/darwin/Engines/SOURCES.md`](../bin/OS/darwin/Engines/SOURCES.md)

---

## Docker-bridged engines (optional)

When Docker Desktop is running, `OSEngines.py` also registers the ~91 Linux and Windows
engines from the upstream Lucas Chess R6 roster.  They are executed inside the
`lucas-engines` container via wrapper scripts under `bin/OS/darwin/Engines/`.

To generate the wrapper scripts for the first time:

```bash
# Docker Desktop must be running
tools/gen_darwin_engines.py
```

The script probes each engine through the bridge and writes a self-locating wrapper.  It is safe
to re-run after `git pull`; wrappers that already exist are skipped unless `--force` is passed.

When Docker is not running, `OSEngines.py` detects this in under 2 seconds and silently omits the
bridged set — only the 14 native engines are registered, and startup is not delayed.

---

## Rebuilding native engines from source

Each native engine has a build script in `tools/`:

| Engine | Build script |
|---|---|
| Stockfish | `tools/build_stockfish.sh` |
| Lc0 | `tools/build_lc0.sh` |
| Drawfish | `tools/build_drawfish.sh` |

Run from the repo root.  After building, update the sha256 in `SOURCES.md`.
