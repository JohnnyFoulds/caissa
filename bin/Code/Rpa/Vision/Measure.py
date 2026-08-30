"""
bin/Code/Rpa/Vision/Measure.py — Pure geometry and comparison functions.

All functions operate on ``Rect``s, ints and strings — no ndarray, no cv2.
Tier 1 (stdlib-only); enforced by test_cv2_confined_to_designated_vision_modules.

Key invariant: ``perceived_gaps`` is the fourth basis and it must be computed
*last*, because it requires the visible edges of neighbouring fills.  A missing
perceived gap is ``Gap(px=None, undefined_reason=...)`` not a zero.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from Code.Rpa.Types import Rect
from Code.Rpa.Vision.Scene import (
    BASIS_FILL,
    BASIS_INK,
    BASIS_PERCEIVED,
    BASIS_WIDGET,
    Corner,
    Fill,
    Gap,
    PeerAttr,
    PeerCluster,
    SceneNode,
    Scene,
    Seam,
    Surface,
)


# ---------------------------------------------------------------------------
# Basic geometry helpers
# ---------------------------------------------------------------------------

def gap(a: Rect, b: Rect, axis: str = "x") -> int:
    """Return the pixel gap between two rects along *axis*.

    :param a: First rect.
    :param b: Second rect (must be to the right / below *a*).
    :param axis: ``"x"`` or ``"y"``.
    :return: Gap in logical pixels (may be negative if rects overlap).
    """
    if axis == "x":
        return b.x - (a.x + a.w)
    return b.y - (a.y + a.h)


def to_logical(r: Rect, dpr: float) -> Rect:
    """Convert a physical-pixel rect to logical pixels.

    :param r: Physical-pixel rect.
    :param dpr: Device pixel ratio (e.g. 2.0 on Retina).
    :return: Logical-pixel rect — x/y floor, right/bottom ceil.
    """
    x = math.floor(r.x / dpr)
    y = math.floor(r.y / dpr)
    right = math.ceil((r.x + r.w) / dpr)
    bottom = math.ceil((r.y + r.h) / dpr)
    return Rect(x, y, right - x, bottom - y)


def aligned(
    rects: Sequence[Rect],
    edge: str = "top",
    tolerance_px: int = 1,
) -> bool:
    """Return whether all rects share the same edge within *tolerance_px*.

    :param rects: Rects to compare.
    :param edge: ``"top"`` | ``"bottom"`` | ``"left"`` | ``"right"`` | ``"cx"`` |
        ``"cy"``.
    :param tolerance_px: Allowed deviation in pixels.
    :return: ``True`` if all values are within tolerance of the first.
    """
    if len(rects) < 2:
        return True
    values = [_edge_value(r, edge) for r in rects]
    return max(values) - min(values) <= tolerance_px


def _edge_value(r: Rect, edge: str) -> int:
    return {
        "top": r.y,
        "bottom": r.y + r.h,
        "left": r.x,
        "right": r.x + r.w,
        "cx": r.x + r.w // 2,
        "cy": r.y + r.h // 2,
    }[edge]


def group_rows(
    rects: Sequence[Rect],
    tolerance_px: int = 2,
) -> list[list[Rect]]:
    """Group rects into horizontal rows by their top-edge proximity.

    :param rects: Rects to group.
    :param tolerance_px: Max top-edge difference to be considered the same row.
    :return: List of rows, each row sorted left-to-right.
    """
    if not rects:
        return []
    sorted_rects = sorted(rects, key=lambda r: (r.y, r.x))
    rows: list[list[Rect]] = []
    current_row: list[Rect] = [sorted_rects[0]]
    for r in sorted_rects[1:]:
        if abs(r.y - current_row[0].y) <= tolerance_px:
            current_row.append(r)
        else:
            rows.append(sorted(current_row, key=lambda x: x.x))
            current_row = [r]
    rows.append(sorted(current_row, key=lambda x: x.x))
    return rows


# ---------------------------------------------------------------------------
# Perceptual helpers
# ---------------------------------------------------------------------------

def relative_luminance(hex_colour: str) -> float:
    """Return the WCAG relative luminance of *hex_colour* (0.0–1.0).

    :param hex_colour: Six-digit hex string with optional leading ``#``.
    :return: Relative luminance.
    """
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return the WCAG contrast ratio between two colours (1.0–21.0).

    :param fg_hex: Foreground colour hex.
    :param bg_hex: Background colour hex.
    :return: Contrast ratio.
    """
    l1 = relative_luminance(fg_hex)
    l2 = relative_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def fill_is_visible(
    fill_hex: str,
    background_hex: str,
    delta: int = 12,
) -> bool:
    """Return whether *fill_hex* is perceptually distinct from *background_hex*.

    Uses a simple luminance-distance proxy.  A gradient fill should use its
    *maximum* channel distance across the ramp, not the mean.

    :param fill_hex: Fill colour.
    :param background_hex: Local background colour.
    :param delta: Minimum per-channel Euclidean distance (0–255 space) to be
        considered visible.
    :return: ``True`` if the fill presents a perceptible edge.
    """
    def _rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = _rgb(fill_hex)
    r2, g2, b2 = _rgb(background_hex)
    dist = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)
    return dist >= delta


