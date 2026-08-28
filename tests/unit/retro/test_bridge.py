"""
tests/unit/retro/test_bridge.py — Phase 6 tests for Bridge.py.

Covers FEN parsing utilities, 0x88 square helpers, and Bridge struct
write/read using FakeCpu (no ROM, no unicorn).

:spec: feature_spec.md §6, N-RETRO-1
:phase: 6
"""

from __future__ import annotations

import struct

import pytest
from Code.Retro.Bridge import (
    AI_BEST_MOVE_ADDR,
    PIECE_COUNTER_ADDR,
    PIECE_ENTRY_SIZE,
    PIECE_TABLE_ADDR,
    PLAYER1_COLOR_ADDR,
    PLAYER2_COLOR_ADDR,
    PLAYER_TYPE_BASE,
    Bridge,
    alg_to_sq88,
    parse_fen,
    parse_piece_placement,
    sq88,
    sq88_to_alg,
    sq88_to_file_rank,
)
from Code.Retro.Errors import BridgeError
from Code.Retro.Fakes import FakeCpu

pytestmark = pytest.mark.retro

_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# ---------------------------------------------------------------------------
# sq88 helpers
# ---------------------------------------------------------------------------

def test_sq88_e2():
    """sq88(4, 1) must equal 0x14 (e2)."""
    assert sq88(4, 1) == 0x14


def test_sq88_a1():
    """sq88(0, 0) must equal 0x00 (a1)."""
    assert sq88(0, 0) == 0x00


def test_sq88_h8():
    """sq88(7, 7) must equal 0x77 (h8)."""
    assert sq88(7, 7) == 0x77


def test_sq88_file_rank_roundtrip():
    """sq88_to_file_rank(sq88(f, r)) must equal (f, r) for all valid squares."""
    for f in range(8):
        for r in range(8):
            assert sq88_to_file_rank(sq88(f, r)) == (f, r)


def test_sq88_to_alg_e2():
    """sq88_to_alg(0x14) must return 'e2'."""
    assert sq88_to_alg(0x14) == "e2"


def test_alg_to_sq88_e4():
    """alg_to_sq88('e4') must return 0x34."""
    assert alg_to_sq88("e4") == 0x34


def test_alg_to_sq88_invalid_raises():
    """alg_to_sq88 with an out-of-range square must raise BridgeError."""
    with pytest.raises(BridgeError):
        alg_to_sq88("z9")


# ---------------------------------------------------------------------------
# FEN parse: piece placement
# ---------------------------------------------------------------------------

def test_parse_piece_placement_startpos():
    """Starting position must yield 32 pieces with kings at e1 and e8."""
    pieces = parse_piece_placement("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")
    assert len(pieces) == 32
    # White king at e1: file=4, rank=0 → sq=0x04; color=0, piece=6
    assert (sq88(4, 0), 0, 6) in pieces
    # Black king at e8: file=4, rank=7 → sq=0x74; color=1, piece=6
    assert (sq88(4, 7), 1, 6) in pieces


def test_parse_piece_placement_empty_ranks():
    """Eight empty ranks must return an empty piece list."""
    pieces = parse_piece_placement("8/8/8/8/8/8/8/8")
    assert pieces == []


# ---------------------------------------------------------------------------
# FEN parse: full FEN
# ---------------------------------------------------------------------------

def test_parse_fen_startpos_side_to_move():
    """Starting position FEN must have side_to_move=0 (White)."""
    board = parse_fen(_STARTPOS)
    assert board["side_to_move"] == 0


def test_parse_fen_black_to_move():
    """FEN with 'b' to move must have side_to_move=1."""
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    board = parse_fen(fen)
    assert board["side_to_move"] == 1


# ---------------------------------------------------------------------------
# Bridge: struct write
# ---------------------------------------------------------------------------

def _make_cpu() -> FakeCpu:
    return FakeCpu()


def test_bridge_write_position_startpos():
    """write_position must set piece_counter=-1 and player colors for startpos."""
    cpu = _make_cpu()
    Bridge(cpu).write_position(_STARTPOS)

    # piece_counter should be 0xFFFF (= -1 as unsigned word)
    raw_ctr = cpu.mem_read(PIECE_COUNTER_ADDR, 2)
    assert struct.unpack(">H", raw_ctr)[0] == 0xFFFF

    # player1_color = 0 (White to move)
    raw_p1 = cpu.mem_read(PLAYER1_COLOR_ADDR, 2)
    assert struct.unpack(">H", raw_p1)[0] == 0

    # player2_color = 1 (Black)
    raw_p2 = cpu.mem_read(PLAYER2_COLOR_ADDR, 2)
    assert struct.unpack(">H", raw_p2)[0] == 1


