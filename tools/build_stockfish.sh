#!/bin/sh
# tools/build_stockfish.sh — rebuild bin/OS/darwin/Engines/stockfish/stockfish-18-arm64
#
# Uses the source Lucas Chess already ships: bin/OS/linux/Engines/stockfish/src.7z
# That Makefile already contains -DNNUE_EMBEDDING_OFF, matching the linux/win32 builds.
#
# Prerequisites: command-line tools (clang/g++), p7zip (brew install p7zip)
# Run from repo root.

set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC7Z="$REPO/bin/OS/linux/Engines/stockfish/src.7z"
OUT="$REPO/bin/OS/darwin/Engines/stockfish/stockfish-18-arm64"
TMPDIR="$(mktemp -d)"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

echo "==> Extracting source from src.7z …"
7za x "$SRC7Z" -o"$TMPDIR" -y >/dev/null

# The Makefile's `build` target depends on `net` (a download script that we skip
# by providing a no-op stub).
mkdir -p "$TMPDIR/scripts"
printf '#!/bin/sh\nexit 0\n' > "$TMPDIR/scripts/net.sh"
chmod +x "$TMPDIR/scripts/net.sh"

echo "==> Building Stockfish 18 arm64 (NNUE_EMBEDDING_OFF) …"
NCPU=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)
make -C "$TMPDIR/src" build ARCH=apple-silicon -j"$NCPU"

echo "==> Installing to $OUT …"
cp "$TMPDIR/src/stockfish" "$OUT"
chmod 755 "$OUT"

echo "==> Verifying …"
file "$OUT"
printf 'uci\nquit\n' | "$OUT" | grep -E 'id name|uciok'
printf 'New sha256: '
shasum -a 256 "$OUT" | cut -d' ' -f1
echo
echo "==> Update SOURCES.md sha256 with the value above if it changed."
