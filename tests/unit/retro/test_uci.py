"""
tests/unit/retro/test_uci.py — Phase 8 tests for Uci.py.

Covers the UCI handshake, option parsing, position handling, and go-without-rom
degradation. All tests use io.StringIO injection — no ROM, no unicorn.

:spec: feature_spec.md §8, FR-1, FR-2, N-RETRO-10
:phase: 8
"""

from __future__ import annotations

import io
import time

import pytest
from Code.Retro.Uci import _ENGINE_NAME, UciSession

pytestmark = pytest.mark.retro

_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _run(commands: str) -> list[str]:
    """Run *commands* through a UciSession and return the output lines."""
    inp = io.StringIO(commands)
    out = io.StringIO()
    UciSession(inp=inp, out=out).run()
    return [line for line in out.getvalue().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------

def test_uci_handshake_emits_id_name_and_uciok():
    """uci command must emit 'id name ...' and 'uciok'."""
    lines = _run("uci\nquit\n")
    names = [ln for ln in lines if ln.startswith("id name")]
    assert len(names) == 1
    assert _ENGINE_NAME in names[0]
    assert "uciok" in lines


def test_uci_handshake_emits_required_options():
    """uci command must emit all four required option lines."""
    lines = _run("uci\nquit\n")
    option_lines = [ln for ln in lines if ln.startswith("option ")]
    expected_names = {"EmuLevel", "EmuClockRate", "EmuStrictOriginal", "EmuRomPath"}
    found = set()
    for line in option_lines:
        for name in expected_names:
            if f"name {name}" in line:
                found.add(name)
    assert found == expected_names, f"missing options: {expected_names - found}"


def test_uci_handshake_succeeds_without_a_rom():
    """UCI handshake must complete without error even with no ROM configured."""
    lines = _run("uci\nquit\n")
    assert "uciok" in lines


def test_uci_handshake_matches_is_valid_engine_probe():
    """uci+quit must emit at least one 'id ' or 'option ' line before 'uciok'.

    Reproduces the Lucas Chess _run_uci_command contract: the probe sends
    'uci\\nquit\\n' and checks for non-empty output with id/option prefix.
    """
    lines = _run("uci\nquit\n")
    probe_lines = [ln for ln in lines if ln.startswith(("id ", "option "))]
    assert len(probe_lines) > 0, "no id/option lines emitted before uciok"
    assert "uciok" in lines


def test_uci_handshake_completes_within_two_seconds():
    """UCI handshake must complete in under 2 seconds (N-RETRO-10)."""
    start = time.monotonic()
    _run("uci\nquit\n")
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"handshake took {elapsed:.2f}s (limit 2s)"


# ---------------------------------------------------------------------------
# isready
# ---------------------------------------------------------------------------

def test_uci_isready_emits_readyok():
    """isready must emit 'readyok'."""
    lines = _run("uci\nisready\nquit\n")
    assert "readyok" in lines


# ---------------------------------------------------------------------------
# setoption
# ---------------------------------------------------------------------------

def test_uci_setoption_emuclockrate_accepted():
    """setoption EmuClockRate with EmuStrictOriginal false must not emit an error."""
    lines = _run(
        "uci\n"
        "setoption name EmuStrictOriginal value false\n"
        "setoption name EmuClockRate value 25\n"
        "quit\n"
    )
    errors = [ln for ln in lines if "error" in ln.lower()]
    assert not errors, f"unexpected error lines: {errors}"


def test_uci_setoption_strict_original_rejects_nondefault_clock():
    """When EmuStrictOriginal is true, setting EmuClockRate != 50 must emit an error."""
    lines = _run(
        "uci\n"
        "setoption name EmuStrictOriginal value true\n"
        "setoption name EmuClockRate value 25\n"
        "quit\n"
    )
    error_lines = [ln for ln in lines if "error" in ln.lower() and "EmuStrictOriginal" in ln]
    assert len(error_lines) >= 1


# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------

def test_uci_position_startpos_updates_board():
    """position startpos moves e2e4 must be accepted without error output."""
    inp = io.StringIO("uci\nposition startpos moves e2e4\nquit\n")
    out = io.StringIO()
    session = UciSession(inp=inp, out=out)
    session.run()
    # After the position command the internal FEN should still be set
    assert session._fen == _STARTPOS  # startpos fen before move application
    assert session._moves == ["e2e4"]
    lines = out.getvalue().splitlines()
    errors = [ln for ln in lines if "error" in ln.lower() and "info" not in ln.lower()]
    assert not errors


def test_uci_position_fen_sets_state():
    """position fen <fen> must update internal FEN state."""
    fen = "8/8/8/8/4k3/8/4K3/8 w - - 0 1"
    inp = io.StringIO(f"uci\nposition fen {fen}\nquit\n")
    out = io.StringIO()
    session = UciSession(inp=inp, out=out)
    session.run()
    assert session._fen == fen


# ---------------------------------------------------------------------------
# go without ROM
# ---------------------------------------------------------------------------

def test_uci_go_without_rom_returns_info_error_and_null_move(monkeypatch):
    """go without a ROM configured must emit info string error + bestmove 0000 (FR-2)."""
    import Code.Retro.Manifest as _manifest_mod
    monkeypatch.setattr(_manifest_mod, "default_rom_path", lambda: None)
    lines = _run("uci\ngo movetime 100\nquit\n")
    info_errors = [ln for ln in lines if ln.startswith("info string error")]
    bestmove = [ln for ln in lines if ln.startswith("bestmove")]
    assert len(info_errors) >= 1
    assert len(bestmove) == 1
    assert bestmove[0] == "bestmove 0000"


# ---------------------------------------------------------------------------
# go with moves — position application
# ---------------------------------------------------------------------------

def test_uci_go_applies_moves_to_fen(monkeypatch):
    """go after 'position startpos moves e2e4' must submit the post-e2e4 FEN."""
    submitted: list[str] = []

    class _CaptureFen:
        def __init__(self, **_kw): pass
        def think(self, req):
            submitted.append(req.fen)
            from Code.Retro.Types import MoveSpec, ThinkResult
            mv = MoveSpec(from_sq=0x67, to_sq=0x47, flags=0, piece=0, legal=1)
            return ThinkResult(move=mv, level=req.level, instructions=0)

    import Code.Retro.Manifest as _manifest_mod
    import Code.Retro.Uci as _uci_mod
    monkeypatch.setattr(_uci_mod, "ThinkSession", _CaptureFen)
    monkeypatch.setattr(_manifest_mod, "default_rom_path", lambda: "fake.amiga")

    inp = io.StringIO("uci\nposition startpos moves e2e4\ngo\nquit\n")
    out = io.StringIO()
    UciSession(inp=inp, out=out).run()

    assert len(submitted) == 1
    expected = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert submitted[0] == expected, f"got FEN: {submitted[0]}"


def test_uci_go_without_moves_passes_fen_unmodified(monkeypatch):
    """go after 'position fen <fen>' (no moves) must pass that FEN unchanged."""
    submitted: list[str] = []
    fen = "8/8/8/8/4k3/8/4K3/8 w - - 0 1"

    class _CaptureFen:
        def __init__(self, **_kw): pass
        def think(self, req):
            submitted.append(req.fen)
            from Code.Retro.Types import MoveSpec, ThinkResult
            mv = MoveSpec(from_sq=0x04, to_sq=0x14, flags=0, piece=0, legal=1)
            return ThinkResult(move=mv, level=req.level, instructions=0)

    import Code.Retro.Manifest as _manifest_mod
    import Code.Retro.Uci as _uci_mod
    monkeypatch.setattr(_uci_mod, "ThinkSession", _CaptureFen)
    monkeypatch.setattr(_manifest_mod, "default_rom_path", lambda: "fake.amiga")

    inp = io.StringIO(f"uci\nposition fen {fen}\ngo\nquit\n")
    out = io.StringIO()
    UciSession(inp=inp, out=out).run()

    assert len(submitted) == 1
    assert submitted[0] == fen


# ---------------------------------------------------------------------------
# retro_rom: real-ROM test (skipped without ROM)
# ---------------------------------------------------------------------------

@pytest.mark.retro_rom
def test_uci_go_with_rom_returns_legal_bestmove():
    """With a real ROM, go must return a legal bestmove for a corpus position."""
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

    lines = _run(f"uci\nisready\nposition fen {fen}\ngo\nquit\n")
    bestmove_lines = [ln for ln in lines if ln.startswith("bestmove ")]
    assert bestmove_lines, "no bestmove line in UCI output"
    move_uci = bestmove_lines[-1].split()[1]
    assert move_uci != "0000", "engine returned null move"
    assert _chess.Move.from_uci(move_uci) in board.legal_moves, (
        f"engine returned illegal move {move_uci!r} in position {fen!r}"
    )
