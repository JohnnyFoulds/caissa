#!/bin/bash
# Build FasterCode Cython extension + irina engine for macOS (Apple Silicon arm64)
# Run from the repo root: bash tools/build_fastercode_macos.sh
set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/bin/_fastercode/src"
IRINA="$SRC/irina"
OUT="$REPO/bin/OS/darwin"

PYTHON="$REPO/.venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
    echo "ERROR: venv not found at $REPO/.venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt Cython setuptools" >&2
    exit 1
fi

echo ""
echo ":: Building FasterCode for macOS (arm64)"
echo ""

# 1. Compile irina C sources into libirina.a
echo "  [1/4] Compiling irina C sources (arm64)..."
cd "$IRINA"
clang -Wall -O2 -fPIC -fno-strict-aliasing -arch arm64 \
    -c lc.c board.c data.c eval.c hash.c loop.c makemove.c movegen.c \
       movegen_piece_to.c search.c util.c pgn.c parser.c polyglot.c -DNDEBUG
ar rcs libirina.a lc.o board.o data.o eval.o hash.o loop.o makemove.o \
    movegen.o movegen_piece_to.o search.o util.o pgn.o parser.o polyglot.o
mv libirina.a "$SRC/"
rm -f *.o

# 2. Build FasterCode Cython extension
echo "  [2/4] Building FasterCode Cython extension..."
cd "$SRC"
cat Faster_Irina.pyx Faster_Polyglot.pyx > FasterCode.pyx

# Write a setuptools-based setup (upstream setup_linux.py still uses deprecated distutils)
cat > setup_macos.py << 'PYEOF'
from setuptools import setup, Extension
from Cython.Build import cythonize

setup(ext_modules=cythonize([
    Extension(
        "FasterCode",
        ["FasterCode.pyx"],
        libraries=["irina"],
        library_dirs=["."],
        extra_link_args=["-arch", "arm64"],
        extra_compile_args=["-arch", "arm64"],
    )
]))
PYEOF

ARCHFLAGS="-arch arm64" "$PYTHON" setup_macos.py build_ext --inplace -q
mkdir -p "$OUT"
cp FasterCode.cpython-*.so "$OUT/"
echo "  -> $(ls "$OUT"/FasterCode*.so)"

# 3. Compile standalone irina UCI engine
echo "  [3/4] Compiling irina UCI engine binary..."
cd "$IRINA"
# The repo's main.c is a test harness, not the UCI entry point.
# The real UCI entry point is begin() + loop() in loop.c.
# We also need stubs for test/perft symbols used only in test.c (not compiled here).
cat > _uci_main_mac.c << 'CEOF'
#include "defs.h"
#include "protos.h"
#include "globals.h"
#include <stdio.h>
/* Stubs for symbols referenced in loop.c/parser.c/pgn.c but defined in test.c */
void test(void) {}
void perft(int depth) { (void)depth; }
void perft_file(char *file) { (void)file; }
Bitmap calc_perft(char *fen, int depth) { (void)fen; (void)depth; return 0; }
/* Real UCI entry point */
int main(void) {
    begin();
    loop();
    return 0;
}
CEOF

mkdir -p "$OUT/Engines/irina"
clang -Wall -O2 -arch arm64 \
    -o "$OUT/Engines/irina/irina" \
    board.c data.c eval.c hash.c loop.c lc.c makemove.c movegen.c \
    movegen_piece.c movegen_piece_to.c search.c util.c pgn.c parser.c \
    polyglot.c _uci_main_mac.c -DNDEBUG
chmod +x "$OUT/Engines/irina/irina"
rm -f _uci_main_mac.c

# 4. Copy shared sqlite options database
echo "  [4/4] Copying uci_options.sqlite..."
cp "$REPO/bin/OS/linux/uci_options.sqlite" "$OUT/uci_options.sqlite"

# 5. Cleanup intermediate build artefacts
rm -f "$SRC/FasterCode.pyx" "$SRC/FasterCode.c" "$SRC/libirina.a" "$SRC/setup_macos.py"
rm -rf "$SRC/build"

echo ""
echo ":: Build complete."
echo "   $("$PYTHON" -c "import sys; sys.path.insert(0,'$OUT'); import FasterCode; print('FasterCode imported OK — bmi2()=' + str(FasterCode.bmi2()))")"
echo ""