def uniformity(
    values: Sequence[Optional[int]],
    tolerance_px: int = 1,
) -> tuple[str, float]:
    """Test whether a sequence of gap values is uniform.

    ``None`` entries are treated as undefined and excluded from the computation.
    A sequence where all values are ``None`` returns ``("indeterminate", 0.0)``.

    :param values: Gap values in logical px; ``None`` = undefined on this basis.
    :param tolerance_px: Allowed deviation for a ``"uniform"`` verdict.
    :return: ``(verdict, spread)`` where verdict is ``"uniform"`` |
        ``"non_uniform"`` | ``"indeterminate"`` and spread is max-min.
    """
    defined = [v for v in values if v is not None]
    if not defined:
        return ("indeterminate", 0.0)
    spread = float(max(defined) - min(defined))
    verdict = "uniform" if spread <= tolerance_px else "non_uniform"
    return (verdict, spread)


# ---------------------------------------------------------------------------
# The four bases
# ---------------------------------------------------------------------------

def gaps(
    nodes: Sequence[SceneNode],
    axis: str = "x",
    basis: str = BASIS_WIDGET,
) -> list[Gap]:
    """Return one ``Gap`` per adjacent pair of *nodes* on the given *basis*.

    :param nodes: Ordered sequence of nodes (left-to-right or top-to-bottom).
    :param axis: ``"x"`` or ``"y"``.
    :param basis: One of ``BASIS_WIDGET``, ``BASIS_FILL``, ``BASIS_INK``.
    :return: List of ``Gap``s, one shorter than *nodes*.
    """
    result: list[Gap] = []
    for i in range(len(nodes) - 1):
        a = nodes[i]
        b = nodes[i + 1]
        px: Optional[int]
        undefined_reason = ""

        if basis == BASIS_WIDGET:
            px = gap(a.rect, b.rect, axis)

        elif basis == BASIS_FILL:
            if a.fill is None or not a.fill.visible:
                px = None
                undefined_reason = f"{a.node_id}.fill.visible is False"
            elif b.fill is None or not b.fill.visible:
                px = None
                undefined_reason = f"{b.node_id}.fill.visible is False"
            else:
                # Use the fill rect's trailing edge
                a_rect = a.fill.rect if a.fill else a.rect
                b_rect = b.fill.rect if b.fill else b.rect
                px = gap(a_rect, b_rect, axis)
        elif basis == BASIS_INK:
            if a.ink is None:
                px = None
                undefined_reason = f"{a.node_id}.ink not measured"
            elif b.ink is None:
                px = None
                undefined_reason = f"{b.node_id}.ink not measured"
            else:
                px = gap(a.ink.rect, b.ink.rect, axis)
        else:
            px = None
            undefined_reason = f"unknown basis {basis!r}"

        result.append(Gap(
            basis=basis,
            before_id=a.node_id,
            after_id=b.node_id,
            axis=axis,
            px=px,
            undefined_reason=undefined_reason,
        ))
    return result


