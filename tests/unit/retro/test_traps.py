"""
tests/unit/retro/test_traps.py — Phase 5 tests for VirtualClock and AmigaTraps.

All tests use FakeCpu — no unicorn, no ROM required.

:spec: feature_spec.md §6, decisions.md D4
:phase: 5
"""

from __future__ import annotations

import pytest
from Code.Retro.Fakes import FakeCpu
from Code.Retro.Traps import (
    ALLOC_POOL,
    EXEC_BASE,
    LIB_RANGE,
    AmigaTraps,
    VirtualClock,
)

pytestmark = pytest.mark.retro


# ---------------------------------------------------------------------------
# VirtualClock
# ---------------------------------------------------------------------------


def test_clock_starts_at_zero():
    """VirtualClock must read 0 immediately after construction.

    :spec: decisions.md D4
    """
    assert VirtualClock().read() == 0


def test_clock_advance_increments():
    """advance(N) must add N to the tick count.

    :spec: decisions.md D4
    """
    clock = VirtualClock()
    clock.advance(10)
    assert clock.read() == 10


def test_clock_advance_default_is_one():
    """advance() with no argument must increment by 1.

    :spec: decisions.md D4
    """
    clock = VirtualClock()
    clock.advance()
    assert clock.read() == 1


def test_clock_reset():
    """reset() must return the tick count to zero.

    :spec: decisions.md D4
    """
    clock = VirtualClock()
    clock.advance(100)
    clock.reset()
    assert clock.read() == 0


def test_clock_custom_tick_rate():
    """tick_rate attribute must reflect the constructor argument.

    :spec: decisions.md D4
    """
    assert VirtualClock(tick_rate=60).tick_rate == 60


def test_clock_default_tick_rate_is_50():
    """Default tick_rate must be 50 (Amiga PAL VBL frequency).

    :spec: decisions.md D4
    """
    assert VirtualClock().tick_rate == 50


# ---------------------------------------------------------------------------
# AmigaTraps — install
# ---------------------------------------------------------------------------


def test_traps_install_maps_library_region():
    """install() must map [EXEC_BASE - LIB_RANGE, size=LIB_RANGE*2] into the CPU.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    expected = (EXEC_BASE - LIB_RANGE, LIB_RANGE * 2)
    assert expected in cpu.mapped_regions()


def test_traps_install_fills_library_with_rts():
    """install() must write 0x4E75 (RTS) bytes throughout the library region.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    # Sample a few bytes from the library region
    base = EXEC_BASE - LIB_RANGE
    chunk = cpu.mem_read(base, 4)
    assert chunk == b"\x4e\x75\x4e\x75"


# ---------------------------------------------------------------------------
# AmigaTraps — AllocMem
# ---------------------------------------------------------------------------


def test_traps_alloc_mem():
    """AllocMem dispatch must set D0 to a pointer in the alloc pool.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    cpu.reg_write("D0", 64)
    traps._dispatch(None, EXEC_BASE - 0xC6, 2)
    ptr = cpu.reg_read("D0")
    assert ALLOC_POOL <= ptr < ALLOC_POOL + 0x100000


def test_traps_alloc_mem_bump_advances():
    """Two AllocMem calls must return distinct non-overlapping addresses.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    cpu.reg_write("D0", 64)
    traps._dispatch(None, EXEC_BASE - 0xC6, 2)
    first = cpu.reg_read("D0")
    cpu.reg_write("D0", 32)
    traps._dispatch(None, EXEC_BASE - 0xC6, 2)
    second = cpu.reg_read("D0")
    assert second > first


# ---------------------------------------------------------------------------
# AmigaTraps — OpenLibrary
# ---------------------------------------------------------------------------


def test_traps_open_library_returns_exec_base():
    """OpenLibrary dispatch must set D0 to EXEC_BASE.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    traps._dispatch(None, EXEC_BASE - 0x198, 2)
    assert cpu.reg_read("D0") == EXEC_BASE


# ---------------------------------------------------------------------------
# AmigaTraps — unknown / non-library
# ---------------------------------------------------------------------------


def test_traps_unknown_returns_zero():
    """Unknown library-region offsets must set D0 to 0.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    cpu.reg_write("D0", 0xDEAD)
    traps._dispatch(None, EXEC_BASE - 0x400, 2)
    assert cpu.reg_read("D0") == 0


def test_traps_ignores_non_library_address():
    """_dispatch must not modify D0 for addresses outside the library region.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    cpu.reg_write("D0", 0xBEEF)
    traps._dispatch(None, 0x1000, 2)
    assert cpu.reg_read("D0") == 0xBEEF


# ---------------------------------------------------------------------------
# AmigaTraps — call counts
# ---------------------------------------------------------------------------


def test_traps_call_counts():
    """call_count() must reflect the number of times each trap was invoked.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install()
    cpu.reg_write("D0", 8)
    traps._dispatch(None, EXEC_BASE - 0xC6, 2)   # AllocMem
    traps._dispatch(None, EXEC_BASE - 0x198, 2)  # OpenLibrary
    assert traps.call_count("AllocMem") == 1
    assert traps.call_count("OpenLibrary") == 1
    assert traps.call_count("unknown") == 0


# ---------------------------------------------------------------------------
# AmigaTraps — mem hook
# ---------------------------------------------------------------------------


def test_mem_hook_writes_exec_base():
    """_mem_dispatch must write EXEC_BASE to address 0x4 when that address is read.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install_mem_hook()
    traps._mem_dispatch(None, 0, 0x4, 4, 0)
    raw = cpu.mem_read(0x4, 4)
    assert raw == EXEC_BASE.to_bytes(4, "big")


def test_mem_hook_ignores_other_addresses():
    """_mem_dispatch must not write anything for addresses other than 0x4.

    :spec: feature_spec.md §6
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    traps.install_mem_hook()
    traps._mem_dispatch(None, 0, 0x8, 4, 0)  # address 0x8, not 0x4
    assert cpu.mem_read(0x8, 4) == b"\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# AmigaTraps — clock injection
# ---------------------------------------------------------------------------


def test_virtual_clock_injected():
    """AmigaTraps must store the supplied VirtualClock with its tick_rate intact.

    :spec: decisions.md D4
    """
    cpu = FakeCpu()
    clock = VirtualClock(tick_rate=60)
    traps = AmigaTraps(cpu, clock=clock)
    assert traps._clock is clock
    assert traps._clock.tick_rate == 60


def test_default_clock_created_if_omitted():
    """AmigaTraps must create a default VirtualClock when none is supplied.

    :spec: decisions.md D4
    """
    cpu = FakeCpu()
    traps = AmigaTraps(cpu)
    assert isinstance(traps._clock, VirtualClock)
    assert traps._clock.tick_rate == 50
