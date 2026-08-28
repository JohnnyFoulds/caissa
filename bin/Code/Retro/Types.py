"""
bin/Code/Retro/Types.py — Dependency-free frozen dataclasses for the Retro Engine.

**ZERO third-party imports** — enforced by ``N-RETRO-1``.

:spec: feature_spec.md §4, N-RETRO-1
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Platform(Enum):
    """Target CPU/OS platform of the ROM binary.

    :cvar AMIGA_68K: Amiga 68000 — the primary Phase 2–8 target.
    :cvar DOS_X86: DOS 16-bit x86 — Phase 9 second target.
    """

    AMIGA_68K = "amiga_68k"
    DOS_X86 = "dos_x86"


@dataclass(frozen=True)
class RomId:
    """Immutable identifier for a verified ROM.

    :param sha256: Lowercase hex sha256 digest (64 characters).
    :param platform: CPU/OS platform this binary was built for.
    :param label: Human-readable name, e.g. ``"Battle Chess (Amiga, Dragon Inc crack)"``.
    """

    sha256: str
    platform: Platform
    label: str

    def __post_init__(self) -> None:
        """Validate the digest format.

        :raises ValueError: If ``sha256`` is not a 64-character hex string.
        """
        if len(self.sha256) != 64 or not all(c in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"sha256 must be 64 lowercase hex chars, got {self.sha256!r}")


@dataclass(frozen=True)
class MemRegion:
    """A contiguous byte range within a loaded ROM image.

    :param offset: Byte offset within the ROM file where the region starts.
    :param size: Number of bytes in the region.
    :param label: Human-readable name, e.g. ``"HUNK_CODE"``.
    :param load_address: Virtual address at which this region is loaded (default 0).
    """

    offset: int
    size: int
    label: str
    load_address: int = 0


@dataclass(frozen=True)
class MoveSpec:
    """An 8-byte move as stored in the original Battle Chess board struct.

    Field layout (big-endian, Amiga HUNK pre-relocated)::

        offset  size  field
        0       2     from_sq   0x88 square index of the source square
        2       2     to_sq     0x88 square index of the destination square
        4       2     flags     move-type flags
        6       1     piece     piece type nibble (0=empty, 1=pawn … 6=king)
        7       1     legal     non-zero if the move is legal

    :param from_sq: Source square (0x88 encoding).
    :param to_sq:   Destination square (0x88 encoding).
    :param flags:   Move-type flags word.
    :param piece:   Piece-type nibble.
    :param legal:   Move legality byte (non-zero = legal).
    """

    from_sq: int
    to_sq: int
    flags: int
    piece: int
    legal: int

    @property
    def from_file(self) -> int:
        """File index 0–7 of the source square.

        :return: ``from_sq & 0x0F``
        """
        return self.from_sq & 0x0F

    @property
    def from_rank(self) -> int:
        """Rank index 0–7 of the source square (0 = rank 1).

        :return: ``from_sq >> 4``
        """
        return self.from_sq >> 4

    @property
    def to_file(self) -> int:
        """File index 0–7 of the destination square.

        :return: ``to_sq & 0x0F``
        """
        return self.to_sq & 0x0F

    @property
    def to_rank(self) -> int:
        """Rank index 0–7 of the destination square (0 = rank 1).

        :return: ``to_sq >> 4``
        """
        return self.to_sq >> 4

    def to_uci(self) -> str:
        """Return the move in UCI notation (e.g. ``"e2e4"``).

        :return: Four-character UCI string; ``"0000"`` for a null move.
        :raises ValueError: If either square index is invalid for the 0x88 board.
        """
        for sq, name in ((self.from_sq, "from_sq"), (self.to_sq, "to_sq")):
            if sq & 0x88:
                raise ValueError(f"{name}=0x{sq:02X} is not a valid 0x88 square")
        f_file = chr(ord("a") + self.from_file)
        f_rank = str(self.from_rank + 1)
        t_file = chr(ord("a") + self.to_file)
        t_rank = str(self.to_rank + 1)
        return f"{f_file}{f_rank}{t_file}{t_rank}"


class Level(Enum):
    """Battle Chess AI difficulty levels.

    Maps to the internal ``level`` byte stored at ``-$4CE0(A4)`` in the original binary.

    :cvar NOVICE:       Level 1 — weakest.
    :cvar EASY:         Level 2.
    :cvar INTERMEDIATE: Level 3.
    :cvar HARD:         Level 4.
    :cvar EXPERT:       Level 5 — strongest.
    """

    NOVICE = 1
    EASY = 2
    INTERMEDIATE = 3
    HARD = 4
    EXPERT = 5


@dataclass(frozen=True)
class ThinkResult:
    """The output of one call to the think orchestrator.

    :param move: The chosen move, or ``None`` if the engine has no legal moves.
    :param level: The difficulty level the search ran at.
    :param instructions: Approximate number of emulated m68k instructions executed.
    :param elapsed_ns: Wall-clock time in nanoseconds (0 if unavailable).
    """

    move: MoveSpec | None
    level: Level
    instructions: int
    elapsed_ns: int = 0

    @property
    def has_move(self) -> bool:
        """Return True if the engine produced a legal move.

        :return: ``move is not None``
        """
        return self.move is not None
