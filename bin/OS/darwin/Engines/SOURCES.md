# darwin/Engines — Native arm64 Binary Provenance

All four native arm64 binaries are committed in Git LFS.  Each binary is
ad-hoc linker-signed (`flags=0x20002`) and depends only on system / Apple
frameworks — no Homebrew dylibs, no `LC_RPATH`.

Rebuild instructions are in `tools/build_*.sh` at the repo root.

---

## Stockfish 18

| field  | value |
|--------|-------|
| upstream | https://github.com/official-stockfish/Stockfish |
| tag | sf_18 |
| source | `bin/OS/linux/Engines/stockfish/src.7z` (Lucas Chess distribution, already in repo) |
| build flags | `ARCH=apple-silicon COMP=gcc` (Makefile already has `-DNNUE_EMBEDDING_OFF`) |
| sha256 | `d2bf39df37b165f7222513d3a9720620cfa78243c749bdeb7737aaacfbd3febf` |
| size | ~634 KB |
| nets | `nn-c288c895ea92.nnue` (104 MB, big) · `nn-37f18f62d772.nnue` (3.4 MB, small) — shared LFS objects with `bin/OS/linux/` and `bin/OS/win32/`, zero additional storage |
| GPL | `Copying.txt` and `AUTHORS` in this folder; source in `src.7z` |

---

## Lc0 v0.32.1

| field  | value |
|--------|-------|
| upstream | https://github.com/LeelaChessZero/lc0 |
| tag | v0.32.1 |
| source | built by Homebrew formula; no official macOS release artifact exists |
| build flags | standard Homebrew meson/ninja build with Metal backend enabled |
| sha256 | `5e3005ed5cdb00cbaf6c8086973bebc2acb67202a5f22ce3c8e82e173eb5ce82` |
| size | ~1.7 MB |
| rebuild | `tools/build_lc0.sh` — meson/ninja source build |
| note | `Lc0-0.32.1` (correct version); the old `Lc0-0.32.0` name was from a Homebrew symlink that resolved to 0.32.1 |
| GPL | https://github.com/LeelaChessZero/lc0/blob/master/COPYING |

---

## Drawfish (Stockfish fork — stalemate-is-a-win variant)

| field  | value |
|--------|-------|
| upstream | https://github.com/nmrugg/Drawfish |
| commit | 74d10eb (master, 2016-era Stockfish 7 fork) |
| source | downloaded at build time by `tools/build_drawfish.sh` |
| build flags | `ARCH=general-64 COMP=clang arch=arm64` (Makefile patched to accept `arm64` in arch sanity check) |
| sha256 | `5f97c1cee9315d282ba6a4c58e770dc4f7ce2cfd20a7949b9742e4b69259343c` |
| size | ~335 KB |
| no nets | pre-NNUE engine; no external net files needed |
| GPL | https://github.com/nmrugg/Drawfish/blob/master/Copying.txt |

---

## irina

| field  | value |
|--------|-------|
| upstream | https://github.com/lukasmonk/lucaschessR6 (compiled from Lucas Chess source) |
| sha256 | `bc03e18499c669b6a7b7d61796fddf689784e489e3d07b5f3b1cdf1e6abc230c` |
| size | ~92 KB |
| note | already a real arm64 binary in the original port; not a Homebrew dependency |
| GPL | via Lucas Chess R6 |
