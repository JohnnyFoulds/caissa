"""
bin/Code/Rpa/Vision/Manifest.py — Template manifest loader and verifier.

The manifest is a JSON file at ``Resources/Rpa/Templates/manifest.json`` that
records metadata for every template PNG used by the RPA layer.  Each entry
includes a ``sha256`` digest so that stale templates (out of date after a theme or
font change) are detected at load time rather than silently producing bad matches.

Manifest entry schema::

    {
        "name": "toolbar_options_button",
        "path": "Resources/Rpa/Templates/toolbar_options_button.png",
        "dpr": 1.0,
        "theme": "Default",
        "ui_mode": "classical",
        "translator": "en",
        "captured_at": "2026-08-28T14:22:33Z",
        "sha256": "abcdef0123456789...",
        "width": 28,
        "height": 28
    }

An empty ``{"templates": []}`` manifest is valid and required even when no
templates have been captured yet.

:spec: FR-7, §9 (feature_spec.md)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field

from Code.Rpa.Errors import ManifestError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateEntry:
    """A single entry from the manifest.

    :param name: Logical name used by workflows to reference the template.
    :param path: Path to the PNG file (relative to the repo root, or absolute).
    :param sha256: Expected SHA-256 hex digest of the PNG file.
    :param dpr: Device pixel ratio the template was captured at.
    :param theme: Theme active when the template was captured.
    :param ui_mode: UI mode active when the template was captured.
    :param translator: Locale/translator active when the template was captured.
    :param captured_at: ISO-8601 timestamp of the capture.
    :param width: Image width in pixels.
    :param height: Image height in pixels.
    """

    name: str
    path: str
    sha256: str
    dpr: float = 1.0
    theme: str = ""
    ui_mode: str = ""
    translator: str = ""
    captured_at: str = ""
    width: int = 0
    height: int = 0


@dataclass
class Manifest:
    """Loaded and verified manifest.

    :param entries: All template entries, keyed by name.
    :param path: Absolute path of the manifest file that was loaded.
    """

    entries: dict[str, TemplateEntry] = field(default_factory=dict)
    path: str = ""

    def get(self, name: str) -> TemplateEntry:
        """Return the entry for *name*.

        :param name: Template name.
        :returns: :class:`TemplateEntry`.
        :raises ManifestError: If the name is not in the manifest.
        """
        if name not in self.entries:
            raise ManifestError(
                f"Template {name!r} is not in the manifest at {self.path!r}. "
                "Re-capture the template or update the manifest."
            )
        return self.entries[name]


def _sha256_file(path: str) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_path(path: str, manifest_dir: str) -> str:
    """Return an absolute path for *path*, resolved relative to *manifest_dir*."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(manifest_dir, path))


def load_and_verify(path: str) -> Manifest:
    """Load and verify the manifest at *path*.

    For each entry:

    1. Check the PNG file exists.
    2. Compute its SHA-256 and compare with the stored digest.

    :param path: Absolute or relative path to ``manifest.json``.
    :returns: Verified :class:`Manifest`.
    :raises ManifestError: If the file is missing, malformed, or any hash
        does not match.
    """
    abs_path = os.path.abspath(path)
    manifest_dir = os.path.dirname(abs_path)

    if not os.path.isfile(abs_path):
        raise ManifestError(f"Manifest file not found: {abs_path!r}")

    try:
        with open(abs_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        raise ManifestError(f"Cannot read manifest {abs_path!r}: {exc}") from exc

    raw_entries = data.get("templates", [])
    if not isinstance(raw_entries, list):
        raise ManifestError(f"Manifest {abs_path!r}: 'templates' must be a list")

    entries: dict[str, TemplateEntry] = {}
    for raw in raw_entries:
        try:
            name = raw["name"]
            rel_path = raw["path"]
            expected_hash = raw["sha256"]
        except KeyError as exc:
            raise ManifestError(
                f"Manifest entry missing required field {exc}: {raw!r}"
            ) from exc

        abs_template = _resolve_path(rel_path, manifest_dir)
        if not os.path.isfile(abs_template):
            raise ManifestError(
                f"Template file not found: {abs_template!r} (entry {name!r})"
            )

        actual_hash = _sha256_file(abs_template)
        if actual_hash != expected_hash:
            raise ManifestError(
                f"SHA-256 mismatch for template {name!r}: "
                f"expected {expected_hash!r}, got {actual_hash!r}. "
                "Re-capture the template and update the manifest."
            )

        entry = TemplateEntry(
            name=name,
            path=abs_template,
            sha256=expected_hash,
            dpr=float(raw.get("dpr", 1.0)),
            theme=str(raw.get("theme", "")),
            ui_mode=str(raw.get("ui_mode", "")),
            translator=str(raw.get("translator", "")),
            captured_at=str(raw.get("captured_at", "")),
            width=int(raw.get("width", 0)),
            height=int(raw.get("height", 0)),
        )
        entries[name] = entry
        logger.debug("Manifest: loaded template %r from %r", name, abs_template)

    manifest = Manifest(entries=entries, path=abs_path)
    logger.debug("Manifest loaded: %d entries from %r", len(entries), abs_path)
    return manifest
