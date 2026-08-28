"""
bin/Code/Rpa/Resolve.py — Tiered target resolver for the Caissa RPA layer.

:class:`TargetResolver` resolves a :class:`~Code.Rpa.Targets.Target` against a
:class:`~Code.Rpa.Types.Snapshot`, returning an :class:`~Code.Rpa.Types.ElementRef`.

**Object-tier confidence model:**

+---------------------------+--------+
| Match type                |  Score |
+===========================+========+
| Exact ``object_name``     |  1.00  |
| Exact ``text``            |  0.95  |
| Text substring            |  0.80  |
| Class-only (``cls``)      |  0.60  |
+---------------------------+--------+

When a non-object tier wins the resolution, a ``WARNING`` is emitted because that
indicates the object selector is broken and should be fixed.

Image and OCR tiers are not yet implemented — they raise
:class:`~Code.Rpa.Errors.VisionUnavailableError` as stubs pending Phase 7.

:spec: FR-4, §6 (feature_spec.md)
"""

from __future__ import annotations

import logging
import math
from typing import Any

from Code.Rpa.Errors import AmbiguousMatchError, TargetNotFoundError, VisionUnavailableError
from Code.Rpa.Targets import Selector, Target
from Code.Rpa.Types import ElementRef, Rect, Snapshot

logger = logging.getLogger(__name__)

# Object-tier confidence scores
_CONF_EXACT_OBJECT_NAME: float = 1.00
_CONF_EXACT_TEXT: float = 0.95
_CONF_SUBSTRING_TEXT: float = 0.80
_CONF_CLASS_ONLY: float = 0.60


