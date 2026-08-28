"""
bin/Code/Retro/Traps.py — Amiga OS-call stubs and deterministic virtual clock.

Provides two classes:

* :class:`VirtualClock` — a deterministic tick counter that replaces the
  Amiga hardware timer so that difficulty levels that used wall-clock cutoffs
  become reproducible (D4).

* :class:`AmigaTraps` — a :data:`~Code.Retro.Cpu.HOOK_CODE` dispatcher that
  intercepts Amiga exec/dos library calls and returns plausible fake values so
  the binary runs headlessly under Unicorn without a real AmigaOS.

**Zero Unicorn import** — callbacks ignore the raw emulator argument and use
``self._cpu`` (the :class:`~Code.Retro.Cpu.Cpu` wrapper) throughout, so the
same trap handler works with :class:`~Code.Retro.Fakes.FakeCpu` in unit tests
and with :class:`~Code.Retro.Cpus.Unicorn68k.Unicorn68k` in real emulation.

:spec: feature_spec.md §6, decisions.md D4
"""

from __future__ import annotations

from collections import defaultdict

from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_READ, Cpu

# ---------------------------------------------------------------------------
# Memory layout — matches Phase 1-B recon and scan_lowaddr.py constants
# ---------------------------------------------------------------------------

EXEC_BASE: int = 0x800000
LIB_RANGE: int = 0x040000
ALLOC_POOL: int = 0x200000
ALLOC_POOL_SIZE: int = 0x100000


# ---------------------------------------------------------------------------
# VirtualClock
# ---------------------------------------------------------------------------


class VirtualClock:
    """Deterministic simulated timer for Battle Chess difficulty-level timing.

    The Amiga game polls a hardware VBL counter to implement timed search
    cutoffs.  By advancing this clock explicitly, all timing-dependent
    behaviour becomes fully reproducible regardless of host-machine speed.

    :param tick_rate: Ticks per simulated second (default 50 — Amiga PAL VBL
        frequency).  Exposed as an attribute so callers can convert ticks to
        seconds for logging.
    """

    def __init__(self, tick_rate: int = 50) -> None:
        """Initialise the clock at zero.

        :param tick_rate: Ticks per simulated second (default 50).
        """
        self.tick_rate: int = tick_rate
        self._ticks: int = 0

    def advance(self, ticks: int = 1) -> None:
        """Advance the clock by *ticks* ticks.

        :param ticks: Number of ticks to add (default 1).
        """
        self._ticks += ticks

    def read(self) -> int:
        """Return the current tick count.

        :return: Current tick count since last :meth:`reset`.
        """
        return self._ticks

    def reset(self) -> None:
        """Reset the tick count to zero."""
        self._ticks = 0


# ---------------------------------------------------------------------------
# AmigaTraps
# ---------------------------------------------------------------------------


