"""
bin/Code/Retro/Trace.py — Observation trace record/replay.

Observation traces record CPU-visible events (register reads/writes, memory
probes) at a level that contains no code bytes and no ROM-derived bytecode.
They serve two purposes: reproducible FakeCpu scripts for unit tests, and
corpus-building ground-truth from real-ROM runs.

**Committed trace fixtures must contain only observation-kind records.**
No "code" key is permitted in any record's ``data`` dict (N-RETRO redaction
rule enforced by :func:`redact_check`).

:spec: feature_spec.md §7, N-RETRO-4
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from Code.Retro.Errors import OracleError

TRACE_OBSERVATION = "observation"

_FORBIDDEN_KEYS = frozenset({"code", "bytecode", "opcodes", "raw_instructions"})


@dataclass
class TraceRecord:
    """One event in an observation trace.

    :param kind: Always :data:`TRACE_OBSERVATION` for committable traces.
    :param data: Arbitrary key/value observation data.
    """

    kind: str
    data: dict = field(default_factory=dict)


def redact_check(record: TraceRecord) -> None:
    """Raise :exc:`~Code.Retro.Errors.OracleError` if *record* contains forbidden keys.

    :param record: TraceRecord to inspect.
    :raises OracleError: If ``data`` contains any key in :data:`_FORBIDDEN_KEYS`.
    """
    bad = _FORBIDDEN_KEYS & set(record.data)
    if bad:
        raise OracleError(
            f"trace record contains forbidden key(s) {sorted(bad)!r} — "
            f"code bytes must not be committed (N-RETRO-4)"
        )


def load_trace(path: Path) -> list[TraceRecord]:
    """Load a JSONL trace file into a list of :class:`TraceRecord` objects.

    Each line must be a JSON object with at least a ``kind`` key.

    :param path: Path to the ``.jsonl`` trace file.
    :return: Ordered list of :class:`TraceRecord`.
    :raises OracleError: If the file is malformed or contains forbidden keys.
    """
    records: list[TraceRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OracleError(f"cannot read trace file {path!r}") from exc

    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OracleError(f"{path}:{lineno}: invalid JSON — {exc}") from exc
        if "kind" not in obj:
            raise OracleError(f"{path}:{lineno}: missing 'kind' key")
        record = TraceRecord(kind=obj["kind"], data={k: v for k, v in obj.items() if k != "kind"})
        redact_check(record)
        records.append(record)

    return records
