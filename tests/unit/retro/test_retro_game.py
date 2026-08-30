"""
tests/unit/retro/test_retro_game.py — End-to-end game tests for the Retro Engine.

Two test functions:
- ``test_engine_plays_black``: human plays White (first legal move), engine plays Black.
- ``test_engine_plays_both_sides``: engine plays every move (White and Black), verifying
  both sides never return ``bestmove 0000``.

Each game continues until checkmate, stalemate, 50-move rule, or a half-move cap.

Requires ``Resources/Retro/BattleChess.amiga``; skips otherwise.

:spec: N-RETRO Gate-E real-execution requirement
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import chess
import pytest

pytestmark = pytest.mark.retro_rom

_REPO_ROOT = Path(__file__).parents[3]
_CAISSA_RETRO = _REPO_ROOT / "tools" / "caissa-retro"
_ROM_PATH = _REPO_ROOT / "Resources" / "Retro" / "BattleChess.amiga"

_MOVE_TIMEOUT_S = 120
_MAX_HALFMOVES = 60


def _send(proc: subprocess.Popen, line: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def _read_until(proc: subprocess.Popen, prefix: str, timeout: float = 30.0) -> str:
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped
    raise TimeoutError(f"timed out waiting for '{prefix}' (timeout={timeout}s)")


def _start_engine() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-u", str(_CAISSA_RETRO)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        cwd=str(_REPO_ROOT),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    _send(proc, "uci")
    _read_until(proc, "uciok", timeout=10)
    _send(proc, "isready")
    _read_until(proc, "readyok", timeout=10)
    return proc


def _engine_move(proc: subprocess.Popen, board: chess.Board, halfmove: int) -> str:
    """Ask the engine for a move from *board*.  Return the UCI string.  Fail on 0000."""
    fen = board.fen()
    _send(proc, f"position fen {fen}")
    _send(proc, "go")
    try:
        bm_line = _read_until(proc, "bestmove", timeout=_MOVE_TIMEOUT_S)
    except TimeoutError:
        pytest.fail(f"Engine did not respond within {_MOVE_TIMEOUT_S}s at half-move {halfmove}")

    parts = bm_line.split()
    assert len(parts) >= 2, f"malformed bestmove line: {bm_line!r}"
    uci = parts[1]
    assert uci != "0000", (
        f"Engine returned bestmove 0000 at half-move {halfmove} "
        f"(side={'W' if board.turn == chess.WHITE else 'B'}, FEN={fen})"
    )
    return uci


def _apply_engine_move(board: chess.Board, uci: str, halfmove: int) -> None:
    """Push *uci* onto *board*, tolerating missing promotion suffix."""
    try:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            move = chess.Move.from_uci(uci[:4])
        if move not in board.legal_moves:
            pytest.fail(
                f"Engine move {uci!r} is illegal at half-move {halfmove}. "
                f"Legal: {sorted(m.uci() for m in board.legal_moves)}"
            )
        board.push(move)
    except (chess.InvalidMoveError, ValueError) as exc:
        pytest.fail(f"Unparseable UCI move {uci!r} at half-move {halfmove}: {exc}")


@pytest.fixture(autouse=True)
def _require_rom():
    if not _ROM_PATH.exists():
        pytest.skip(f"ROM not found: {_ROM_PATH}")
    if not _CAISSA_RETRO.exists():
        pytest.skip(f"tools/caissa-retro not found: {_CAISSA_RETRO}")


# ---------------------------------------------------------------------------


def test_engine_plays_black():
    """Engine plays Black; White uses the first legal pawn move each turn.

    Asserts:
    - Engine never returns bestmove 0000
    - All engine moves are legal
    - At least 10 engine responses obtained
    """
    proc = _start_engine()
    try:
        board = chess.Board()
        engine_moves: list[str] = []

        for halfmove in range(1, _MAX_HALFMOVES + 1):
            if board.is_game_over():
                print(f"  Game over at half-move {halfmove}: {board.result()}")
                break

            if board.turn == chess.WHITE:
                white_move = next(
                    (m for m in board.legal_moves
                     if board.piece_at(m.from_square) and
                     board.piece_at(m.from_square).piece_type == chess.PAWN),
                    next(iter(board.legal_moves)),
                )
                board.push(white_move)
                print(f"  half-move {halfmove}: White plays {white_move.uci()}")
            else:
                uci = _engine_move(proc, board, halfmove)
                _apply_engine_move(board, uci, halfmove)
                engine_moves.append(uci)
                print(f"  half-move {halfmove}: Engine (B) plays {uci}")

        _send(proc, "quit")
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\nEngine (Black) moves: {engine_moves}")
    assert len(engine_moves) >= 10, (
        f"Expected ≥10 engine moves, got {len(engine_moves)}"
    )


def test_engine_plays_both_sides():
    """Engine plays every half-move (both White and Black), verifying both sides work.

    Asserts:
    - Engine never returns bestmove 0000 for either color
    - All engine moves are legal
    - At least 20 half-moves completed (10 per side)
    """
    proc = _start_engine()
    try:
        board = chess.Board()
        all_moves: list[str] = []

        for halfmove in range(1, _MAX_HALFMOVES + 1):
            if board.is_game_over():
                print(f"  Game over at half-move {halfmove}: {board.result()}")
                break

            side = "W" if board.turn == chess.WHITE else "B"
            uci = _engine_move(proc, board, halfmove)
            _apply_engine_move(board, uci, halfmove)
            all_moves.append(f"{side}:{uci}")
            print(f"  half-move {halfmove}: Engine ({side}) plays {uci}")

        _send(proc, "quit")
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\nAll moves: {' '.join(all_moves)}")
    white_moves = [m for m in all_moves if m.startswith("W:")]
    black_moves = [m for m in all_moves if m.startswith("B:")]
    print(f"White: {len(white_moves)} moves, Black: {len(black_moves)} moves")
    assert len(all_moves) >= 20, (
        f"Expected ≥20 half-moves, got {len(all_moves)}"
    )
    assert len(white_moves) >= 10, (
        f"Expected ≥10 White engine moves, got {len(white_moves)}"
    )
    assert len(black_moves) >= 10, (
        f"Expected ≥10 Black engine moves, got {len(black_moves)}"
    )
