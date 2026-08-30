"""
bin/Code/Retro/Fakes.py — Scripted CPU for unit tests.

``FakeCpu`` is a drop-in ``Cpu`` implementation that uses a pre-allocated in-memory
byte array and a dict-backed register store — no emulator, no ROM, no third-party
imports required.  Test suites use it to exercise ``Bridge``, ``Think``, ``Oracle``,
and ``Uci`` without a verified binary.

**Zero Unicorn import. Zero PySide6 import.**

:spec: feature_spec.md §5 (testing strategy), N-RETRO-2, N-RETRO-5
"""

from __future__ import annotations

from collections.abc import Callable

from Code.Retro.Cpu import Cpu

_MEM_SIZE = 2**24  # 16 MB flat address space


class FakeCpu(Cpu):
    """Scripted CPU for unit tests — no emulator, no ROM required.

    Allocates a 16 MB ``bytearray`` at construction time.  Register reads on
    names that have never been written return 0.  ``emu_start()`` calls an
    optional callback (set via :meth:`set_emu_callback`) instead of executing
    real machine code.

    :spec: feature_spec.md §5 (testing strategy)
    """

    def __init__(self) -> None:
        """Initialise with zeroed memory and an empty register file."""
        self._regs: dict[str, int] = {}
        self._mem: bytearray = bytearray(_MEM_SIZE)
        self._emu_callback: Callable[[FakeCpu], None] | None = None
        self._mapped: list[tuple[int, int]] = []
        self._hook_counter: int = 0
        self.instruction_count: int = 0

    # ------------------------------------------------------------------
    # Test-helper methods (not part of the Cpu base)
    # ------------------------------------------------------------------

    def set_reg(self, name: str, value: int) -> None:
        """Pre-set a register value before calling :meth:`emu_start`.

        :param name: Register name (case-insensitive).
        :param value: Value to store.
        """
        self._regs[name.upper()] = value

    def set_emu_callback(self, callback: Callable[[FakeCpu], None]) -> None:
        """Register a scripted trace function called by :meth:`emu_start`.

        The callback receives this ``FakeCpu`` instance as its only argument,
        letting tests read/write registers and memory to simulate execution.

        :param callback: Callable that accepts this ``FakeCpu``.
        """
        self._emu_callback = callback

    def mapped_regions(self) -> list[tuple[int, int]]:
        """Return a copy of all regions passed to :meth:`map_region`.

        :return: List of ``(address, size)`` tuples in call order.
        """
        return list(self._mapped)

    # ------------------------------------------------------------------
    # Cpu base implementation
    # ------------------------------------------------------------------

    def map_region(self, address: int, size: int) -> None:
        """Record the mapping request.  FakeCpu's flat memory needs no actual mapping.

        :param address: Start address.
        :param size: Number of bytes.
        """
        self._mapped.append((address, size))

    def mem_read(self, address: int, size: int) -> bytes:
        """Read *size* bytes from the flat memory store.

        :param address: Start address.
        :param size: Number of bytes to read.
        :return: Slice of the internal bytearray as bytes.
        """
        return bytes(self._mem[address:address + size])

    def mem_write(self, address: int, data: bytes) -> None:
        """Write *data* into the flat memory store.

        :param address: Destination address.
        :param data: Bytes to write.
        """
        self._mem[address:address + len(data)] = data

    def reg_read(self, name: str) -> int:
        """Return the value of the named register (0 if never written).

        :param name: Register name (case-insensitive).
        :return: Current value, or 0 for any unwritten register.
        """
        return self._regs.get(name.upper(), 0)

    def reg_write(self, name: str, value: int) -> None:
        """Store *value* in the named register.

        :param name: Register name (case-insensitive).
        :param value: New value.
        """
        self._regs[name.upper()] = value

    def emu_start(self, begin: int = 0, until: int = 0xFFFFFFFF, count: int = 0) -> None:
        """Increment :attr:`instruction_count` and invoke the scripted callback.

        :param begin: Ignored by FakeCpu (no real execution).
        :param until: Ignored by FakeCpu.
        :param count: Ignored by FakeCpu.
        """
        self.instruction_count += 1
        if self._emu_callback is not None:
            self._emu_callback(self)

    def emu_stop(self) -> None:
        """No-op for FakeCpu (no live execution to stop)."""

    def hook_add(
        self,
        hook_type: str,
        callback,
        begin: int | None = None,
        end: int | None = None,
    ) -> int:
        """Return a monotonically incrementing handle; no real hook is registered.

        :param hook_type: Hook type string (ignored).
        :param callback: Callable (ignored).
        :param begin: Ignored by FakeCpu.
        :param end: Ignored by FakeCpu.
        :return: Integer handle for use with :meth:`hook_del`.
        """
        self._hook_counter += 1
        return self._hook_counter

    def hook_del(self, handle: int) -> None:
        """No-op for FakeCpu.

        :param handle: Handle returned by :meth:`hook_add` (ignored).
        """
