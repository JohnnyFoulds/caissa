"""
tests/unit/retro/test_manifest.py — Phase 3 tests for Code.Retro.Manifest.

Covers load(), sha256_file(), verify(), and the N-RETRO-6 schema invariant
against the real manifest.json.  Uses only synthetic data — no copyrighted ROM.

:spec: N-RETRO-6, feature_spec.md §5
:phase: 3
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.retro

_REPO_ROOT = Path(__file__).parents[3]
_REAL_MANIFEST = _REPO_ROOT / "Resources" / "Retro" / "manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_manifest(entries=None):
    return {
        "version": 1,
        "entries": entries or [
            {
                "sha256": "a" * 64,
                "platform": "amiga_68k",
                "label": "Test ROM",
                "file_size": 100,
                "supported": True,
            }
        ],
    }


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

def test_load_valid_manifest(tmp_path):
    """load() returns a list with the expected entry for a well-formed manifest.

    :spec: N-RETRO-6
    """
    from Code.Retro.Manifest import load

    p = _write_manifest(tmp_path, _minimal_manifest())
    entries = load(p)

    assert isinstance(entries, list)
    assert len(entries) == 1
    assert entries[0]["sha256"] == "a" * 64


def test_load_missing_file_raises_manifest_error():
    """load() raises ManifestError when the manifest file does not exist.

    :spec: N-RETRO-6
    """
    from Code.Retro.Errors import ManifestError
    from Code.Retro.Manifest import load

    with pytest.raises(ManifestError, match="cannot open"):
        load(Path("/nonexistent_caissa_manifest_99.json"))


def test_load_bad_json_raises_manifest_error(tmp_path):
    """load() raises ManifestError when the file contains invalid JSON.

    :spec: N-RETRO-6
    """
    from Code.Retro.Errors import ManifestError
    from Code.Retro.Manifest import load

    bad = tmp_path / "bad.json"
    bad.write_text("not json {{}", encoding="utf-8")
    with pytest.raises(ManifestError, match="not valid JSON"):
        load(bad)


def test_load_wrong_version_raises_manifest_error(tmp_path):
    """load() raises ManifestError when the manifest version is not 1.

    :spec: N-RETRO-6
    """
    from Code.Retro.Errors import ManifestError
    from Code.Retro.Manifest import load

    data = _minimal_manifest()
    data["version"] = 99
    p = _write_manifest(tmp_path, data)
    with pytest.raises(ManifestError, match="unsupported version"):
        load(p)


def test_load_short_digest_raises_manifest_error(tmp_path):
    """load() raises ManifestError when an entry has a malformed sha256 digest.

    :spec: N-RETRO-6
    """
    from Code.Retro.Errors import ManifestError
    from Code.Retro.Manifest import load

    data = _minimal_manifest(entries=[
        {"sha256": "abc", "platform": "amiga_68k", "label": "Bad", "supported": True}
    ])
    p = _write_manifest(tmp_path, data)
    with pytest.raises(ManifestError, match="not a 64-character"):
        load(p)


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------

def test_verify_matching_rom(tmp_path):
    """verify() returns the correct RomId when the ROM's digest matches a manifest entry.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Manifest import verify
    from Code.Retro.Types import Platform, RomId

    rom = tmp_path / "test.rom"
    rom.write_bytes(b"\x00" * 32)
    digest = hashlib.sha256(b"\x00" * 32).hexdigest()

    data = _minimal_manifest(entries=[
        {
            "sha256": digest,
            "platform": "amiga_68k",
            "label": "Test ROM v1",
            "file_size": 32,
            "supported": True,
        }
    ])
    manifest_path = _write_manifest(tmp_path, data)

    rom_id = verify(str(rom), manifest_path)

    assert isinstance(rom_id, RomId)
    assert rom_id.sha256 == digest
    assert rom_id.platform == Platform.AMIGA_68K
    assert rom_id.label == "Test ROM v1"


def test_verify_hash_mismatch_raises(tmp_path):
    """verify() raises HashMismatchError with .path and .digest when no entry matches.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Errors import HashMismatchError
    from Code.Retro.Manifest import verify

    rom = tmp_path / "unknown.rom"
    rom.write_bytes(b"\xFF" * 16)
    manifest_path = _write_manifest(tmp_path, _minimal_manifest())

    with pytest.raises(HashMismatchError) as exc_info:
        verify(str(rom), manifest_path)

    err = exc_info.value
    assert err.path == str(rom)
    assert len(err.digest) == 64


def test_verify_unsupported_rom_raises(tmp_path):
    """verify() raises UnsupportedRomError when the digest matches but supported is False.

    :spec: feature_spec.md §5
    """
    from Code.Retro.Errors import UnsupportedRomError
    from Code.Retro.Manifest import verify

    rom = tmp_path / "unsupported.rom"
    rom.write_bytes(b"\xAB" * 8)
    digest = hashlib.sha256(b"\xAB" * 8).hexdigest()

    data = _minimal_manifest(entries=[
        {
            "sha256": digest,
            "platform": "amiga_68k",
            "label": "Unsupported Build",
            "file_size": 8,
            "supported": False,
        }
    ])
    manifest_path = _write_manifest(tmp_path, data)

    with pytest.raises(UnsupportedRomError):
        verify(str(rom), manifest_path)


# ---------------------------------------------------------------------------
# N-RETRO-6: real manifest invariant
# ---------------------------------------------------------------------------

def test_manifest_n_retro_6_real_manifest():
    """Every entry in Resources/Retro/manifest.json satisfies the N-RETRO-6 schema.

    Checks:
    - Every sha256 is exactly 64 lowercase hex characters.
    - Every numeric value in the 'offsets' dict (hex string or int) is ≥ 0 and
      ≤ file_size (if file_size is present in the entry).

    :spec: N-RETRO-6
    """
    from Code.Retro.Manifest import load

    entries = load(_REAL_MANIFEST)
    assert entries, "manifest.json has no entries"

    _HEX = frozenset("0123456789abcdef")
    for i, entry in enumerate(entries):
        sha = entry.get("sha256", "")
        assert (
            isinstance(sha, str) and len(sha) == 64 and all(c in _HEX for c in sha)
        ), f"entries[{i}].sha256 is malformed: {sha!r}"

        file_size = entry.get("file_size")
        offsets = entry.get("offsets", {})
        if isinstance(offsets, dict) and file_size is not None:
            for key, val in offsets.items():
                # Values are hex strings like "0x1113C" or plain ints.
                if isinstance(val, str):
                    try:
                        num = int(val, 16)
                    except ValueError:
                        continue
                elif isinstance(val, int):
                    num = val
                else:
                    continue
                assert 0 <= num <= file_size, (
                    f"entries[{i}].offsets[{key!r}] = {val!r} is outside "
                    f"[0, file_size={file_size}]"
                )
