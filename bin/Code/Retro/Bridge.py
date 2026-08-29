"""
bin/Code/Retro/Bridge.py — FEN ↔ Battle Chess board struct marshalling.

Converts FEN position strings into the original game's piece-table format and
reads back the AI's chosen move from the ``ai_best_move`` buffer.

**Memory layout** (A4 = 0x7FFE; virtual address = A4 - offset)::

    PIECE_COUNTER_ADDR  0x3320  word    iteration index; -1 = ready
    PIECE_TABLE_ADDR    0x3322  array   8 bytes/entry, piece list
    PLAYER1_COLOR_ADDR  0x331E  word    0=White, 1=Black (side to move)
    PLAYER2_COLOR_ADDR  0x331C  word    0=White, 1=Black (other side)
    AI_BEST_MOVE_ADDR   0x3662  8 bytes [to_sq, from_sq, state, ...]
    PLAYER_TYPE_BASE    0x07D4  array   1=Human, 2=Computer; entry[color*2]
    BOARD_ARRAY_ADDR    0x30F4  array   128*4 bytes; [sq*4]=type, [sq*4+1]=color
    PAWN_DIR_TABLE      0x07A2  array   2 words; [0]=white_dir (+0x10), [1]=black_dir (-0x10)
    SEARCH_SKIP_FLAG    0x07D2  word    non-zero → AI skips search at 0x824C

**Piece-table entry** (8 bytes, confirmed from disassembly of 0xD960–0xD97A)::

    offset  size  field        encoding
    0       2     to_sq        0x88 index; filled by search, 0 initially
    2       2     from_sq      0x88 index; current piece position (FROM square)
    4       2     search_state filled by search, 0 initially
    6       2     reserved     filled by search, 0 initially

**Board-array type codes** (written to BOARD_ARRAY_ADDR, confirmed from recon)::

    1=King  2=Queen  3=Rook  4=Bishop  5=Knight  6=Pawn

**Zero third-party imports** — stdlib + Code.Retro only.

:spec: feature_spec.md §6, decisions.md D4
"""

from __future__ import annotations

import struct

from Code.Retro.Cpu import Cpu
from Code.Retro.Errors import BridgeError
from Code.Retro.Types import MoveSpec

# ---------------------------------------------------------------------------
# Virtual-address constants (A4 = 0x7FFE; addr = A4 − a4_offset)
# ---------------------------------------------------------------------------

A4: int = 0x7FFE

PIECE_COUNTER_ADDR: int = A4 - 0x4CDE  # 0x3320
PIECE_TABLE_ADDR: int = A4 - 0x4CDC    # 0x3322
PLAYER1_COLOR_ADDR: int = A4 - 0x4CE0  # 0x331E
PLAYER2_COLOR_ADDR: int = A4 - 0x4CE2  # 0x331C
# AI_BEST_MOVE_ADDR = PIECE_TABLE + 0x68*8: confirmed from disassembly of write at 0xD97A
AI_BEST_MOVE_ADDR: int = PIECE_TABLE_ADDR + 0x68 * 8  # 0x3662
PLAYER_TYPE_BASE: int = A4 - 0x782A    # 0x07D4
BOARD_ARRAY_ADDR: int = A4 - 0x4F0A   # 0x30F4  (128 entries * 4 bytes each)
PAWN_DIR_TABLE: int = A4 - 0x785C     # 0x07A2  (2 words: white_dir, black_dir)
SEARCH_SKIP_FLAG: int = A4 - 0x782C   # 0x07D2  (non-zero skips search at 0x824C)

PIECE_ENTRY_SIZE: int = 8
MAX_PIECES: int = 32   # 16 per side

# Confirmed from disassembly: 0x8230 = AI_INIT entry (link.w a5, #-0x3C)
# 0x81DC = outer driver entry (used for iterative deepening; AI_INIT is sufficient for one ply)
AI_INIT_ADDR: int = 0x8230
AI_OUTER_DRIVER_ADDR: int = 0x81DC

# ---------------------------------------------------------------------------
# FEN piece-character → (color, piece_type) mapping
# Board-array type codes confirmed from recon (BOARD_ARRAY_ADDR):
#   1=King  2=Queen  3=Rook  4=Bishop  5=Knight  6=Pawn
# ---------------------------------------------------------------------------

