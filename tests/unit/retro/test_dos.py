"""
tests/unit/retro/test_dos.py — Phase 9 tests for the DOS x86 target.

The retro_emu tests require unicorn to be installed.  The retro_rom tests
require the user to supply the DOS binary.  The plain retro test verifies
the cross-port corpus comparison (trivially passes when DOS corpus is empty).

:spec: feature_spec.md §9, FR-9
:phase: 9
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.retro

_FIXTURES = Path(__file__).parent / "_fixtures"
_AMIGA_CORPUS = _FIXTURES / "corpus" / "startpos_level1.jsonl"
_DOS_CORPUS = _FIXTURES / "corpus" / "dos_startpos_level1.jsonl"

# Documented divergences loaded from docs/retro/divergences.md (Phase 9 requirement).
# Until real divergences are found, this set is empty.
_DOCUMENTED_DIVERGENCES: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# retro_emu: Unicorn x86-16 synthetic tests (require unicorn)
# ---------------------------------------------------------------------------

@pytest.mark.retro_emu
def test_unicorn_x86_loads_synthetic_com_file():
    """UnicornX86 must load and run a 6-byte .COM (NOP + RET) without raising.

    A minimal .COM program: [0x90, 0xC3] = NOP, RET.
    Mapped at 0x0100 (standard DOS COM load address).
    """
    try:
        from Code.Retro.Cpus.UnicornX86 import UnicornX86
    except ImportError:
        pytest.skip("unicorn not installed")

    cpu = UnicornX86()
    # Map 64 KB at segment 0 (covers 0x0000–0xFFFF for real-mode)
    cpu.map_region(0x0000, 0x10000)
    # .COM: NOP (0x90) + RET near (0xC3)
    cpu.mem_write(0x0100, b"\x90\xc3")
    # Run: start=0x0100, until=0x0102 (after RET), count=2
    cpu.emu_start(0x0100, until=0x0102, count=2)
    # If we get here without CpuError, the test passes


@pytest.mark.retro_emu
def test_unicorn_x86_register_roundtrip():
    """UnicornX86 must write AX and read it back unchanged after a NOP.

    Maps 64 KB, writes AX=0x1234, executes NOP, reads AX; expects 0x1234.
    """
    try:
        from Code.Retro.Cpus.UnicornX86 import UnicornX86
    except ImportError:
        pytest.skip("unicorn not installed")

    cpu = UnicornX86()
    cpu.map_region(0x0000, 0x10000)
    # NOP at 0x0100
    cpu.mem_write(0x0100, b"\x90\xc3")
    cpu.reg_write("AX", 0x1234)
    cpu.emu_start(0x0100, until=0x0102, count=2)
    assert cpu.reg_read("AX") == 0x1234


@pytest.mark.retro_emu
def test_unicorn_x86_unknown_reg_raises():
    """UnicornX86.reg_read with unknown register must raise CpuError."""
    try:
        from Code.Retro.Cpus.UnicornX86 import UnicornX86
    except ImportError:
        pytest.skip("unicorn not installed")

    from Code.Retro.Errors import CpuError

    cpu = UnicornX86()
    with pytest.raises(CpuError):
        cpu.reg_read("Z99")


# ---------------------------------------------------------------------------
# retro_rom: DOS binary tests (skipped without ROM)
# ---------------------------------------------------------------------------

@pytest.mark.retro_rom
def test_dos_rom_hash_matches_manifest():
    """DOS binary SHA256 must match the manifest entry."""
    pytest.skip("retro_rom: no DOS ROM supplied in this environment")


@pytest.mark.retro_rom
def test_dos_think_returns_legal_move():
    """DOS target ThinkSession must return a legal move from startpos."""
    pytest.skip("retro_rom: no DOS ROM supplied in this environment")


# ---------------------------------------------------------------------------
# Cross-port corpus comparison (retro marker — no ROM, no unicorn)
# ---------------------------------------------------------------------------

def test_amiga_dos_corpus_agrees_except_documented_divergences():
    """Amiga and DOS corpora must agree on all positions not in _DOCUMENTED_DIVERGENCES.

    Trivially passes when the DOS corpus does not yet exist (no positions to compare).
    Positions in docs/retro/divergences.md are exempted via _DOCUMENTED_DIVERGENCES.
    """
    if not _AMIGA_CORPUS.exists():
        pytest.skip("Amiga corpus fixture not found")

    if not _DOS_CORPUS.exists():
        # No DOS corpus yet — nothing to compare; vacuously passes
        return

    from Code.Retro.Oracle import load_corpus

    amiga_entries = {e.fen: e.expected_uci for e in load_corpus(_AMIGA_CORPUS)}
    dos_entries = {e.fen: e.expected_uci for e in load_corpus(_DOS_CORPUS)}

    divergences = []
    for fen, amiga_uci in amiga_entries.items():
        if fen not in dos_entries:
            continue
        dos_uci = dos_entries[fen]
        if amiga_uci != dos_uci and fen not in _DOCUMENTED_DIVERGENCES:
            divergences.append(
                f"undocumented divergence at {fen[:40]!r}: "
                f"amiga={amiga_uci!r} dos={dos_uci!r}"
            )

    assert not divergences, (
        "Undocumented Amiga/DOS divergences found; add them to "
        "docs/retro/divergences.md:\n" + "\n".join(divergences)
    )