def perceived_gaps(
    nodes: Sequence[SceneNode],
    axis: str = "x",
) -> list[Gap]:
    """Return the *perceived* gap sequence — the fourth, derived basis.

    For each adjacent pair, walks from the left node's ink right edge looking
    for the first visible boundary (a fill edge or border edge from either node).
    Falls through to ink-to-ink when no visible boundary is found.

    ``None`` when neither node has measured ink.

    :param nodes: Ordered sequence of nodes.
    :param axis: ``"x"`` or ``"y"``.
    :return: List of ``Gap``s with ``basis=BASIS_PERCEIVED``.
    """
    result: list[Gap] = []
    for i in range(len(nodes) - 1):
        a = nodes[i]
        b = nodes[i + 1]
        px: Optional[int]
        undefined_reason = ""

        # Find the nearest visible edge to the *left* of b's ink
        # Priority: a's visible fill edge → b's visible fill/border edge → ink-to-ink
        nearest_boundary: Optional[int] = None

        # a's visible fill trailing edge
        if a.fill is not None and a.fill.visible:
            if axis == "x":
                candidate = a.fill.rect.x + a.fill.rect.w
            else:
                candidate = a.fill.rect.y + a.fill.rect.h
            if nearest_boundary is None or candidate > nearest_boundary:
                nearest_boundary = candidate

        # a's border trailing edge
        if a.borders:
            side = "right" if axis == "x" else "bottom"
            border_info = a.borders.get(side)
            if border_info:
                border_px, _ = border_info
                if axis == "x":
                    candidate = a.rect.x + a.rect.w + border_px
                else:
                    candidate = a.rect.y + a.rect.h + border_px
                if nearest_boundary is None or candidate > nearest_boundary:
                    nearest_boundary = candidate

        # b's visible fill leading edge
        if b.fill is not None and b.fill.visible:
            if axis == "x":
                candidate = b.fill.rect.x
            else:
                candidate = b.fill.rect.y
            if nearest_boundary is None or candidate < nearest_boundary:
                nearest_boundary = candidate

        # b's border leading edge
        if b.borders:
            side = "left" if axis == "x" else "top"
            border_info = b.borders.get(side)
            if border_info:
                border_px, _ = border_info
                if axis == "x":
                    candidate = b.rect.x - border_px
                else:
                    candidate = b.rect.y - border_px
                if nearest_boundary is None or candidate < nearest_boundary:
                    nearest_boundary = candidate

        # Fall through to ink-to-ink
        if a.ink is None or b.ink is None:
            px = None
            undefined_reason = "ink not measured on one or both nodes"
        else:
            if axis == "x":
                ink_a_edge = a.ink.rect.x + a.ink.rect.w
                ink_b_edge = b.ink.rect.x
            else:
                ink_a_edge = a.ink.rect.y + a.ink.rect.h
                ink_b_edge = b.ink.rect.y

            if nearest_boundary is not None:
                px = ink_b_edge - nearest_boundary
            else:
                px = ink_b_edge - ink_a_edge
                undefined_reason = "no visible boundary found; ink-to-ink fallback"

        result.append(Gap(
            basis=BASIS_PERCEIVED,
            before_id=a.node_id,
            after_id=b.node_id,
            axis=axis,
            px=px,
            undefined_reason=undefined_reason,
        ))
    return result


def gaps_all_bases(
    nodes: Sequence[SceneNode],
    axis: str = "x",
) -> dict[str, list[Gap]]:
    """Return gap sequences for all four bases.

    :param nodes: Ordered sequence of nodes.
    :param axis: ``"x"`` or ``"y"``.
    :return: ``{basis: [Gap, ...]}`` for all four bases.
    """
    return {
        BASIS_WIDGET: gaps(nodes, axis, BASIS_WIDGET),
        BASIS_FILL: gaps(nodes, axis, BASIS_FILL),
        BASIS_INK: gaps(nodes, axis, BASIS_INK),
        BASIS_PERCEIVED: perceived_gaps(nodes, axis),
    }


# ---------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------

