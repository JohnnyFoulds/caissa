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
from Code.Retro.Bridge import AI_INIT_ADDR, Bridge
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID, Cpu
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
        self._cpu: Cpu | None = cpu

    # ------------------------------------------------------------------

    def _ensure_cpu(self) -> Cpu:
        if self._cpu is not None:
            return self._cpu

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

        logger.info("loading ROM from %s", self._rom_path)

        # Verify ROM integrity before loading.
        verify_rom(str(self._rom_path), _MANIFEST_PATH)

        rom_data = self._rom_path.read_bytes()
        regions = parse_amiga_hunk(rom_data)

        cpu: Cpu = Unicorn68k()

        # Map chip RAM as one 2 MB flat region — covers code, BSS, stack,
        # and all A4-relative globals.  This mirrors how the original Amiga
        # loaded the binary into chip RAM without gaps.
        cpu.map_region(_CHIP_RAM_BASE, _CHIP_RAM_SIZE)

        # Write each hunk segment's code data into chip RAM.
        for region in regions:
            if region.size > 0:
                cpu.mem_write(
                    region.load_address,
                    rom_data[region.offset : region.offset + region.size],
                )

        # AllocMem pool (Amiga exec allocator) sits above chip RAM.
        cpu.map_region(ALLOC_POOL, ALLOC_POOL_SIZE)

        # Amiga OS stubs + AbsExecBase mem hook.
        traps = AmigaTraps(cpu)
        traps.install()
        traps.install_mem_hook()

        self._cpu = cpu
        logger.info("ROM loaded; %d memory region(s) mapped", len(regions))
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

        # Restore A4 and reset the stack before each call.
        cpu.reg_write("A4", _A4_VALUE)
        sp = _STACK_TOP - 4
        cpu.mem_write(sp, struct.pack(">I", _SENTINEL))
        cpu.reg_write("A7", sp)

        _mapped: set[int] = set()

        def _code_hook(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            if addr == _TIME_CHECK_ADDR:
                # Set abort flag so the iterative-deepening loop stops after one pass.
                cpu.mem_write(_ABORT_FLAG_ADDR, struct.pack(">H", 1))
                # Pop return address and return to caller.
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

        hook_code = cpu.hook_add(HOOK_CODE, _code_hook)
        hook_mem  = cpu.hook_add(HOOK_MEM_INVALID, _mem_invalid)
        logger.debug("starting emulation from 0x%X", AI_INIT_ADDR)
        try:
            cpu.emu_start(AI_INIT_ADDR, until=_SENTINEL, count=_MAX_INSTRUCTIONS)
        finally:
            cpu.hook_del(hook_code)
            cpu.hook_del(hook_mem)

        move = bridge.read_best_move()
        if move is None:
            raise ThinkError(
                "emulation completed without writing a best move to AI_BEST_MOVE_ADDR"
            )

        logger.debug("best move: %s", move.to_uci())
        return ThinkResult(move=move, level=request.level, instructions=0)
