#!/bin/sh
# tools/build_drawfish.sh — rebuild bin/OS/darwin/Engines/drawfish/drawfish
#
# Drawfish is a Stockfish 7-era fork (stalemate = win) by Nathan Rugg.
# https://github.com/nmrugg/Drawfish
#
# Prerequisites: clang (Xcode command-line tools)
# Run from repo root.

set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/bin/OS/darwin/Engines/drawfish/drawfish"
TMPDIR="$(mktemp -d)"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

echo "==> Downloading Drawfish source (commit 74d10eb) …"
curl -fsSL --max-time 60 \
    'https://github.com/nmrugg/Drawfish/tarball/master' \
    -o "$TMPDIR/drawfish.tar.gz"
tar -xzf "$TMPDIR/drawfish.tar.gz" -C "$TMPDIR"
SRC="$TMPDIR/$(ls "$TMPDIR" | grep -v tar)/src"

# Patch the Makefile to accept 'arm64' in the arch sanity check.
# The check was written before Apple Silicon existed.
sed -i '' \
    's/test "$(arch)" = "ppc" || test "$(arch)" = "armv7"/test "$(arch)" = "ppc" || test "$(arch)" = "armv7" || test "$(arch)" = "arm64"/' \
    "$SRC/Makefile"

echo "==> Building Drawfish arm64 …"
NCPU=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)
make -C "$SRC" build ARCH=general-64 COMP=clang arch=arm64 -j"$NCPU"

echo "==> Installing to $OUT …"
cp "$SRC/drawfish" "$OUT"
chmod 755 "$OUT"

echo "==> Verifying …"
file "$OUT"
printf 'uci\nquit\n' | "$OUT" | grep -E 'id name|uciok'
printf 'New sha256: '
shasum -a 256 "$OUT" | cut -d' ' -f1
echo
echo "==> Update SOURCES.md sha256 with the value above if it changed."