def seams(
    nodes: Sequence[SceneNode],
    axis: str = "x",
) -> list[Seam]:
    """Return one ``Seam`` per adjacent pair of *nodes*.

    ``shows_owner`` is left as ``"unknown"`` here — the caller should fill it
    using ``seam_owner`` once the parent chain is available.

    :param nodes: Ordered sequence of nodes.
    :param axis: ``"x"`` or ``"y"``.
    :return: List of ``Seam``s.
    """
    result: list[Seam] = []
    for i in range(len(nodes) - 1):
        a = nodes[i]
        b = nodes[i + 1]
        px_gap = gap(a.rect, b.rect, axis)

        # Detect a border run crossing the gap
        closed = False
        border_hex = ""
        if px_gap == 0:
            # Touching — check if both sides have a matching border
            a_side = "right" if axis == "x" else "bottom"
            b_side = "left" if axis == "x" else "top"
            a_border = a.borders.get(a_side)
            b_border = b.borders.get(b_side)
            if a_border and b_border:
                if a_border[1] == b_border[1]:
                    closed = True
                    border_hex = a_border[1]

        result.append(Seam(
            before_id=a.node_id,
            after_id=b.node_id,
            axis=axis,
            px=px_gap,
            shows_hex="",
            shows_owner="unknown",
            closed=closed,
            border_hex=border_hex,
        ))
    return result


def seam_owner(
    shows_hex: str,
    node: SceneNode,
    ancestors: Sequence[SceneNode],
) -> str:
    """Classify what *shows_hex* belongs to — parent, ancestor, or unknown.

    :param shows_hex: Colour visible in the gap.
    :param node: One of the two nodes adjacent to the gap.
    :param ancestors: Parent chain from the immediate parent outward.
    :return: ``"parent"`` | ``"ancestor"`` | ``"unknown"``.
    """
    if not ancestors:
        return "unknown"
    parent = ancestors[0]
    if parent.fill is not None and parent.fill.hex_color.lstrip("#").lower() == shows_hex.lstrip("#").lower():
        return "parent"
    if parent.fill is not None and parent.fill.hex_start.lstrip("#").lower() == shows_hex.lstrip("#").lower():
        return "parent"
    for anc in ancestors[1:]:
        if anc.fill is not None:
            if anc.fill.hex_color.lstrip("#").lower() == shows_hex.lstrip("#").lower():
                return "ancestor"
            if anc.fill.hex_start.lstrip("#").lower() == shows_hex.lstrip("#").lower():
                return "ancestor"
    return "unknown"


def edge_is_open(
    node: SceneNode,
    side: str,
    neighbour: SceneNode,
) -> bool:
    """Return whether *node*'s *side* presents no continuous border toward *neighbour*.

    A closed edge has a ``borders`` entry on the relevant side; an open edge does not.

    :param node: The node whose edge is being tested.
    :param side: ``"top"`` | ``"bottom"`` | ``"left"`` | ``"right"``.
    :param neighbour: The node on the other side (used for context in future).
    :return: ``True`` if the edge is open (no border run).
    """
    return side not in node.borders or node.borders[side][0] == 0


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def surfaces(
    scene: Scene,
    spec: dict,
) -> list[Surface]:
    """Construct ``Surface`` objects from spec-supplied role declarations.

    The spec must contain a ``"surfaces"`` list, each entry declaring
    ``surface_id``, ``member_ids``, and ``role``.

    :param scene: The scene containing the nodes.
    :param spec: Design spec dict (e.g. from ``panes.spec.json``).
    :return: List of ``Surface`` objects with ``joined_at`` set when a
        seam between the first two members exists in ``scene.seams``.
    """
    result: list[Surface] = []
    spec_surfaces = spec.get("surfaces", [])
    seam_index = {(s.before_id, s.after_id): s for s in scene.seams}
    for entry in spec_surfaces:
        members = tuple(entry.get("member_ids", []))
        joined_at = None
        if len(members) >= 2:
            joined_at = seam_index.get((members[0], members[1]))
        result.append(Surface(
            surface_id=entry.get("surface_id", ""),
            member_ids=members,
            role=entry.get("role", ""),
            joined_at=joined_at,
        ))
    return result


