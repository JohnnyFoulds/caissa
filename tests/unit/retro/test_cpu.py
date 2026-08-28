"""
tests/unit/retro/test_cpu.py — Phase 4 CPU seam and FakeCpu tests.

Covers:
- FakeCpu register/memory/hook/emu contract
- Cpus/Availability.py probe
- Unicorn68k integration (retro_emu marker, skipped when unicorn absent)

:spec: feature_spec.md §5, N-RETRO-2
:phase: 4
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.retro


# ---------------------------------------------------------------------------
# FakeCpu — register tests
# ---------------------------------------------------------------------------

def test_fake_cpu_reg_read_default_zero():
    """Unwritten registers must return 0.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    assert cpu.reg_read("D0") == 0
    assert cpu.reg_read("PC") == 0
    assert cpu.reg_read("A7") == 0


def test_fake_cpu_reg_write_read_roundtrip():
    """reg_write followed by reg_read must return the written value.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    cpu.reg_write("D0", 42)
    assert cpu.reg_read("D0") == 42


def test_fake_cpu_reg_case_insensitive():
    """Register names must be case-insensitive.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    cpu.reg_write("d0", 0x1234)
    assert cpu.reg_read("D0") == 0x1234
    cpu.set_reg("A4", 0x7FFE)
    assert cpu.reg_read("a4") == 0x7FFE


# ---------------------------------------------------------------------------
# FakeCpu — memory tests
# ---------------------------------------------------------------------------

def test_fake_cpu_mem_write_read_roundtrip():
    """Bytes written to memory must be read back unchanged.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    payload = b'\xDE\xAD\xBE\xEF'
    cpu.mem_write(0x1000, payload)
    assert cpu.mem_read(0x1000, 4) == payload


def test_fake_cpu_mem_default_zero():
    """Unwritten memory must read as zero bytes.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    assert cpu.mem_read(0x2000, 8) == b'\x00' * 8


# ---------------------------------------------------------------------------
# FakeCpu — map_region
# ---------------------------------------------------------------------------

def test_fake_cpu_map_region_recorded():
    """map_region calls must be recorded and retrievable via mapped_regions().

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    cpu.map_region(0x1000, 0x1000)
    cpu.map_region(0x100000, 0x20000)
    regions = cpu.mapped_regions()
    assert (0x1000, 0x1000) in regions
    assert (0x100000, 0x20000) in regions
    assert len(regions) == 2


def test_fake_cpu_mapped_regions_returns_copy():
    """mapped_regions() must return a copy, not the internal list.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    cpu.map_region(0x0, 0x1000)
    r = cpu.mapped_regions()
    r.clear()
    assert len(cpu.mapped_regions()) == 1


# ---------------------------------------------------------------------------
# FakeCpu — emu_start / callback
# ---------------------------------------------------------------------------

def test_fake_cpu_emu_start_increments_count():
    """instruction_count must increment by 1 on each emu_start() call.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    assert cpu.instruction_count == 0
    cpu.emu_start(0)
    cpu.emu_start(0)
    assert cpu.instruction_count == 2


def test_fake_cpu_emu_callback_called():
    """The emu callback must be called by emu_start and can write registers.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Fakes import FakeCpu

    def _trace(cpu):
        cpu.reg_write("D0", 99)

    cpu = FakeCpu()
    cpu.set_emu_callback(_trace)
    cpu.emu_start(0)
    assert cpu.reg_read("D0") == 99


def test_fake_cpu_replays_trace():
    """FakeCpu callback can write a known pattern to memory; mem_read returns it.

    This replaces the Phase-3 xfail stub of the same name.

    :spec: feature_spec.md §5 (testing strategy)
    """
    from Code.Retro.Fakes import FakeCpu

    pattern = b'\xCA\xFE\xBA\xBE\x00\x01\x02\x03'

    def _trace(cpu):
        cpu.mem_write(0x365A, pattern)  # simulate writing to -$49A4(A4)

    cpu = FakeCpu()
    cpu.set_emu_callback(_trace)
    cpu.emu_start(0)
    assert cpu.mem_read(0x365A, 8) == pattern


# ---------------------------------------------------------------------------
# FakeCpu — hook_add / hook_del
# ---------------------------------------------------------------------------

