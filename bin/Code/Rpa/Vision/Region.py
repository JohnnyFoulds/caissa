"""
bin/Code/Rpa/Vision/Region.py — Widget-tree flattening and phrase-based region grounding.

The two public functions that block work:

- :func:`flatten` — convert a nested ``widget_tree`` (parent-relative rects, as returned by
  ``Driver.dump_ui``) into a flat list of dicts with capture-absolute rects.  **This is the
  P5 fix**: ``Resolve.visible_elements`` and ``_object_candidates`` previously iterated the
  root list only, missing every widget below the top level.

- :func:`named_regions` — expose the human-navigable region names (objectName, pane-spec
  keys, layout-preset zone names) as a ``{name: Rect}`` mapping.  Used by ``resolve_phrase``
  and by ``caissa-eyes regions``.

Phrase-grounding (:func:`resolve_phrase`) and the full detector set live in later phases;
this module ships only what Phase 1 needs to unblock ``owner_of`` and peer clustering.

:spec: §6, Phase 1 (feature_spec.md)
"""

from __future__ import annotations

from typing import Any

from Code.Rpa.Types import Rect


def flatten(
    widget_tree: list[dict[str, Any]],
    origin: Rect | None = None,
) -> list[dict[str, Any]]:
    """Recursively flatten a nested widget tree into a list with capture-absolute rects.

    ``Driver.dump_ui`` returns rects in **parent-relative** coordinates (matching
    ``QWidget.geometry()``).  Hit-testing and peer clustering both need capture-absolute
    coordinates, which requires accumulating parent offsets while descending.

    Each output dict is a shallow copy of the source dict with ``rect`` replaced by a
    capture-absolute :class:`~Code.Rpa.Types.Rect` and ``children`` removed.  A
    ``_depth`` key records nesting depth (0 = root) for diagnostics.

    :param widget_tree: List of widget-info dicts as returned by ``Driver.dump_ui``.
        Each dict may contain a ``"children"`` list of the same shape.
    :param origin: Capture-absolute position of the parent's top-left corner.
        Pass ``None`` (or ``Rect(0, 0, 0, 0)``) for top-level windows.
    :returns: Flat list of widget dicts with capture-absolute ``rect`` values.
    """
    if origin is None:
        origin = Rect(0, 0, 0, 0)

    result: list[dict[str, Any]] = []
    _flatten_into(widget_tree, origin, depth=0, out=result)
    return result


def _flatten_into(
    nodes: list[dict[str, Any]],
    parent_origin: Rect,
    depth: int,
    out: list[dict[str, Any]],
) -> None:
    for node in nodes:
        raw = node.get("rect") or node.get("geometry") or {}
        if isinstance(raw, Rect):
            rel = raw
        else:
            rel = Rect(
                int(raw.get("x", 0)),
                int(raw.get("y", 0)),
                int(raw.get("w", raw.get("width", 0))),
                int(raw.get("h", raw.get("height", 0))),
            )
        abs_rect = Rect(
            parent_origin.x + rel.x,
            parent_origin.y + rel.y,
            rel.w,
            rel.h,
        )
        flat = {k: v for k, v in node.items() if k not in ("children", "rect", "geometry")}
        flat["rect"] = abs_rect
        flat["_depth"] = depth
        out.append(flat)

        children = node.get("children", [])
        if children:
            _flatten_into(children, abs_rect, depth + 1, out)


def named_regions(snapshot: Any) -> dict[str, Rect]:
    """Return a mapping of human-navigable region names to capture-absolute rects.

    Iterates the flattened widget tree and indexes widgets by ``object_name`` (when
    set) and by class name.  The result is what ``caissa-eyes regions`` prints and
    what ``resolve_phrase`` consults first.

    :param snapshot: Current app snapshot (``Snapshot`` instance; typed ``Any`` to
        avoid a circular import with ``Types``).
    :returns: Dict mapping name strings to :class:`~Code.Rpa.Types.Rect` values.
    """
    flat = flatten(snapshot.widget_tree)
    regions: dict[str, Rect] = {}
    for w in flat:
        if not w.get("visible", True):
            continue
        raw = w.get("rect")
        if not isinstance(raw, Rect):
            continue
        name = w.get("object_name")
        if name:
            regions[name] = raw
        cls = w.get("cls")
        if cls and cls not in regions:
            regions[cls] = raw
    return regions
