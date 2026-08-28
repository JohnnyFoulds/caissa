"""
bin/Code/Retro/Cpus/UnicornX86.py — Unicorn Engine x86-16 backend.

**This is the ONLY module in ``Code.Retro`` permitted to import ``unicorn``
for the x86 target** (N-RETRO-2 extended to second target).  All other
``Code.Retro`` modules remain unicorn-free.

Wraps ``unicorn.Uc(UC_ARCH_X86, UC_MODE_16)`` behind the ``Cpu`` seam.
The 16-bit mode emulates real-mode DOS — correct for Battle Chess DOS (1988).

:spec: feature_spec.md §9, N-RETRO-2, decisions.md D1
"""

from __future__ import annotations

import unicorn
import unicorn.x86_const as _x86
from unicorn import (
    UC_ARCH_X86,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MODE_16,
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
    "AX": _x86.UC_X86_REG_AX,
    "BX": _x86.UC_X86_REG_BX,
    "CX": _x86.UC_X86_REG_CX,
    "DX": _x86.UC_X86_REG_DX,
    "SI": _x86.UC_X86_REG_SI,
    "DI": _x86.UC_X86_REG_DI,
    "SP": _x86.UC_X86_REG_SP,
    "BP": _x86.UC_X86_REG_BP,
    "IP": _x86.UC_X86_REG_IP,
    "CS": _x86.UC_X86_REG_CS,
    "DS": _x86.UC_X86_REG_DS,
    "ES": _x86.UC_X86_REG_ES,
    "SS": _x86.UC_X86_REG_SS,
    "FLAGS": _x86.UC_X86_REG_FLAGS,
}

_HOOK_MAP: dict[str, int] = {
    HOOK_CODE: UC_HOOK_CODE,
    HOOK_MEM_READ: UC_HOOK_MEM_READ,
    HOOK_MEM_WRITE: UC_HOOK_MEM_WRITE,
    HOOK_MEM_INVALID: UC_HOOK_MEM_INVALID,
}


class UnicornX86(Cpu):
    """Unicorn Engine x86-16 (real-mode DOS) emulator backend.

    Creates a Unicorn ``Uc`` instance configured as 16-bit x86 real mode.
    All register and memory operations are thin wrappers around the Unicorn API.

    :raises EmulatorUnavailableError: If ``unicorn`` is not installed (raised
        at import time of this module, not at construction time).
    :spec: feature_spec.md §9, N-RETRO-2
    """

    def __init__(self) -> None:
        """Initialise the Unicorn x86-16 emulator instance."""
        self._uc = unicorn.Uc(UC_ARCH_X86, UC_MODE_16)

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

        :param name: Register name (case-insensitive, e.g. ``"AX"``, ``"IP"``).
        :return: Current register value.
        :raises CpuError: If *name* is not a recognised x86-16 register.
        """
        key = name.upper()
        if key not in _REG_MAP:
            raise CpuError(f"unknown register {name!r}")
        return self._uc.reg_read(_REG_MAP[key])

    def reg_write(self, name: str, value: int) -> None:
        """Set the named register to *value*.

        :param name: Register name (case-insensitive).
        :param value: New value.
        :raises CpuError: If *name* is not a recognised x86-16 register.
        """
        key = name.upper()
        if key not in _REG_MAP:
            raise CpuError(f"unknown register {name!r}")
        self._uc.reg_write(_REG_MAP[key], value)

    def emu_start(self, begin: int, until: int = 0xFFFF, count: int = 0) -> None:
        """Start emulation from *begin*.

        :param begin: Start address (16-bit physical address).
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

    def hook_add(self, hook_type: str, callback) -> int:
        """Register *callback* for the given hook type.

        :param hook_type: One of the ``HOOK_*`` constants from ``Code.Retro.Cpu``.
        :param callback: Unicorn-style hook callback.
        :return: Opaque integer handle.
        :raises CpuError: If *hook_type* is not recognised.
        """
        if hook_type not in _HOOK_MAP:
            raise CpuError(f"unknown hook type {hook_type!r}")
        return self._uc.hook_add(_HOOK_MAP[hook_type], callback)

    def hook_del(self, handle: int) -> None:
        """Remove a previously registered hook.

        :param handle: Handle returned by :meth:`hook_add`.
        """
        self._uc.hook_del(handle)
