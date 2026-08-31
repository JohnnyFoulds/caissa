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
from Code.Retro.Bridge import (
    AI_BEST_MOVE_ADDR, AI_OUTER_DRIVER_ADDR, BOARD_ARRAY_ADDR, Bridge,
    PLAYER_TYPE_BASE,
    flip_fen as _flip_fen, flip_sq88 as _flip_sq88,
)
from Code.Retro.Cpu import HOOK_CODE, HOOK_MEM_INVALID, HOOK_MEM_WRITE, Cpu
from Code.Retro.Errors import EmulatorUnavailableError, RomNotFoundError, ThinkError
from Code.Retro.Types import Level, MoveSpec, ThinkResult

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

# Safety cap: the AI runs ~88k write events at 1 ply; budget 500 million instructions.
_MAX_INSTRUCTIONS: int = 500_000_000

# Amiga OS stubs that crash if executed — pop return address and return immediately.
# Confirmed from recon: 0x8820 timer/event, 0x8D32/0x7CCE/0x857E pre-search inits,
# 0x005A event pump, 0x015C/0x00E4/0x0138/0x17D2 other OS stubs.
# 0x008A = ElapsedTime/TC stub: handled separately by _hook_tc (counts invocations,
#          sets abort flag after threshold, then NOOPs) — NOT in BYPASS_NOOP.
_BYPASS_NOOP: frozenset[int] = frozenset({
    # 0x000C = A4-relative OS call (offset -0x7FF2) — timer/event check.
    # 0x013E = A4-relative OS call from 0x84D4 (dirty path); added defensively.
    # 0x0036 = Amiga OS timer-rearm stub called from 0xDE7A when not yet aborted.
    # 0x0084 = Amiga OS elapsed-time stub called from 0xDE7A before abort check.
    0x000C, 0x013E, 0x0036, 0x0084,
    0x8820, 0x8D32, 0x7CCE, 0x857E, 0x005A, 0x015C, 0x00E4, 0x0138, 0x17D2,
})

# TC stub address: called from 0xC2C8 as `jsr -$7f74(a4)` — fires once at the
# start of the inner search loop (when [0x48B6]=0x0278 ≥ depth param).  Does NOT
# set abort — the real abort mechanism is _hook_de7a below.
_TC_ADDR: int = 0x008A

# 0xDE7A = the search-iteration handler called repeatedly from the inner loop
# (0xC2CE-0xC2F2).  Each invocation drives one call to 0xDD7E (alpha-beta tree
# traversal) then updates state.  Setting [_ABORT_FLAG_ADDR]=1 before 0xDE7A
# entry causes 0xC300 inside 0xDE7A to return D0≠0, which clears [0x4A5E] and
# makes the inner loop exit cleanly → 0xC198 returns → phases 1+2 run.
_DE7A_ADDR: int = 0xDE7A

# [0x8270] = A4+0x0272 = ROM code bytes at game-load time (value 0x0003).
# The inner loop (0xC2D4) and outer-loop shortcuts (0xC25E, 0xC294) treat a
# non-zero value as "game-state complete → exit immediately".  Zero it before
# each search so the iteration loop enters and uses _hook_de7a for termination.
_SEARCH_COMPLETE_FLAG_ADDR: int = 0x8270

# DE7A invocation thresholds per level.  One 0xDE7A invocation = one call to
# 0xDD7E (the alpha-beta tree walk).  Setting abort after N invocations lets
# the AI_INIT inner search (0xC198) run N alpha-beta passes before the loop
# exits and phase 1 takes over.  Phase 1's own search is driven by [0x48BA]
# (see _PHASE1_EVAL_CTR_ADDR), not by DE7A.  These values let phase 0 do a
# meaningful depth-1 pass before handing off; calibrate via Phase B RPA runs.
_LEVEL_DE7A_THRESHOLD: dict[int, int] = {
    1: 30, 2: 60, 3: 120, 4: 200,
    5: 350, 6: 600, 7: 1000, 8: 1500, 9: 2200,
}

# Phase-1 evaluation counter: [0x48BA].  0x88DE (called from phase 1 via
# JSR 0x8876) increments this each entry; phase 1 at 0x8392 checks
# [0x48BA] < 0x78 (120) to decide whether to run JSR 0xA266 (real search).
# BSS pre-init sets this to 0x0278 (632), which is above the 120 threshold,
# so the search is immediately skipped.  Zero it before each think call so
# phase 1 can do up to 120 evaluation passes before entering the "done" path.
_PHASE1_EVAL_CTR_ADDR: int = _A4_VALUE - 0x3744   # 0x48BA

# Phase-1 position-index counter: [0x3320].  Used in phase 1 at 0x8358 to
# index a game-state table; 0x88DE increments it alongside [0x48BA].
# BSS pre-init of 0x0278 causes an out-of-range table index.  Zero it.
_PHASE1_POS_IDX_ADDR: int = _A4_VALUE - 0x4CDE    # 0x3320

# Abort flag: [0x4A4A] tested at 0xC2CE (search exits if non-zero).
# A4 - 0x35B4 = 0x7FFE - 0x35B4 = 0x4A4A.
# The ROM initialises this to 0xFFFC; must be zeroed before each search.
_ABORT_FLAG_ADDR: int = _A4_VALUE - 0x35B4  # 0x4A4A

