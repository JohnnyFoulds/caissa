"""
bin/Code/Rpa/Vision/Scene.py — Frozen dataclasses for the RPA design-vision feature.

Every type produced by the Vision layer lives here: Fill, Ink, Seam, Corner, Surface,
SceneNode, Scene, Gap, Hypothesis, Finding, PeerAttr, PeerCluster, RegionMatch.

Measure.py, Region.py, Detectors.py, StyleSource.py and Report.py contain *functions*
only — they import these types, never define them. This keeps the dependency graph a
tree and the ≥90% branch gate honest (Scene.py is data + two renderers, trivially
coverable; branchy logic lives in leaf modules).

ZERO cv2/numpy imports — Tier 1 (stdlib-only). Enforced by test_cv2_confined_to_
designated_vision_modules.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Tuple

from Code.Rpa.Types import Rect

# ---------------------------------------------------------------------------
# Basis constants
# ---------------------------------------------------------------------------

BASIS_WIDGET = "widget"
BASIS_FILL = "fill"
BASIS_INK = "ink"
BASIS_PERCEIVED = "perceived"

# The completeness inventory.  describe() must attempt every entry and record
# the result in SceneNode.measured; to_ascii() prints the difference as
# "not measured:".  This constant IS the fix for the corner-miss: the
# inventory is data, not a habit.
MEASURABLE: Tuple[str, ...] = ("fill", "ink", "borders", "corners", "seams")


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Fill:
    """Measured fill of one node, supporting flat and gradient kinds.

    :param rect: The bounding rect of the fill band (may be smaller than node rect
        after border stripping).
    :param kind: ``"flat"`` | ``"gradient_v"`` | ``"gradient_h"`` | ``"textured"``.
    :param hex_color: Dominant colour for flat fills (empty string otherwise).
    :param hex_start: Start colour for gradients (sampled at the band's top/left extreme).
    :param hex_end: End colour for gradients (sampled at the band's bottom/right extreme).
    :param visible: Whether the fill presents a perceptible edge against its background.
        For gradients this is the **maximum** distance from background_hex over the ramp —
        a band that straddles its background has visible extremes but an invisible midpoint,
        which is a different defect from a uniformly invisible band.
    :param visible_delta: The maximum perceptual distance (ΔE proxy) used to compute
        ``visible``, kept so the report can show its own margin.
    :param background_hex: The local background colour compared against — never a global
        constant.
    :param border_px: Uniform border ring thickness, stripped before ink measurement.
    :param border_hex: Colour of the border ring (empty string when ``border_px == 0``).
    """

    rect: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    kind: str = "flat"
    hex_color: str = ""
    hex_start: str = ""
    hex_end: str = ""
    visible: bool = False
    visible_delta: int = 0
    background_hex: str = ""
    border_px: int = 0
    border_hex: str = ""


@dataclass(frozen=True, slots=True)
class Ink:
    """Measured glyph-ink extent for one node.

    :param rect: Bounding rect of all glyph pixels within the node (logical px).
    :param coverage: Fraction of node pixels that are ink (0.0–1.0).
    :param hex_dominant: Most common ink colour in this node.
    """

    rect: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    coverage: float = 0.0
    hex_dominant: str = ""


@dataclass(frozen=True, slots=True)
class Seam:
    """The shared boundary between two adjacent nodes, or a node and its container.

    ``shows_owner`` is the verdict-changing field: a gap showing the *parent's* own
    background is a designed margin; a gap showing an *ancestor's* background is a
    hole through to a grandparent.

    :param before_id: node_id of the node to the left/above.
    :param after_id: node_id of the node to the right/below.
    :param axis: ``"x"`` (horizontal gap) or ``"y"`` (vertical gap).
    :param px: Gap width in logical pixels (0 = nodes touch).
    :param shows_hex: Colour visible in the gap (empty when ``px == 0``).
    :param shows_owner: ``"parent"`` | ``"ancestor"`` | ``"unknown"`` — distinguishes
        a designed margin from a hole.
    :param closed: Whether a continuous border run crosses the seam.
    :param border_hex: Colour of that border run (empty when ``closed is False``).
    """

    before_id: str = ""
    after_id: str = ""
    axis: str = "x"
    px: int = 0
    shows_hex: str = ""
    shows_owner: str = "unknown"
    closed: bool = False
    border_hex: str = ""


@dataclass(frozen=True, slots=True)
class Corner:
    """One corner of a node's border, measured from the arc's pixel staircase.

    ``shows_owner == "ancestor"`` means the notch outside the arc shows a grandparent
    colour — a visible bite taken out of the surface.

    :param which: ``"tl"`` | ``"tr"`` | ``"bl"`` | ``"br"``.
    :param radius_px: Measured arc radius (0 = square corner).
    :param shows_hex: Colour filling the notch outside the arc.
    :param shows_owner: ``"parent"`` | ``"ancestor"`` | ``"unknown"``.
    """

    which: str = "tl"
    radius_px: int = 0
    shows_hex: str = ""
    shows_owner: str = "unknown"


@dataclass(frozen=True, slots=True)
class Surface:
    """Nodes that a design convention says should render as one continuous plane.

    Spec-supplied — the design rule (*"a tab and its content are one page"*) cannot
    be derived from pixels alone.

    :param surface_id: Stable identifier, e.g. ``"tab_page"``.
    :param member_ids: node_ids of every member, in reading order.
    :param role: Design role, e.g. ``"tab_page"`` | ``"card"``.
    :param joined_at: The ``Seam`` the members must merge across (``None`` when not
        yet measured).
    :param breaks: Detected surface breaks, e.g. ``"corner_tl_radius_8"``,
        ``"seam_closed"``, ``"fill_mismatch"``, ``"seam_shows_ancestor"``.
    """

    surface_id: str = ""
    member_ids: Tuple[str, ...] = ()
    role: str = ""
    joined_at: Optional[Seam] = None
    breaks: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Supporting types (used by Measure / Detectors / Report)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Gap:
    """One measured gap between two adjacent nodes on a given basis.

    ``px`` is ``None`` when this basis is not applicable (e.g. fill basis when the
    fill is invisible).

    :param basis: One of the ``BASIS_*`` constants.
    :param before_id: node_id of the node before the gap.
    :param after_id: node_id of the node after the gap.
    :param axis: ``"x"`` or ``"y"``.
    :param px: Gap width in logical px; ``None`` = undefined on this basis.
    :param undefined_reason: Human-readable reason when ``px is None``.
    """

    basis: str = BASIS_WIDGET
    before_id: str = ""
    after_id: str = ""
    axis: str = "x"
    px: Optional[int] = None
    undefined_reason: str = ""


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A candidate causal mechanism for a finding, ranked by likelihood.

    :param mechanism: Plain-English description of the proposed cause.
    :param likelihood: ``"likely"`` | ``"possible"`` | ``"unlikely"``.
    :param would_confirm: What evidence would settle the hypothesis.
    :param ruled_out_by: Set when a measurement already excludes this mechanism.
    """

    mechanism: str = ""
    likelihood: str = "possible"
    would_confirm: str = ""
    ruled_out_by: str = ""


@dataclass(frozen=True, slots=True)
class Finding:
    """One finding produced by a detector or by the StyleSource bridge.

    ``summary`` states only what was measured — no causal language.
    ``hypotheses`` lists candidate mechanisms; ``confirmed_by`` is empty until
    step 5 resolves one.

    :param kind: Detector name from the canonical registry, e.g. ``"invisible_fill"``.
    :param verdict: ``"ok"`` | ``"non_uniform"`` | ``"violated"`` | ``"indeterminate"``.
    :param summary: One-line plain-English statement of the measurement.
    :param node_ids: Every node the finding covers (drives ranking by node count).
    :param severity: ``"error"`` | ``"warn"`` | ``"info"``.
    :param measurements: Key→value dict of what the pixels say.
    :param hypotheses: Candidate mechanisms, ranked, never asserted.
    :param confirmed_by: Empty until the StyleSource bridge or a live probe resolves
        the mechanism; renders as ``"(pending)"`` when empty.
    :param per_basis: Basis→verdict mapping (spacing_uniformity only).
    :param gaps: Gap list (spacing_uniformity only).
    :param caused_by: ``kind`` of the finding this one is a consequence of.
    :param evidence: Free-form evidence dict.
    :param sources: StyleSource output — list of style-source dicts.
    """

    kind: str = ""
    verdict: str = "ok"
    summary: str = ""
    node_ids: Tuple[str, ...] = ()
    severity: str = "warn"
    measurements: dict = field(default_factory=dict)
    hypotheses: Tuple[Hypothesis, ...] = ()
    confirmed_by: str = ""
    per_basis: dict = field(default_factory=dict)
    gaps: Tuple[Gap, ...] = ()
    caused_by: str = ""
    evidence: dict = field(default_factory=dict)
    sources: Tuple[dict, ...] = ()


@dataclass(frozen=True, slots=True)
class PeerAttr:
    """One attribute comparison across a peer cluster.

    :param name: Attribute name, e.g. ``"width"``.
    :param status: ``"CONSTANT"`` | ``"VARYING"``.
    :param values: One value per cluster member, in member order.
    :param normalised: Normalised values (e.g. width/parent_w), when applicable.
    """

    name: str = ""
    status: str = "CONSTANT"
    values: tuple = ()
    normalised: tuple = ()


@dataclass(frozen=True, slots=True)
class PeerCluster:
    """A set of nodes that share a structural signature (same role, position, size class).

    :param cluster_id: Descriptive identifier, e.g. ``"pane_caption"``.
    :param signature: The (role, parent_role, index_within_parent, height_bucket,
        fill_hex_bucket, font_size_bucket) tuple used to group nodes.
    :param members: node_ids in reading order.
    :param parents: parent node_ids, one per member.
    """

    cluster_id: str = ""
    signature: tuple = ()
    members: Tuple[str, ...] = ()
    parents: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RegionMatch:
    """Result of ``Region.resolve_phrase``.

    :param rect: Resolved region in capture-absolute logical pixels.
    :param source: Resolution path — ``"lexicon"`` | ``"objectname"`` |
        ``"classname"`` | ``"attrpath"`` | ``"geometric"`` | ``"pixel"``.
    :param confidence: 0.0–1.0 estimate of match quality.
    :param object_name: Qt objectName of the matched widget, when available.
    """

    rect: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    source: str = ""
    confidence: float = 1.0
    object_name: str = ""


# ---------------------------------------------------------------------------
# SceneNode
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SceneNode:
    """One measured UI element in a Scene.

    ``fill=None`` means *not measured*, which is different from
    ``fill=Fill(visible=False)`` (*measured, and invisible*).  The same
    distinction applies to ``ink`` and ``corners``.  ``measured`` records which
    inventory items were actually attempted; ``to_ascii`` prints the difference
    as ``not measured:``.

    :param node_id: Stable positional identifier, e.g. ``"tab[1]"``.
    :param rect: Widget/sub_rect basis in logical px (capture-absolute after
        ``Region.flatten``).
    :param role: ``"widget"`` | ``"tab"`` | ``"action"`` | ``"region"``.
    :param alias: Human-readable name derived from OCR; never load-bearing.
    :param label: OCR text; empty string when OCR failed or was off.
    :param label_confidence: OCR confidence 0.0–1.0.
    :param object_name: Qt objectName.
    :param cls: Qt class name.
    :param fill: Measured fill, or ``None`` when not attempted.
    :param ink: Measured ink, or ``None`` when not attempted.
    :param corners: Up to 4 measured corners; empty tuple = NOT MEASURED (not square).
    :param borders: Per-side border: ``{side: (thickness_px, hex_color)}``.
    :param measured: Which inventory items from ``MEASURABLE`` were attempted.
    :param sources: Tiers that contributed, strongest first.
    :param style_rules: Ordered list of style-source dicts from StyleSource.
    :param paint_authority: The paintEvent override dict, when present.
    :param children: Child nodes (used by ``to_ascii`` for tree rendering).
    :param attrs: Arbitrary string attributes, e.g. ``{"selected": "true"}``.
    """

    node_id: str = ""
    rect: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    role: str = "widget"
    alias: str = ""
    label: str = ""
    label_confidence: float = 0.0
    object_name: str = ""
    cls: str = ""
    fill: Optional[Fill] = None
    ink: Optional[Ink] = None
    corners: Tuple[Corner, ...] = ()
    borders: dict = field(default_factory=dict)
    measured: frozenset = field(default_factory=frozenset)
    sources: Tuple[str, ...] = ()
    style_rules: Tuple[dict, ...] = ()
    paint_authority: Optional[dict] = None
    children: Tuple["SceneNode", ...] = ()
    attrs: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Scene:
    """A fully measured snapshot of one UI region.

    ``seams``, ``surfaces`` and ``clusters`` hang off ``Scene`` rather than
    ``SceneNode`` because they are relations *between* nodes — a ``Seam`` has two
    endpoints, a ``Surface`` names members in different parents, a ``PeerCluster``
    spans parents entirely.

    :param scene_id: Stable identifier, e.g. ``"ribbon_tabbar"``.
    :param region: The capture rect this scene covers, logical px.
    :param root: The root ``SceneNode`` (may have children for tree rendering).
    :param palette: Top-N colours as ``(hex, pixel_count)`` pairs, descending.
    :param theme: Active theme name, e.g. ``"Caissa"``.
    :param ui_mode: Active UI mode name, e.g. ``"Modern Fritz"``.
    :param dpr: Device pixel ratio of the capture.
    :param seams: All inter-node seams measured for this scene.
    :param surfaces: Spec-supplied multi-node planes.
    :param clusters: Peer clusters detected by ``Measure.peers``.
    :param findings: Findings produced by ``Detectors.run_all``.
    :param warnings: String tags for degraded measurement:
        ``"cv_unavailable"``, ``"ocr_unavailable"``, ``"no_capture"``,
        ``"qss_unconfirmed"``.
    """

    scene_id: str = ""
    region: Rect = field(default_factory=lambda: Rect(0, 0, 0, 0))
    root: Optional[SceneNode] = None
    palette: Tuple[Tuple[str, int], ...] = ()
    theme: str = ""
    ui_mode: str = ""
    dpr: float = 1.0
    seams: Tuple[Seam, ...] = ()
    surfaces: Tuple[Surface, ...] = ()
    clusters: Tuple[PeerCluster, ...] = ()
    findings: Tuple[Finding, ...] = ()
    warnings: Tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the scene to a JSON-compatible dict.

        :return: Dict suitable for ``json.dumps``.
        """

        def _finding(f: Finding) -> dict:
            return {
                "kind": f.kind,
                "verdict": f.verdict,
                "summary": f.summary,
                "node_ids": list(f.node_ids),
                "severity": f.severity,
                "measurements": f.measurements,
                "hypotheses": [
                    {
                        "mechanism": h.mechanism,
                        "likelihood": h.likelihood,
                        "would_confirm": h.would_confirm,
                        "ruled_out_by": h.ruled_out_by,
                    }
                    for h in f.hypotheses
                ],
                "confirmed_by": f.confirmed_by or "(pending)",
                "per_basis": f.per_basis,
                "gaps": [
                    {
                        "basis": g.basis,
                        "before_id": g.before_id,
                        "after_id": g.after_id,
                        "axis": g.axis,
                        "px": g.px,
                        "undefined_reason": g.undefined_reason,
                    }
                    for g in f.gaps
                ],
                "caused_by": f.caused_by,
                "evidence": f.evidence,
                "sources": list(f.sources),
            }

        def _node(n: SceneNode) -> dict:
            d: dict = {
                "node_id": n.node_id,
                "rect": {"x": n.rect.x, "y": n.rect.y, "w": n.rect.w, "h": n.rect.h},
                "role": n.role,
                "alias": n.alias,
                "label": n.label,
                "label_confidence": n.label_confidence,
                "object_name": n.object_name,
                "cls": n.cls,
                "measured": sorted(n.measured),
                "sources": list(n.sources),
                "attrs": n.attrs,
            }
            if n.fill is not None:
                d["fill"] = {
                    "kind": n.fill.kind,
                    "hex_color": n.fill.hex_color,
                    "hex_start": n.fill.hex_start,
                    "hex_end": n.fill.hex_end,
                    "visible": n.fill.visible,
                    "visible_delta": n.fill.visible_delta,
                    "background_hex": n.fill.background_hex,
                    "border_px": n.fill.border_px,
                    "border_hex": n.fill.border_hex,
                }
            else:
                d["fill"] = None
            if n.ink is not None:
                d["ink"] = {
                    "rect": {"x": n.ink.rect.x, "y": n.ink.rect.y,
                             "w": n.ink.rect.w, "h": n.ink.rect.h},
                    "coverage": n.ink.coverage,
                    "hex_dominant": n.ink.hex_dominant,
                }
            else:
                d["ink"] = None
            d["corners"] = [
                {"which": c.which, "radius_px": c.radius_px,
                 "shows_hex": c.shows_hex, "shows_owner": c.shows_owner}
                for c in n.corners
            ]
            d["borders"] = n.borders
            if n.children:
                d["children"] = [_node(c) for c in n.children]
            return d

        return {
            "scene_id": self.scene_id,
            "region": {"x": self.region.x, "y": self.region.y,
                       "w": self.region.w, "h": self.region.h},
            "theme": self.theme,
            "ui_mode": self.ui_mode,
            "dpr": self.dpr,
            "palette": [{"hex": h, "px": p} for h, p in self.palette],
            "warnings": list(self.warnings),
            "root": _node(self.root) if self.root else None,
            "seams": [
                {"before_id": s.before_id, "after_id": s.after_id,
                 "axis": s.axis, "px": s.px, "shows_hex": s.shows_hex,
                 "shows_owner": s.shows_owner, "closed": s.closed,
                 "border_hex": s.border_hex}
                for s in self.seams
            ],
            "surfaces": [
                {"surface_id": s.surface_id, "member_ids": list(s.member_ids),
                 "role": s.role, "breaks": list(s.breaks)}
                for s in self.surfaces
            ],
            "clusters": [
                {"cluster_id": c.cluster_id, "members": list(c.members),
                 "parents": list(c.parents)}
                for c in self.clusters
            ],
            "findings": [_finding(f) for f in self.findings],
        }

    # ------------------------------------------------------------------

    def to_ascii(self, verbosity: str = "full") -> str:
        """Render the scene as text for in-context consumption.

        :param verbosity: ``"findings"`` — findings list only (≤2 KB);
            ``"summary"`` — findings + one line per node;
            ``"full"`` — complete table with all bases.
        :return: UTF-8 string.
        """
        lines: list[str] = []

        # Header
        lines.append(
            f"scene: {self.scene_id or '(unnamed)'}  "
            f"region=({self.region.x},{self.region.y},"
            f"{self.region.w},{self.region.h})  "
            f"dpr={self.dpr}  theme={self.theme or '?'}  "
            f"ui_mode={self.ui_mode or '?'}"
        )
        if self.palette:
            pal = "  ".join(f"{h}:{p}" for h, p in self.palette[:6])
            lines.append(f"palette  {pal}")
        if self.warnings:
            lines.append(f"WARNINGS  {', '.join(self.warnings)}")
        lines.append("")

        if verbosity == "findings":
            _append_findings(lines, self.findings)
            return "\n".join(lines)

        # Node table
        if self.root:
            _append_node(lines, self.root, verbosity=verbosity, depth=0)
            lines.append("")

        _append_findings(lines, self.findings)
        return "\n".join(lines)

    # ------------------------------------------------------------------

    @classmethod
    def from_observations(
        cls,
        nodes: list[SceneNode],
        seams: tuple[Seam, ...] = (),
        palette: tuple[tuple[str, int], ...] = (),
        **meta,
    ) -> "Scene":
        """Construct a ``Scene`` from a flat list of ``SceneNode``s.

        The first node is used as ``root``; all others become its children
        (flat layout — callers that need a tree should build it themselves).

        :param nodes: Flat list of ``SceneNode``s; first is the root.
        :param seams: Pre-computed seams (optional).
        :param palette: Pre-computed palette (optional).
        :param meta: Additional keyword arguments passed to the ``Scene`` constructor
            (``scene_id``, ``region``, ``theme``, ``ui_mode``, ``dpr``, ``findings``,
            ``clusters``, ``surfaces``, ``warnings``).
        :return: A new ``Scene``.
        """
        if not nodes:
            return cls(seams=seams, palette=palette, **meta)
        root = nodes[0]
        if len(nodes) > 1:
            # Attach remaining nodes as children of root (flat layout)
            root = SceneNode(
                node_id=root.node_id,
                rect=root.rect,
                role=root.role,
                alias=root.alias,
                label=root.label,
                label_confidence=root.label_confidence,
                object_name=root.object_name,
                cls=root.cls,
                fill=root.fill,
                ink=root.ink,
                corners=root.corners,
                borders=root.borders,
                measured=root.measured,
                sources=root.sources,
                style_rules=root.style_rules,
                paint_authority=root.paint_authority,
                children=tuple(nodes[1:]),
                attrs=root.attrs,
            )
        return cls(root=root, seams=seams, palette=palette, **meta)


# ---------------------------------------------------------------------------
# Private rendering helpers
# ---------------------------------------------------------------------------

def _append_node(lines: list, node: SceneNode, verbosity: str, depth: int) -> None:
    """Append one node line to *lines*, then recurse into children."""
    indent = "  " * depth
    rect = node.rect
    rect_str = f"({rect.x},{rect.y},{rect.w},{rect.h})"
    name = node.object_name or node.cls or node.role
    measured_str = ""
    not_measured = set(MEASURABLE) - node.measured
    if not_measured and verbosity == "full":
        measured_str = f"  [not measured: {', '.join(sorted(not_measured))}]"

    fill_str = ""
    if "fill" in node.measured:
        if node.fill is not None:
            vis = "VISIBLE" if node.fill.visible else "INVISIBLE"
            if node.fill.kind == "flat":
                fill_str = f"  fill={node.fill.hex_color} {vis}"
            else:
                fill_str = (
                    f"  fill={node.fill.kind}({node.fill.hex_start}->"
                    f"{node.fill.hex_end}) {vis}"
                )
        else:
            fill_str = "  fill=null"

    ink_str = ""
    if "ink" in node.measured and node.ink is not None:
        r = node.ink.rect
        ink_str = f"  ink=({r.x}..{r.x+r.w})"

    lines.append(
        f"{indent}{name} #{node.node_id} {rect_str}"
        f"{fill_str}{ink_str}{measured_str}"
    )
    for child in node.children:
        _append_node(lines, child, verbosity=verbosity, depth=depth + 1)


def _append_findings(lines: list, findings: tuple[Finding, ...]) -> None:
    """Append the findings block to *lines*."""
    if not findings:
        lines.append("FINDINGS  (none)")
        return
    lines.append("FINDINGS")
    for f in findings:
        node_info = f" nodes={len(f.node_ids)}" if f.node_ids else ""
        confirmed = f.confirmed_by or "(pending)"
        lines.append(
            f"  [{f.severity} {f.verdict}] {f.kind}{node_info}"
        )
        lines.append(f"    {f.summary}")
        if f.per_basis:
            for basis, verdict in f.per_basis.items():
                lines.append(f"    {basis:<12} {verdict}")
        if f.hypotheses:
            lines.append(f"    hypotheses:")
            for h in f.hypotheses:
                ruled = f"  [ruled out: {h.ruled_out_by}]" if h.ruled_out_by else ""
                lines.append(f"      [{h.likelihood}] {h.mechanism}{ruled}")
        lines.append(f"    confirmed_by: {confirmed}")
