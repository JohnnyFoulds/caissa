#!/usr/bin/env python3
"""
tools/retro-recon/record_corpus.py — Interactive Phase 1-A ground truth recorder.

EXPERIMENTAL — Phase 1 spike. Deleted in Phase 10.

Usage:
    python3 tools/retro-recon/record_corpus.py \\
        --output Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl \\
        --target amiga

Run this while playing Battle Chess in FS-UAE. For each position you want to
record: set up the position in FS-UAE, let the engine think, observe the move,
then enter it here.

The script appends one JSONL record per entry to the output file.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


EXAMPLE_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def get_input(prompt: str, default: str = "") -> str:
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default


def validate_uci_move(move: str) -> bool:
    if len(move) not in (4, 5):
        return False
    files = "abcdefgh"
    ranks = "12345678"
    return (
        move[0] in files and move[1] in ranks
        and move[2] in files and move[3] in ranks
    )


def record_corpus(output_path: Path, target: str) -> None:
    if output_path.exists():
        existing = [l for l in output_path.read_text().splitlines() if l.strip()]
        print(f"Output file exists with {len(existing)} entries. Appending.")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Creating new corpus file: {output_path}")

    print()
    print("=" * 60)
    print("Battle Chess Ground Truth Recorder — Phase 1-A")
    print("=" * 60)
    print()
    print("Instructions:")
    print("  1. Run Battle Chess in FS-UAE (or DOSBox for DOS target)")
    print("  2. Set up the position by playing through the moves")
    print("  3. Set the difficulty level to what you want to record")
    print("  4. Let the engine think and observe the move it plays")
    print("  5. Enter the data below")
    print("  6. Type 'done' at the FEN prompt to finish")
    print()

    entries_added = 0

    while True:
        print(f"\n--- Entry {entries_added + 1} ---")

        fen = get_input("FEN (or 'done' to quit)", EXAMPLE_FEN)
        if fen.lower() in ("done", "quit", "exit", ""):
            break

        level = get_input("Difficulty level (1–8 as shown in the game)", "3")
        try:
            level_int = int(level)
        except ValueError:
            print("  ERROR: level must be an integer")
            continue

        move = get_input("Move the engine played (UCI format, e.g. e2e4)")
        if not validate_uci_move(move):
            print(f"  WARNING: '{move}' does not look like a valid UCI move (expected e.g. 'e2e4')")
            confirm = get_input("  Continue anyway? (y/n)", "n")
            if confirm.lower() != "y":
                continue

        observed_seconds = get_input("Observed think time in seconds (approx.)", "unknown")
        try:
            observed_seconds_val = float(observed_seconds)
        except ValueError:
            observed_seconds_val = None

        notes = get_input("Notes (optional, e.g. 'start position', 'after 1.e4 e5')", "")

        entry = {
            "fen": fen,
            "target": target,
            "level": level_int,
            "move": move.lower(),
            "observed_seconds": observed_seconds_val,
            "instr": None,
            "source": f"{target}-manual",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        }

        # Append to file immediately
        with output_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

        entries_added += 1
        print(f"  Saved: {fen[:40]}... level={level_int} move={move}")

    print(f"\nDone. Added {entries_added} entries to {output_path}")
    print(f"Total entries in file: {sum(1 for _ in output_path.open())}")

    # Print a summary
    print()
    print("Corpus summary:")
    entries = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    by_level: dict[int, list[str]] = {}
    for e in entries:
        by_level.setdefault(e["level"], []).append(e["move"])
    for lvl in sorted(by_level):
        print(f"  Level {lvl}: {len(by_level[lvl])} entries — {by_level[lvl]}")


def main():
    parser = argparse.ArgumentParser(description="Record Battle Chess ground truth corpus entries")
    parser.add_argument("--output", type=Path,
                        default=Path("Resources/Retro/Corpus/groundtruth-amiga-manual.jsonl"))
    parser.add_argument("--target", default="amiga", choices=["amiga", "dos"])
    args = parser.parse_args()
    record_corpus(args.output, args.target)


if __name__ == "__main__":
    main()
