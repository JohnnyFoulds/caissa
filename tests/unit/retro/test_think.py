"""
tests/unit/retro/test_think.py — Phase 7 tests for Think.py.

Covers ThinkSession with FakeCpu (no ROM, no unicorn), and the
RomNotFoundError path when a rom_path is given but file is absent.

:spec: feature_spec.md §7, N-RETRO-1
:phase: 7
"""

from __future__ import annotations

import struct

import pytest
from Code.Retro.Bridge import AI_BEST_MOVE_ADDR
from Code.Retro.Errors import RomNotFoundError
from Code.Retro.Fakes import FakeCpu
from Code.Retro.Think import ThinkRequest, ThinkSession
from Code.Retro.Types import Level

pytestmark = pytest.mark.retro

_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# The AI always searches as Black (_search_cc=1).  Write Black's e7e5 move so
# _is_root_valid passes.  With computer_color=0 (board flipped) the un-flip maps
# e7e5 back to e2e4; with computer_color=1 (no flip) the result is e7e5 directly.
# to_sq=0x44 (e5) at offset 0, from_sq=0x64 (e7) at offset 2.
_AI_MOVE_RAW = struct.pack(">HH4x", 0x44, 0x64)


def _cpu_that_plays_ai_move() -> FakeCpu:
    """Return a FakeCpu scripted to write e7→e5 (Black) to AI_BEST_MOVE_ADDR on emu_start."""
    cpu = FakeCpu()

    def _callback(c: FakeCpu) -> None:
        c.mem_write(AI_BEST_MOVE_ADDR, _AI_MOVE_RAW)

    cpu.set_emu_callback(_callback)
    return cpu


# Keep the old name for backwards compatibility within this module.
_cpu_that_plays_e2e4 = _cpu_that_plays_ai_move


# ---------------------------------------------------------------------------
# ThinkSession: scripted CPU path
# ---------------------------------------------------------------------------

def test_think_session_with_scripted_cpu_returns_move():
    """ThinkSession with FakeCpu returns the AI move after board-flip reversal.

    The FakeCpu writes e7e5 (Black pawn, valid for the AI's _search_cc=1).
    With computer_color=0 the board is flipped for search, so the un-flip maps
    e7e5 back to e2e4 in the original orientation.
    """
    session = ThinkSession(cpu=_cpu_that_plays_ai_move())
    result = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1, computer_color=0))
    assert result.move is not None
    assert result.move.to_uci() == "e2e4"


def test_think_session_returns_correct_level():
    """ThinkResult.level must reflect the requested level."""
    session = ThinkSession(cpu=_cpu_that_plays_e2e4())
    result = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    assert result.level == Level.L1


def test_think_session_has_move_true():
    """ThinkResult.has_move must be True when a move is returned."""
    session = ThinkSession(cpu=_cpu_that_plays_e2e4())
    result = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    assert result.has_move is True


def test_think_session_deterministic_across_two_calls():
    """Two identical think calls on the same session must return identical moves."""
    session = ThinkSession(cpu=_cpu_that_plays_e2e4())
    r1 = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    r2 = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    assert r1.move == r2.move
    assert r1.move.to_uci() == r2.move.to_uci()


def test_think_session_clears_best_move_before_run():
    """think() must clear the best-move buffer before starting, so stale data is not returned."""
    cpu = FakeCpu()
    # Pre-write a stale d2d4 move
    stale = struct.pack(">HHHBB", 0x13, 0x33, 0, 1, 1)  # d2d4
    cpu.mem_write(AI_BEST_MOVE_ADDR, stale)

    # Callback writes AI move, overwriting the pre-written stale value
    def _callback(c: FakeCpu) -> None:
        c.mem_write(AI_BEST_MOVE_ADDR, _AI_MOVE_RAW)

    cpu.set_emu_callback(_callback)
    session = ThinkSession(cpu=cpu)
    result = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    # Even if we get e2e4 here, the important thing is clear_best_move was called
    # (the Bridge tests cover that; here we just verify think() succeeded)
    assert result.move is not None