_FEN_PIECE: dict[str, tuple[int, int]] = {
    'K': (0, 1), 'Q': (0, 2), 'R': (0, 3), 'B': (0, 4), 'N': (0, 5), 'P': (0, 6),
    'k': (1, 1), 'q': (1, 2), 'r': (1, 3), 'b': (1, 4), 'n': (1, 5), 'p': (1, 6),
}


# ---------------------------------------------------------------------------
# Square helpers
# ---------------------------------------------------------------------------

def sq88(file: int, rank: int) -> int:
    """Return the 0x88 square index for *file* and *rank*.

    :param file: File index 0–7 (0='a', 7='h').
    :param rank: Rank index 0–7 (0=rank-1, 7=rank-8).
    :return: ``rank * 16 + file``
    :raises BridgeError: If *file* or *rank* is out of range.
    """
    if not (0 <= file <= 7 and 0 <= rank <= 7):
        raise BridgeError(f"file={file} rank={rank} out of 0–7 range")
    return rank * 16 + file


def sq88_to_file_rank(sq: int) -> tuple[int, int]:
    """Decompose a 0x88 square index into (file, rank).

    :param sq: 0x88 square index.
    :return: ``(file, rank)`` both in 0–7.
    :raises BridgeError: If *sq* is not a valid 0x88 square.
    """
    if sq & 0x88:
        raise BridgeError(f"0x{sq:02X} is not a valid 0x88 square (sq & 0x88 != 0)")
    return sq & 0x0F, sq >> 4


def sq88_to_alg(sq: int) -> str:
    """Convert a 0x88 square index to algebraic notation (e.g. ``"e2"``).

    :param sq: 0x88 square index.
    :return: Two-character algebraic string.
    :raises BridgeError: If *sq* is not a valid 0x88 square.
    """
    file, rank = sq88_to_file_rank(sq)
    return f"{chr(ord('a') + file)}{rank + 1}"


def alg_to_sq88(alg: str) -> int:
    """Convert algebraic notation (e.g. ``"e4"``) to a 0x88 square index.

    :param alg: Two-character algebraic square name.
    :return: 0x88 square index.
    :raises BridgeError: If *alg* is malformed or out of range.
    """
    if len(alg) != 2:
        raise BridgeError(f"algebraic square must be 2 chars, got {alg!r}")
    file_ch, rank_ch = alg[0], alg[1]
    if file_ch not in "abcdefgh" or rank_ch not in "12345678":
        raise BridgeError(f"invalid algebraic square {alg!r}")
    return sq88(ord(file_ch) - ord('a'), int(rank_ch) - 1)


# ---------------------------------------------------------------------------
# FEN parsers
# ---------------------------------------------------------------------------

def parse_piece_placement(placement: str) -> list[tuple[int, int, int]]:
    """Parse a FEN piece-placement string into a list of (sq, color, piece_type) tuples.

    :param placement: FEN piece-placement field, e.g.
        ``"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"``.
    :return: List of ``(sq88_index, color, piece_type)`` for every piece present.
    :raises BridgeError: If *placement* is malformed.
    """
    pieces: list[tuple[int, int, int]] = []
    ranks = placement.split('/')
    if len(ranks) != 8:
        raise BridgeError(f"expected 8 ranks in piece placement, got {len(ranks)}")
    # FEN rank-8 (index 0) is rank 7 in 0-based; rank-1 (index 7) is rank 0.
    for rank_idx, rank_str in enumerate(ranks):
        rank = 7 - rank_idx  # convert FEN rank order to 0-based
        file = 0
        for ch in rank_str:
            if ch.isdigit():
                file += int(ch)
            elif ch in _FEN_PIECE:
                if file > 7:
                    raise BridgeError(f"rank {rank + 1}: file overflow at {ch!r}")
                color, piece_type = _FEN_PIECE[ch]
                pieces.append((sq88(file, rank), color, piece_type))
                file += 1
            else:
                raise BridgeError(f"unexpected character {ch!r} in piece placement")
        if file != 8:
            raise BridgeError(f"rank {rank + 1}: expected 8 files, got {file}")
    return pieces


