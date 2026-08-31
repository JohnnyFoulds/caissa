"""
bin/Code/Retro/Cpus/Unicorn68k.py — Unicorn Engine m68k backend.

**This is the ONLY module in ``Code.Retro`` permitted to import ``unicorn``.**
All other modules in ``Code.Retro`` must remain unicorn-free (N-RETRO-2).

Wraps ``unicorn.Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)`` configured as a 68000
(``ctl_set_cpu_model(UC_CPU_M68K_M68000)``) behind the ``Cpu`` seam.  The seam
means that ``Cpus/Unicorn68k.py`` can be swapped for a Musashi backend (Phase 4,
R2 mitigation) without changing any caller.

:spec: feature_spec.md §5, N-RETRO-2, D2, R2
"""

from __future__ import annotations

import unicorn
import unicorn.m68k_const as _m68k
from unicorn import (
    UC_ARCH_M68K,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MODE_BIG_ENDIAN,
    UcError,
)

from Code.Retro.Cpu import (
    HOOK_CODE,
    HOOK_MEM_INVALID,
    HOOK_MEM_READ,
    HOOK_MEM_WRITE,
    Cpu,
)
from Code.Retro.Errors import CpuError

_REG_MAP: dict[str, int] = {
    "D0": _m68k.UC_M68K_REG_D0,
    "D1": _m68k.UC_M68K_REG_D1,
    "D2": _m68k.UC_M68K_REG_D2,
    "D3": _m68k.UC_M68K_REG_D3,
    "D4": _m68k.UC_M68K_REG_D4,
    "D5": _m68k.UC_M68K_REG_D5,
    "D6": _m68k.UC_M68K_REG_D6,
    "D7": _m68k.UC_M68K_REG_D7,
    "A0": _m68k.UC_M68K_REG_A0,
    "A1": _m68k.UC_M68K_REG_A1,
    "A2": _m68k.UC_M68K_REG_A2,
    "A3": _m68k.UC_M68K_REG_A3,
    "A4": _m68k.UC_M68K_REG_A4,
    "A5": _m68k.UC_M68K_REG_A5,
    "A6": _m68k.UC_M68K_REG_A6,
    "A7": _m68k.UC_M68K_REG_A7,
    "PC": _m68k.UC_M68K_REG_PC,
    "SP": _m68k.UC_M68K_REG_A7,  # SP is an alias for A7
    "SR": _m68k.UC_M68K_REG_SR,  # Status Register (CCR in low byte)
}

_HOOK_MAP: dict[str, int] = {
    HOOK_CODE: UC_HOOK_CODE,
    HOOK_MEM_READ: UC_HOOK_MEM_READ,
    HOOK_MEM_WRITE: UC_HOOK_MEM_WRITE,
    HOOK_MEM_INVALID: UC_HOOK_MEM_INVALID,
}


class Unicorn68k(Cpu):
    """Unicorn Engine m68k/68000 emulator backend.

    Creates a Unicorn ``Uc`` instance configured as a Motorola 68000 in
    big-endian mode.  All register and memory operations are thin wrappers
    around the Unicorn API.

    :raises EmulatorUnavailableError: If ``unicorn`` is not installed (raised
        at import time of this module, not at construction time).
    :spec: feature_spec.md §5, N-RETRO-2
    """

    def __init__(self) -> None:
        """Initialise the Unicorn m68k/68000 emulator instance."""
        self._uc = unicorn.Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self._uc.ctl_set_cpu_model(_m68k.UC_CPU_M68K_M68000)

    def map_region(self, address: int, size: int) -> None:
        """Map a contiguous memory region.

        :param address: Start address (must be 0x1000-aligned for Unicorn).
        :param size: Number of bytes (must be a multiple of 0x1000).
        :raises CpuError: If the region cannot be mapped.
        """
        try:
            self._uc.mem_map(address, size)
        except UcError as exc:
            raise CpuError(f"mem_map(0x{address:X}, 0x{size:X}) failed: {exc}") from exc

    def mem_read(self, address: int, size: int) -> bytes:
        """Read *size* bytes from emulated memory.

        :param address: Start address.
        :param size: Number of bytes.
        :return: Memory contents as bytes.
        :raises CpuError: If the read falls outside a mapped region.
        """
        try:
            return bytes(self._uc.mem_read(address, size))
        except UcError as exc:
            raise CpuError(f"mem_read(0x{address:X}, {size}) failed: {exc}") from exc

    def mem_write(self, address: int, data: bytes) -> None:
        """Write *data* to emulated memory.

        :param address: Destination address.
        :param data: Bytes to write.
        :raises CpuError: If the write falls outside a mapped region.
        """
        try:
            self._uc.mem_write(address, bytes(data))
        except UcError as exc:
            raise CpuError(f"mem_write(0x{address:X}) failed: {exc}") from exc

    def reg_read(self, name: str) -> int:
        """Return the value of the named register.

        :param name: Register name (case-insensitive, e.g. ``"D0"``, ``"PC"``).
        :return: Current register value.
        :raises CpuError: If *name* is not a recognised m68k register.
        """
        key = name.upper()
        if key not in _REG_MAP:
            raise CpuError(f"unknown register {name!r}")
        return self._uc.reg_read(_REG_MAP[key])

    def reg_write(self, name: str, value: int) -> None:
        """Set the named register to *value*.

        :param name: Register name (case-insensitive).
        :param value: New value.
        :raises CpuError: If *name* is not a recognised m68k register.
        """
        key = name.upper()
        if key not in _REG_MAP:
            raise CpuError(f"unknown register {name!r}")
        self._uc.reg_write(_REG_MAP[key], value)

    def emu_start(self, begin: int, until: int = 0xFFFFFFFF, count: int = 0) -> None:
        """Start emulation from *begin*.

        :param begin: Start address.
        :param until: Stop address (exclusive).
        :param count: Maximum instruction count (0 = unlimited).
        :raises CpuError: On unhandled emulation fault.
        """
        try:
            self._uc.emu_start(begin, until, count=count)
        except UcError as exc:
            raise CpuError(f"emu_start(0x{begin:X}) failed: {exc}") from exc

    def emu_stop(self) -> None:
        """Stop emulation.

        :raises CpuError: If no emulation is active.
        """
        try:
            self._uc.emu_stop()
        except UcError as exc:
            raise CpuError(f"emu_stop failed: {exc}") from exc

    def hook_add(
        self,
        hook_type: str,
        callback,
        begin: int | None = None,
        end: int | None = None,
    ) -> int:
        """Register *callback* for the given hook type.

        When *begin* / *end* are given the hook fires only within that
        inclusive address range, avoiding per-instruction Python overhead
        for all other addresses.

        :param hook_type: One of the ``HOOK_*`` constants from ``Code.Retro.Cpu``.
        :param callback: Unicorn-style hook callback.
        :param begin: Optional start of address range (inclusive).
        :param end: Optional end of address range (inclusive).
        :return: Opaque integer handle.
        :raises CpuError: If *hook_type* is not recognised.
        """
        if hook_type not in _HOOK_MAP:
            raise CpuError(f"unknown hook type {hook_type!r}")
        kwargs: dict = {}
        if begin is not None:
            kwargs["begin"] = begin
        if end is not None:
            kwargs["end"] = end
        return self._uc.hook_add(_HOOK_MAP[hook_type], callback, **kwargs)

    def hook_del(self, handle: int) -> None:
        """Remove a previously registered hook.

        :param handle: Handle returned by :meth:`hook_add`.
        """
        self._uc.hook_del(handle)