def test_bridge_write_piece_entries_present():
    """First piece entry must be non-zero after write_position."""
    cpu = _make_cpu()
    Bridge(cpu).write_position(_STARTPOS)
    first = cpu.mem_read(PIECE_TABLE_ADDR, PIECE_ENTRY_SIZE)
    assert any(first)


def test_bridge_write_32_pieces():
    """write_position(startpos) must write exactly 32 non-zero piece entries."""
    cpu = _make_cpu()
    b = Bridge(cpu)
    b.write_position(_STARTPOS)
    entries = b.read_piece_entries()
    assert len(entries) == 32


# ---------------------------------------------------------------------------
# Bridge: read best move
# ---------------------------------------------------------------------------

def test_bridge_read_best_move_empty():
    """read_best_move must return None when the buffer is all-zero."""
    cpu = _make_cpu()
    assert Bridge(cpu).read_best_move() is None


def test_bridge_read_best_move_valid():
    """read_best_move must return the correct MoveSpec for a written move."""
    cpu = _make_cpu()
    # Write e2e4: from=0x14, to=0x34, flags=0, piece=1 (pawn), legal=1
    raw = struct.pack(">HHHBB", 0x14, 0x34, 0, 1, 1)
    cpu.mem_write(AI_BEST_MOVE_ADDR, raw)
    move = Bridge(cpu).read_best_move()
    assert move is not None
    assert move.from_sq == 0x14
    assert move.to_sq == 0x34
    assert move.piece == 1


# ---------------------------------------------------------------------------
# Bridge: round-trip
# ---------------------------------------------------------------------------

def test_bridge_fen_round_trip():
    """write_position + read_piece_entries must reproduce 32 correctly-typed pieces."""
    cpu = _make_cpu()
    b = Bridge(cpu)
    b.write_position(_STARTPOS)
    entries = b.read_piece_entries()

    # 32 pieces total
    assert len(entries) == 32

    whites = [(sq, pt) for sq, c, pt in entries if c == 0]
    blacks = [(sq, pt) for sq, c, pt in entries if c == 1]
    assert len(whites) == 16
    assert len(blacks) == 16

    # 2 kings (one per side)
    white_kings = [pt for _, pt in whites if pt == 6]
    black_kings = [pt for _, pt in blacks if pt == 6]
    assert len(white_kings) == 1
    assert len(black_kings) == 1

    # 8 pawns per side
    white_pawns = [pt for _, pt in whites if pt == 1]
    black_pawns = [pt for _, pt in blacks if pt == 1]
    assert len(white_pawns) == 8
    assert len(black_pawns) == 8

    # All squares are valid 0x88 squares
    for sq, _c, _pt in entries:
        assert sq & 0x88 == 0, f"square 0x{sq:02X} is not a valid 0x88 square"


# ---------------------------------------------------------------------------
# Bridge: clear best move
# ---------------------------------------------------------------------------

def test_bridge_clear_best_move():
    """clear_best_move must zero the buffer so read_best_move returns None."""
    cpu = _make_cpu()
    raw = struct.pack(">HHHBB", 0x14, 0x34, 0, 1, 1)
    cpu.mem_write(AI_BEST_MOVE_ADDR, raw)
    b = Bridge(cpu)
    b.clear_best_move()
    assert b.read_best_move() is None


# ---------------------------------------------------------------------------
# Bridge: set computer color
# ---------------------------------------------------------------------------

def test_bridge_set_computer_color():
    """set_computer_color(1) must mark White=Human and Black=Computer."""
    cpu = _make_cpu()
    Bridge(cpu).set_computer_color(1)

    # White (color=0) at PLAYER_TYPE_BASE + 0*2 = base+0 → Human=1
    raw_white = cpu.mem_read(PLAYER_TYPE_BASE + 0, 2)
    assert struct.unpack(">H", raw_white)[0] == 1

    # Black (color=1) at PLAYER_TYPE_BASE + 1*2 = base+2 → Computer=2
    raw_black = cpu.mem_read(PLAYER_TYPE_BASE + 2, 2)
    assert struct.unpack(">H", raw_black)[0] == 2
