#!/bin/bash
# Double-clickable launcher (macOS .command file)
exec "$(dirname "$0")/tools/lucaschess" "$@"