def surface_breaks(
    surface: Surface,
    scene: Scene,
) -> list[str]:
    """Enumerate every way *surface* fails to be one continuous plane.

    :param surface: The surface to check.
    :param scene: Scene containing nodes and seams.
    :return: List of break descriptions ordered by severity (corner breaks
        first, then seam, then fill).
    """
    breaks: list[str] = []
    node_index = _node_index(scene)

    # Collect corner breaks — corner breaks are listed first (most visible)
    for mid in surface.member_ids:
        node = node_index.get(mid)
        if node is None:
            continue
        if "corners" not in node.measured:
            # Corner was NOT measured — cannot assert break or no-break
            continue
        for corner in node.corners:
            if corner.radius_px > 0 and corner.shows_owner == "ancestor":
                breaks.append(f"corner_{corner.which}_radius_{corner.radius_px}")

    # Seam break — the joining seam must be open (not closed)
    if surface.joined_at is not None:
        s = surface.joined_at
        if s.closed:
            breaks.append("seam_closed")
        if s.shows_owner == "ancestor":
            breaks.append("seam_shows_ancestor")

    # Fill mismatch: the selected member's fill must differ visibly from the content
    # fill — otherwise the tab conveys no selection signal (ΔE < 4 on the Caissa
    # dark palette).  Only fire when both fills exist AND hexes differ AND delta < 4.
    if len(surface.member_ids) >= 2:
        n0 = node_index.get(surface.member_ids[0])
        n1 = node_index.get(surface.member_ids[1])
        if n0 and n1 and n0.fill is not None and n1.fill is not None:
            hex0 = n0.fill.hex_color or n0.fill.hex_start
            hex1 = n1.fill.hex_color or n1.fill.hex_start
            if (
                hex0 and hex1
                and hex0.lstrip("#").lower() != hex1.lstrip("#").lower()
                and not fill_is_visible(hex0, hex1, delta=4)
            ):
                breaks.append("fill_mismatch")

    return breaks


# ---------------------------------------------------------------------------
# Peer clustering
# ---------------------------------------------------------------------------

