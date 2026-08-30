"""
bin/Code/Rpa/Vision/Detectors.py — The detector registry for the design-vision feature.

Every detector is a pure function ``(scene: Scene, spec: dict) -> list[Finding]``.
Zero cv2/numpy — Tier 1 (stdlib-only).

Phase 2b ships the five detectors with evidence behind them:

  - ``invisible_fill``     — fires on all three queries.
  - ``spacing_uniformity`` — fires on query 1.
  - ``peer_adjacency``     — fires on query 3; stays silent where spacing_uniformity passes.
  - ``surface_broken``     — fires on queries 3 and 3b.
  - ``orphan_style_rule``  — fires on query 3b; needs no pixels at all.

The remaining eight are deferred to Phase 7.  Each is registered as an
``xfail(strict=True)`` stub in ``test_detectors.py`` so a secretly-passing stub
becomes a hard failure.

``run_all`` also emits ``basis_disagreement`` when ``spacing_uniformity`` finds
a per-basis split between a uniform and a non-uniform basis.

Design notes:
  - Detectors use ``scene.clusters`` (pre-computed) when present; they fall back to
    calling ``Measure.peers()`` only when ``scene.clusters`` is empty.  This allows
    tests to inject specific clusters while letting production code auto-detect.
  - ``peer_adjacency`` reads ``scene.seams`` (pre-computed with ``shows_owner``
    resolved) rather than re-deriving seams from node borders.  ``shows_owner``
    can only be resolved when the full parent chain is available.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

from __future__ import annotations

import re
from typing import Callable, Sequence

from Code.Rpa.Vision.Measure import (
    fill_is_visible,
    gaps_all_bases,
    peers,
    surface_breaks,
    uniformity,
    _flatten_nodes,
    _node_index,
)
from Code.Rpa.Vision.Scene import (
    BASIS_FILL,
    BASIS_INK,
    BASIS_PERCEIVED,
    BASIS_WIDGET,
    Finding,
    Gap,
    Hypothesis,
    PeerCluster,
    Scene,
    SceneNode,
    Seam,
    Surface,
)

# ---------------------------------------------------------------------------
# Severity ordering for ranking
# ---------------------------------------------------------------------------

_SEV_ORDER = {"error": 0, "warn": 1, "info": 2}


# ---------------------------------------------------------------------------
# invisible_fill
# ---------------------------------------------------------------------------

def invisible_fill(scene: Scene, spec: dict) -> list[Finding]:
    """Detect elements painted with a fill indistinguishable from their background.

    Fires on both flat fills (palette().window() matching background) and
    gradient fills where the maximum endpoint distance is below threshold.
    All three queries trigger this detector via three unrelated paint paths.

    :param scene: The scene to inspect.
    :param spec: Design spec (reserved for future tolerance override).
    :return: List of ``Finding``s, one per invisible element.
    """
    if scene.root is None:
        return []

    findings: list[Finding] = []
    all_nodes = _flatten_nodes(scene.root)

    for node in all_nodes:
        if node.fill is None:
            continue
        if "fill" not in node.measured:
            continue
        if node.fill.visible:
            continue

        fill = node.fill
        bg = fill.background_hex or ""

        if fill.kind in ("gradient_v", "gradient_h"):
            summary = (
                f"node {node.node_id!r}: {fill.kind} fill "
                f"{fill.hex_start}->{fill.hex_end} is INVISIBLE against "
                f"background {bg} (max delta={fill.visible_delta})"
            )
            hypotheses = (
                Hypothesis(
                    mechanism="gradient endpoints straddle the background colour",
                    likelihood="likely",
                    would_confirm="measure hex_start and hex_end against background_hex",
                ),
                Hypothesis(
                    mechanism="gradient direction inverted vs approved mockup",
                    likelihood="possible",
                    would_confirm="compare fill.hex_start vs mockup titleTop",
                ),
                Hypothesis(
                    mechanism="background-color changed without updating gradient endpoints",
                    likelihood="possible",
                    would_confirm="check qproperty-titleTop/Bottom against current palette",
                ),
            )
        else:
            summary = (
                f"node {node.node_id!r}: fill {fill.hex_color!r} is INVISIBLE "
                f"against background {bg} (delta={fill.visible_delta})"
            )
            hypotheses = (
                Hypothesis(
                    mechanism="fill colour equals palette().window() — painted but invisible",
                    likelihood="likely",
                    would_confirm="compare fill.hex_color against local background",
                ),
                Hypothesis(
                    mechanism="QSS colour literal uses hard-coded background value",
                    likelihood="possible",
                    would_confirm="check paintEvent constants vs current palette",
                ),
            )

        findings.append(Finding(
            kind="invisible_fill",
            verdict="violated",
            summary=summary,
            node_ids=(node.node_id,),
            severity="warn",
            measurements={
                "fill_kind": fill.kind,
                "fill_hex": fill.hex_color or f"{fill.hex_start}->{fill.hex_end}",
                "background_hex": bg,
                "visible_delta": str(fill.visible_delta),
            },
            hypotheses=hypotheses,
            confirmed_by="",
        ))

    return findings


# ---------------------------------------------------------------------------
# spacing_uniformity
# ---------------------------------------------------------------------------

def spacing_uniformity(scene: Scene, spec: dict) -> list[Finding]:
    """Detect non-uniform gaps between peer elements, measured on all four bases.

    Uses ``scene.clusters`` when populated; falls back to ``Measure.peers()`` when
    empty.  This allows tests to inject specific clusters.

    ``Finding.verdict`` is ``"non_uniform"`` if *any* basis says non-uniform.
    Basis disagreement is surfaced in ``Finding.per_basis``; ``run_all`` promotes it
    to a separate ``basis_disagreement`` finding.

    :param scene: The scene to inspect.
    :param spec: Design spec (may carry ``tolerance_px`` under ``"invariants"``).
    :return: List of ``Finding``s — one per peer group.
    """
    if scene.root is None:
        return []

    tolerance_px = _spec_tolerance(spec, "spacing_uniformity")
    findings: list[Finding] = []

    # Use pre-computed clusters if available, else derive them
    if scene.clusters:
        cluster_list: list[PeerCluster] = list(scene.clusters)
    else:
        cluster_list = peers(scene, min_size=3)

    node_idx = _node_index(scene)

    for cluster in cluster_list:
        nids = list(cluster.members)
        nodes = [node_idx[n] for n in nids if n in node_idx]
        if len(nodes) < 2:
            continue

        axis = _dominant_axis(nodes)
        all_bases = gaps_all_bases(nodes, axis)

        per_basis: dict[str, str] = {}
        all_gaps_flat: list[Gap] = []
        any_non_uniform = False

        for basis, gap_list in all_bases.items():
            values = [g.px for g in gap_list]
            verdict, spread = uniformity(values, tolerance_px=tolerance_px)
            per_basis[basis] = verdict
            all_gaps_flat.extend(gap_list)
            if verdict == "non_uniform":
                any_non_uniform = True

        w_values = [g.px for g in all_bases[BASIS_WIDGET]]
        p_values = [g.px for g in all_bases[BASIS_PERCEIVED]]

        verdict = "non_uniform" if any_non_uniform else "uniform"
        summary_parts = [
            f"{basis}=non_uniform"
            for basis, bv in per_basis.items()
            if bv == "non_uniform"
        ]
        if summary_parts:
            summary = (
                f"cluster {cluster.cluster_id!r} ({len(nodes)} nodes): "
                + ", ".join(summary_parts)
            )
        else:
            summary = (
                f"cluster {cluster.cluster_id!r} ({len(nodes)} nodes): "
                "uniform on all bases"
            )

        findings.append(Finding(
            kind="spacing_uniformity",
            verdict=verdict,
            summary=summary,
            node_ids=tuple(nids),
            severity="warn" if verdict == "non_uniform" else "info",
            measurements={
                "axis": axis,
                "widget_gaps": str(w_values),
                "perceived_gaps": str(p_values),
            },
            per_basis=per_basis,
            gaps=tuple(all_gaps_flat),
        ))

    return findings


# ---------------------------------------------------------------------------
# peer_adjacency
# ---------------------------------------------------------------------------

def peer_adjacency(scene: Scene, spec: dict) -> list[Finding]:
    """Detect peer group members that show a non-parent background in their gaps.

    A 2 px gap showing the *parent's* colour is a designed margin — this detector
    stays silent.  A 2 px gap showing an *ancestor's* colour is a hole through to
    a grandparent — this detector fires.

    Reads ``scene.seams`` (pre-computed with ``shows_owner`` resolved) and
    ``scene.clusters`` (pre-computed peer groups).  Both must be populated for this
    detector to fire; it cannot derive ``shows_owner`` without the full parent chain.

    This detector catches exactly what ``spacing_uniformity`` passes: perfectly
    uniform gaps of 2,2,2,2 that show the window background instead of the immediate
    parent.

    :param scene: The scene to inspect.
    :param spec: Design spec (unused).
    :return: List of ``Finding``s for groups with ancestor-showing seams.
    """
    if scene.root is None:
        return []

    # Build seam lookup from pre-computed seams (shows_owner already resolved)
    seam_index: dict[tuple[str, str], Seam] = {
        (s.before_id, s.after_id): s for s in scene.seams
    }
    if not seam_index:
        return []

    # Use pre-computed clusters if available, else derive them
    if scene.clusters:
        cluster_list: list[PeerCluster] = list(scene.clusters)
    else:
        cluster_list = peers(scene, min_size=2)

    findings: list[Finding] = []

    for cluster in cluster_list:
        nids = list(cluster.members)
        if len(nids) < 2:
            continue

        ancestor_seams: list[Seam] = []
        for i in range(len(nids) - 1):
            key = (nids[i], nids[i + 1])
            s = seam_index.get(key)
            if s is not None and s.shows_owner == "ancestor":
                ancestor_seams.append(s)

        if not ancestor_seams:
            continue

        shows_hexes = list({s.shows_hex for s in ancestor_seams if s.shows_hex})
        pxs = list({s.px for s in ancestor_seams})

        findings.append(Finding(
            kind="peer_adjacency",
            verdict="violated",
            summary=(
                f"cluster {cluster.cluster_id!r}: {len(ancestor_seams)} seam(s) "
                f"show ancestor background (px={pxs}, hex={shows_hexes}); "
                f"these are holes, not margins"
            ),
            node_ids=tuple(nids),
            severity="warn",
            measurements={
                "seam_count": str(len(ancestor_seams)),
                "seam_px": str(pxs),
                "shows_hex": str(shows_hexes),
                "shows_owner": "ancestor",
            },
            hypotheses=(
                Hypothesis(
                    mechanism="margin-right or margin-bottom set in QSS creates gaps that "
                               "show through to the grandparent container",
                    likelihood="likely",
                    would_confirm="check QTabBar::tab margin-right in stylesheet",
                ),
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# surface_broken
# ---------------------------------------------------------------------------

def surface_broken(scene: Scene, spec: dict) -> list[Finding]:
    """Detect surfaces that fail to render as one continuous plane.

    A surface is spec-supplied (design convention + role).  This detector
    enumerates breaks: corner notches, closed seams, fill mismatches.
    Corner breaks are listed first — they are the most visually significant.

    When no breaks are found and corners were not measured on any member, the
    finding is ``"indeterminate"`` rather than ``"ok"``, because absence of
    measured corners means we cannot confirm the surface has no corner defects.

    :param scene: The scene to inspect.
    :param spec: Design spec; ``scene.surfaces`` must be populated.
    :return: List of ``Finding``s for broken or indeterminate surfaces.
    """
    findings: list[Finding] = []
    node_idx = _node_index(scene)

    for surface in scene.surfaces:
        breaks = surface_breaks(surface, scene)

        # Check whether corners were measured on any member node
        corners_measured = any(
            "corners" in node_idx[mid].measured
            for mid in surface.member_ids
            if mid in node_idx
        )

        if not breaks:
            if not corners_measured:
                # Cannot conclude clean surface — corners were never attempted
                findings.append(Finding(
                    kind="surface_broken",
                    verdict="indeterminate",
                    summary=(
                        f"surface {surface.surface_id!r} ({surface.role}): "
                        "no breaks found but corners were NOT measured — "
                        "surface may have corner defects"
                    ),
                    node_ids=surface.member_ids,
                    severity="warn",
                    measurements={
                        "breaks": "[]",
                        "break_count": "0",
                        "corners_measured": "false",
                        "role": surface.role,
                    },
                ))
            # If corners were measured and no breaks: clean surface — no finding
            continue

        # Order: corners first (most visible), then seam, then fill
        ordered_breaks = (
            [b for b in breaks if b.startswith("corner_")] +
            [b for b in breaks if b.startswith("seam_")] +
            [b for b in breaks if b.startswith("fill_")]
        )

        first_break = ordered_breaks[0] if ordered_breaks else "unknown"

        findings.append(Finding(
            kind="surface_broken",
            verdict="violated",
            summary=(
                f"surface {surface.surface_id!r} ({surface.role}): "
                f"{len(breaks)} break(s): {', '.join(ordered_breaks[:3])}"
                + (f" (+{len(breaks)-3} more)" if len(breaks) > 3 else "")
            ),
            node_ids=surface.member_ids,
            severity="warn",
            measurements={
                "breaks": str(ordered_breaks),
                "break_count": str(len(breaks)),
                "first_break": first_break,
                "role": surface.role,
            },
            hypotheses=(
                Hypothesis(
                    mechanism="content widget has generic border-radius rule "
                               "not zeroed for the tab-edge sides",
                    likelihood="likely",
                    would_confirm="check QTabWidget or equivalent for border-radius "
                                  "rules; confirm QTabWidget presence in widget tree",
                ),
                Hypothesis(
                    mechanism="selected tab retains explicit bottom border instead "
                               "of opening into content",
                    likelihood="likely",
                    would_confirm="check ::tab:selected border-bottom in stylesheet",
                ),
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# orphan_style_rule
# ---------------------------------------------------------------------------

def orphan_style_rule(scene: Scene, spec: dict) -> list[Finding]:
    """Detect QSS selectors that name a widget type absent from the widget tree.

    Editing an orphan rule has no visual effect.  This is the cheapest detector:
    it needs no pixels — only a flat set of class names in the scene.

    :param scene: The scene to inspect.
    :param spec: Design spec (unused).
    :return: List of ``Finding``s, one per ``loaded_unmatched`` style_rule entry.
    """
    if scene.root is None:
        return []

    all_nodes = _flatten_nodes(scene.root)

    findings: list[Finding] = []

    for node in all_nodes:
        for rule in node.style_rules:
            if rule.get("effective") == "loaded_unmatched":
                selector = rule.get("selector", "")
                widget_type = _selector_widget_type(selector)
                findings.append(Finding(
                    kind="orphan_style_rule",
                    verdict="violated",
                    summary=(
                        f"selector {selector!r} at "
                        f"{rule.get('file', '?')!s}:{rule.get('line', '?')} "
                        f"matches no widget in the tree — editing it has no effect"
                    ),
                    node_ids=(node.node_id,),
                    severity="warn",
                    measurements={
                        "selector": selector,
                        "widget_type": widget_type,
                        "file": rule.get("file", ""),
                        "line": str(rule.get("line", "")),
                    },
                    hypotheses=(
                        Hypothesis(
                            mechanism=(
                                f"no {widget_type!r} widget exists in this "
                                "application; the rule was authored for a "
                                "widget class that is never instantiated"
                            ),
                            likelihood="likely",
                            would_confirm=f"grep widget tree for {widget_type!r} class",
                        ),
                    ),
                ))

    return findings


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------

# The canonical Phase 2b registry
DETECTORS: dict[str, Callable[[Scene, dict], list[Finding]]] = {
    "invisible_fill": invisible_fill,
    "spacing_uniformity": spacing_uniformity,
    "peer_adjacency": peer_adjacency,
    "surface_broken": surface_broken,
    "orphan_style_rule": orphan_style_rule,
}


def run_all(
    scene: Scene,
    spec: dict | None = None,
    only: Sequence[str] = (),
) -> list[Finding]:
    """Run all registered detectors and return ranked findings.

    Also emits ``basis_disagreement`` when ``spacing_uniformity`` finds a split
    between a uniform basis and a non-uniform basis.

    :param scene: The scene to analyse.
    :param spec: Design spec dict (optional).
    :param only: If non-empty, run only these detector names.
    :return: Findings ranked by ``error > warn > info`` then by node count
        descending.
    """
    if spec is None:
        spec = {}

    all_findings: list[Finding] = []
    detectors_to_run = {
        k: v for k, v in DETECTORS.items()
        if not only or k in only
    }

    for name, fn in detectors_to_run.items():
        try:
            results = fn(scene, spec)
            all_findings.extend(results)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Detector %r raised an exception", name
            )

    # Emit basis_disagreement when spacing_uniformity reports split bases
    for f in list(all_findings):
        if f.kind == "spacing_uniformity" and f.per_basis:
            verdicts = set(f.per_basis.values())
            # Only concrete disagreements count (ignore "indeterminate")
            concrete = {v for v in verdicts if v != "indeterminate"}
            if len(concrete) > 1:
                all_findings.append(Finding(
                    kind="basis_disagreement",
                    verdict="non_uniform",
                    summary=(
                        f"cluster covered by {f.kind!r}: bases disagree — "
                        f"{dict(f.per_basis)}"
                    ),
                    node_ids=f.node_ids,
                    severity="warn",
                    caused_by="spacing_uniformity",
                    per_basis=f.per_basis,
                ))

    # Rank: error < warn < info, then by node count descending
    return sorted(
        all_findings,
        key=lambda f: (
            _SEV_ORDER.get(f.severity, 9),
            -len(f.node_ids),
        ),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _dominant_axis(nodes: list[SceneNode]) -> str:
    """Return ``'x'`` or ``'y'`` based on which axis spans the greater range."""
    if not nodes:
        return "x"
    xs = [n.rect.x for n in nodes]
    ys = [n.rect.y for n in nodes]
    return "x" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "y"


def _spec_tolerance(spec: dict, detector_name: str) -> int:
    """Extract ``tolerance_px`` for *detector_name* from the spec invariants."""
    for inv in spec.get("invariants", []):
        if inv.get("kind") == detector_name:
            return int(inv.get("tolerance_px", 1))
    return 1


def _selector_widget_type(selector: str) -> str:
    """Extract the base widget type from a QSS selector string.

    ``"QTabWidget::pane"`` → ``"QTabWidget"``
    ``"#WRibbonTabBar::tab:first"`` → ``"#WRibbonTabBar"``

    :param selector: QSS selector string.
    :return: The base widget type or object-name prefix.
    """
    base = re.split(r"::?", selector)[0].strip()
    return base
