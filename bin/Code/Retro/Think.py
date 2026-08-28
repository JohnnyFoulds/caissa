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

:spec: feature_spec.md §7, decisions.md D2, D4, N-RETRO-8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from Code.Retro.Bridge import AI_INIT_ADDR, Bridge
from Code.Retro.Cpu import Cpu
from Code.Retro.Errors import EmulatorUnavailableError, RomNotFoundError, ThinkError
from Code.Retro.Types import Level, ThinkResult

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MANIFEST_PATH = Path(__file__).parents[3] / "Resources" / "Retro" / "manifest.json"


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
        from Code.Retro.Manifest import load as load_manifest
        from Code.Retro.Rom import parse_amiga_hunk
        from Code.Retro.Traps import AmigaTraps

        logger.info("loading ROM from %s", self._rom_path)
        manifest = load_manifest(_MANIFEST_PATH)
        manifest.verify(self._rom_path)

        rom_data = self._rom_path.read_bytes()
        regions = parse_amiga_hunk(rom_data)

        cpu: Cpu = Unicorn68k()
        for region in regions:
            cpu.map_region(region.base, region.size)
            cpu.mem_write(region.base, region.data)

        traps = AmigaTraps(cpu)
        traps.install()

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

        logger.debug("starting emulation from 0x%X", AI_INIT_ADDR)
        cpu.emu_start(AI_INIT_ADDR, until=0xFFFFFFFF, count=0)

        move = bridge.read_best_move()
        if move is None:
            raise ThinkError(
                "emulation completed without writing a best move to AI_BEST_MOVE_ADDR"
            )

        logger.debug("best move: %s", move.to_uci())
        return ThinkResult(move=move, level=request.level, instructions=0)