class AmigaTraps:
    """Amiga exec/dos library stub dispatcher.

    Registers a :data:`~Code.Retro.Cpu.HOOK_CODE` hook on the supplied
    :class:`~Code.Retro.Cpu.Cpu`.  When the emulator executes an instruction
    in the library vector region
    ``[EXEC_BASE - LIB_RANGE, EXEC_BASE + LIB_RANGE)``, :meth:`_dispatch`
    intercepts the call and writes a plausible return value into D0 before the
    (all-RTS) stub returns to the caller.

    Three library calls are handled based on Phase 1-B recon findings:

    * ``AllocMem`` (exec_base − 0xC6): bump-allocator returning pointers from
      the alloc pool at :data:`ALLOC_POOL`.
    * ``OpenLibrary`` (exec_base − 0x198): returns :data:`EXEC_BASE` so the
      game treats it as a valid library base.
    * Everything else: returns 0 (harmless for FreeMem and unknown calls).

    A second hook (:meth:`install_mem_hook`) intercepts reads from virtual
    address 0x4 (the Amiga ``AbsExecBase`` pointer) and fills in
    :data:`EXEC_BASE`, which the binary reads during initialisation.

    :param cpu: The CPU wrapper to install hooks into.
    :param clock: Optional :class:`VirtualClock`; a default 50 Hz clock is
        created if not supplied.
    """

    EXEC_BASE: int = EXEC_BASE
    LIB_RANGE: int = LIB_RANGE
    ALLOC_POOL: int = ALLOC_POOL
    ALLOC_POOL_SIZE: int = ALLOC_POOL_SIZE

    def __init__(self, cpu: Cpu, clock: VirtualClock | None = None) -> None:
        """Initialise traps for *cpu*.

        :param cpu: CPU wrapper to install hooks into.
        :param clock: Deterministic clock; a 50 Hz default is used if omitted.
        """
        self._cpu: Cpu = cpu
        self._clock: VirtualClock = clock if clock is not None else VirtualClock()
        self._bump: int = ALLOC_POOL
        self._call_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public install / uninstall
    # ------------------------------------------------------------------

    def install(self) -> int:
        """Map the library region, fill it with RTS stubs, and install the hook.

        Maps ``[EXEC_BASE - LIB_RANGE, EXEC_BASE + LIB_RANGE)`` into the CPU's
        address space, writes 0x4E75 (RTS) bytes throughout, then registers the
        :meth:`_dispatch` hook.

        :return: Hook handle suitable for passing to :meth:`uninstall`.
        """
        base = EXEC_BASE - LIB_RANGE
        size = LIB_RANGE * 2
        self._cpu.map_region(base, size)
        self._cpu.mem_write(base, b"\x4e\x75" * size)
        return self._cpu.hook_add(HOOK_CODE, self._dispatch)

    def uninstall(self, handle: int) -> None:
        """Remove the code hook previously returned by :meth:`install`.

        :param handle: Hook handle returned by :meth:`install`.
        """
        self._cpu.hook_del(handle)

    def install_mem_hook(self) -> int:
        """Register the AbsExecBase memory-read hook.

        Intercepts reads from virtual address 0x4 (the Amiga ``AbsExecBase``
        pointer) and writes :data:`EXEC_BASE` there so the binary finds a
        valid exec base during initialisation.

        :return: Hook handle suitable for passing to :meth:`uninstall`.
        """
        return self._cpu.hook_add(HOOK_MEM_READ, self._mem_dispatch)

    def call_count(self, name: str) -> int:
        """Return how many times the named trap was called.

        :param name: Trap name — ``"AllocMem"``, ``"OpenLibrary"``, or
            ``"unknown"``.
        :return: Call count since construction (0 if never called).
        """
        return self._call_counts[name]

    # ------------------------------------------------------------------
    # Hook callbacks — emulator arg is ignored; self._cpu used throughout
    # ------------------------------------------------------------------

    def _dispatch(self, _emu, address: int, size: int, _user_data=None) -> None:
        """Code hook: intercept library vector calls.

        :param _emu: Raw emulator object (ignored — use ``self._cpu``).
        :param address: Instruction address that fired the hook.
        :param size: Instruction size in bytes (unused).
        :param _user_data: Unicorn user-data slot (ignored).
        """
        if not (EXEC_BASE - LIB_RANGE <= address < EXEC_BASE + LIB_RANGE):
            return

        offset = address - EXEC_BASE

        if offset == -0xC6:
            d0 = self._cpu.reg_read("D0")
            aligned = (d0 + 7) & ~7
            alloc_size = max(aligned, 8)
            self._cpu.reg_write("D0", self._bump)
            self._bump += alloc_size
            self._call_counts["AllocMem"] += 1

        elif offset == -0x198:
            self._cpu.reg_write("D0", EXEC_BASE)
            self._call_counts["OpenLibrary"] += 1

        else:
            self._cpu.reg_write("D0", 0)
            self._call_counts["unknown"] += 1

    def _mem_dispatch(
        self,
        _emu,
        access: int,
        address: int,
        size: int,
        value: int,
        _user_data=None,
    ) -> None:
        """Memory-read hook: supply the AbsExecBase pointer at address 0x4.

        :param _emu: Raw emulator object (ignored).
        :param access: Memory access type (unused).
        :param address: Address being read.
        :param size: Read size in bytes (unused).
        :param value: Value at the address before the hook fires (unused).
        :param _user_data: Unicorn user-data slot (ignored).
        """
        if address == 0x4:
            self._cpu.mem_write(0x4, EXEC_BASE.to_bytes(4, "big"))