# Wait/timer flag: [0x4A92] checked at 0xCB18 before the actual search begins.
# A4 - 0x356C = 0x7FFE - 0x356C = 0x4A92.
# The outer driver loops at 0xCB18-0xCB2E calling the Amiga timer stub at
# 0x000C until [0x4A92] becomes 0 (timer expired).  We pre-zero it so the
# wait loop exits immediately and the real search starts.
_WAIT_FLAG_ADDR: int = _A4_VALUE - 0x356C  # 0x4A92

# Loop-continue flag: outer driver loops while [0x4A5A]==2.
# Setting this to 0 forces the outer driver to exit after the current phase.
_LOOP_FLAG_ADDR: int = _A4_VALUE - 0x35A4  # 0x4A5A

# Final best-move address: written by best_move_writer (0x0126) during phase-2 cleanup.
# Field order: from_sq (offset 0), to_sq (offset 2) — opposite of AI_BEST_MOVE_ADDR.
_AI_BEST_MOVE_FINAL_ADDR: int = _A4_VALUE - 0x49A4  # 0x365A

# Sentinel to_sq value for search-stack initialisation.
# The inner search at 0xD99A checks BOARD_ARRAY[to_sq*4]; if non-zero (any occupied
# square) it skips writing the best move.  Clearing to_sq=0 maps to a1 (Rook) which
# is always occupied.  0x1000*4=0x4000: BOARD_ARRAY+0x4000=0x70F4, outside BSS
# (which ends at 0x5FFE), so the _mem_invalid hook maps that page as zeros → check
# passes and the search can write a move.
_SEARCH_STACK_SENTINEL: int = 0x1000

# Safety ceiling: outer driver loop passes allowed before forced exit.
# We stop at 0x81F2 (after phase 0) if a valid move was found, so this is only
# a backstop in case the 0x81F2 stop never fires.
_OUTER_LOOP_PASSES: dict[int, int] = {
    1: 2, 2: 2, 3: 2, 4: 2, 5: 2,
    6: 2, 7: 2, 8: 2, 9: 2,
}

# [0x07D2] is 2 bytes before PLAYER_TYPE_BASE (0x07D4).  When non-zero (ROM code
# bytes at that address), AI_INIT at 0x8250 branches to the dirty path (0x8262+)
# which calls the search with a BSS-sentinel parameter and invokes OS stubs not
# in BYPASS_NOOP (including 0x013E via 0x84D4).  Zero it so AI_INIT always takes
# the clean path: CLR.W [0x4A50]; MOVE.W #1, -(A7); JSR 0xC198; BRA 0x82C4.
_AI_INIT_PATH_FLAG_ADDR: int = 0x07D2

# BSS region: [0x3000..0x5FFE] initialised to 0x0278 by the game's own BSS init
# routine (0x8820), which we BYPASS_NOOP.  Pre-init in Python before each search
# so the hash/transposition table contains the correct "empty entry" sentinel.
_BSS_START: int = 0x3000
_BSS_END: int   = 0x5FFE  # inclusive, word-aligned; size = 0x3000 bytes

# Address of the abort-flag check inside alpha-beta (confirmed from disassembly).
# Hooked to count search nodes (for diagnostics / fallback snapshot).
_ABORT_CHECK_ADDR: int = 0x0C2CE


def _scan_cmpiw(code: bytes, base: int = 0) -> dict[int, tuple]:
    """Scan *code* for 6-byte ``cmpi.w`` instructions mis-decoded by Unicorn M68K.

    Unicorn M68K decodes 6-byte ``cmpi.w #imm, (d16,An)`` and
    ``cmpi.w #imm, (An,Xn)`` as 4 bytes, leaving the trailing 2 bytes to
    execute as a separate instruction.  Many trailing pairs cause
    divide-by-zero or F-line traps that crash the emulator.

    Returns a dict mapping each instruction address to
    ``(mode, an_reg, imm16_unsigned, d16_signed_or_ext_word)`` so that
    :func:`think` can register a correcting per-address hook for each one.

    :param code: ROM bytes (HUNK_CODE content).
    :param base: Virtual load address of *code* (0 for Battle Chess).
    """
    # Opcodes for 6-byte word-size immediate instructions with (d16,An) or (An,Xn) EA.
    # Unicorn M68K decodes these as 4 bytes, leaving 2 trailing bytes to execute.
    # op key → instruction semantics for the hook dispatcher.
    _OP_MAP_D16: dict[int, str] = {
        0x00: 'ori', 0x02: 'andi', 0x04: 'subi', 0x06: 'addi', 0x0A: 'eori', 0x0C: 'cmp',
    }
    result: dict[int, tuple] = {}
    n = len(code)
    i = 0
    while i < n - 5:
        b0 = code[i]
        b1 = code[i + 1]
        op = _OP_MAP_D16.get(b0)
        if op is not None:
            if 0x68 <= b1 <= 0x6F:  # op.w #imm, (d16, An)
                an_reg = b1 & 0x07
                imm16 = (code[i + 2] << 8) | code[i + 3]
                raw_d16 = (code[i + 4] << 8) | code[i + 5]
                d16 = raw_d16 if raw_d16 < 0x8000 else raw_d16 - 0x10000
                result[base + i] = (op, 'd16', an_reg, imm16, d16)
                i += 6
                continue
            elif 0x70 <= b1 <= 0x77:  # op.w #imm, (An, Xn)
                an_reg = b1 & 0x07
                imm16 = (code[i + 2] << 8) | code[i + 3]
                ext = (code[i + 4] << 8) | code[i + 5]
                result[base + i] = (op, 'anXn', an_reg, imm16, ext)
                i += 6
                continue
        i += 2  # M68K instructions are always word-aligned
    return result


