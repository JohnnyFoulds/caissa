"""
bin/Code/Retro/Oracle.py — Corpus record and replay for the Retro Engine.

The Oracle loads JSONL corpus files and verifies that a given
:class:`~Code.Retro.Think.ThinkSession` returns the expected move for each
:class:`CorpusEntry`.

Corpus files contain no code bytes — only move notation and position data
(decision D3).

:spec: feature_spec.md §7, decisions.md D3
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from Code.Retro.Errors import OracleError
from Code.Retro.Types import Level

logger = logging.getLogger(__name__)


@dataclass
class CorpusEntry:
    """One ground-truth record: position + expected move.

    :param fen: FEN position string.
    :param level: Difficulty level used when the move was captured.
    :param expected_uci: The move Battle Chess played, in UCI notation.
    """

    fen: str
    level: Level
    expected_uci: str


def load_corpus(path: Path) -> list[CorpusEntry]:
    """Load a JSONL corpus file into a list of :class:`CorpusEntry` objects.

    Each line must be a JSON object with keys ``fen``, ``level``,
    ``expected_uci``.

    :param path: Path to the ``.jsonl`` corpus file.
    :return: Ordered list of :class:`CorpusEntry`.
    :raises OracleError: If the file is missing, malformed, or has missing keys.
    """
    entries: list[CorpusEntry] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OracleError(f"cannot read corpus file {path!r}") from exc

    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OracleError(f"{path}:{lineno}: invalid JSON — {exc}") from exc

        for key in ("fen", "level", "expected_uci"):
            if key not in obj:
                raise OracleError(f"{path}:{lineno}: missing required key {key!r}")

        try:
            level = Level(int(obj["level"]))
        except (ValueError, KeyError) as exc:
            raise OracleError(f"{path}:{lineno}: invalid level value {obj['level']!r}") from exc

        entries.append(CorpusEntry(
            fen=obj["fen"],
            level=level,
            expected_uci=obj["expected_uci"],
        ))

    logger.debug("loaded %d corpus entries from %s", len(entries), path)
    return entries


class Oracle:
    """Verifies :class:`~Code.Retro.Think.ThinkSession` results against a corpus.

    :param corpus_path: Path to a JSONL corpus file.  Loaded lazily on first
        call to :meth:`verify_corpus_entry`.
    """

    def __init__(self, corpus_path: Path | None = None) -> None:
        self._corpus_path = corpus_path
        self._entries: list[CorpusEntry] | None = None

    def load(self, path: Path) -> list[CorpusEntry]:
        """Load corpus from *path* and cache it.

        :param path: Path to JSONL corpus file.
        :return: List of :class:`CorpusEntry`.
        """
        self._entries = load_corpus(path)
        return self._entries

    def verify_corpus_entry(
        self,
        entry: CorpusEntry,
        session,  # ThinkSession — forward ref avoids circular import
    ) -> bool:
        """Run *session* on *entry* and return whether the move matches.

        :param entry: :class:`CorpusEntry` with fen, level, expected_uci.
        :param session: A :class:`~Code.Retro.Think.ThinkSession` instance.
        :return: ``True`` if the session returns the expected move, ``False`` otherwise.
        """
        from Code.Retro.Think import ThinkRequest

        request = ThinkRequest(fen=entry.fen, level=entry.level)
        try:
            result = session.think(request)
        except Exception as exc:  # noqa: BLE001
            logger.warning("think() raised %r for corpus entry %r", exc, entry.fen)
            return False

        if result.move is None:
            return False

        actual = result.move.to_uci()
        matches = actual == entry.expected_uci
        if not matches:
            logger.info(
                "corpus mismatch for %s: expected %r got %r",
                entry.fen[:40],
                entry.expected_uci,
                actual,
            )
        return matches
