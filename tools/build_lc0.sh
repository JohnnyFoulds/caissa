#!/bin/sh
# tools/build_lc0.sh — rebuild bin/OS/darwin/Engines/lc0/Lc0-0.32.1
#
# Lc0 publishes no macOS artifacts, so this repo vendors a binary built on the
# developer's machine.  Use this script to regenerate it from source when upgrading.
#
# Prerequisites: meson, ninja, python3 (brew install meson ninja)
#                Xcode command-line tools
# Run from repo root.
#
# The build targets Metal (Apple GPU) and the standard backend.
# Adjust MESON_OPTS below to change backends.

set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TAG="v0.32.1"
OUT="$REPO/bin/OS/darwin/Engines/lc0/Lc0-0.32.1"
TMPDIR="$(mktemp -d)"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

# Check prerequisites
for cmd in meson ninja; do
    command -v "$cmd" >/dev/null || {
        echo "ERROR: $cmd not found.  brew install meson ninja"
        exit 1
    }
done

echo "==> Cloning lc0 $TAG …"
git clone --depth 1 --branch "$TAG" \
    https://github.com/LeelaChessZero/lc0.git "$TMPDIR/lc0"

echo "==> Fetching submodules …"
git -C "$TMPDIR/lc0" submodule update --init --recursive

echo "==> Configuring (Metal + default backends) …"
cd "$TMPDIR/lc0"
MESON_OPTS="--buildtype=release -Dgtest=false -Dopenblas=false"
CC=clang CXX=clang++ meson setup build $MESON_OPTS
meson compile -C build

echo "==> Installing to $OUT …"
# The built binary is 'lc0' in the build directory
cp build/lc0 "$OUT"
chmod 755 "$OUT"

echo "==> Verifying …"
file "$OUT"
printf 'uci\nquit\n' | "$OUT" 2>/dev/null | grep -E 'id name|uciok'
printf 'New sha256: '
shasum -a 256 "$OUT" | cut -d' ' -f1
echo
echo "==> Update SOURCES.md sha256 with the value above."
echo "==> Also rename the file if the version changed (e.g. Lc0-0.33.0),"
echo "    update OSEngines.py accordingly, and re-commit."
