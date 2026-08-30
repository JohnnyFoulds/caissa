#!/usr/bin/env /opt/homebrew/bin/python3.14
"""
Record ground-truth corpus from Battle Chess (Amiga) via FS-UAE.
Runs multiple games from different openings, recording AI (Black) responses.
Stops each game immediately on first illegal move detection (strict tracker sync).

Output: Resources/Retro/Corpus/fs-uae-manual.jsonl  (appended)
Format: {"fen": "...", "expected_uci": "...", "side": "black", "move_num": N,
         "game_id": N}
"""

import sys
import types
import json
import time
import logging
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "bin"))
_code_pkg = types.ModuleType("Code")
_code_pkg.__path__ = [str(_REPO / "bin" / "Code")]
_code_pkg.__package__ = "Code"
sys.modules["Code"] = _code_pkg

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

import chess
from Code.Amiga.Driver import FsUaeProcess, FsUaeDriver
from Code.Amiga.Activities import (
    AmigaRunner, StartNewGame, SelectTwoDBoard,
    PlayMove, WaitForComputerReply, ExtractComputerMove,
)

CONFIG = Path("/Users/johannes/Documents/FS-UAE/Configurations/BattleChess-ADF.fs-uae")
CORPUS = _REPO / "Resources/Retro/Corpus/fs-uae-manual.jsonl"

# Opening lines: (name, list-of-White-UCI-moves)
# No castling — avoids rook-animation detection bug.
OPENINGS = [
    ("e4_italian",   ["e2e4", "g1f3", "f1c4", "d2d3", "b1c3", "c1g5", "a2a3", "h2h3",
                      "d1e2", "e1d1"]),
    ("e4_4knights",  ["e2e4", "g1f3", "b1c3", "d2d3", "f1e2", "e1f1", "a2a3", "h2h3",
                      "g3h1", "d1e1"]),
    ("d4_london",    ["d2d4", "g1f3", "c1f4", "e2e3", "h2h3", "f1d3", "b1d2", "c2c3",
                      "a2a3", "d1c2"]),
    ("c4_english",   ["c2c4", "g1f3", "b1c3", "e2e3", "f1e2", "e1f1", "a2a3", "d2d3",
                      "d1c2", "h2h3"]),
    ("e4_king_ind",  ["e2e4", "d2d3", "b1c3", "g1f3", "f1e2", "e1f1", "a2a3", "h2h3",
                      "c1e3", "d1d2"]),
]


def pick_white_move(board: chess.Board, moves: list[str], move_idx: int) -> str | None:
    """Return the preferred White move if legal, else first legal move, else None."""
    if 0 <= move_idx < len(moves):
        candidate = moves[move_idx]
        try:
            m = chess.Move.from_uci(candidate)
            if m in board.legal_moves:
                return candidate
        except Exception:
            pass
    # Fallback to first legal move
    for m in board.legal_moves:
        return m.uci()
    return None


def _correct_illegal_move(board: chess.Board, detected_uci: str) -> str | None:
    """Try to find a legal move that's close to the detected (illegal) one.

    When piece-animation mid-capture causes sprite bleed onto an adjacent square,
    the detected TO is off by 1-2 squares.  Look for a legal move FROM the same
    square whose TO is nearest (Euclidean in file/rank space) to the detected TO.
    """
    try:
        detected = chess.Move.from_uci(detected_uci)
    except Exception:
        return None
    from_sq = detected.from_square
    to_sq = detected.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)

    candidates = [m for m in board.legal_moves if m.from_square == from_sq]
    if not candidates:
        # Also try by TO square (piece arrived, FROM is wrong)
        candidates = [m for m in board.legal_moves if m.to_square == to_sq]
    if not candidates:
        return None

    def dist(m: chess.Move) -> float:
        f = chess.square_file(m.to_square) - to_file
        r = chess.square_rank(m.to_square) - to_rank
        return (f * f + r * r) ** 0.5

    best = min(candidates, key=dist)
    return best.uci()


