"""
bin/Code/Retro/Manifest.py — ROM manifest loading and verification.

Loads ``Resources/Retro/manifest.json``, validates its schema, and verifies a
user-supplied ROM file by comparing its sha256 digest against the manifest.

**ZERO third-party imports** — stdlib only (json, hashlib, pathlib).

:spec: feature_spec.md §5, N-RETRO-6
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Code.Retro.Errors import HashMismatchError, ManifestError, UnsupportedRomError
from Code.Retro.Types import Platform, RomId

_DEFAULT_MANIFEST: Path = Path(__file__).parents[3] / "Resources" / "Retro" / "manifest.json"

__all__ = ["load", "sha256_file", "verify"]


def sha256_file(path: str) -> str:
    """Compute the sha256 hex digest of a file, streaming in 64 KB chunks.

    :param path: Filesystem path to the file to hash.
    :return: 64-character lowercase hex digest.
    :raises ManifestError: If the file cannot be opened or read.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError as exc:
        raise ManifestError(f"cannot read ROM file {path!r}: {exc}") from exc
    return h.hexdigest()


def load(path: Path = _DEFAULT_MANIFEST) -> list[dict]:
    """Load and schema-validate a Retro manifest file.

    Validates:

    - Top-level object with ``version == 1``
    - ``entries`` is a list
    - Every entry has a ``sha256`` that is exactly 64 lowercase hex characters

    :param path: Path to the manifest JSON file.  Defaults to
        ``Resources/Retro/manifest.json`` in the repository root.
    :return: List of validated entry dicts from the manifest.
    :raises ManifestError: If the file is missing, malformed, or fails schema validation.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except OSError as exc:
        raise ManifestError(f"cannot open manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest {path} is not valid JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ManifestError(f"manifest {path}: top-level value must be a JSON object")

    version = manifest.get("version")
    if version != 1:
        raise ManifestError(
            f"manifest {path}: unsupported version {version!r} (expected 1)"
        )

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ManifestError(f"manifest {path}: missing or invalid 'entries' list")

    _HEX = frozenset("0123456789abcdef")
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest {path}: entries[{i}] is not an object")
        sha = entry.get("sha256", "")
        if not isinstance(sha, str) or len(sha) != 64 or not all(c in _HEX for c in sha):
            raise ManifestError(
                f"manifest {path}: entries[{i}].sha256 {sha!r} is not a "
                f"64-character lowercase hex string"
            )

    return entries


def verify(
    rom_path: str,
    manifest_path: Path = _DEFAULT_MANIFEST,
) -> RomId:
    """Verify a ROM file against the manifest and return its identity.

    Computes the sha256 of *rom_path* and searches the manifest for a matching
    entry.  Returns a :class:`~Code.Retro.Types.RomId` on success.

    :param rom_path: Filesystem path to the ROM file to verify.
    :param manifest_path: Path to the manifest JSON file.  Defaults to the
        bundled ``Resources/Retro/manifest.json``.
    :return: A :class:`~Code.Retro.Types.RomId` describing the verified ROM.
    :raises ManifestError: If the manifest cannot be loaded or is invalid.
    :raises HashMismatchError: If the file's digest does not match any manifest entry.
    :raises UnsupportedRomError: If the digest matches an entry marked
        ``"supported": false``.
    """
    entries = load(manifest_path)
    digest = sha256_file(rom_path)

    for entry in entries:
        if entry["sha256"] == digest:
            if not entry.get("supported", True):
                label = entry.get("label", "<unknown>")
                raise UnsupportedRomError(
                    f"ROM {label!r} is known but not supported by this version of Caissa"
                )
            platform = Platform(entry["platform"])
            return RomId(sha256=digest, platform=platform, label=entry["label"])

    raise HashMismatchError(rom_path, digest)
