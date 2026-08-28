"""
bin/Code/Rpa/Targets.py — Selector and Target model for the Caissa RPA layer.

:class:`Selector` describes how to find a UI element across three tiers:
object (Qt widget tree), image (template matching), and OCR (tesseract).

:class:`Target` wraps a ``Selector`` with optional anchor, direction, max distance,
and timeout.

**Wire forms** — two representations for the same selector:

- **JSON** (primary): ``{"tier": "auto", "cls": "QPushButton", "text": "Play"}``
  — no escaping issues; used by ``_dispatch`` and the CLI.
- **Compact string** (debugging): ``obj:cls=QPushButton,text=Play``
  — percent-encoded values; used for hand-typed socket commands.

:spec: FR-4, §6 (feature_spec.md)
"""

from __future__ import annotations

import dataclasses
import json
import urllib.parse
from typing import Any

from Code.Rpa.Errors import SelectorError

# Valid tier values
_TIERS = frozenset({"auto", "object", "image", "ocr"})

# Valid anchor directions (used in compact-string anchor notation)
_DIRECTIONS = frozenset({"right-of", "left-of", "above", "below"})

# Fields that count as discriminating — at least one must be set (non-None, non-empty)
_DISCRIMINATING = frozenset({"object_name", "text", "cls", "image", "role"})