def parse_fen(fen: str) -> dict:
    """Parse a full FEN string into its component fields.

    :param fen: Standard FEN string, e.g.
        ``"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"``.
    :return: Dict with keys ``pieces``, ``side_to_move`` (0=White/1=Black),
        ``castling`` (str), ``ep_square`` (0x88 index or -1), ``halfmove``,
        ``fullmove``.
    :raises BridgeError: If *fen* is malformed.
    """
    parts = fen.strip().split()
    if len(parts) < 2:
        raise BridgeError(f"FEN must have at least 2 fields, got {len(parts)}")

    placement = parts[0]
    side_str = parts[1]
    castling = parts[2] if len(parts) > 2 else "-"
    ep_str = parts[3] if len(parts) > 3 else "-"
    halfmove_str = parts[4] if len(parts) > 4 else "0"
    fullmove_str = parts[5] if len(parts) > 5 else "1"

    pieces = parse_piece_placement(placement)

    if side_str not in ("w", "b"):
        raise BridgeError(f"side-to-move must be 'w' or 'b', got {side_str!r}")
    side_to_move = 0 if side_str == "w" else 1

    ep_square = -1
    if ep_str != "-":
        try:
            ep_square = alg_to_sq88(ep_str)
        except BridgeError as exc:
            raise BridgeError(f"invalid en-passant square {ep_str!r}") from exc

    try:
        halfmove = int(halfmove_str)
        fullmove = int(fullmove_str)
    except ValueError as exc:
        raise BridgeError("invalid halfmove/fullmove counts in FEN") from exc

    return {
        "pieces": pieces,
        "side_to_move": side_to_move,
        "castling": castling,
        "ep_square": ep_square,
        "halfmove": halfmove,
        "fullmove": fullmove,
    }


# ---------------------------------------------------------------------------
# Piece-table entry packing
# ---------------------------------------------------------------------------

def _make_entry(sq: int) -> bytes:
    """Pack one 8-byte piece-table entry.

    :param sq: 0x88 square index (FROM square — current piece position).
    :return: 8-byte big-endian struct.

    Layout confirmed from disassembly of 0xD972 (reads FROM at +2) and
    0xD97A (writes TO at +0 during search):
      offset 0 (WORD): TO square  — 0 initially, filled during search
      offset 2 (WORD): FROM square — current piece position
      offset 4-7:      0 — search state, filled during search
    """
    return struct.pack(">HH4x", 0, sq)


def _read_entry(data: bytes) -> tuple[int, int]:
    """Unpack one 8-byte piece-table entry.

    :param data: Exactly 8 bytes.
    :return: ``(to_sq, from_sq)`` — to_sq is 0 before search runs.
    """
    to_sq, from_sq = struct.unpack(">HH", data[:4])
    return to_sq, from_sq


# ---------------------------------------------------------------------------
# Bridge class
# ---------------------------------------------------------------------------