def test_fake_cpu_hook_add_returns_int():
    """hook_add must return an integer handle.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Cpu import HOOK_CODE
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    handle = cpu.hook_add(HOOK_CODE, lambda *a: None)
    assert isinstance(handle, int)


def test_fake_cpu_hook_add_increments():
    """Each hook_add call must return a distinct handle.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_READ
    from Code.Retro.Fakes import FakeCpu
    cpu = FakeCpu()
    h1 = cpu.hook_add(HOOK_CODE, lambda *a: None)
    h2 = cpu.hook_add(HOOK_MEM_READ, lambda *a: None)
    assert h1 != h2


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def test_availability_returns_bool():
    """is_available() must return a bool without raising.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Cpus.Availability import is_available
    result = is_available()
    assert isinstance(result, bool)


def test_require_raises_if_unavailable():
    """require() must raise EmulatorUnavailableError when unicorn is absent.

    :spec: feature_spec.md §5, N-RETRO-3
    """
    from Code.Retro.Cpus.Availability import require
    from Code.Retro.Errors import EmulatorUnavailableError
    with patch("Code.Retro.Cpus.Availability.is_available", return_value=False):
        with pytest.raises(EmulatorUnavailableError):
            require()


# ---------------------------------------------------------------------------
# Unicorn68k — retro_emu tier (skipped when unicorn absent)
# ---------------------------------------------------------------------------

@pytest.mark.retro_emu
def test_unicorn68k_initialises():
    """Unicorn68k() must not raise when unicorn is installed.

    :spec: feature_spec.md §5
    """
    pytest.importorskip("unicorn")
    from Code.Retro.Cpus.Unicorn68k import Unicorn68k
    cpu = Unicorn68k()
    assert cpu is not None


@pytest.mark.retro_emu
def test_unicorn68k_mem_write_read():
    """Unicorn68k must correctly round-trip a mem_write / mem_read.

    :spec: feature_spec.md §5
    """
    pytest.importorskip("unicorn")
    from Code.Retro.Cpus.Unicorn68k import Unicorn68k
    cpu = Unicorn68k()
    cpu.map_region(0x1000, 0x1000)
    payload = b'\x11\x22\x33\x44'
    cpu.mem_write(0x1000, payload)
    assert cpu.mem_read(0x1000, 4) == payload


@pytest.mark.retro_emu
def test_unicorn68k_reg_write_read():
    """Unicorn68k must correctly round-trip a reg_write / reg_read for D0.

    :spec: feature_spec.md §5
    """
    pytest.importorskip("unicorn")
    from Code.Retro.Cpus.Unicorn68k import Unicorn68k
    cpu = Unicorn68k()
    cpu.reg_write("D0", 0xDEAD)
    assert cpu.reg_read("D0") == 0xDEAD


@pytest.mark.retro_emu
def test_unicorn68k_unknown_reg_raises():
    """Unicorn68k.reg_read with an unknown name must raise CpuError.

    :spec: feature_spec.md §5
    """
    pytest.importorskip("unicorn")
    from Code.Retro.Cpus.Unicorn68k import Unicorn68k
    from Code.Retro.Errors import CpuError
    cpu = Unicorn68k()
    with pytest.raises(CpuError, match="unknown register"):
        cpu.reg_read("ZZ")


@pytest.mark.retro_emu
def test_unicorn68k_executes_nop():
    """Unicorn68k must execute NOP + RTS without raising.

    :spec: feature_spec.md §5
    """
    pytest.importorskip("unicorn")
    from Code.Retro.Cpus.Unicorn68k import Unicorn68k
    cpu = Unicorn68k()
    # Map code region and stack
    cpu.map_region(0x0000, 0x1000)
    cpu.map_region(0x10000, 0x1000)
    # NOP (0x4E71) + RTS (0x4E75)
    cpu.mem_write(0x0000, b'\x4E\x71\x4E\x75')
    cpu.reg_write("SP", 0x10FF0)
    # Write a fake return address on the stack so RTS doesn't fault
    cpu.mem_write(0x10FF0, b'\x00\x00\x00\x00')
    # Execute 2 instructions; should return without error
    cpu.emu_start(0, 0xFFFF, count=2)
