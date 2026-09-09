"""
bin/Code/Retro/Uci.py — UCI protocol shim for the Retro Engine.

Implements the minimal UCI subset needed to register Battle Chess as a fixed-Elo
engine in Lucas Chess:

    uci / isready / setoption / position / go / stop / quit

When no ROM is configured, ``go`` returns ``bestmove 0000`` with an info-string
error rather than crashing (FR-2 — graceful degradation).

**Input/Output seam** — :class:`UciSession` accepts any pair of ``IO[str]``
objects so unit tests can inject ``io.StringIO`` instead of stdin/stdout.

:spec: feature_spec.md §8, FR-1, FR-2, FR-6, FR-7, N-RETRO-10
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import IO

from Code.Retro.Think import ThinkRequest, ThinkSession
from Code.Retro.Types import Level

logger = logging.getLogger(__name__)

_ENGINE_NAME = "Battle Chess Retro Engine"
_ENGINE_AUTHOR = "Interplay / Dragon (original); Caissa wrapper"

_STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_DEFAULT_OPTIONS: dict[str, object] = {
    "EmuLevel": 1,
    "EmuClockRate": 100,
    "EmuStrictOriginal": True,
    "EmuRomPath": "",
}

_OPTION_LINES = [
    "option name EmuLevel type spin default 1 min 1 max 9",
    "option name EmuClockRate type spin default 100 min 1 max 200",
    "option name EmuStrictOriginal type check default true",
    "option name EmuRomPath type string default <empty>",
]


class UciSession:
    """Stateful UCI protocol session.

    :param inp: Input stream (default: sys.stdin).
    :param out: Output stream (default: sys.stdout).
    """

    def __init__(
        self,
        inp: IO[str] | None = None,
        out: IO[str] | None = None,
    ) -> None:
        self._inp = inp or sys.stdin
        self._out = out or sys.stdout
        self._options: dict[str, object] = dict(_DEFAULT_OPTIONS)
        self._fen: str = _STARTPOS_FEN
        self._moves: list[str] = []
        self._session: ThinkSession | None = None

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _emit(self, line: str) -> None:
        self._out.write(line + "\n")
        self._out.flush()

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _handle_uci(self) -> None:
        self._emit(f"id name {_ENGINE_NAME}")
        self._emit(f"id author {_ENGINE_AUTHOR}")
        for line in _OPTION_LINES:
            self._emit(line)
        self._emit("uciok")

    def _handle_isready(self) -> None:
        self._emit("readyok")

    def _handle_setoption(self, rest: str) -> None:
        # setoption name <name> value <value>
        parts = rest.split()
        try:
            name_idx = parts.index("name") + 1
        except ValueError:
            return
        try:
            value_idx = parts.index("value") + 1
        except ValueError:
            return

        name_parts = parts[name_idx:parts.index("value")]
        name = " ".join(name_parts)
        value_str = " ".join(parts[value_idx:])

        if name == "EmuLevel":
            try:
                self._options["EmuLevel"] = int(value_str)
            except ValueError:
                pass
        elif name == "EmuClockRate":
            try:
                rate = int(value_str)
                if self._options.get("EmuStrictOriginal") and rate != 100:
                    self._emit(
                        f"info string error: EmuStrictOriginal is true; "
                        f"EmuClockRate must remain 100 (got {rate})"
                    )
                    return
                self._options["EmuClockRate"] = rate
            except ValueError:
                pass
        elif name == "EmuStrictOriginal":
            self._options["EmuStrictOriginal"] = value_str.lower() in ("true", "1", "yes")
        elif name == "EmuRomPath":
            self._options["EmuRomPath"] = value_str
            self._session = None  # invalidate cached session

    def _handle_position(self, rest: str) -> None:
        parts = rest.strip().split()
        if not parts:
            return

        if parts[0] == "startpos":
            self._fen = _STARTPOS_FEN
            self._moves = parts[2:] if len(parts) > 2 and parts[1] == "moves" else []
        elif parts[0] == "fen":
            # FEN fields: up to 6 space-separated tokens, then optional "moves"
            fen_parts = []
            moves_start = len(parts)
            for i, p in enumerate(parts[1:], 1):
                if p == "moves":
                    moves_start = i
                    break
                fen_parts.append(p)
            self._fen = " ".join(fen_parts)
            self._moves = parts[moves_start + 1:] if moves_start < len(parts) else []

    def _handle_go(self, _rest: str) -> None:
        rom_path_str = str(self._options.get("EmuRomPath", "")).strip()
        if not rom_path_str:
            from Code.Retro.Manifest import default_rom_path
            rom_path_str = default_rom_path() or ""
        if not rom_path_str:
            self._emit("info string error: no ROM configured; set EmuRomPath via setoption")
            self._emit("bestmove 0000")
            return

        rom_path = Path(rom_path_str)
        if self._session is None:
            self._session = ThinkSession(rom_path=rom_path)

        try:
            level = Level(int(self._options.get("EmuLevel", 1)))
        except (ValueError, KeyError):
            level = Level.L1

        # Compute computer_color from initial FEN + move parity so it is
        # correct even when python-chess is unavailable.  Each applied half-move
        # flips the active color; an odd number of moves means the side has
        # changed from whatever the FEN says.
        _fen_fields0 = self._fen.split()
        _initial_active = _fen_fields0[1] if len(_fen_fields0) > 1 else "w"
        if len(self._moves) % 2 == 1:
            _active = "b" if _initial_active == "w" else "w"
        else:
            _active = _initial_active
        computer_color = 0 if _active == "w" else 1

        # Apply move list to get actual position FEN before calling the AI.
        fen = self._fen
        if self._moves:
            try:
                import chess as _chess  # noqa: PLC0415
                _board = _chess.Board(fen)
                for _mv in self._moves:
                    _board.push_uci(_mv)
                fen = _board.fen()
            except Exception as exc:  # noqa: BLE001
                logger.warning("move application failed (%s); using base FEN", exc)

        try:
            result = self._session.think(
                ThinkRequest(fen=fen, level=level, computer_color=computer_color)
            )
            uci = result.move.to_uci() if result.move else "0000"
        except Exception as exc:  # noqa: BLE001
            logger.error("think() failed: %s", exc, exc_info=True)
            self._emit(f"info string error: {exc}")
            uci = "0000"

        self._emit(f"bestmove {uci}")

    def _handle_stop(self) -> None:
        pass  # no background search to stop in Phase 8

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Read lines from *inp* and process UCI commands until ``quit``."""
        for raw in self._inp:
            line = raw.strip()
            if not line:
                continue
            logger.debug("< %s", line)
            cmd, _, rest = line.partition(" ")
            if cmd == "uci":
                self._handle_uci()
            elif cmd == "isready":
                self._handle_isready()
            elif cmd == "setoption":
                self._handle_setoption(rest)
            elif cmd == "position":
                self._handle_position(rest)
            elif cmd == "go":
                self._handle_go(rest)
            elif cmd == "stop":
                self._handle_stop()
            elif cmd == "quit":
                break
            else:
                logger.debug("ignored unknown command: %r", cmd)