def record_game(driver, runner, game_id: int, opening_name: str,
                white_moves: list[str], max_moves: int = 10) -> list[dict]:
    """Record one game; stop on first illegal AI move."""
    board = chess.Board()
    entries = []
    ctx = {}

    for move_idx in range(max_moves):
        move_num = move_idx + 1
        print(f"  Move {move_num}/{max_moves}...", end=" ", flush=True)

        our_uci = pick_white_move(board, white_moves, move_idx)
        if not our_uci:
            print("no legal move — stopping")
            break

        from_sq = our_uci[:2]
        to_sq = our_uci[2:4]

        board.push(chess.Move.from_uci(our_uci))
        fen_for_ai = board.fen()

        ctx.pop("computer_move", None)
        ctx.pop("after_our_move", None)
        ctx.pop("pre_move_img", None)

        try:
            runner.run(driver, [
                PlayMove(from_sq, to_sq),
                WaitForComputerReply(),
                ExtractComputerMove(),
            ], ctx=ctx)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            break

        ai_uci = ctx.get("computer_move")
        if not ai_uci:
            print("no AI move — stopping")
            break

        # Validate — attempt legal-move correction before stopping
        try:
            ai_move = chess.Move.from_uci(ai_uci)
            if ai_move not in board.legal_moves:
                corrected = _correct_illegal_move(board, ai_uci)
                if corrected:
                    print(f"(corrected {ai_uci}→{corrected}) ", end="")
                    ai_uci = corrected
                    ai_move = chess.Move.from_uci(corrected)
                else:
                    print(f"illegal ({ai_uci}), no correction — stopping")
                    break
        except Exception as e:
            print(f"invalid UCI {ai_uci!r}: {e} — stopping")
            break

        board.push(ai_move)
        entry = {
            "fen": fen_for_ai,
            "expected_uci": ai_uci,
            "side": "black",
            "move_num": move_num,
            "game_id": game_id,
            "opening": opening_name,
        }
        entries.append(entry)
        print(f"AI={ai_uci} ✓")
        time.sleep(0.8)

    return entries


def main():
    process = FsUaeProcess(CONFIG)
    driver = FsUaeDriver(process)
    driver.wake_sdl2()
    runner = AmigaRunner(save_dir="/tmp")

    CORPUS.parent.mkdir(parents=True, exist_ok=True)

    # Load existing unique FENs to avoid duplicates
    existing = []
    existing_fens: set[str] = set()
    if CORPUS.exists():
        with open(CORPUS) as f:
            for line in f:
                line = line.strip()
                if line:
                    e = json.loads(line)
                    if e["fen"] not in existing_fens:
                        existing.append(e)
                        existing_fens.add(e["fen"])
    print(f"Existing unique corpus entries: {len(existing)}")
    print(f"Target: 25+ unique entries\n")

    # Ensure 2D board mode — game starts in 3D by default after a fresh launch.
    print("Switching to 2D board mode...")
    runner.run(driver, [SelectTwoDBoard()], ctx={})
    time.sleep(1.0)
    print("2D mode active.\n")

    all_new = []
    new_fens: set[str] = set()
    for game_id, (opening_name, white_moves) in enumerate(OPENINGS, start=1):
        unique_so_far = len(existing) + len(all_new)
        if unique_so_far >= 25:
            print(f"Reached {unique_so_far} unique entries — stopping early.")
            break

        print(f"\n=== Game {game_id}: {opening_name} ===")
        print(f"  Starting new game...")
        ctx_ng = {}
        runner.run(driver, [StartNewGame()], ctx=ctx_ng)
        # Off-board click clears any lingering piece selection and parks the cursor.
        # Also ensures SDL2 mouse capture is active in the correct mode.
        time.sleep(1.5)
        driver.click(50, 50)
        time.sleep(3.0)

        entries = record_game(driver, runner, game_id, opening_name,
                               white_moves, max_moves=10)
        # De-duplicate by FEN
        for e in entries:
            if e["fen"] not in existing_fens and e["fen"] not in new_fens:
                all_new.append(e)
                new_fens.add(e["fen"])
        print(f"  Game {game_id}: {len(entries)} raw entries, "
              f"{len(all_new)} unique new total")

    # Rewrite corpus with existing unique + new unique entries
    all_entries = existing + all_new
    if all_new:
        with open(CORPUS, "w") as f:
            for entry in all_entries:
                f.write(json.dumps(entry) + "\n")
        print(f"\n✓ Corpus now has {len(all_entries)} unique entries "
              f"(added {len(all_new)} new)")
        for e in all_new:
            print(f"  game {e['game_id']} move {e['move_num']:2d}: "
                  f"{e['expected_uci']}  ({e['opening']})")
    else:
        print(f"\nNo new entries recorded. Corpus has {len(existing)} unique entries.")


if __name__ == "__main__":
    main()
