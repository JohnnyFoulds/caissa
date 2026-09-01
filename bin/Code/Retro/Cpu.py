"""
bin/Code/Retro/Cpu.py — Platform-agnostic CPU emulator seam.

Defines the ``Cpu`` base class that all emulator backends must implement, plus the
``HOOK_*`` string constants used throughout the Retro layer.

**Zero Unicorn import** — enforced by ``N-RETRO-2``.  Only ``Cpus/Unicorn68k.py``
(and other future ``Cpus/`` backends) may import ``unicorn``.

:spec: feature_spec.md §5, N-RETRO-2
"""

from __future__ import annotations

HOOK_CODE = "code"
HOOK_MEM_READ = "mem_read"
HOOK_MEM_WRITE = "mem_write"
HOOK_MEM_INVALID = "mem_invalid"


class Cpu:
    """Abstract emulator backend.

    Concrete implementations live in ``Cpus/``.  All register names are
    passed as upper-case strings (``"D0"``–``"D7"``, ``"A0"``–``"A7"``,
    ``"PC"``, ``"SP"``).  ``"SP"`` is an alias for ``"A7"``.

    :spec: feature_spec.md §5
    """

    def map_region(self, address: int, size: int) -> None:
        """Map a contiguous memory region into the emulated address space.

        Must be called before any :meth:`mem_read` or :meth:`mem_write` that
        touches the region.

        :param address: Start address (must be page-aligned on most backends).
        :param size: Number of bytes to map (must be page-aligned on most backends).
        :raises CpuError: If the region cannot be mapped (e.g. overlaps existing).
        """
        raise NotImplementedError

    def mem_read(self, address: int, size: int) -> bytes:
        """Read *size* bytes from emulated memory starting at *address*.

        :param address: Start address.
        :param size: Number of bytes to read.
        :return: Exactly *size* bytes of memory content.
        :raises CpuError: If the read falls outside a mapped region.
        """
        raise NotImplementedError

    def mem_write(self, address: int, data: bytes) -> None:
        """Write *data* to emulated memory starting at *address*.

        :param address: Destination address.
        :param data: Bytes to write.
        :raises CpuError: If the write falls outside a mapped region.
        """
        raise NotImplementedError

    def reg_read(self, name: str) -> int:
        """Return the current value of the named register.

        :param name: Register name (case-insensitive, e.g. ``"D0"``, ``"PC"``).
        :return: Current register value as an unsigned integer.
        :raises CpuError: If *name* is not a recognised register.
        """
        raise NotImplementedError

    def reg_write(self, name: str, value: int) -> None:
        """Set the named register to *value*.

        :param name: Register name (case-insensitive).
        :param value: New register value (unsigned integer).
        :raises CpuError: If *name* is not a recognised register.
        """
        raise NotImplementedError

    def emu_start(self, begin: int, until: int = 0xFFFFFFFF, count: int = 0) -> None:
        """Start emulation from *begin* until *until* or *count* instructions.

        :param begin: Start address (PC is set to this value before execution).
        :param until: Stop when PC reaches this address (exclusive).
        :param count: Stop after this many instructions (0 = unlimited).
        :raises CpuError: If emulation encounters an unhandled fault.
        """
        raise NotImplementedError

    def emu_stop(self) -> None:
        """Stop emulation from within a hook callback.

        :raises CpuError: If no emulation is active.
        """
        raise NotImplementedError

    def hook_add(
        self,
        hook_type: str,
        callback,
        begin: int | None = None,
        end: int | None = None,
    ) -> int:
        """Register *callback* for the given hook type.

        When *begin* and *end* are given the hook fires only for addresses
        in the inclusive range ``[begin, end]``.  Address-specific hooks are
        far cheaper than global hooks because the Python callback is invoked
        only at the specified addresses instead of on every instruction /
        memory access.

        :param hook_type: One of ``HOOK_CODE``, ``HOOK_MEM_READ``,
            ``HOOK_MEM_WRITE``, ``HOOK_MEM_INVALID``.
        :param callback: Callable invoked when the hook fires.  Signature
            varies by hook type (mirrors the Unicorn convention).
        :param begin: Optional start of address range (inclusive).
        :param end: Optional end of address range (inclusive).
        :return: Opaque integer handle, passed to :meth:`hook_del` to remove.
        :raises CpuError: If *hook_type* is not recognised.
        """
        raise NotImplementedError

    def hook_del(self, handle: int) -> None:
        """Remove a previously registered hook.

        :param handle: Handle returned by :meth:`hook_add`.
        :raises CpuError: If *handle* is not a live hook.
        """
        raise NotImplementedError

    def flush_tb(self) -> None:
        """Flush the JIT translation-block cache.

        Call after patching emulated memory so that recompiled blocks pick up
        the new bytes.  No-op on backends that do not cache translated blocks.
        """