def _identify(path_str: str) -> None:
    """Print identification information for an Amiga HUNK binary.

    Outputs: sha256, file size, packer detection (if any), and the hunk table
    parsed from the binary header.  Also checks the manifest for a matching entry.

    :param path_str: Path to the binary to identify.
    """
    import hashlib

    from Code.Retro.Rom import detect_packer, parse_amiga_hunk

    path = Path(path_str)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"path:    {path}")
    print(f"size:    {len(data)} bytes")
    print(f"sha256:  {digest}")

    packer = detect_packer(data)
    if packer:
        print(f"packer:  {packer} — binary must be unpacked before use")
        return

    try:
        regions = parse_amiga_hunk(data)
        print(f"hunks:   {len(regions)} loadable region(s)")
        for i, r in enumerate(regions):
            print(f"  hunk {i}: {r.label:10s}  load_addr=0x{r.load_address:06X}"
                  f"  size={r.size} bytes  file_offset={r.offset}")
    except Exception as exc:  # noqa: BLE001
        print(f"parse error: {exc}")

    # Manifest lookup
    try:
        from Code.Retro.Manifest import load as load_manifest
        _MANIFEST = Path(__file__).parents[3] / "Resources" / "Retro" / "manifest.json"
        entries = load_manifest(_MANIFEST)
        match = next((e for e in entries if e.get("sha256") == digest), None)
        if match:
            print(f"manifest: MATCH — {match.get('label', '(no label)')}")
            print(f"          supported={match.get('supported')}")
        else:
            print("manifest: NOT IN MANIFEST — unknown binary")
    except Exception as exc:  # noqa: BLE001
        print(f"manifest: (lookup failed: {exc})")


def main(inp: IO[str] | None = None, out: IO[str] | None = None) -> None:
    """Entry point for the ``caissa-retro`` tool.

    Supports an optional sub-command::

        tools/caissa-retro identify /path/to/binary

    Without a sub-command, starts a UCI session on stdin/stdout.

    :param inp: Input stream override (for testing, UCI mode only).
    :param out: Output stream override (for testing, UCI mode only).
    """
    if len(sys.argv) >= 2 and sys.argv[1] == "identify":
        if len(sys.argv) < 3:
            print("usage: caissa-retro identify <path>", file=sys.stderr)
            sys.exit(1)
        _identify(sys.argv[2])
        return

    UciSession(inp=inp, out=out).run()
