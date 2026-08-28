"""
tests/unit/retro/test_oracle.py — Phase 7 tests for Oracle.py and Trace.py.

Covers corpus loading, verify_corpus_entry with FakeCpu, wrong-move detection,
and observation-trace redaction rules.

:spec: feature_spec.md §7, decisions.md D3, N-RETRO-4
:phase: 7
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from Code.Retro.Bridge import AI_BEST_MOVE_ADDR
from Code.Retro.Errors import OracleError
from Code.Retro.Fakes import FakeCpu
from Code.Retro.Oracle import CorpusEntry, Oracle, load_corpus
from Code.Retro.Think import ThinkSession
from Code.Retro.Trace import TRACE_OBSERVATION, TraceRecord, load_trace, redact_check
from Code.Retro.Types import Level

pytestmark = pytest.mark.retro

_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_FIXTURES = Path(__file__).parent / "_fixtures"
_TRACE_FIXTURES = _FIXTURES / "traces"
_CORPUS_FIXTURES = _FIXTURES / "corpus"

# e2e4: from_sq=0x14, to_sq=0x34
_E2E4_RAW = struct.pack(">HHHBB", 0x14, 0x34, 0, 1, 1)
# d2d4: from_sq=0x13, to_sq=0x33
_D2D4_RAW = struct.pack(">HHHBB", 0x13, 0x33, 0, 1, 1)


def _session_returns(raw: bytes) -> ThinkSession:
    cpu = FakeCpu()

    def _cb(c: FakeCpu) -> None:
        c.mem_write(AI_BEST_MOVE_ADDR, raw)

    cpu.set_emu_callback(_cb)
    return ThinkSession(cpu=cpu)


# ---------------------------------------------------------------------------
# Corpus load
# ---------------------------------------------------------------------------

def test_oracle_loads_corpus_jsonl_files():
    """load_corpus must return a non-empty list for the fixture corpus file."""
    entries = load_corpus(_CORPUS_FIXTURES / "startpos_level1.jsonl")
    assert len(entries) >= 1
    assert all(isinstance(e, CorpusEntry) for e in entries)


def test_corpus_entry_fields():
    """Loaded CorpusEntry must have fen, level, expected_uci populated."""
    entries = load_corpus(_CORPUS_FIXTURES / "startpos_level1.jsonl")
    e = entries[0]
    assert e.fen == _STARTPOS
    assert e.level == Level.NOVICE
    assert len(e.expected_uci) == 4  # e.g. "e2e4"


def test_oracle_load_missing_file_raises():
    """load_corpus on a missing file must raise OracleError."""
    with pytest.raises(OracleError):
        load_corpus(Path("/nonexistent/corpus.jsonl"))


def test_oracle_load_malformed_json_raises(tmp_path):
    """load_corpus on a malformed JSONL file must raise OracleError."""
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n")
    with pytest.raises(OracleError):
        load_corpus(bad)


def test_oracle_load_missing_key_raises(tmp_path):
    """load_corpus on a record missing 'expected_uci' must raise OracleError."""
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"fen": _STARTPOS, "level": 1}) + "\n")
    with pytest.raises(OracleError):
        load_corpus(bad)


# ---------------------------------------------------------------------------
# Oracle.verify_corpus_entry
# ---------------------------------------------------------------------------

def test_oracle_verifies_entry_against_scripted_cpu():
    """verify_corpus_entry must return True when the session returns the expected move."""
    oracle = Oracle()
    entry = CorpusEntry(fen=_STARTPOS, level=Level.NOVICE, expected_uci="e2e4")
    session = _session_returns(_E2E4_RAW)
    assert oracle.verify_corpus_entry(entry, session) is True


def test_oracle_detects_wrong_move():
    """verify_corpus_entry must return False when the session returns a different move."""
    oracle = Oracle()
    entry = CorpusEntry(fen=_STARTPOS, level=Level.NOVICE, expected_uci="e2e4")
    session = _session_returns(_D2D4_RAW)  # returns d2d4, not e2e4
    assert oracle.verify_corpus_entry(entry, session) is False


def test_oracle_verify_no_move_returns_false():
    """verify_corpus_entry must return False when think() raises ThinkError."""
    oracle = Oracle()
    entry = CorpusEntry(fen=_STARTPOS, level=Level.NOVICE, expected_uci="e2e4")
    cpu = FakeCpu()  # no callback → ThinkError
    session = ThinkSession(cpu=cpu)
    assert oracle.verify_corpus_entry(entry, session) is False


def test_oracle_load_method():
    """Oracle.load() must populate internal entries."""
    oracle = Oracle()
    entries = oracle.load(_CORPUS_FIXTURES / "startpos_level1.jsonl")
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# Trace load and redaction
# ---------------------------------------------------------------------------

def test_trace_observation_constant():
    """TRACE_OBSERVATION must equal the string 'observation'."""
    assert TRACE_OBSERVATION == "observation"


def test_load_trace_fixture():
    """load_trace must return records from the committed fixture."""
    records = load_trace(_TRACE_FIXTURES / "startpos_level1.jsonl")
    assert len(records) >= 1
    for r in records:
        assert r.kind == TRACE_OBSERVATION


def test_observation_trace_contains_no_code_bytes():
    """Committed trace fixtures must have no forbidden keys (N-RETRO-4)."""
    for fixture in _TRACE_FIXTURES.glob("*.jsonl"):
        records = load_trace(fixture)
        for r in records:
            # redact_check raises on forbidden keys — if it doesn't raise, we pass
            redact_check(r)


def test_redact_check_passes_clean_record():
    """redact_check must not raise for a clean observation record."""
    r = TraceRecord(kind=TRACE_OBSERVATION, data={"event": "move_written"})
    redact_check(r)  # should not raise


def test_redact_check_raises_on_code_key():
    """redact_check must raise OracleError when 'code' key is present."""
    r = TraceRecord(kind=TRACE_OBSERVATION, data={"code": b"\x4e\x75", "event": "halt"})
    with pytest.raises(OracleError):
        redact_check(r)


def test_load_trace_forbidden_key_raises(tmp_path):
    """load_trace must raise OracleError if any record has a forbidden key."""
    bad = tmp_path / "bad_trace.jsonl"
    bad.write_text(json.dumps({"kind": "observation", "code": "4e75"}) + "\n")
    with pytest.raises(OracleError):
        load_trace(bad)


def test_load_trace_missing_kind_raises(tmp_path):
    """load_trace must raise OracleError if a record has no 'kind' key."""
    bad = tmp_path / "bad_trace.jsonl"
    bad.write_text(json.dumps({"data": "something"}) + "\n")
    with pytest.raises(OracleError):
        load_trace(bad)