class Bridge:
    """Marshals FEN positions into the Battle Chess board struct and reads AI moves.

    :param cpu: Emulator backend (any :class:`~Code.Retro.Cpu.Cpu` implementation).
    """

    def __init__(self, cpu: Cpu) -> None:
        """Initialise the bridge with an emulator backend.

        :param cpu: Emulator backend.
        """
        self._cpu = cpu
        self._piece_count: int = 0

    def write_position(self, fen: str) -> None:
        """Write a FEN position into the emulated board struct.

        Writes the board array, piece table, pawn direction table, and player
        color globals.  Clears the search-skip flag so the AI runs.

        :param fen: FEN position string.
        :raises BridgeError: If *fen* is malformed.
        """
        board = parse_fen(fen)
        pieces = board["pieces"]
        if len(pieces) > MAX_PIECES:
            raise BridgeError(f"FEN has {len(pieces)} pieces; max is {MAX_PIECES}")

        # Write BOARD_ARRAY (128 entries * 4 bytes): [sq*4]=type, [sq*4+1]=color.
        # The move generator reads piece type and occupancy from here.
        board_data = bytearray(128 * 4)
        for sq, color, piece_type in pieces:
            board_data[sq * 4]     = piece_type
            board_data[sq * 4 + 1] = color
        self._cpu.mem_write(BOARD_ARRAY_ADDR, bytes(board_data))

        # Pawn direction table: game startup writes these at runtime, but we bypass
        # startup.  Without these the pawn move generator computes garbage TO squares.
        # +0x10 = north (+1 rank), 0xFFF0 = south (−1 rank, −0x10 in signed 16-bit).
        self._cpu.mem_write(PAWN_DIR_TABLE, struct.pack(">HH", 0x0010, 0xFFF0))

        # Allow the AI to run (0 = search enabled at 0x824C).
        self._cpu.mem_write(SEARCH_SKIP_FLAG, struct.pack(">H", 0))

        # Zero the entire piece table, then write one entry per piece.
        self._cpu.mem_write(PIECE_TABLE_ADDR, b"\x00" * PIECE_ENTRY_SIZE * MAX_PIECES)
        for idx, (sq, _color, _piece_type) in enumerate(pieces):
            entry = _make_entry(sq)
            self._cpu.mem_write(PIECE_TABLE_ADDR + idx * PIECE_ENTRY_SIZE, entry)
        self._piece_count = len(pieces)

        # Set piece counter to -1 (ai_phase0_init ready state)
        self._cpu.mem_write(PIECE_COUNTER_ADDR, struct.pack(">h", -1))

        # Set player colors
        side = board["side_to_move"]
        self._cpu.mem_write(PLAYER1_COLOR_ADDR, struct.pack(">H", side))
        self._cpu.mem_write(PLAYER2_COLOR_ADDR, struct.pack(">H", 1 - side))

    def read_best_move(self) -> MoveSpec | None:
        """Read the AI's chosen move from the ``ai_best_move`` buffer.

        Entry format (confirmed from disassembly):
          offset 0 (WORD): TO square   — destination
          offset 2 (WORD): FROM square — source (piece's original position)

        :return: :class:`~Code.Retro.Types.MoveSpec` if a valid move is present,
            ``None`` if the buffer is all-zero or squares fail 0x88 validation.
        """
        raw = bytes(self._cpu.mem_read(AI_BEST_MOVE_ADDR, 8))
        to_sq   = struct.unpack(">H", raw[0:2])[0]
        from_sq = struct.unpack(">H", raw[2:4])[0]
        if from_sq == 0 and to_sq == 0:
            return None
        if (from_sq & 0x88) or (to_sq & 0x88):
            return None
        return MoveSpec(from_sq=from_sq, to_sq=to_sq, flags=0, piece=0, legal=1)

    def clear_best_move(self) -> None:
        """Zero the ``ai_best_move`` buffer so a new move can be detected.

        :return: None
        """
        self._cpu.mem_write(AI_BEST_MOVE_ADDR, b"\x00" * 8)

    def set_computer_color(self, color: int) -> None:
        """Set which side the computer plays.

        Writes the player-type table so the human side = 1 and the computer side = 2.

        :param color: 0=Computer plays White, 1=Computer plays Black.
        :raises BridgeError: If *color* is not 0 or 1.
        """
        if color not in (0, 1):
            raise BridgeError(f"color must be 0 or 1, got {color!r}")
        human = 1 - color
        self._cpu.mem_write(PLAYER_TYPE_BASE + human * 2, struct.pack(">H", 1))
        self._cpu.mem_write(PLAYER_TYPE_BASE + color * 2, struct.pack(">H", 2))

    def read_piece_entries(self) -> list[tuple[int, int]]:
        """Read piece entries written by the most recent :meth:`write_position` call.

        :return: List of ``(to_sq, from_sq)`` for every piece written.
            ``to_sq`` is 0 before the search has run.
        """
        count = self._piece_count
        if count == 0:
            return []
        raw = bytes(self._cpu.mem_read(PIECE_TABLE_ADDR, PIECE_ENTRY_SIZE * count))
        entries = []
        for i in range(count):
            chunk = raw[i * PIECE_ENTRY_SIZE:(i + 1) * PIECE_ENTRY_SIZE]
            to_sq, from_sq = _read_entry(chunk)
            entries.append((to_sq, from_sq))
        return entries