@dataclasses.dataclass(frozen=True)
class Selector:
    """Descriptor for locating a UI element across object, image, and OCR tiers.

    At least one *discriminating field* (``object_name``, ``text``, ``cls``,
    ``image``, or ``role``) must be set; construction raises :class:`~Code.Rpa.Errors.SelectorError`
    otherwise.

    :param tier: Resolution tier — ``"auto"`` (object → image → OCR), ``"object"``,
        ``"image"``, or ``"ocr"``.
    :param cls: Qt widget class name (e.g. ``"QPushButton"``).
    :param object_name: Qt ``objectName`` property — highest confidence discriminator.
    :param text: Label or display text. Matched as exact then substring.
    :param text_exact: If True, only exact text matches are accepted (default False).
    :param role: Accessibility role string.
    :param scope: Search scope — ``"all"`` (default) or ``"toolbar"``.
    :param index: 0-based index when multiple elements match (default 0).
    :param image: Template name from the manifest (image-tier only).
    :param threshold: Minimum confidence to accept a match (default 0.50 — admits
        class-only matches at 0.60; raise to 0.80+ when only text/name matches are wanted).
    """

    tier: str = "auto"
    cls: str | None = None
    object_name: str | None = None
    text: str | None = None
    text_exact: bool = False
    role: str | None = None
    scope: str = "all"
    index: int = 0
    image: str | None = None
    threshold: float = 0.50

    def __post_init__(self) -> None:
        """Validate tier and that at least one discriminating field is set.

        :raises SelectorError: If the tier is unknown or no discriminating field is set.
        """
        if self.tier not in _TIERS:
            raise SelectorError(
                f"Unknown tier {self.tier!r}. Must be one of: {sorted(_TIERS)}"
            )
        has_discriminator = any(
            getattr(self, f) for f in _DISCRIMINATING
        )
        if not has_discriminator:
            raise SelectorError(
                "Selector has no discriminating field. "
                "Set at least one of: object_name, text, cls, image, role."
            )

    # ------------------------------------------------------------------
    # JSON codec
    # ------------------------------------------------------------------

    def to_json(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict, omitting fields at their defaults.

        :returns: Dict suitable for ``json.dumps``.
        """
        defaults = dataclasses.fields(Selector)
        result = {}
        for f in defaults:
            val = getattr(self, f.name)
            if val != f.default:
                result[f.name] = val
        return result

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Selector":
        """Deserialise from a dict (e.g. from ``json.loads``).

        Unknown keys are silently ignored.

        :param data: Dict with selector fields.
        :returns: :class:`Selector` instance.
        :raises SelectorError: If the resulting selector has no discriminating field.
        """
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_json_str(cls, s: str) -> "Selector":
        """Parse a JSON string into a :class:`Selector`.

        :param s: JSON string.
        :returns: :class:`Selector` instance.
        :raises SelectorError: If JSON is invalid or selector lacks a discriminating field.
        """
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise SelectorError(f"Invalid JSON selector: {exc}") from exc
        if not isinstance(data, dict):
            raise SelectorError("Selector JSON must be an object, not a list or scalar.")
        return cls.from_json(data)

    # ------------------------------------------------------------------
    # Compact-string codec
    # ------------------------------------------------------------------

    def to_compact(self) -> str:
        """Serialise to a compact string, omitting fields at their defaults.

        Format: ``<tier>:<key>=<pct-encoded-value>[,<key>=<value>][@<dir>(<anchor>)]``

        Example: ``obj:object_name=play_btn``

        :returns: Compact string representation.
        """
        tier_abbr = {"auto": "auto", "object": "obj", "image": "img", "ocr": "ocr"}
        parts = [tier_abbr.get(self.tier, self.tier) + ":"]
        defaults_map = {f.name: f.default for f in dataclasses.fields(Selector)}
        kv_parts = []
        for f in dataclasses.fields(Selector):
            if f.name == "tier":
                continue
            val = getattr(self, f.name)
            if val == f.default or val is None:
                continue
            encoded = urllib.parse.quote(str(val), safe="")
            kv_parts.append(f"{f.name}={encoded}")
        return parts[0] + ",".join(kv_parts)

    @classmethod
    def from_compact(cls, s: str) -> "Selector":
        """Parse a compact selector string.

        Format: ``<tier_abbr>:<key>=<value>[,<key>=<value>...]``

        :param s: Compact selector string.
        :returns: :class:`Selector` instance.
        :raises SelectorError: If the string cannot be parsed or lacks a discriminating field.
        """
        tier_map = {"auto": "auto", "obj": "object", "img": "image", "ocr": "ocr",
                    "object": "object", "image": "image"}
        if ":" not in s:
            raise SelectorError(f"Compact selector missing tier prefix: {s!r}")
        prefix, rest = s.split(":", 1)
        tier = tier_map.get(prefix)
        if tier is None:
            raise SelectorError(f"Unknown tier abbreviation {prefix!r} in selector {s!r}")

        kwargs: dict[str, Any] = {"tier": tier}
        field_types = {f.name: f.type for f in dataclasses.fields(cls)}
        field_defaults = {f.name: f.default for f in dataclasses.fields(cls)}

        # Strip anchor if present (format: @dir(anchor_compact))
        # Anchors are handled at the Target level; we tolerate and discard them here.
        if "@" in rest:
            rest = rest[:rest.index("@")]

        if rest:
            for pair in rest.split(","):
                if "=" not in pair:
                    continue
                key, val_enc = pair.split("=", 1)
                val = urllib.parse.unquote(val_enc)
                if key not in field_defaults:
                    continue
                # Coerce booleans and integers
                if field_defaults[key] is False or field_defaults[key] is True:
                    kwargs[key] = val.lower() in ("1", "true", "yes")
                elif isinstance(field_defaults[key], int):
                    try:
                        kwargs[key] = int(val)
                    except ValueError:
                        pass
                elif isinstance(field_defaults[key], float):
                    try:
                        kwargs[key] = float(val)
                    except ValueError:
                        pass
                else:
                    kwargs[key] = val

        return cls(**kwargs)


@dataclasses.dataclass(frozen=True)
class Target:
    """A :class:`Selector` with optional anchor, direction, distance, and timeout.

    :param selector: The selector that identifies the target element.
    :param anchor: A second selector used as the spatial anchor (e.g. a label to the
        left of an input field). ``None`` means no anchor is applied.
    :param direction: Spatial relationship to the anchor — one of ``"right-of"``,
        ``"left-of"``, ``"above"``, ``"below"`` (required if ``anchor`` is set).
    :param max_distance: Maximum distance in logical pixels between anchor and target
        centres. ``None`` means no distance limit.
    :param timeout_ms: Override the default find-timeout for this target. ``None``
        inherits the resolver default.
    """

    selector: Selector
    anchor: Selector | None = None
    direction: str | None = None
    max_distance: int | None = None
    timeout_ms: int | None = None

    def __post_init__(self) -> None:
        """Validate anchor/direction consistency.

        :raises SelectorError: If anchor is set but direction is missing or invalid.
        """
        if self.anchor is not None and self.direction is None:
            raise SelectorError("Target has an anchor but no direction. Set direction.")
        if self.direction is not None and self.direction not in _DIRECTIONS:
            raise SelectorError(
                f"Unknown direction {self.direction!r}. Must be one of: {sorted(_DIRECTIONS)}"
            )

    def to_json(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict.

        :returns: Dict suitable for ``json.dumps``.
        """
        out: dict[str, Any] = {"selector": self.selector.to_json()}
        if self.anchor is not None:
            out["anchor"] = self.anchor.to_json()
        if self.direction is not None:
            out["direction"] = self.direction
        if self.max_distance is not None:
            out["max_distance"] = self.max_distance
        if self.timeout_ms is not None:
            out["timeout_ms"] = self.timeout_ms
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Target":
        """Deserialise from a dict.

        :param data: Dict with target fields.
        :returns: :class:`Target` instance.
        :raises SelectorError: If the selector is missing or malformed.
        """
        if "selector" not in data:
            raise SelectorError("Target dict must have a 'selector' key.")
        selector = Selector.from_json(data["selector"])
        anchor = Selector.from_json(data["anchor"]) if "anchor" in data else None
        return cls(
            selector=selector,
            anchor=anchor,
            direction=data.get("direction"),
            max_distance=data.get("max_distance"),
            timeout_ms=data.get("timeout_ms"),
        )