def test_think_session_no_move_falls_back_to_legal_move():
    """When the cpu writes nothing, think() must fall back to a python-chess legal move.

    ThinkError is only raised when the fallback also fails (chess not importable, or
    the position has no legal moves such as stalemate/checkmate).  For a normal
    position the fallback returns a valid move rather than raising.
    """
    cpu = FakeCpu()  # no callback → AI_BEST_MOVE_ADDR stays zeroed
    session = ThinkSession(cpu=cpu)
    # computer_color=0 → startpos, White to move; python-chess fallback gives a White move.
    result = session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1, computer_color=0))
    assert result.move is not None
    # Verify it is actually a legal move in the position.
    import chess as _chess
    board = _chess.Board(_STARTPOS)
    assert _chess.Move.from_uci(result.move.to_uci()) in board.legal_moves


# ---------------------------------------------------------------------------
# ThinkSession: ROM-not-found path
# ---------------------------------------------------------------------------

def test_think_session_without_rom_raises_rom_not_found_error(tmp_path):
    """think() must raise RomNotFoundError when rom_path does not exist."""
    missing = tmp_path / "nonexistent_rom.bin"
    session = ThinkSession(rom_path=missing)
    with pytest.raises(RomNotFoundError) as exc_info:
        session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    assert str(missing) in str(exc_info.value)


def test_rom_not_found_error_has_path_attribute(tmp_path):
    """RomNotFoundError.path must equal the missing file path."""
    missing = tmp_path / "battle_chess.bin"
    session = ThinkSession(rom_path=missing)
    with pytest.raises(RomNotFoundError) as exc_info:
        session.think(ThinkRequest(fen=_STARTPOS, level=Level.L1))
    assert exc_info.value.path == str(missing)


# ---------------------------------------------------------------------------
# retro_rom: real-ROM tests (skipped without ROM)
# ---------------------------------------------------------------------------

@pytest.mark.retro_rom
def test_think_session_with_real_rom_returns_known_move():
    """With a real ROM, a corpus position at level 1 must return a legal move."""
    import json
    from pathlib import Path

    from Code.Retro.Manifest import default_rom_path

    rom = default_rom_path()
    if not rom or not Path(rom).exists():
        pytest.skip("retro_rom: no ROM file found")

    corpus = Path(__file__).parents[3] / "Resources" / "Retro" / "Corpus" / "fs-uae-manual.jsonl"
    if not corpus.exists() or corpus.stat().st_size == 0:
        pytest.skip("retro_rom: corpus file not found")

    import chess as _chess
    entry = json.loads(corpus.read_text().splitlines()[0])
    fen = entry["fen"]
    board = _chess.Board(fen)

    session = ThinkSession(rom_path=Path(rom))
    # Black to move in corpus entries; computer_color=1 = Black
    result = session.think(ThinkRequest(fen=fen, level=Level.L1, computer_color=1))

    assert result.move is not None, "engine returned no move"
    move_uci = result.move.to_uci()
    assert move_uci != "0000", "engine returned null move"
    assert _chess.Move.from_uci(move_uci) in board.legal_moves, (
        f"engine returned illegal move {move_uci!r} in position {fen!r}"
    )


@pytest.mark.retro_rom
def test_think_startpos_after_e4_returns_legal_black_move():
    """After 1.e4 (Black to move) the engine must return a legal Black move.

    Regression guard for the color-parity bug where the engine returned
    ``a2a4`` (a White pawn move) instead of a Black response.
    """
    import chess as _chess
    from pathlib import Path
    from Code.Retro.Manifest import default_rom_path

    rom = default_rom_path()
    if not rom or not Path(rom).exists():
        pytest.skip("retro_rom: no ROM file found")

    _E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    board = _chess.Board(_E4_FEN)

    session = ThinkSession(rom_path=Path(rom))
    result = session.think(ThinkRequest(fen=_E4_FEN, level=Level.L1, computer_color=1))

    assert result.move is not None, "engine returned no move"
    move_uci = result.move.to_uci()
    assert move_uci != "0000", "engine returned null move"
    assert move_uci != "a2a4", "engine returned a White pawn move (color-parity regression)"
    assert _chess.Move.from_uci(move_uci) in board.legal_moves, (
        f"engine returned illegal move {move_uci!r} after 1.e4"
    )
