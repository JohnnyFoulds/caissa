"""
bin/Code/Retro/Think.py — ThinkSession orchestrator.

Drives whole-binary headless emulation of Battle Chess to obtain a best move.

**Seam design** — pass *cpu* directly to skip ROM loading (FakeCpu for unit
tests).  Pass *rom_path* for production (Unicorn68k path).  Providing neither
raises :exc:`~Code.Retro.Errors.EmulatorUnavailableError` at think-time.

**Flow** (production path)::

    verify ROM hash  →  parse HUNK  →  map regions  →  install traps
    →  write_position  →  clear_best_move  →  set_computer_color
    →  emu_start  →  read_best_move  →  ThinkResult

**Memory map** (virtual addresses)::

    0x000000 – 0x015000   HUNK_CODE (page-aligned)
    0x0E0000 – 0x0F0000   stack (64 KB)
    0x200000 – 0x300000   AllocMem pool
    0x7C0000 – 0x840000   Amiga exec library stubs (mapped by AmigaTraps)

:spec: feature_spec.md §7, decisions.md D2, D4, N-RETRO-8
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path

from Code.Retro.Bridge import A4 as _A4_VALUE
from Code.Retro.Bridge import AI_BEST_MOVE_ADDR, AI_INIT_ADDR, BOARD_ARRAY_ADDR, Bridge
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID, HOOK_MEM_WRITE, Cpu
from Code.Retro.Errors import EmulatorUnavailableError, RomNotFoundError, ThinkError
from Code.Retro.Types import Level, ThinkResult

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).parents[3] / "Resources" / "Retro" / "manifest.json"

# Chip RAM: 2 MB flat block covering code, BSS, stack, globals.
# The original Amiga ran with chip RAM from 0x000000..0x1FFFFF; we map it
# as one region so the AI can write to any address without an unmapped fault.
_CHIP_RAM_BASE: int = 0x000000
_CHIP_RAM_SIZE: int = 0x200000  # 2 MB

# Stack top sits near the end of chip RAM.
_STACK_TOP: int = 0x1F0000

# Sentinel return address — emulation stops when PC reaches this value.
# Must not collide with any mapped region.
_SENTINEL: int = 0xFFFF0000

# Safety cap: the AI runs ~88k write events at 1 ply; budget 2 billion instructions.
_MAX_INSTRUCTIONS: int = 2_000_000_000

# Amiga OS stubs that crash if executed — pop return address and return immediately.
# Confirmed from recon: 0x8820 timer/event, 0x8D32/0x7CCE/0x857E pre-search inits,
# 0x005A event pump, 0x015C/0x00E4/0x0138/0x17D2 other OS stubs.
_BYPASS_NOOP: frozenset[int] = frozenset({
    0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2,
})

# Time-check vector: set abort flag so iterative deepening stops after one pass.
_TIME_CHECK_ADDR: int = 0x008A
# [A4 - 0x35B4] = 0x4A4A — abort-search flag read by the iterative deepening loop.
_ABORT_FLAG_ADDR: int = _A4_VALUE - 0x35B4  # 0x4A4A


@dataclass
class ThinkRequest:
    """Parameters for a single think call.

    :param fen: FEN position string.
    :param level: Requested difficulty level (passed through to ThinkResult).
    :param computer_color: 0=computer plays White, 1=computer plays Black (default).
    """

    fen: str
    level: Level
    computer_color: int = field(default=1)


class ThinkSession:
    """Orchestrates ROM load, emulation setup, and think calls.

    Provide *cpu* directly for unit tests (FakeCpu seam — skips all ROM
    loading).  Provide *rom_path* for production.  Providing neither causes
    :meth:`think` to raise :exc:`~Code.Retro.Errors.EmulatorUnavailableError`.

    :param rom_path: Path to the verified ROM binary.  Loaded and cached on
        the first :meth:`think` call.
    :param cpu: Pre-built :class:`~Code.Retro.Cpu.Cpu` instance.  When given,
        *rom_path* is ignored.
    """

    def __init__(
        self,
        rom_path: Path | None = None,
        cpu: Cpu | None = None,
    ) -> None:
        self._rom_path = rom_path
        self._test_cpu: Cpu | None = cpu   # unit-test seam only; never mutated
        self._rom_bytes: bytes | None = None   # cached after first ROM load
        self._rom_regions: list | None = None  # cached parsed HUNK regions

    # ------------------------------------------------------------------

    def _ensure_cpu(self) -> Cpu:
        """Return a CPU ready for emulation.

        Unit-test seam: if *cpu* was supplied to the constructor, return it
        unchanged every time (FakeCpu contract).

        Production path: verify + parse the ROM once (cached), then build a
        **fresh** Unicorn instance on every call so that BSS, search tables,
        and interrupt vectors start clean for each think() invocation.
        """
        if self._test_cpu is not None:
            return self._test_cpu

        if self._rom_path is None:
            raise EmulatorUnavailableError()

        if not self._rom_path.exists():
            raise RomNotFoundError(str(self._rom_path))

        from Code.Retro.Cpus.Availability import require
        require()

        from Code.Retro.Cpus.Unicorn68k import Unicorn68k
        from Code.Retro.Manifest import verify as verify_rom
        from Code.Retro.Rom import parse_amiga_hunk
        from Code.Retro.Traps import ALLOC_POOL, ALLOC_POOL_SIZE, AmigaTraps

        # Load and verify the ROM once; re-use cached bytes on subsequent calls.
        if self._rom_bytes is None:
            logger.info("loading ROM from %s", self._rom_path)
            verify_rom(str(self._rom_path), _MANIFEST_PATH)
            self._rom_bytes = self._rom_path.read_bytes()
            self._rom_regions = parse_amiga_hunk(self._rom_bytes)
            logger.info("ROM parsed; %d memory region(s)", len(self._rom_regions))

        # Create a fresh CPU each call — the first search leaves stale BSS,
        # search tables, and register state in chip RAM that corrupt subsequent
        # searches if the same CPU instance is reused.
        cpu: Cpu = Unicorn68k()

        # Map chip RAM as one 2 MB flat region — covers code, BSS, stack,
        # and all A4-relative globals.  This mirrors how the original Amiga
        # loaded the binary into chip RAM without gaps.
        cpu.map_region(_CHIP_RAM_BASE, _CHIP_RAM_SIZE)

        # Write each hunk segment's code data into chip RAM.
        for region in self._rom_regions:
            if region.size > 0:
                cpu.mem_write(
                    region.load_address,
                    self._rom_bytes[region.offset : region.offset + region.size],
                )

        # AllocMem pool (Amiga exec allocator) sits above chip RAM.
        cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)

        # Amiga OS stubs + AbsExecBase mem hook.
        traps = AmigaTraps(cpu)
        traps.install()
        traps.install_mem_hook()

        return cpu

    # ------------------------------------------------------------------

    def think(self, request: ThinkRequest) -> ThinkResult:
        """Run the AI for *request* and return a :class:`~Code.Retro.Types.ThinkResult`.

        :param request: :class:`ThinkRequest` with fen, level, computer_color.
        :return: :class:`~Code.Retro.Types.ThinkResult` with the AI's chosen move.
        :raises RomNotFoundError: If *rom_path* was provided but the file is missing.
        :raises EmulatorUnavailableError: If neither *rom_path* nor *cpu* was provided,
            or if ``unicorn`` is not installed.
        :raises ThinkError: If emulation completes without writing a best move.
        """
        cpu = self._ensure_cpu()
        bridge = Bridge(cpu)

        bridge.clear_best_move()
        bridge.write_position(request.fen)
        bridge.set_computer_color(request.computer_color)

        # Initialise registers and place the sentinel return address.
        cpu.reg_write("A4", _A4_VALUE)
        sp = _STACK_TOP - 4
        cpu.mem_write(sp, struct.pack(">I", _SENTINEL))
        cpu.reg_write("A7", sp)

        # Snapshot of the root board, taken before emulation.  The search
        # modifies BOARD_ARRAY_ADDR in-place during make/unmake, so we must
        # capture it here and use it throughout for root-position validation.
        _root_board: bytes = bytes(cpu.mem_read(BOARD_ARRAY_ADDR, 128 * 4))

        _mapped: set[int] = set()
        # Two snapshot slots:
        # _tc_snapshot  — filled when TC fires with a root-valid move; emulation stops.
        # _write_snapshot — filled by every root-valid write to AI_BEST_MOVE_ADDR;
        #                   used as fallback when TC fires with garbage (which happens
        #                   for positions where the search overwrites results before TC).
        _tc_snapshot:    list[bytes | None] = [None]
        _write_snapshot: list[bytes | None] = [None]

        def _is_root_valid(to_sq: int, from_sq: int) -> bool:
            """Return True if (from_sq → to_sq) is plausibly legal in the root position.

            Validates against the saved root board, not the live board_array that the
            search modifies.  Rejects:
            * moves where from_sq is not the computer's piece
            * moves that capture own pieces
            * pawn straight pushes to occupied squares (blocked pushes)
            """
            if from_sq >= 128 or to_sq >= 128:
                return False
            from_color = _root_board[from_sq * 4 + 1]
            dest_type  = _root_board[to_sq  * 4]
            dest_color = _root_board[to_sq  * 4 + 1]
            if from_color != request.computer_color:
                return False
            if dest_type != 0 and dest_color == request.computer_color:
                return False
            from_type = _root_board[from_sq * 4]
            if (from_type == 6
                    and (to_sq & 0x0F) == (from_sq & 0x0F)
                    and dest_type != 0):
                return False
            return True

        def _code_hook(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            if addr == _TIME_CHECK_ADDR:
                # TC fires once per depth iteration.  When AI_BEST_MOVE_ADDR holds a
                # root-valid move, snapshot it and redirect PC to sentinel so emulation
                # stops immediately — this prevents any deeper search node from
                # overwriting the result with a sub-variation move (e.g. a pawn push
                # through an occupied square that became empty at depth 2).
                raw = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 4))
                to_sq, from_sq = struct.unpack(">HH", raw)
                _passes_88 = (
                    (from_sq != 0 or to_sq != 0)
                    and from_sq <= 0x77
                    and to_sq <= 0x77
                    and not (from_sq & 0x88)
                    and not (to_sq & 0x88)
                )
                if _passes_88 and _is_root_valid(to_sq, from_sq):
                    _tc_snapshot[0] = struct.pack(">HH", to_sq, from_sq)
                    cpu.reg_write("PC", _SENTINEL)
                    return
                # TC fired but AI_BEST_MOVE_ADDR is garbage or root-illegal —
                # return normally so the search can continue.
                try:
                    a7 = cpu.reg_read("A7")
                    ret = struct.unpack(">I", bytes(cpu.mem_read(a7, 4)))[0]
                    cpu.reg_write("A7", a7 + 4)
                    cpu.reg_write("PC", ret)
                except Exception:
                    pass
                return
            if addr in _BYPASS_NOOP:
                try:
                    a7 = cpu.reg_read("A7")
                    ret = struct.unpack(">I", bytes(cpu.mem_read(a7, 4)))[0]
                    cpu.reg_write("A7", a7 + 4)
                    cpu.reg_write("PC", ret)
                except Exception:
                    pass

        def _mem_write(
            _emu: object, _acc: int, addr: int, sz: int, val: int, _u: object = None
        ) -> None:
            # Track every root-valid write to AI_BEST_MOVE_ADDR as a fallback
            # snapshot.  The search transiently overwrites valid results with garbage
            # just before TC fires; if TC fires while the value is garbage, this
            # snapshot holds the last known-good root-valid move.
            if addr != AI_BEST_MOVE_ADDR or sz != 2:
                return
            to_sq = val & 0xFFFF
            if to_sq == 0 or to_sq > 0x77 or (to_sq & 0x88):
                return
            try:
                raw_from = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR + 2, 2))
                from_sq = struct.unpack(">H", raw_from)[0]
                if from_sq > 0x77 or (from_sq & 0x88):
                    return
                if _is_root_valid(to_sq, from_sq):
                    _write_snapshot[0] = struct.pack(">HH", to_sq, from_sq)
            except Exception:
                pass

        def _mem_invalid(_emu: object, _acc: int, addr: int, _sz: int, _v: int, _u: object = None) -> bool:
            page = addr & 0xFFFF0000
            if page not in _mapped:
                try:
                    cpu.map_region(page, 0x10000)
                    cpu.mem_write(page, bytes(0x10000))
                    _mapped.add(page)
                except Exception:
                    pass
            return True

        hook_code  = cpu.hook_add(HOOK_CODE, _code_hook)
        hook_mem   = cpu.hook_add(HOOK_MEM_INVALID, _mem_invalid)
        hook_write = cpu.hook_add(HOOK_MEM_WRITE, _mem_write)
        logger.debug("starting emulation from 0x%X", AI_INIT_ADDR)
        try:
            cpu.emu_start(AI_INIT_ADDR, until=_SENTINEL, count=_MAX_INSTRUCTIONS)
        finally:
            cpu.hook_del(hook_code)
            cpu.hook_del(hook_mem)
            cpu.hook_del(hook_write)

        # Priority: TC snapshot (clean depth-N result) > write snapshot (fallback
        # for positions where TC fires after the result was already overwritten with
        # garbage) > direct read (for searches that complete without TC).
        if _tc_snapshot[0] is not None:
            snap = _tc_snapshot[0]
            snap_kind = "TC"
        elif _write_snapshot[0] is not None:
            snap = _write_snapshot[0]
            snap_kind = "write"
        else:
            snap = None
            snap_kind = ""

        if snap is not None:
            snap_to, snap_from = struct.unpack(">HH", snap)
            from Code.Retro.Types import MoveSpec
            move = MoveSpec(from_sq=snap_from, to_sq=snap_to, flags=0, piece=0, legal=1)
            logger.debug("%s-snapshot move: %s", snap_kind, move.to_uci())
        else:
            move = bridge.read_best_move()
            if move is None:
                raise ThinkError(
                    "emulation completed without writing a best move to AI_BEST_MOVE_ADDR"
                )

        logger.debug("best move: %s", move.to_uci())
        return ThinkResult(move=move, level=request.level, instructions=0)