def _fallback_legal_move(fen: str, computer_color: int) -> MoveSpec | None:
    """Return the first python-chess legal move for *computer_color* in *fen*.

    Last-resort fallback when the emulated AI cannot produce a valid move.
    Logs a warning so callers know the move came from the fallback path.
    """
    try:
        import chess as _chess
        board = _chess.Board(fen)
        legal = list(board.legal_moves)
        if not legal:
            return None
        m = legal[0]
        from_sq = (m.from_square // 8) * 16 + (m.from_square % 8)
        to_sq   = (m.to_square   // 8) * 16 + (m.to_square   % 8)
        logger.warning(
            "AI emulation produced no valid move; python-chess fallback: %s%s",
            _chess.square_name(m.from_square),
            _chess.square_name(m.to_square),
        )
        return MoveSpec(from_sq=from_sq, to_sq=to_sq, flags=0, piece=0, legal=1)
    except Exception as exc:  # noqa: BLE001
        logger.error("fallback move generation failed: %s", exc, exc_info=True)
        return None


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
        self._cmpiw_info: dict | None = None   # cached cmpiw scan results

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
            # Pre-scan for all 6-byte cmpi.w instructions mis-decoded by Unicorn.
            # Scan every executable region (HUNK_CODE + DRAGON_CRACK).
            _all_cmpiw: dict = {}
            for _r in self._rom_regions:
                if _r.label in ("HUNK_CODE", "DRAGON_CRACK") and _r.size > 0:
                    _all_cmpiw.update(
                        _scan_cmpiw(
                            self._rom_bytes[_r.offset:_r.offset + _r.size],
                            base=_r.load_address,
                        )
                    )
            self._cmpiw_info = _all_cmpiw
            logger.info("cmpi.w scan: %d 6-byte instructions to patch", len(self._cmpiw_info))

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

        # Sentinel page: the AI returns here when its outer function exits normally.
        # Also absorbs stray writes through garbage index registers (e.g. the
        # CLR.B (A0+D1.L) at 0x9BAE during the hash-table build loop when D1 is
        # computed from the transposition table).  Unicorn M68K raises UC_ERR_EXCEPTION
        # (bus error) rather than UC_ERR_MEM_WRITE_UNMAPPED for high-address writes,
        # so HOOK_MEM_INVALID is bypassed — pre-map the region to prevent the crash.
        _SENTINEL_PAGE = _SENTINEL & ~0xFFFF  # 0xFFFF0000
        cpu.map_region(_SENTINEL_PAGE, 0x10000)
        cpu.mem_write(_SENTINEL_PAGE, bytes(0x10000))

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

        # The AI's TC abort mechanism requires PLAYER2_COLOR=1 (Black).
        # For White-to-move positions, mirror the board so the AI sees a
        # Black-to-move problem; flip the result move back afterwards.
        _board_flipped = (request.computer_color == 0)
        if _board_flipped:
            _search_fen = _flip_fen(request.fen)
            _search_cc  = 1
        else:
            _search_fen = request.fen
            _search_cc  = request.computer_color

        # Pre-initialise the BSS hash/transposition table to 0x0278 ("empty entry").
        # The game's BSS init routine (0x8820) normally does this, but we BYPASS_NOOP
        # it to avoid its 10-16M instruction overhead.  write_position() overwrites
        # the chess-board portion of BSS, so BSS pre-init must come first.
        bss_size = (_BSS_END - _BSS_START + 2)
        cpu.mem_write(_BSS_START, b"\x02\x78" * (bss_size // 2))

        # Phase-1 evaluation counter and position-index start at 0x0278 (BSS
        # pre-init value).  BSS pre-init = 0x0278 → [0x48BA]=632 which is already
        # above the 120 threshold checked at 0x8392, so the real phase-1 search
        # (JSR 0xA266) is skipped entirely.  Zero both counters so the search runs.
        cpu.mem_write(_PHASE1_EVAL_CTR_ADDR, struct.pack(">H", 0))
        cpu.mem_write(_PHASE1_POS_IDX_ADDR,  struct.pack(">H", 0))

        # Zero the abort flag (ROM initialises it to 0xFFFC; non-zero makes the
        # search exit at the very first abort-check, before any moves are evaluated).
        cpu.mem_write(_ABORT_FLAG_ADDR, struct.pack(">H", 0))
        # Zero the wait/timer flag so the pre-search timer loop at 0xCB18 exits
        # immediately instead of spinning until the Amiga timer expires.
        cpu.mem_write(_WAIT_FLAG_ADDR, struct.pack(">H", 0))
        # The outer driver loops while [0x4A5A]==2.  The caller (the Amiga game UI)
        # normally writes 2 here before invoking the driver; in our headless setup
        # we must do it explicitly, otherwise the BSS init value (0x0278) causes the
        # loop to exit on the very first check, before any phase runs.
        cpu.mem_write(_LOOP_FLAG_ADDR, struct.pack(">H", 2))

        # Force AI_INIT to take the clean path (depth=1 call to 0xC198).
        cpu.mem_write(_AI_INIT_PATH_FLAG_ADDR, struct.pack(">H", 0))
        # [0x8270] = ROM code bytes (0x0003) — the inner search loop exits when
        # non-zero and the outer-loop body shortcuts directly to TC.  Zero it so
        # the search enters the 0xDE7A-based iteration loop.
        cpu.mem_write(_SEARCH_COMPLETE_FLAG_ADDR, struct.pack(">H", 0))

        bridge.clear_best_move()
        bridge.write_position(_search_fen)
        bridge.set_computer_color(_search_cc)
        # The outer driver's loop condition (0x8226) branches back through all 3
        # phases only when player_type[player2_color] = 1 (Human).  With the default
        # value of 2 (Computer), it exits after phase 0 (init only) and the search
        # (phase 1) and move-selection (phase 2) never run.  Override to 1 so that
        # one emu_start call drives all three phases to completion.
        cpu.mem_write(PLAYER_TYPE_BASE + _search_cc * 2, struct.pack(">H", 1))
        # Clear the final-result slot so a stale value isn't mistaken for the result.
        cpu.mem_write(_AI_BEST_MOVE_FINAL_ADDR, b"\x00" * 8)
        # Initialise search-stack entries 0x67..0x78 (18 × 8 bytes, starting at
        # _AI_BEST_MOVE_FINAL_ADDR = 0x365A) with sentinel to_sq=_SEARCH_STACK_SENTINEL.
        # The inner search at 0xD99A checks BOARD_ARRAY[to_sq*4]: with to_sq=0 (from
        # clear_best_move) that maps to a1 which has a Rook → non-zero → bne 0xDAC4
        # (no-write path) fires every time, so the search never records a best move.
        # The sentinel 0x1000 maps BOARD_ARRAY+0x4000 = 0x70F4, outside BSS (ends at
        # 0x5FFE), so _mem_invalid maps that page as zeros → check passes.
        _sentinel_entry = struct.pack(">HH4x", _SEARCH_STACK_SENTINEL, _SEARCH_STACK_SENTINEL)
        cpu.mem_write(_AI_BEST_MOVE_FINAL_ADDR, _sentinel_entry * 18)

        # Initialise registers and place the sentinel return address.
        cpu.reg_write("A4", _A4_VALUE)
        sp = _STACK_TOP - 4
        cpu.mem_write(sp, struct.pack(">I", _SENTINEL))
        cpu.reg_write("A7", sp)

        # Snapshot of the root board (may be the flipped board), taken before
        # emulation.  The search modifies BOARD_ARRAY_ADDR in-place during
        # make/unmake, so we must capture it here.
        _root_board: bytes = bytes(cpu.mem_read(BOARD_ARRAY_ADDR, 128 * 4))

        _mapped: set[int] = set()
        # Outer driver loop pass counter (safety backstop only — TC is primary).
        _loop_count: list[int] = [0]
        _loop_820c_fires: list[int] = [0]  # every time hook at 0x820C fires
        _diag_81f2_fires: list[int] = [0]  # 0x81F2 reached (BRA->0x820C should follow)
        _diag_c198_fires: list[int] = [0]  # 0xC198 search entry reached
        _loop_threshold = _OUTER_LOOP_PASSES.get(request.level.value, 9999)
        # TC invocation counter — TC fires once before the inner loop starts.
        # Does NOT set abort; abort is set by _hook_de7a.
        _tc_count: list[int] = [0]
        # DE7A invocation counter — each call drives one alpha-beta pass.
        # Abort flag is set when _de7a_count reaches _de7a_threshold.
        _de7a_count: list[int] = [0]
        _de7a_threshold = _LEVEL_DE7A_THRESHOLD.get(request.level.value, 1)
        # Search node counter (visits to 0x0C2CE) — for diagnostics only.
        _node_count: list[int] = [0]
        # _write_snapshot — last root-valid write to AI_BEST_MOVE_ADDR;
        #                   fallback for positions where the outer driver exits
        #                   before writing a final result.
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
            if from_color != _search_cc:
                return False
            if dest_type != 0 and dest_color == _search_cc:
                return False
            from_type = _root_board[from_sq * 4]
            if (from_type == 6
                    and (to_sq & 0x0F) == (from_sq & 0x0F)
                    and dest_type != 0):
                return False
            return True

        def _hook_diag_81f2(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # Fires when 0x81F2 is reached (AI_INIT / phase-0 has just returned).
            # Phase 1 runs 9999+ times and corrupts AI_BEST_MOVE_ADDR with garbage;
            # stop now if phase 0 already wrote a valid move there.
            _diag_81f2_fires[0] += 1
            try:
                cpu.mem_write(_ABORT_FLAG_ADDR, struct.pack(">H", 0))
                cpu.mem_write(_SEARCH_COMPLETE_FLAG_ADDR, struct.pack(">H", 0))
                raw = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 4))
                _to, _from = struct.unpack(">HH", raw)
                if (_to != _SEARCH_STACK_SENTINEL and _from != _SEARCH_STACK_SENTINEL
                        and 0 < _to <= 0x77 and not (_to & 0x88)
                        and 0 <= _from <= 0x77 and not (_from & 0x88)
                        and _is_root_valid(_to, _from)):
                    cpu.emu_stop()
            except Exception:
                pass

        def _hook_diag_c198(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            _diag_c198_fires[0] += 1  # fires on search entry

        def _hook_loop_check(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # Unicorn M68K mis-decodes `cmpi.w #2, -$35a4(a4)` (6 bytes) as 4 bytes,
            # leaving trailing bytes `ca 5c` to execute as `and.w (a4)+, d5` — which
            # corrupts A4 by +2 each outer loop iteration.
            # We implement cmpi.w + bne.b manually and redirect PC.
            # Additionally: count outer driver loop passes and exit at the level threshold
            # instead of relying on the game's own TC/timer mechanism.
            _loop_820c_fires[0] += 1
            try:
                a4_val = cpu.reg_read("A4")
                loop_flag_addr = (a4_val - 0x35A4) & 0xFFFFFFFF
                raw = bytes(cpu.mem_read(loop_flag_addr, 2))
                loop_flag = (raw[0] << 8) | raw[1]
                if loop_flag != 2:
                    cpu.reg_write("PC", 0x8228)
                    return
                _loop_count[0] += 1
                if _loop_count[0] >= _loop_threshold:
                    cpu.reg_write("PC", 0x8228)  # threshold reached — exit outer driver
                else:
                    cpu.reg_write("PC", 0x8214)  # continue to player check
            except Exception:
                cpu.reg_write("PC", 0x8228)

        def _hook_player_check(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # Unicorn M68K mis-decodes `cmpi.w #1, (a0, d0.l)` (6 bytes) as 4 bytes,
            # trailing `08 00` bytes corrupt A4 by +2.
            # A0 = player_type_base, D0 = player2_color * 2 (set at 0x8214-0x821C).
            # We implement cmpi.w + beq.b manually and redirect PC.
            try:
                a0_val = cpu.reg_read("A0")
                d0_val = cpu.reg_read("D0")
                d0_signed = d0_val if d0_val < 0x80000000 else d0_val - 0x100000000
                cmp_addr = (a0_val + d0_signed) & 0xFFFFFFFF
                raw = bytes(cpu.mem_read(cmp_addr, 2))
                player_type_val = (raw[0] << 8) | raw[1]
                cpu.reg_write("PC", 0x81E4 if player_type_val == 1 else 0x8228)
            except Exception:
                cpu.reg_write("PC", 0x8228)

        def _hook_abort_check(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # Called at 0x0C2CE (tst.w [0x4A4A]).  Count search nodes for diagnostics
            # and snapshot AI_BEST_MOVE_ADDR as a fallback in case phase 2 never writes
            # _AI_BEST_MOVE_FINAL_ADDR.
            # Termination is now handled by _hook_tc (abort flag mechanism), NOT
            # emu_stop() — emu_stop() halts mid-phase-1 before phase 2 runs, causing
            # the final result address to stay zeroed.
            _node_count[0] += 1
            try:
                raw = bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 4))
                _to_sq, _from_sq = struct.unpack(">HH", raw)
                if _is_root_valid(_to_sq, _from_sq):
                    _write_snapshot[0] = raw
            except Exception:
                pass

        def _hook_noop(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            try:
                a7 = cpu.reg_read("A7")
                ret = struct.unpack(">I", bytes(cpu.mem_read(a7, 4)))[0]
                cpu.reg_write("A7", a7 + 4)
                cpu.reg_write("PC", ret)
            except Exception:
                pass

        def _hook_tc(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # TC (ElapsedTime) stub at 0x008A — fires once before the inner loop
            # starts (when outer-loop BGE at 0xC2A2 triggers with [0x48B6]=0x0278).
            # Does NOT set abort; abort is owned by _hook_de7a.  Just NOOP it.
            _tc_count[0] += 1
            try:
                a7 = cpu.reg_read("A7")
                ret = struct.unpack(">I", bytes(cpu.mem_read(a7, 4)))[0]
                cpu.reg_write("A7", a7 + 4)
                cpu.reg_write("PC", ret)
            except Exception:
                pass

        def _hook_de7a(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # 0xDE7A = search-iteration handler.  Each invocation calls 0xDD7E
            # (alpha-beta tree walk) then checks timer/abort state.  After
            # _de7a_threshold invocations, set the abort flag so 0xC300 inside
            # 0xDE7A returns D0≠0, which clears [0x4A5E] and lets the inner loop
            # exit → 0xC198 returns → outer driver phases 1+2 run → best move written.
            # Do NOT redirect PC — let 0xDE7A execute normally with abort=1 set.
            _de7a_count[0] += 1
            if _de7a_count[0] >= _de7a_threshold:
                try:
                    cpu.mem_write(_ABORT_FLAG_ADDR, struct.pack(">H", 1))
                except Exception:
                    pass

        # Precomputed cmpi.w info for this session (None when using FakeCpu).
        _cmpiw_info = self._cmpiw_info or {}

        def _hook_cmpiw(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # Implement the 6-byte instruction that Unicorn mis-decodes as 4 bytes.
            # Unicorn correctly computes the EA and performs the data operation but
            # advances PC by only 4, leaving 2 trailing bytes to execute. This hook
            # fires before execution, performs the correct operation, and skips to addr+6.
            info = _cmpiw_info.get(addr)
            if info is None:
                return
            op, mode, an_reg, imm16, d16_or_ext = info
            try:
                an_val = cpu.reg_read(f"A{an_reg}")
                if mode == 'd16':
                    ea_addr = (an_val + d16_or_ext) & 0xFFFFFFFF
                else:
                    ext = d16_or_ext
                    xn_is_an = (ext >> 15) & 1
                    xn_reg   = (ext >> 12) & 0x07
                    xn_long  = (ext >> 11) & 1
                    # 68000 does not have a scale field — bits 9-8 are reserved.
                    # Always use scale=0 (index * 1).
                    disp8    = ext & 0xFF
                    if disp8 >= 0x80:
                        disp8 -= 256
                    xn_name = f"A{xn_reg}" if xn_is_an else f"D{xn_reg}"
                    xn_raw = cpu.reg_read(xn_name)
                    if xn_long:
                        if xn_raw >= 0x80000000:
                            xn_raw -= 0x100000000
                    else:
                        xn_raw = xn_raw & 0xFFFF
                        if xn_raw >= 0x8000:
                            xn_raw -= 0x10000
                    ea_addr = (an_val + xn_raw + disp8) & 0xFFFFFFFF
                if op == 'cmp':
                    raw = bytes(cpu.mem_read(ea_addr, 2))
                    ea_u = (raw[0] << 8) | raw[1]
                    result_u = (ea_u - imm16) & 0xFFFF
                    n_flag = 1 if result_u >= 0x8000 else 0
                    z_flag = 1 if result_u == 0 else 0
                    c_flag = 1 if ea_u < imm16 else 0
                    ea_s  = ea_u  if ea_u  < 0x8000 else ea_u  - 0x10000
                    imm_s = imm16 if imm16 < 0x8000 else imm16 - 0x10000
                    v_flag = 1 if not (-0x8000 <= ea_s - imm_s <= 0x7FFF) else 0
                    sr_old = cpu.reg_read("SR")
                    new_sr = ((sr_old & ~0x0F) | (n_flag << 3) | (z_flag << 2) | (v_flag << 1) | c_flag) & 0xFFFF
                    cpu.reg_write("SR", new_sr)
                elif op == 'mov':
                    cpu.mem_write(ea_addr, struct.pack(">H", imm16))
                    n_flag = 1 if imm16 >= 0x8000 else 0
                    z_flag = 1 if imm16 == 0 else 0
                    sr_old = cpu.reg_read("SR")
                    new_sr = ((sr_old & ~0x0F) | (n_flag << 3) | (z_flag << 2)) & 0xFFFF
                    cpu.reg_write("SR", new_sr)
                else:
                    # Read-modify-write: ORI/ANDI/SUBI/ADDI/EORI — dispatch per op.
                    raw = bytes(cpu.mem_read(ea_addr, 2))
                    ea_u = (raw[0] << 8) | raw[1]
                    if op == 'ori':
                        result_u = (ea_u | imm16) & 0xFFFF
                    elif op == 'andi':
                        result_u = (ea_u & imm16) & 0xFFFF
                    elif op == 'eori':
                        result_u = (ea_u ^ imm16) & 0xFFFF
                    elif op == 'addi':
                        result_u = (ea_u + imm16) & 0xFFFF
                    else:  # 'subi'
                        result_u = (ea_u - imm16) & 0xFFFF
                    cpu.mem_write(ea_addr, struct.pack(">H", result_u))
                    n_flag = 1 if result_u >= 0x8000 else 0
                    z_flag = 1 if result_u == 0 else 0
                    sr_old = cpu.reg_read("SR")
                    new_sr = ((sr_old & ~0x0F) | (n_flag << 3) | (z_flag << 2)) & 0xFFFF
                    cpu.reg_write("SR", new_sr)
                cpu.reg_write("PC", addr + 6)
            except Exception:
                cpu.reg_write("PC", addr + 6)

        def _mem_write(
            _emu: object, _acc: int, addr: int, sz: int, val: int, _u: object = None
        ) -> None:
            if addr != AI_BEST_MOVE_ADDR or sz != 2:
                return
            to_sq = val & 0xFFFF
            try:
                pc = cpu.reg_read("PC")
                d1 = cpu.reg_read("D1")
                d3 = cpu.reg_read("D3")
                logger.debug(
                    "AI_BEST_MOVE write: to_sq=0x%04X pc=0x%04X d1=0x%08X d3=0x%08X nodes=%d",
                    to_sq, pc, d1, d3, _node_count[0],
                )
            except Exception:
                pass
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

        def _mem_write_final(
            _emu: object, _acc: int, addr: int, sz: int, val: int, _u: object = None
        ) -> None:
            # Fires when phase 2 writes to _AI_BEST_MOVE_FINAL_ADDR (or +2).
            # Stop emulation once BOTH from_sq and to_sq are non-zero so we
            # don't stop on partial writes (MOVE.W from_sq; not yet to_sq).
            # Guard: ignore writes before any search passes have run.
            if _de7a_count[0] < _de7a_threshold:
                return
            if val == 0:
                return
            try:
                data = bytes(cpu.mem_read(_AI_BEST_MOVE_FINAL_ADDR, 4))
                f_sq, t_sq = struct.unpack(">HH", data)
                if f_sq > 0 and t_sq > 0 and not (f_sq & 0x88) and not (t_sq & 0x88):
                    cpu.emu_stop()
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

        # --- Decompressor prefetch simulation (0x79BC and 0x79C8) ---
        # Battle Chess has a self-modifying decompressor that overwrites its own
        # instruction bytes while executing. The real 68000 has a 4-byte prefetch
        # buffer — the CPU executes old bytes while new ones are being written.
        # Unicorn has no prefetch buffer and reads fresh bytes, so it hits
        # UC_ERR_EXCEPTION on the partially-written (invalid) instructions.
        # These two hooks intercept execution at the two critical addresses and,
        # when the bytes there have been overwritten with an illegal pattern,
        # manually emulate the original ROM instruction so decompression proceeds
        # exactly as it would on real hardware.
        _orig_79bc = bytes(cpu.mem_read(0x79BC, 2))  # E5 4A  lsl.w #2, d2
        _orig_79c8 = bytes(cpu.mem_read(0x79C8, 2))  # 12 DA  move.b (a2)+, (a1)+

        def _hook_prefetch_79bc(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            # ORI/CMPI to An is always illegal in M68K.
            # Pattern: first byte 0x00 and bits 5-3 of second byte == 001 (An-direct EA).
            try:
                cur = bytes(cpu.mem_read(0x79BC, 2))
                if cur == _orig_79bc or not (cur[0] == 0x00 and (cur[1] & 0x38) == 0x08):
                    return  # original or valid new bytes — let Unicorn execute normally
                # Zeroing loop wrote a partially-invalid pattern; emulate lsl.w #2, d2.
                d2 = cpu.reg_read("D2")
                d2_word = d2 & 0xFFFF
                c_bit = (d2_word >> 14) & 1  # last bit shifted out for count=2
                result = (d2_word << 2) & 0xFFFF
                n_flag = (result >> 15) & 1
                z_flag = 1 if result == 0 else 0
                sr = cpu.reg_read("SR")
                sr = (sr & ~0x1F) | (c_bit << 4) | (n_flag << 3) | (z_flag << 2) | c_bit
                cpu.reg_write("SR", sr & 0xFFFF)
                cpu.reg_write("D2", (d2 & 0xFFFF0000) | result)
                cpu.reg_write("PC", 0x79BE)
            except Exception:
                pass

        def _hook_prefetch_79c8(_emu: object, addr: int, _sz: int, _u: object = None) -> None:
            try:
                cur = bytes(cpu.mem_read(0x79C8, 2))
                if cur == _orig_79c8:
                    return  # original bytes — let Unicorn execute normally
                # Copy loop has overwritten itself; emulate move.b (a2)+, (a1)+.
                a2 = cpu.reg_read("A2")
                a1 = cpu.reg_read("A1")
                b = bytes(cpu.mem_read(a2 & 0xFFFFFFFF, 1))[0]
                cpu.mem_write(a1 & 0xFFFFFFFF, bytes([b]))
                cpu.reg_write("A2", (a2 + 1) & 0xFFFFFFFF)
                cpu.reg_write("A1", (a1 + 1) & 0xFFFFFFFF)
                n_flag = (b >> 7) & 1
                z_flag = 1 if b == 0 else 0
                sr = cpu.reg_read("SR")
                sr = (sr & ~0x0F) | (n_flag << 3) | (z_flag << 2)
                cpu.reg_write("SR", sr & 0xFFFF)
                cpu.reg_write("PC", 0x79CA)
            except Exception:
                pass

        hooks: list[int] = []
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_loop_check,    begin=0x820C,          end=0x820C))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_player_check,  begin=0x8220,          end=0x8220))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_diag_81f2,     begin=0x81F2,          end=0x81F2))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_diag_c198,     begin=0xC198,          end=0xC198))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_abort_check,   begin=_ABORT_CHECK_ADDR, end=_ABORT_CHECK_ADDR))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_prefetch_79bc, begin=0x79BC,          end=0x79BC))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_prefetch_79c8, begin=0x79C8,          end=0x79C8))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_tc,            begin=_TC_ADDR,        end=_TC_ADDR))
        hooks.append(cpu.hook_add(HOOK_CODE, _hook_de7a,          begin=_DE7A_ADDR,      end=_DE7A_ADDR))
        for _noop_addr in _BYPASS_NOOP:
            hooks.append(cpu.hook_add(HOOK_CODE, _hook_noop, begin=_noop_addr, end=_noop_addr))
        # Register per-address CMPI.W correction hooks for all 6-byte instructions
        # that Unicorn M68K mis-decodes as 4 bytes.  Exclude 0x820C and 0x8220 which
        # are already handled by _hook_loop_check / _hook_player_check above.
        # Also exclude _TC_ADDR (0x008A) which is handled by _hook_tc above.
        for _cmpiw_addr in _cmpiw_info:
            if _cmpiw_addr not in (0x820C, 0x8220, _TC_ADDR):
                hooks.append(cpu.hook_add(HOOK_CODE, _hook_cmpiw, begin=_cmpiw_addr, end=_cmpiw_addr))
        hook_mem       = cpu.hook_add(HOOK_MEM_INVALID, _mem_invalid)
        hook_mem_write = cpu.hook_add(
            HOOK_MEM_WRITE, _mem_write,
            begin=AI_BEST_MOVE_ADDR,
            end=AI_BEST_MOVE_ADDR + 3,
        )
        hook_mem_final = cpu.hook_add(
            HOOK_MEM_WRITE, _mem_write_final,
            begin=_AI_BEST_MOVE_FINAL_ADDR,
            end=_AI_BEST_MOVE_FINAL_ADDR + 3,  # cover both from_sq (+0) and to_sq (+2)
        )
        # The ROM initialises abort_flag to 0xFFFC; clear it so the search runs.
        cpu.mem_write(_ABORT_FLAG_ADDR, struct.pack(">H", 0))
        cpu.mem_write(_WAIT_FLAG_ADDR,  struct.pack(">H", 0))
        logger.debug("starting emulation from 0x%X (level=%s, de7a_threshold=%d)",
                     AI_OUTER_DRIVER_ADDR, request.level, _de7a_threshold)
        _emu_error: Exception | None = None
        try:
            cpu.emu_start(AI_OUTER_DRIVER_ADDR, until=_SENTINEL, count=_MAX_INSTRUCTIONS)
        except Exception as _exc:
            _emu_error = _exc
            try:
                _crash_pc = cpu.reg_read("PC")
                logger.warning(
                    "emulation raised %s; crash PC=0x%X loop=%d nodes=%d",
                    _exc, _crash_pc, _loop_count[0], _node_count[0],
                )
            except Exception:
                logger.warning("emulation raised %s; attempting move recovery", _exc)
        finally:
            for _h in hooks:
                cpu.hook_del(_h)
            cpu.hook_del(hook_mem)
            cpu.hook_del(hook_mem_write)
            cpu.hook_del(hook_mem_final)
        logger.warning(
            "emulation done; loop=%d 820c=%d tc=%d de7a=%d nodes=%d 81f2=%d c198=%d "
            "final=%s best=%s a4=0x%X",
            _loop_count[0], _loop_820c_fires[0], _tc_count[0], _de7a_count[0],
            _node_count[0], _diag_81f2_fires[0], _diag_c198_fires[0],
            bytes(cpu.mem_read(_AI_BEST_MOVE_FINAL_ADDR, 4)).hex(),
            bytes(cpu.mem_read(AI_BEST_MOVE_ADDR, 4)).hex(),
            cpu.reg_read("A4"),
        )

        # Priority 1: phase-2 final result at 0x365A (from_sq @ offset 0, to_sq @ offset 2).
        # Written by best_move_writer (0x0126) during phase-2 cleanup — the actual
        # selected best move after all candidates are evaluated.
        move: MoveSpec | None = None
        _final_raw = bytes(cpu.mem_read(_AI_BEST_MOVE_FINAL_ADDR, 8))
        _final_from, _final_to = struct.unpack(">HH", _final_raw[:4])
        if (_final_from > 0 and _final_from <= 0x77 and not (_final_from & 0x88)
                and _final_to > 0 and _final_to <= 0x77 and not (_final_to & 0x88)
                and _is_root_valid(_final_to, _final_from)):
            move = MoveSpec(from_sq=_final_from, to_sq=_final_to, flags=0, piece=0, legal=1)
            logger.debug("phase2-final move: %s", move.to_uci())

        # Priority 2: direct read from AI_BEST_MOVE_ADDR (0x3662).
        # When emu_stop() halts the search mid-flight, this holds the search's last
        # committed result — prefer it over the node-snapshot which may be from an
        # earlier iteration.
        if move is None:
            _raw = bridge.read_best_move()
            if _raw is not None and _is_root_valid(_raw.to_sq, _raw.from_sq):
                move = _raw
                logger.debug("bridge-read move: %s", move.to_uci())

        # Priority 3: node-snapshot — last root-valid value seen at 0xC2CE abort check.
        # Fallback for positions where the bridge read returns garbage after search ends.
        if move is None and _write_snapshot[0] is not None:
            snap_to, snap_from = struct.unpack(">HH", _write_snapshot[0])
            move = MoveSpec(from_sq=snap_from, to_sq=snap_to, flags=0, piece=0, legal=1)
            logger.debug("node-snapshot move: %s", move.to_uci())

        if move is None:
            move = _fallback_legal_move(request.fen, request.computer_color)
        if move is None:
            raise ThinkError(
                "emulation completed without writing a best move to AI_BEST_MOVE_ADDR"
            )

        # Un-flip the move back to original board orientation when we searched
        # on the mirrored board (White-to-move positions).
        if _board_flipped and move is not None:
            move = MoveSpec(
                from_sq=_flip_sq88(move.from_sq),
                to_sq=_flip_sq88(move.to_sq),
                flags=move.flags,
                piece=move.piece,
                legal=move.legal,
            )

        # Final legality check: validate the move against python-chess before
        # returning it.  The emulated AI can produce moves that pass the 0x88
        # and color checks but are still illegal (e.g. pawn backward).
        try:
            import chess as _chess
            _pos = _chess.Board(request.fen)
            if _chess.Move.from_uci(move.to_uci()) not in _pos.legal_moves:
                logger.warning(
                    "AI returned illegal move %s; using python-chess fallback",
                    move.to_uci(),
                )
                move = _fallback_legal_move(request.fen, request.computer_color)
                if move is None:
                    raise ThinkError(
                        "emulation completed without writing a best move to AI_BEST_MOVE_ADDR"
                    )
        except (ImportError, ValueError):
            pass

        logger.debug("best move: %s", move.to_uci())
        return ThinkResult(move=move, level=request.level, instructions=0)
