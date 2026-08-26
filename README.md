# Caissa

**A modern macOS chess GUI, forked from [Lucas Chess R6](https://github.com/lukasmonk/lucaschessR6)**

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue)
![Apple Silicon only](https://img.shields.io/badge/Apple_Silicon-M1%2B_only-orange)
![Python 3.13](https://img.shields.io/badge/Python-3.13-green)
![PySide6 / Qt6](https://img.shields.io/badge/PySide6-Qt6-41CD52)
![GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-lightgrey)
![Git LFS required](https://img.shields.io/badge/Git_LFS-required-red)

---

## Requirements

> **Apple Silicon (M1 or later) · macOS 14 Sonoma or later · `git-lfs`**

Intel Macs are not supported — the vendored native engines are built `arm64` only.
Windows and Linux users should use [upstream Lucas Chess R6](https://github.com/lukasmonk/lucaschessR6).

---

## Install

```bash
# 1. Install Git LFS (once per machine)
brew install git-lfs
git lfs install

# 2. Clone — do NOT use the GitHub "Download ZIP" button
#    (ZIP archives carry no LFS objects and macOS quarantines the result)
git clone https://github.com/JohnnyFoulds/caissa
cd caissa

# 3. Create the Python virtual environment
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Launch
./Caissa.command
```

That is all. No Homebrew chess engines, no build tools, no Docker — the native engines are
committed in LFS and are ready the moment the clone finishes.

---

## What you get out of the box

Fourteen native arm64 engines, playable immediately with no extra setup:

| Engine | Version | Notes |
|---|---|---|
| Stockfish | 18 | NNUE nets included beside the binary |
| Lc0 | 0.32.1 | Metal backend; `791556.pb.gz` net included |
| Maia | 1100 – 2200 (10 nets) | Human-like play at your Elo; shares the Lc0 binary |
| irina | current | Fast, lightweight |
| Drawfish | 74d10eb | Stockfish derivative: stalemate = win |

See [`bin/OS/darwin/Engines/SOURCES.md`](bin/OS/darwin/Engines/SOURCES.md) for exact versions,
build flags, and sha256 checksums.

---

## Optional: the Docker engine bridge

Docker unlocks ~91 additional Linux/Windows engines (the full upstream roster of 105 total):

```bash
# Install Docker Desktop, then:
tools/setup_darwin_engines.py   # generates the wrapper scripts once
./Caissa.command                # Docker container is pre-warmed automatically
```

Docker is genuinely optional — the app starts and plays normally without it.

---

## How Caissa differs from upstream Lucas Chess R6

- **Native Apple Silicon engines** — Stockfish, Lc0, Maia, irina and Drawfish committed in Git
  LFS; no Homebrew symlinks, no build tools required after cloning
- **Docker bridge is optional** — the app is fully playable with the 14 native engines alone
- **Auto-updater removed** — upstream's update mechanism targets Lucas Chess versioning and would
  corrupt a fork; see [Releases](https://github.com/JohnnyFoulds/caissa/releases) for updates
- **Modern macOS-first focus** — this fork targets Apple Silicon and macOS; Intel and
  Windows/Linux users should use [upstream](https://github.com/lukasmonk/lucaschessR6)

This is a modified work under GPL 3.0. The original Lucas Chess R6 is by
[Lucas Monge](https://github.com/lukasmonk/lucaschessR6).

---

## Credits and licence

- **Lucas Chess R6** — © Lucas Monge, GPL 3.0 — [github.com/lukasmonk/lucaschessR6](https://github.com/lukasmonk/lucaschessR6)
- **Stockfish** — Tord Romstad, Marco Costalba, Joona Kiiski et al., GPL 3.0
- **Lc0** — Gary Linscott, Folkert Huizinga et al., GPL 3.0
- **Maia** — Reid McIlroy-Young et al., MIT
- **irina** — upstream authors, GPL 3.0
- **Drawfish** — Nathan Rugg, GPL 3.0

All source pointers and licence texts are in [`bin/OS/darwin/Engines/SOURCES.md`](bin/OS/darwin/Engines/SOURCES.md).
This repository is licensed under [GPL 3.0](LICENSE).

---

## Developer notes

```bash
# Install dependencies
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Run directly
cd bin && ../.venv/bin/python3 LucasR.py
```

- **macOS platform entry point**: `bin/OS/darwin/OSEngines.py`
- **Native engine build scripts**: `tools/build_stockfish.sh`, `tools/build_lc0.sh`,
  `tools/build_drawfish.sh`
- **Engine provenance**: `bin/OS/darwin/Engines/SOURCES.md`
- **Docker wrapper generator**: `tools/gen_darwin_engines.py`

The full implementation plan lives at `.claude/plans/i-want-you-to-lazy-truffle.md`.
