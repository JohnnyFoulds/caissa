#!/bin/bash
# Update LucasChess to the latest upstream version.
# Run from the repo root or from anywhere — uses absolute paths.
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "=== Pulling latest upstream ==="
GIT_LFS_SKIP_SMUDGE=1 git pull --ff-only

echo "=== Rebuilding FasterCode + irina (arm64) ==="
bash tools/build_fastercode_macos.sh

echo "=== Re-enumerating bridged engines ==="
"$REPO/.venv/bin/python3" tools/gen_darwin_engines.py --force

echo "=== Done. ==="
