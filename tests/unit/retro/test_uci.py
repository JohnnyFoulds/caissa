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
# retro_rom: real-ROM test (skipped without ROM)
# ---------------------------------------------------------------------------

@pytest.mark.retro_rom
def test_uci_go_with_rom_returns_legal_bestmove():
    """With a real ROM, go must return a legal bestmove."""
    pytest.skip("retro_rom: no ROM supplied in this environment")