def _widget_rect(widget: dict[str, Any]) -> Rect | None:
    """Extract a :class:`~Code.Rpa.Types.Rect` from a widget-info dict.

    Widget info dicts produced by ``QtDriver.snapshot()`` carry a ``rect`` key
    with either a ``Rect`` instance or a ``{x, y, w, h}`` sub-dict.

    :param widget: Widget info dict.
    :returns: :class:`~Code.Rpa.Types.Rect` or ``None`` if the key is absent/invalid.
    """
    raw = widget.get("rect")
    if raw is None:
        return None
    if isinstance(raw, Rect):
        return raw
    if isinstance(raw, dict):
        try:
            return Rect(
                x=int(raw["x"]),
                y=int(raw["y"]),
                w=int(raw["w"]),
                h=int(raw["h"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _object_confidence(selector: Selector, widget: dict[str, Any]) -> float | None:
    """Return object-tier confidence for *widget* against *selector*, or ``None`` if below threshold.

    :param selector: The selector to match against.
    :param widget: Widget info dict from the snapshot.
    :returns: Confidence in [0.0, 1.0] if the widget matches, else ``None``.
    """
    # Class filter — must match if specified
    if selector.cls is not None and widget.get("cls") != selector.cls:
        return None

    score: float | None = None

    if selector.object_name is not None:
        if widget.get("object_name") == selector.object_name:
            score = _CONF_EXACT_OBJECT_NAME

    if selector.text is not None and score is None:
        wtext = widget.get("text", "") or ""
        if selector.text_exact:
            if wtext == selector.text:
                score = _CONF_EXACT_TEXT
        else:
            if wtext == selector.text:
                score = _CONF_EXACT_TEXT
            elif selector.text in wtext:
                score = _CONF_SUBSTRING_TEXT

    # Class-only match (no object_name or text selector fields set)
    if (selector.object_name is None
            and selector.text is None
            and selector.cls is not None
            and score is None):
        score = _CONF_CLASS_ONLY

    if score is None:
        return None

    return score if score >= selector.threshold else None


def _centre_distance(a: Rect, b: Rect) -> float:
    """Euclidean distance between the centres of two rects in logical pixels.

    :param a: First rect.
    :param b: Second rect.
    :returns: Distance in logical pixels.
    """
    dx = a.cx - b.cx
    dy = a.cy - b.cy
    return math.sqrt(dx * dx + dy * dy)


def _is_in_direction(anchor_rect: Rect, candidate_rect: Rect, direction: str) -> bool:
    """Return True if *candidate_rect* lies in *direction* relative to *anchor_rect*.

    Uses centre-to-centre comparison.

    :param anchor_rect: The anchor element's bounding rect.
    :param candidate_rect: The candidate element's bounding rect.
    :param direction: One of ``"right-of"``, ``"left-of"``, ``"above"``, ``"below"``.
    :returns: True if the spatial relationship holds.
    """
    if direction == "right-of":
        return candidate_rect.cx > anchor_rect.cx
    if direction == "left-of":
        return candidate_rect.cx < anchor_rect.cx
    if direction == "above":
        return candidate_rect.cy < anchor_rect.cy
    if direction == "below":
        return candidate_rect.cy > anchor_rect.cy
    return False


class _Candidate:
    """Internal: a widget match with its confidence and rect."""

    __slots__ = ("widget", "confidence", "rect")

    def __init__(self, widget: dict[str, Any], confidence: float, rect: Rect) -> None:
        self.widget = widget
        self.confidence = confidence
        self.rect = rect


class TargetResolver:
    """Resolves :class:`~Code.Rpa.Targets.Target` descriptors against
    :class:`~Code.Rpa.Types.Snapshot` data.

    The resolver is **stateless** — it holds no cached widget lists between calls.
    The per-pump cache described in the architecture is the responsibility of the
    ``Runner`` (which holds the current ``Snapshot`` for the duration of a pump).

    :param default_timeout_ms: Timeout used when ``Target.timeout_ms`` is ``None``.
        This value is informational for the caller; ``resolve_one`` does not wait —
        it resolves synchronously against the supplied snapshot.
    """

    def __init__(self, default_timeout_ms: int = 5000) -> None:
        """Initialise the resolver.

        :param default_timeout_ms: Default find-timeout in milliseconds.
        """
        self.default_timeout_ms = default_timeout_ms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def visible_elements(self, snapshot: Snapshot) -> list[ElementRef]:
        """Return all visible elements from *snapshot* as :class:`~Code.Rpa.Types.ElementRef` objects.

        Elements without a ``rect`` are omitted. Uses the widget's ``object_name`` as
        the selector string in the returned ref; falls back to class if ``object_name``
        is absent.

        :param snapshot: Current app snapshot.
        :returns: List of :class:`~Code.Rpa.Types.ElementRef` for all visible widgets.
        """
        refs = []
        for w in snapshot.widget_tree:
            if not w.get("visible", True):
                continue
            rect = _widget_rect(w)
            if rect is None:
                continue
            name = w.get("object_name") or w.get("cls", "")
            refs.append(ElementRef(selector=name, rect=rect))
        return refs

    def resolve_one(self, target: Target, snapshot: Snapshot) -> ElementRef:
        """Resolve *target* against *snapshot*, returning the best-match element.

        Resolution order:
        1. Object tier (Qt widget tree).
        2. Image tier — stub; raises :class:`~Code.Rpa.Errors.VisionUnavailableError`.
        3. OCR tier — stub; raises :class:`~Code.Rpa.Errors.VisionUnavailableError`.

        When a non-object tier wins, ``logger.warning`` is emitted.

        :param target: The target to resolve.
        :param snapshot: Current app snapshot.
        :returns: :class:`~Code.Rpa.Types.ElementRef` for the best match.
        :raises AmbiguousMatchError: If two or more candidates share the highest confidence.
        :raises TargetNotFoundError: If no candidate meets the threshold.
        :raises VisionUnavailableError: If the image or OCR tier is explicitly requested.
        """
        tier = target.selector.tier

        if tier == "image":
            raise VisionUnavailableError(
                "Image tier not yet implemented (Phase 7). "
                "Install: pip install -r requirements-rpa.txt"
            )
        if tier == "ocr":
            raise VisionUnavailableError(
                "OCR tier not yet implemented (Phase 7). "
                "Install: pip install -r requirements-rpa.txt && brew install tesseract"
            )

        # Object tier
        candidates = self._object_candidates(target.selector, snapshot)

        if not candidates and tier == "auto":
            # Image and OCR tiers are Phase 7 stubs — fall through to not-found
            logger.warning(
                "Object tier found no match for selector %r; image/OCR tiers not yet available",
                target.selector,
            )

        # Apply anchor filter
        if target.anchor is not None and candidates:
            candidates = self._apply_anchor(
                candidates, target, snapshot
            )

        if not candidates:
            raise TargetNotFoundError(
                f"No element found matching {target.selector!r}"
            )

        return self._pick_best(candidates, target.selector)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _object_candidates(
        self, selector: Selector, snapshot: Snapshot
    ) -> list[_Candidate]:
        """Score all visible widgets in *snapshot* against *selector*.

        :param selector: The selector to match against.
        :param snapshot: Current app snapshot.
        :returns: List of :class:`_Candidate` objects whose confidence meets the threshold.
        """
        results = []
        for widget in snapshot.widget_tree:
            if not widget.get("visible", True):
                continue
            conf = _object_confidence(selector, widget)
            if conf is None:
                continue
            rect = _widget_rect(widget)
            if rect is None:
                continue
            results.append(_Candidate(widget=widget, confidence=conf, rect=rect))
        return results

    def _apply_anchor(
        self,
        candidates: list[_Candidate],
        target: Target,
        snapshot: Snapshot,
    ) -> list[_Candidate]:
        """Filter *candidates* to those spatially related to the anchor.

        Resolves the anchor selector against the snapshot first. If the anchor
        cannot be resolved, the candidates are returned unfiltered (a warning is
        emitted).

        :param candidates: Pre-filtered candidates for the main selector.
        :param target: The target supplying anchor, direction, and max_distance.
        :param snapshot: Current snapshot.
        :returns: Filtered (or original) candidates list.
        """
        try:
            anchor_ref = self.resolve_one(
                Target(selector=target.anchor), snapshot  # type: ignore[arg-type]
            )
        except (TargetNotFoundError, AmbiguousMatchError) as exc:
            logger.warning("Anchor resolution failed (%s); ignoring anchor", exc)
            return candidates

        direction = target.direction
        max_dist = target.max_distance
        filtered = []
        for c in candidates:
            if not _is_in_direction(anchor_ref.rect, c.rect, direction):
                continue
            if max_dist is not None:
                dist = _centre_distance(anchor_ref.rect, c.rect)
                if dist > max_dist:
                    continue
            filtered.append(c)
        return filtered if filtered else candidates

    @staticmethod
    def _pick_best(candidates: list[_Candidate], selector: Selector) -> ElementRef:
        """Return the unique best candidate or raise on ambiguity.

        :param candidates: Non-empty list of candidates.
        :param selector: Original selector (for error messages).
        :returns: :class:`~Code.Rpa.Types.ElementRef` for the best match.
        :raises AmbiguousMatchError: If two or more share the highest confidence.
        """
        best_conf = max(c.confidence for c in candidates)
        best = [c for c in candidates if c.confidence == best_conf]

        # If index is set, use positional selection among tied winners
        if len(best) > 1 and selector.index > 0:
            if selector.index < len(best):
                best = [best[selector.index]]
            else:
                best = []

        if len(best) == 0:
            raise TargetNotFoundError(f"No element found after index filtering for {selector!r}")

        if len(best) > 1:
            names = [c.widget.get("object_name") or c.widget.get("text", "?") for c in best]
            raise AmbiguousMatchError(
                f"Ambiguous match for {selector!r}: {len(best)} candidates at "
                f"confidence {best_conf:.2f} — {names!r}. "
                "Use object_name, text_exact=True, or index to disambiguate."
            )

        winner = best[0]
        name = winner.widget.get("object_name") or winner.widget.get("text") or selector.cls or ""
        return ElementRef(selector=name, rect=winner.rect)