def peer_signature(
    node: SceneNode,
    parent: Optional[SceneNode],
) -> tuple:
    """Compute the clustering signature for *node*.

    Buckets height to ±1 px and fill hex to the first 4 chars to absorb
    antialiasing drift.

    :param node: The node to compute a signature for.
    :param parent: Immediate parent node (may be ``None``).
    :return: Tuple used as a clustering key.
    """
    height_bucket = (node.rect.h // 2) * 2  # ±1 px bucket
    fill_bucket = ""
    if node.fill is not None:
        fill_bucket = (node.fill.hex_color or node.fill.hex_start)[:4]
    parent_role = parent.role if parent else ""
    # index within parent approximated from x/y position bucket
    pos_bucket = node.rect.x // 20 if node.rect.x else node.rect.y // 20
    return (node.role, parent_role, pos_bucket, height_bucket, fill_bucket)


def peers(
    scene: Scene,
    min_size: int = 2,
) -> list[PeerCluster]:
    """Cluster all scene nodes by structural signature.

    :param scene: The scene to cluster.
    :param min_size: Minimum cluster size to include.
    :return: List of ``PeerCluster``s, each with ``≥ min_size`` members.
    """
    if scene.root is None:
        return []
    all_nodes = _flatten_nodes(scene.root)
    parent_map: dict[str, SceneNode] = {}
    _build_parent_map(scene.root, None, parent_map)

    buckets: dict[tuple, list[SceneNode]] = {}
    for node in all_nodes:
        parent = parent_map.get(node.node_id)
        sig = peer_signature(node, parent)
        buckets.setdefault(sig, []).append(node)

    result: list[PeerCluster] = []
    for sig, members in buckets.items():
        if len(members) < min_size:
            continue
        # Name the cluster from the role + fill bucket
        role = sig[0]
        cluster_id = f"{role}_{len(result)}" if role else f"cluster_{len(result)}"
        result.append(PeerCluster(
            cluster_id=cluster_id,
            signature=sig,
            members=tuple(n.node_id for n in members),
            parents=tuple(
                parent_map[n.node_id].node_id
                if n.node_id in parent_map and parent_map[n.node_id] else ""
                for n in members
            ),
        ))
    return result


def compare_peers(
    cluster: PeerCluster,
    scene: Scene,
) -> dict[str, PeerAttr]:
    """Compare attribute uniformity across a peer cluster.

    :param cluster: The cluster to analyse.
    :param scene: The scene containing the nodes.
    :return: ``{attr_name: PeerAttr}`` — one entry per measured attribute.
    """
    node_index = _node_index(scene)
    nodes = [node_index[mid] for mid in cluster.members if mid in node_index]
    if not nodes:
        return {}

    attrs: dict[str, PeerAttr] = {}

    # Geometric attributes
    for attr_name, getter in [
        ("left_edge", lambda n: n.rect.x),
        ("top_offset", lambda n: n.rect.y),
        ("width", lambda n: n.rect.w),
        ("height", lambda n: n.rect.h),
    ]:
        values = tuple(getter(n) for n in nodes)
        status = "CONSTANT" if len(set(values)) == 1 else "VARYING"
        attrs[attr_name] = PeerAttr(name=attr_name, status=status, values=values)

    # Fill attributes
    fill_hexes = tuple(
        (n.fill.hex_color or n.fill.hex_start) if n.fill else ""
        for n in nodes
    )
    fill_status = "CONSTANT" if len(set(fill_hexes)) == 1 else "VARYING"
    attrs["fill_hex"] = PeerAttr(name="fill_hex", status=fill_status, values=fill_hexes)

    fill_visible = tuple(
        n.fill.visible if n.fill else None for n in nodes
    )
    fv_status = "CONSTANT" if len(set(fill_visible)) == 1 else "VARYING"
    attrs["fill_visible"] = PeerAttr(
        name="fill_visible", status=fv_status, values=fill_visible
    )

    # Label attributes
    labels = tuple(n.label for n in nodes)
    label_status = "CONSTANT" if len(set(labels)) == 1 else "VARYING"
    attrs["label"] = PeerAttr(name="label", status=label_status, values=labels)

    return attrs


# ---------------------------------------------------------------------------
# Style-source bridge helpers
# ---------------------------------------------------------------------------

def owner_of(
    rect: Rect,
    flat_nodes: Sequence[dict],
    min_overlap: float = 0.9,
) -> Optional[dict]:
    """Return the smallest widget dict that contains *rect* with at least
    *min_overlap* coverage.

    *flat_nodes* must be the output of ``Region.flatten`` — capture-absolute rects.

    :param rect: Target rect in capture-absolute logical px.
    :param flat_nodes: Flattened widget dicts with capture-absolute ``rect`` keys.
    :param min_overlap: Minimum IoU fraction to count as a match.
    :return: Best-matching widget dict, or ``None``.
    """
    best: Optional[dict] = None
    best_area = float("inf")
    for node in flat_nodes:
        node_rect: Rect = node.get("rect")
        if node_rect is None:
            continue
        overlap = rect.intersection(node_rect)
        if overlap is None:
            continue
        iou_val = rect.iou(node_rect)
        if iou_val >= min_overlap:
            area = node_rect.area
            if area < best_area:
                best_area = area
                best = node
    return best


def sub_rect_of(
    widget: dict,
    rect: Rect,
) -> Optional[dict]:
    """Return the sub_rect entry within *widget* that best contains *rect*.

    :param widget: Widget dict from ``Driver.widget_info`` (may have ``sub_rects``).
    :param rect: Target rect in the same coordinate space as the widget.
    :return: Matching sub_rect dict, or ``None``.
    """
    sub_rects = widget.get("sub_rects", [])
    best: Optional[dict] = None
    best_iou = 0.0
    for sr in sub_rects:
        sr_rect = sr.get("rect")
        if sr_rect is None:
            continue
        iou_val = rect.iou(sr_rect)
        if iou_val > best_iou:
            best_iou = iou_val
            best = sr
    return best if best_iou > 0.5 else None


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _node_index(scene: Scene) -> dict[str, SceneNode]:
    """Build a flat ``{node_id: SceneNode}`` index for *scene*."""
    if scene.root is None:
        return {}
    index: dict[str, SceneNode] = {}
    _collect_nodes(scene.root, index)
    return index


def _collect_nodes(node: SceneNode, index: dict) -> None:
    index[node.node_id] = node
    for child in node.children:
        _collect_nodes(child, index)


def _flatten_nodes(root: SceneNode) -> list[SceneNode]:
    """Return all nodes in the tree as a flat list (pre-order)."""
    result: list[SceneNode] = [root]
    for child in root.children:
        result.extend(_flatten_nodes(child))
    return result


def _build_parent_map(
    node: SceneNode,
    parent: Optional[SceneNode],
    parent_map: dict[str, SceneNode],
) -> None:
    """Populate *parent_map* with ``{node_id: parent}`` entries."""
    if parent is not None:
        parent_map[node.node_id] = parent
    for child in node.children:
        _build_parent_map(child, node, parent_map)
